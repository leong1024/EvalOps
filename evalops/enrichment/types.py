from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Assessment = Literal["supports", "weakens", "inconclusive", "not_found"]


@dataclass
class EvidenceSnippet:
    file: str
    reason: str = ""
    snippet: str = ""
    start_line: int | None = None
    end_line: int | None = None


@dataclass
class IssueEvidence:
    issue_id: str
    file: str
    claim: str = ""
    related_files: list[str] = field(default_factory=list)
    evidence: list[EvidenceSnippet] = field(default_factory=list)
    agent_assessment: Assessment = "inconclusive"


@dataclass
class ContextBundle:
    mode_requested: str
    mode_used: str
    repo_ref: str = ""
    graph_refreshed: bool = False
    issues: list[IssueEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def has_context(self) -> bool:
        return bool(self.issues or self.warnings or self.metadata)
