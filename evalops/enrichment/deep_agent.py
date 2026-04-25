from __future__ import annotations

import concurrent.futures
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable

from ..project_config import ProjectConfig
from ..report_struct import Issue
from ..runtime import settings
from ..tokenization import fit_to_token_size
from .graph import GraphIndex
from .types import ContextBundle, EvidenceSnippet, IssueEvidence


PROMPT_VERSION = "deep-agent-context-v1"


class DeepAgentUnavailableError(RuntimeError):
    pass


class DeepAgentContextRunner:
    def __init__(self, agent_factory: Callable[..., Any] | None = None):
        self.agent_factory = agent_factory

    def collect_context(
        self,
        repo_root: Path,
        issues: list[Issue],
        diff: Iterable[Any],
        graph: GraphIndex,
        config: ProjectConfig,
        repo_ref: str = "",
    ) -> ContextBundle:
        self._validate_config(config)
        if not issues:
            return ContextBundle(
                mode_requested=getattr(config, "context_mode", "diff_only"),
                mode_used="deep_agent",
                repo_ref=repo_ref,
                metadata={"prompt_version": PROMPT_VERSION},
            )

        create_deep_agent, filesystem_backend, filesystem_permission = self._load_deepagents()
        backend = filesystem_backend(root_dir=str(repo_root), virtual_mode=True)
        permissions = self._permissions(filesystem_permission, config)
        prompt = self._system_prompt(config)
        agent = (self.agent_factory or create_deep_agent)(
            model=self._model(config),
            backend=backend,
            permissions=permissions,
            system_prompt=prompt,
        )
        payload = self._input_payload(issues, diff, graph, config)
        timeout = int(getattr(config, "deep_agent_timeout_seconds", 120))
        response = self._invoke_with_timeout(agent, payload, timeout)
        parsed = _extract_json_payload(_last_message_content(response))
        return self._bundle_from_payload(parsed, config, repo_ref)

    def _validate_config(self, config: ProjectConfig) -> None:
        backend = str(getattr(config, "deep_agent_backend", "filesystem") or "filesystem")
        if backend != "filesystem":
            raise ValueError("Deep Agent context mode currently supports only filesystem backend")
        if not getattr(config, "deep_agent_readonly", True):
            raise ValueError("Deep Agent context mode requires deep_agent_readonly=true")

    def _load_deepagents(self):
        try:
            from deepagents import FilesystemPermission, create_deep_agent
            from deepagents.backends import FilesystemBackend
        except ImportError as exc:
            raise DeepAgentUnavailableError(
                "Deep Agents is not installed. Install the optional deep-agent dependencies "
                "or use context_mode='graph_context' or 'diff_only'."
            ) from exc
        return create_deep_agent, FilesystemBackend, FilesystemPermission

    def _model(self, config: ProjectConfig) -> str:
        return getattr(config, "deep_agent_model", "") or settings().model

    def _permissions(self, permission_cls: Any, config: ProjectConfig) -> list[Any]:
        rules = [
            permission_cls(operations=["write"], paths=["/**"], mode="deny"),
        ]
        excluded = [
            _permission_path(pattern)
            for pattern in getattr(config, "deep_agent_exclude_files", [])
            if pattern
        ]
        if excluded:
            rules.append(permission_cls(operations=["read"], paths=excluded, mode="deny"))
        rules.append(permission_cls(operations=["read"], paths=["/**"], mode="allow"))
        return rules

    def _system_prompt(self, config: ProjectConfig) -> str:
        max_hops = int(getattr(config, "deep_agent_max_hops", 2))
        max_files = int(getattr(config, "deep_agent_max_files", 20))
        return f"""You are EvalOps' read-only repository context retriever.

Your task is not to perform a new code review. Your task is to gather concise
repository evidence for already extracted review issues, using the reviewed diff
to understand the exact change that triggered each issue.

Rules:
- Use the repository graph first to choose related files.
- Read only files needed to support or weaken each issue.
- Do not write files, edit files, run commands, or create scratch files.
- Do not inspect secrets or VCS internals.
- Stay within {max_hops} graph hops and {max_files} related files unless the input budget is lower.
- Return only valid JSON matching the requested schema.

Assessment values:
- supports: repository context makes the issue more credible.
- weakens: broader context suggests the issue is likely a false positive.
- inconclusive: related context was found, but not enough to decide.
- not_found: expected related context was unavailable within budget.
"""

    def _input_payload(
        self,
        issues: list[Issue],
        diff: Iterable[Any],
        graph: GraphIndex,
        config: ProjectConfig,
    ) -> dict[str, Any]:
        issue_payloads = [_issue_payload(issue) for issue in issues]
        reviewed_diff = _diff_payload(diff, config)
        changed_files = sorted(
            {issue.file for issue in issues}
            | {item["file"] for item in reviewed_diff if item.get("file")}
        )
        graph_context = graph.describe_neighborhood(
            changed_files,
            max_hops=int(getattr(config, "deep_agent_max_hops", 2)),
            max_files=int(getattr(config, "deep_agent_max_files", 20)),
        )
        return {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "Collect issue-specific repository evidence.",
                            "prompt_version": PROMPT_VERSION,
                            "changed_files": changed_files,
                            "reviewed_diff": reviewed_diff,
                            "graph_neighborhood": graph_context,
                            "issues": issue_payloads,
                            "output_schema": {
                                "issues": [
                                    {
                                        "issue_id": "string",
                                        "file": "string",
                                        "claim": "string",
                                        "related_files": ["string"],
                                        "evidence": [
                                            {
                                                "file": "string",
                                                "reason": "string",
                                                "snippet": "string",
                                                "start_line": "integer or null",
                                                "end_line": "integer or null",
                                            }
                                        ],
                                        "agent_assessment": (
                                            "supports | weakens | inconclusive | not_found"
                                        ),
                                    }
                                ]
                            },
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    def _invoke_with_timeout(self, agent: Any, payload: dict[str, Any], timeout: int) -> Any:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(agent.invoke, payload)
        try:
            return future.result(timeout=timeout)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _bundle_from_payload(
        self,
        payload: Any,
        config: ProjectConfig,
        repo_ref: str,
    ) -> ContextBundle:
        if not isinstance(payload, dict):
            raise ValueError("Deep Agent response must be a JSON object")
        issues = [
            _issue_evidence_from_dict(item)
            for item in payload.get("issues", [])
            if isinstance(item, dict)
        ]
        return ContextBundle(
            mode_requested=getattr(config, "context_mode", "deep_agent"),
            mode_used="deep_agent",
            repo_ref=repo_ref,
            issues=issues,
            metadata={"prompt_version": PROMPT_VERSION},
        )


def _issue_payload(issue: Issue) -> dict[str, Any]:
    payload = asdict(issue)
    payload["issue_id"] = str(issue.id)
    return payload


def _diff_payload(diff: Iterable[Any], config: ProjectConfig) -> list[dict[str, str]]:
    max_tokens = max(1, int(getattr(config, "deep_agent_max_tokens", 8000)) // 2)
    diff_parts = [
        {
            "file": str(getattr(file_diff, "path", "")),
            "diff": str(file_diff),
        }
        for file_diff in diff
    ]
    fitted, removed = fit_to_token_size(
        [json.dumps(part, ensure_ascii=False) for part in diff_parts],
        max_tokens,
    )
    payload = [json.loads(part) for part in fitted]
    if removed:
        payload.append(
            {
                "file": "",
                "diff": f"[Trimmed {removed} diff part(s) before Deep Agent context retrieval.]",
            }
        )
    return payload


def _issue_evidence_from_dict(payload: dict[str, Any]) -> IssueEvidence:
    snippets = [
        EvidenceSnippet(
            file=str(item.get("file", "")),
            reason=str(item.get("reason", "")),
            snippet=str(item.get("snippet", "")),
            start_line=_optional_int(item.get("start_line")),
            end_line=_optional_int(item.get("end_line")),
        )
        for item in payload.get("evidence", [])
        if isinstance(item, dict)
    ]
    fitted, removed = fit_to_token_size(snippets, None)
    evidence = list(fitted)
    if removed and evidence:
        evidence[-1].snippet += f"\n[Trimmed {removed} evidence snippet(s).]"
    return IssueEvidence(
        issue_id=str(payload.get("issue_id", "")),
        file=str(payload.get("file", "")),
        claim=str(payload.get("claim", "")),
        related_files=[str(file) for file in payload.get("related_files", [])],
        evidence=evidence,
        agent_assessment=_assessment(payload.get("agent_assessment")),
    )


def _assessment(value: Any) -> str:
    allowed = {"supports", "weakens", "inconclusive", "not_found"}
    text = str(value or "inconclusive")
    return text if text in allowed else "inconclusive"


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _last_message_content(response: Any) -> Any:
    if isinstance(response, dict) and response.get("messages"):
        message = response["messages"][-1]
        if isinstance(message, dict):
            return message.get("content")
        return getattr(message, "content", None)
    return response


def _extract_json_payload(response: Any) -> Any:
    if not isinstance(response, str):
        return response
    value = response.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for start, char in enumerate(value):
            if char not in {"{", "["}:
                continue
            try:
                payload, _ = decoder.raw_decode(value[start:])
                return payload
            except json.JSONDecodeError:
                continue
        raise


def _permission_path(pattern: str) -> str:
    normalized = pattern.replace("\\", "/")
    return normalized if normalized.startswith("/") else f"/{normalized}"
