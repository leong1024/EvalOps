from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from git import Repo
from unidiff import PatchedFile

from ..graph import GraphContextResult
from ..project_config import ProjectConfig
from ..report_struct import Issue, Report
from ..tokenization import fit_to_token_size
from .deep_agent import DeepAgentContextRunner
from .graph import GraphIndex
from .types import ContextBundle, EvidenceSnippet, IssueEvidence


DIFF_ONLY = "diff_only"
GRAPH_CONTEXT = "graph_context"
DEEP_AGENT = "deep_agent"
AUTO = "auto"
VALID_CONTEXT_MODES = {DIFF_ONLY, GRAPH_CONTEXT, DEEP_AGENT, AUTO}


class ContextEnricher:
    def __init__(self, deep_agent_runner: DeepAgentContextRunner | None = None):
        self.deep_agent_runner = deep_agent_runner or DeepAgentContextRunner()

    def enrich(
        self,
        repo: Repo,
        diff: Iterable[PatchedFile],
        report: Report,
        graph_result: GraphContextResult,
        config: ProjectConfig,
    ) -> ContextBundle | None:
        requested = effective_context_mode(config)
        if requested == DIFF_ONLY:
            return None

        repo_ref = _repo_ref(graph_result)
        if requested == GRAPH_CONTEXT:
            return _graph_context_bundle(report.plain_issues, graph_result, config, repo_ref)

        if requested in {DEEP_AGENT, AUTO}:
            try:
                graph = GraphIndex.from_graph_dir(graph_result.graph_dir)
                bundle = self.deep_agent_runner.collect_context(
                    repo_root=Path(repo.working_tree_dir or "."),
                    issues=report.plain_issues,
                    graph=graph,
                    config=config,
                    repo_ref=repo_ref,
                )
                bundle.mode_requested = requested
                bundle.graph_refreshed = graph_result.refreshed
                return _fit_bundle(bundle, int(getattr(config, "deep_agent_max_tokens", 8000)))
            except Exception as exc:
                message = f"Deep Agent context unavailable: {type(exc).__name__}: {exc}"
                if not getattr(config, "deep_agent_fail_open", True) and requested == DEEP_AGENT:
                    raise
                logging.warning(message)
                if requested == AUTO and graph_result.combined:
                    bundle = _graph_context_bundle(report.plain_issues, graph_result, config, repo_ref)
                    bundle.mode_requested = requested
                    bundle.warnings.append(message)
                    return bundle
                return ContextBundle(
                    mode_requested=requested,
                    mode_used=DIFF_ONLY,
                    repo_ref=repo_ref,
                    graph_refreshed=graph_result.refreshed,
                    warnings=[message],
                )
        raise ValueError(f"Unsupported context_mode: {requested}")


def effective_context_mode(config: ProjectConfig) -> str:
    mode = str(getattr(config, "context_mode", DIFF_ONLY) or DIFF_ONLY).lower()
    if mode not in VALID_CONTEXT_MODES:
        raise ValueError(
            f"Unsupported context_mode {mode!r}. Expected one of: {', '.join(sorted(VALID_CONTEXT_MODES))}"
        )
    if mode == DIFF_ONLY and getattr(config, "graph_context_enabled", False):
        return GRAPH_CONTEXT
    return mode


def needs_graph_context(config: ProjectConfig) -> bool:
    mode = effective_context_mode(config)
    return mode in {GRAPH_CONTEXT, DEEP_AGENT, AUTO}


def should_include_prompt_graph(config: ProjectConfig) -> bool:
    return effective_context_mode(config) == GRAPH_CONTEXT


def _graph_context_bundle(
    issues: list[Issue],
    graph_result: GraphContextResult,
    config: ProjectConfig,
    repo_ref: str,
) -> ContextBundle:
    issue_evidence: list[IssueEvidence] = []
    for issue in issues:
        context = graph_result.by_file.get(issue.file, "")
        snippets = []
        if context:
            snippets.append(
                EvidenceSnippet(
                    file=issue.file,
                    reason="Graphify neighborhood for changed file",
                    snippet=context,
                )
            )
        issue_evidence.append(
            IssueEvidence(
                issue_id=str(issue.id),
                file=issue.file,
                claim=issue.title,
                related_files=[],
                evidence=snippets,
                agent_assessment="inconclusive" if snippets else "not_found",
            )
        )
    return ContextBundle(
        mode_requested=effective_context_mode(config),
        mode_used=GRAPH_CONTEXT,
        repo_ref=repo_ref,
        graph_refreshed=graph_result.refreshed,
        issues=issue_evidence,
        warnings=list(graph_result.warnings),
    )


def _fit_bundle(bundle: ContextBundle, max_tokens: int) -> ContextBundle:
    lines = _bundle_context_lines(bundle)
    fitted, removed = fit_to_token_size(lines, max_tokens)
    if removed:
        bundle.metadata["trimmed_context_lines"] = removed
    bundle.metadata["context_preview"] = "\n".join(str(line) for line in fitted)
    return bundle


def _bundle_context_lines(bundle: ContextBundle) -> list[str]:
    lines: list[str] = []
    for issue in bundle.issues:
        lines.append(f"Issue {issue.issue_id} ({issue.agent_assessment}): {issue.claim}")
        for snippet in issue.evidence:
            location = snippet.file
            if snippet.start_line:
                location += f":{snippet.start_line}"
                if snippet.end_line and snippet.end_line != snippet.start_line:
                    location += f"-{snippet.end_line}"
            lines.append(f"- {location}: {snippet.reason}\n{snippet.snippet}")
    return lines


def _repo_ref(graph_result: GraphContextResult) -> str:
    metadata = graph_result.metadata or {}
    return str(
        metadata.get("review_fingerprint")
        or metadata.get("diff_hash")
        or metadata.get("head_sha")
        or ""
    )
