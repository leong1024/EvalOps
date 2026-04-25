import json
import logging
import os
import shutil
import subprocess
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from git import Repo
from unidiff import PatchedFile

from ..constants import DEFAULT_GRAPHIFY_PATH
from ..project_config import ProjectConfig
from ..tokenization import fit_to_token_size


@dataclass
class GraphContextResult:
    by_file: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    refreshed: bool = False
    graph_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def combined(self) -> str:
        parts = [
            f"### {file_path}\n{context}"
            for file_path, context in self.by_file.items()
            if context
        ]
        return "\n\n".join(parts)


class GraphifyContextProvider:
    def __init__(self, runner=subprocess.run):
        self.runner = runner

    def get_context(
        self,
        repo: Repo,
        diff: Iterable[PatchedFile],
        config: ProjectConfig,
    ) -> GraphContextResult:
        if not self._enabled(config):
            return GraphContextResult()

        diff = list(diff)
        result = GraphContextResult()
        graph_dir = self._graph_dir(repo, config)
        result.graph_dir = graph_dir
        try:
            result.refreshed = self._refresh_if_needed(repo, diff, config, graph_dir)
            result.metadata = self._read_metadata(graph_dir)
            result.by_file = self._query_changed_files(repo, diff, config, graph_dir)
        except Exception as exc:
            message = f"Graphify context unavailable: {type(exc).__name__}: {exc}"
            if getattr(config, "graph_context_fail_open", True):
                logging.warning(message)
                result.warnings.append(message)
                return result
            raise
        return result

    def _enabled(self, config: ProjectConfig) -> bool:
        mode = str(getattr(config, "context_mode", "diff_only") or "diff_only").lower()
        return bool(getattr(config, "graph_context_enabled", False)) or mode in {
            "graph_context",
            "deep_agent",
            "auto",
        }

    def _graph_dir(self, repo: Repo, config: ProjectConfig) -> Path:
        root = Path(repo.working_tree_dir or ".")
        configured = Path(getattr(config, "graph_context_path", str(DEFAULT_GRAPHIFY_PATH)))
        return configured if configured.is_absolute() else root / configured

    def _refresh_if_needed(
        self,
        repo: Repo,
        diff: Iterable[PatchedFile],
        config: ProjectConfig,
        graph_dir: Path,
    ) -> bool:
        refresh = str(getattr(config, "graph_context_refresh", "auto")).lower()
        metadata = self._read_metadata(graph_dir)
        graph_file = graph_dir / "graph.json"
        diff_hash = self._diff_hash(diff)
        review_fingerprint = self._review_fingerprint(repo, diff_hash, config)
        should_refresh = refresh == "always"
        if refresh == "never":
            should_refresh = False
        elif refresh == "auto":
            expected = metadata.get("review_fingerprint")
            if expected:
                should_refresh = not graph_file.exists() or expected != review_fingerprint
            else:
                should_refresh = not graph_file.exists() or metadata.get("head_sha") != self._head_sha(repo)

        if not should_refresh:
            return False

        self._build_or_refresh(repo, config, graph_dir)
        self._write_metadata(repo, graph_dir, diff_hash, review_fingerprint)
        return True

    def _build_or_refresh(self, repo: Repo, config: ProjectConfig, graph_dir: Path) -> None:
        command = os.getenv("EVALOPS_GRAPHIFY_COMMAND", "graphify")
        if shutil.which(command) is None:
            raise RuntimeError(
                f"Graphify CLI '{command}' was not found. Install the graphifyy package "
                "or set EVALOPS_GRAPHIFY_COMMAND."
            )

        graph_dir.mkdir(parents=True, exist_ok=True)
        root = Path(repo.working_tree_dir or ".")
        timeout = int(getattr(config, "graph_context_timeout_seconds", 120))
        graph_file = graph_dir / "graph.json"
        report_file = graph_dir / "GRAPH_REPORT.md"
        candidates = [
            [command, "update", str(root)],
            [command, "build", str(root), "--output", str(graph_file), "--report", str(report_file)],
            [command, str(root), "--output", str(graph_dir)],
            [command, "analyze", str(root), "--output", str(graph_dir)],
        ]
        errors: list[str] = []
        for args in candidates:
            completed = self.runner(
                args,
                cwd=str(graph_dir),
                text=True,
                capture_output=True,
                timeout=timeout,
            )
            if completed.returncode == 0:
                self._normalize_graphify_output(graph_dir)
                return
            errors.append((completed.stderr or completed.stdout or "").strip())
        raise RuntimeError("; ".join(error for error in errors if error) or "Graphify failed")

    def _normalize_graphify_output(self, graph_dir: Path) -> None:
        output_dir = graph_dir / "graphify-out"
        if not output_dir.exists():
            return
        for name in ("graph.json", "GRAPH_REPORT.md", "graph.html"):
            source = output_dir / name
            if source.exists():
                shutil.copy2(source, graph_dir / name)

    def _query_changed_files(
        self,
        repo: Repo,
        diff: Iterable[PatchedFile],
        config: ProjectConfig,
        graph_dir: Path,
    ) -> dict[str, str]:
        graph_text = self._graph_text(graph_dir)
        if not graph_text:
            return {}
        max_tokens = int(getattr(config, "graph_context_max_tokens", 4000))
        files = [file.path for file in diff]
        if not files:
            return {}
        per_file_budget = max(1, max_tokens // len(files))
        contexts = {}
        for file_path in files:
            context = self._context_for_file(graph_text, file_path, per_file_budget)
            if context:
                contexts[file_path] = context
        return contexts

    def _graph_text(self, graph_dir: Path) -> str:
        graph_file = graph_dir / "graph.json"
        report_file = graph_dir / "GRAPH_REPORT.md"
        if graph_file.exists():
            try:
                return "\n".join(self._flatten_json(json.loads(graph_file.read_text(encoding="utf-8"))))
            except json.JSONDecodeError:
                return graph_file.read_text(encoding="utf-8", errors="ignore")
        if report_file.exists():
            return report_file.read_text(encoding="utf-8", errors="ignore")
        return ""

    def _context_for_file(self, graph_text: str, file_path: str, max_tokens: int) -> str:
        lines = graph_text.splitlines()
        matches: list[str] = []
        normalized = file_path.replace("\\", "/")
        for idx, line in enumerate(lines):
            if normalized in line.replace("\\", "/"):
                start = max(0, idx - 3)
                end = min(len(lines), idx + 4)
                matches.extend(lines[start:end])
        if not matches:
            return ""
        fitted, removed = fit_to_token_size(matches, max_tokens)
        context = "\n".join(str(item) for item in fitted)
        if removed:
            context += f"\n[Trimmed {removed} graph context line(s).]"
        return context

    def _flatten_json(self, value: Any, prefix: str = "") -> list[str]:
        if isinstance(value, dict):
            lines: list[str] = []
            for key, nested in value.items():
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                lines.extend(self._flatten_json(nested, next_prefix))
            return lines
        if isinstance(value, list):
            lines = []
            for idx, nested in enumerate(value):
                lines.extend(self._flatten_json(nested, f"{prefix}[{idx}]"))
            return lines
        return [f"{prefix}: {value}"]

    def _read_metadata(self, graph_dir: Path) -> dict[str, Any]:
        metadata_file = graph_dir / "metadata.json"
        if not metadata_file.exists():
            return {}
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_metadata(
        self,
        repo: Repo,
        graph_dir: Path,
        diff_hash: str,
        review_fingerprint: str,
    ) -> None:
        metadata = {
            "head_sha": self._head_sha(repo),
            "diff_hash": diff_hash,
            "review_fingerprint": review_fingerprint,
            "graphify_version": self._graphify_version(repo),
            "built_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(repo.git.ls_files().splitlines()),
        }
        graph_dir.mkdir(parents=True, exist_ok=True)
        (graph_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

    def _head_sha(self, repo: Repo) -> str:
        return repo.head.commit.hexsha

    def _diff_hash(self, diff: Iterable[PatchedFile]) -> str:
        digest = hashlib.sha256()
        for file_diff in diff:
            digest.update(str(getattr(file_diff, "path", "")).encode("utf-8", errors="ignore"))
            digest.update(str(file_diff).encode("utf-8", errors="ignore"))
        return digest.hexdigest()

    def _review_fingerprint(self, repo: Repo, diff_hash: str, config: ProjectConfig) -> str:
        payload = {
            "head_sha": self._head_sha(repo),
            "diff_hash": diff_hash,
            "graph_context_max_tokens": getattr(config, "graph_context_max_tokens", None),
            "context_mode": getattr(config, "context_mode", None),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8", errors="ignore")
        ).hexdigest()

    def _graphify_version(self, repo: Repo) -> str:
        command = os.getenv("EVALOPS_GRAPHIFY_COMMAND", "graphify")
        if shutil.which(command) is None:
            return ""
        try:
            completed = self.runner(
                [command, "--version"],
                cwd=str(repo.working_tree_dir or "."),
                text=True,
                capture_output=True,
                timeout=10,
            )
        except Exception:
            return ""
        return (completed.stdout or completed.stderr or "").strip()
