import json
from pathlib import Path

import pytest

from evalops.enrichment.deep_agent import DeepAgentContextRunner, _permission_path
from evalops.enrichment.graph import GraphIndex
from evalops.enrichment.modes import ContextEnricher, effective_context_mode, needs_graph_context
from evalops.graph.context import GraphContextResult
from evalops.project_config import ProjectConfig
from evalops.report_struct import Report


class FakeRepo:
    def __init__(self, root: Path):
        self.working_tree_dir = str(root)


def _report_with_issues():
    report = Report(number_of_processed_files=1, summary="Summary")
    report.register_issues(
        {
            "app.py": [
                {
                    "title": "Bug",
                    "details": "Details",
                    "severity": 2,
                    "confidence": 1,
                    "tags": ["bug"],
                    "affected_lines": [],
                }
            ]
        }
    )
    return report


def test_legacy_graph_enabled_maps_to_graph_context_mode():
    cfg = ProjectConfig(context_mode="diff_only", graph_context_enabled=True)

    assert effective_context_mode(cfg) == "graph_context"
    assert needs_graph_context(cfg) is True


def test_graph_context_mode_builds_context_bundle(tmp_path):
    cfg = ProjectConfig(context_mode="graph_context")
    graph_result = GraphContextResult(
        by_file={"app.py": "app.py depends on lib.py"},
        refreshed=True,
        metadata={"review_fingerprint": "abc123"},
    )

    bundle = ContextEnricher().enrich(
        repo=FakeRepo(tmp_path),
        diff=[],
        report=_report_with_issues(),
        graph_result=graph_result,
        config=cfg,
    )

    assert bundle.mode_used == "graph_context"
    assert bundle.repo_ref == "abc123"
    assert bundle.issues[0].evidence[0].snippet == "app.py depends on lib.py"


def test_auto_mode_falls_back_to_graph_context_when_deep_agent_fails(tmp_path):
    class FailingRunner:
        def collect_context(self, *args, **kwargs):
            raise RuntimeError("no deep agent")

    cfg = ProjectConfig(context_mode="auto")
    graph_result = GraphContextResult(
        by_file={"app.py": "graph context"},
        graph_dir=tmp_path,
        metadata={"head_sha": "head"},
    )

    bundle = ContextEnricher(deep_agent_runner=FailingRunner()).enrich(
        repo=FakeRepo(tmp_path),
        diff=[],
        report=_report_with_issues(),
        graph_result=graph_result,
        config=cfg,
    )

    assert bundle.mode_requested == "auto"
    assert bundle.mode_used == "graph_context"
    assert "Deep Agent context unavailable" in bundle.warnings[0]


def test_deep_agent_runner_constructs_readonly_filesystem_backend(tmp_path):
    calls = {}

    class FakePermission:
        def __init__(self, operations, paths, mode="allow"):
            self.operations = operations
            self.paths = paths
            self.mode = mode

    class FakeBackend:
        def __init__(self, root_dir, virtual_mode=False):
            calls["backend"] = {"root_dir": root_dir, "virtual_mode": virtual_mode}

    class FakeAgent:
        def invoke(self, payload):
            calls["payload"] = payload
            return {
                "messages": [
                    {
                        "content": json.dumps(
                            {
                                "issues": [
                                    {
                                        "issue_id": "1",
                                        "file": "app.py",
                                        "claim": "Bug",
                                        "related_files": ["lib.py"],
                                        "evidence": [
                                            {
                                                "file": "lib.py",
                                                "reason": "callee",
                                                "snippet": "def helper(): pass",
                                                "start_line": 1,
                                                "end_line": 1,
                                            }
                                        ],
                                        "agent_assessment": "supports",
                                    }
                                ]
                            }
                        )
                    }
                ]
            }

    def fake_factory(**kwargs):
        calls["factory"] = kwargs
        return FakeAgent()

    runner = DeepAgentContextRunner(agent_factory=fake_factory)
    runner._load_deepagents = lambda: (fake_factory, FakeBackend, FakePermission)

    bundle = runner.collect_context(
        repo_root=tmp_path,
        issues=_report_with_issues().plain_issues,
        graph=GraphIndex.from_payload(
            {
                "nodes": [
                    {"id": "app", "file": "app.py"},
                    {"id": "lib", "file": "lib.py"},
                ],
                "edges": [{"source": "app", "target": "lib"}],
            }
        ),
        config=ProjectConfig(context_mode="deep_agent"),
        repo_ref="ref",
    )

    assert calls["backend"] == {"root_dir": str(tmp_path), "virtual_mode": True}
    permissions = calls["factory"]["permissions"]
    assert permissions[0].operations == ["write"]
    assert permissions[0].mode == "deny"
    assert permissions[-1].operations == ["read"]
    assert permissions[-1].mode == "allow"
    assert bundle.issues[0].agent_assessment == "supports"


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        (".env", "/.env"),
        ("**/*.pem", "/**/*.pem"),
        ("/.git/**", "/.git/**"),
    ],
)
def test_permission_path_normalizes_to_virtual_absolute_paths(pattern, expected):
    assert _permission_path(pattern) == expected
