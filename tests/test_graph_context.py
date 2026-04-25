import json
import subprocess
from pathlib import Path

from evalops.graph.context import GraphifyContextProvider
from evalops.prompts import render_string
from evalops.project_config import ProjectConfig


class FakeCommit:
    hexsha = "head-sha"


class FakeHead:
    commit = FakeCommit()


class FakeGit:
    def ls_files(self):
        return "app.py\nlib.py\n"


class FakeRepo:
    def __init__(self, root: Path):
        self.working_tree_dir = str(root)
        self.head = FakeHead()
        self.git = FakeGit()


class FakeDiff:
    path = "app.py"

    def __str__(self):
        return "diff --git a/app.py b/app.py"


def _config(tmp_path: Path, **overrides):
    values = {
        "graph_context_enabled": True,
        "graph_context_path": str(tmp_path / ".evalops" / "graphify"),
        "graph_context_max_tokens": 200,
    }
    values.update(overrides)
    return ProjectConfig(**values)


def _runner_writes_graph(calls):
    def runner(args, cwd, **kwargs):
        calls.append(args)
        if args[-1] == "--version":
            return subprocess.CompletedProcess(args, 0, stdout="graphify 0.5.0", stderr="")
        output = Path(cwd) / "graphify-out"
        output.mkdir(parents=True, exist_ok=True)
        (output / "graph.json").write_text(
            json.dumps(
                {
                    "nodes": [
                        {"id": "app.py:add", "file": "app.py"},
                        {"id": "lib.py:helper", "file": "lib.py"},
                    ],
                    "edges": [{"source": "app.py:add", "target": "lib.py:helper"}],
                }
            ),
            encoding="utf-8",
        )
        (output / "GRAPH_REPORT.md").write_text("Graph report", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="updated", stderr="")

    return runner


def test_missing_graph_triggers_build_and_writes_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr("evalops.graph.context.shutil.which", lambda command: command)
    calls = []
    provider = GraphifyContextProvider(runner=_runner_writes_graph(calls))
    result = provider.get_context(FakeRepo(tmp_path), [FakeDiff()], _config(tmp_path))

    graph_dir = tmp_path / ".evalops" / "graphify"
    assert result.refreshed is True
    assert (graph_dir / "graph.json").exists()
    metadata = json.loads((graph_dir / "metadata.json").read_text())
    assert metadata["head_sha"] == "head-sha"
    assert metadata["diff_hash"]
    assert metadata["review_fingerprint"]
    assert "app.py" in result.by_file["app.py"]
    assert calls[0][:2] == ["graphify", "update"]


def test_matching_metadata_skips_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr("evalops.graph.context.shutil.which", lambda command: command)
    graph_dir = tmp_path / ".evalops" / "graphify"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text('{"nodes":[{"file":"app.py"}]}', encoding="utf-8")
    (graph_dir / "metadata.json").write_text('{"head_sha":"head-sha"}', encoding="utf-8")
    calls = []
    provider = GraphifyContextProvider(runner=_runner_writes_graph(calls))

    result = provider.get_context(FakeRepo(tmp_path), [FakeDiff()], _config(tmp_path))

    assert result.refreshed is False
    assert calls == []
    assert "app.py" in result.by_file


def test_stale_metadata_triggers_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr("evalops.graph.context.shutil.which", lambda command: command)
    graph_dir = tmp_path / ".evalops" / "graphify"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text('{"nodes":[{"file":"app.py"}]}', encoding="utf-8")
    (graph_dir / "metadata.json").write_text('{"head_sha":"old"}', encoding="utf-8")
    calls = []
    provider = GraphifyContextProvider(runner=_runner_writes_graph(calls))

    result = provider.get_context(FakeRepo(tmp_path), [FakeDiff()], _config(tmp_path))

    assert result.refreshed is True
    assert calls[0][:2] == ["graphify", "update"]


def test_changed_diff_fingerprint_triggers_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr("evalops.graph.context.shutil.which", lambda command: command)
    graph_dir = tmp_path / ".evalops" / "graphify"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text('{"nodes":[{"file":"app.py"}]}', encoding="utf-8")
    provider = GraphifyContextProvider()
    old_hash = provider._diff_hash([FakeDiff()])
    old_fingerprint = provider._review_fingerprint(FakeRepo(tmp_path), old_hash, _config(tmp_path))
    (graph_dir / "metadata.json").write_text(
        json.dumps({"head_sha": "head-sha", "review_fingerprint": old_fingerprint}),
        encoding="utf-8",
    )

    class ChangedDiff:
        path = "app.py"

        def __str__(self):
            return "diff --git a/app.py b/app.py\n+changed"

    calls = []
    provider = GraphifyContextProvider(runner=_runner_writes_graph(calls))

    result = provider.get_context(FakeRepo(tmp_path), [ChangedDiff()], _config(tmp_path))

    assert result.refreshed is True
    assert calls[0][:2] == ["graphify", "update"]


def test_graphify_failure_returns_warning_when_fail_open(tmp_path, monkeypatch):
    monkeypatch.setattr("evalops.graph.context.shutil.which", lambda command: command)

    def failing_runner(args, cwd, **kwargs):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")

    provider = GraphifyContextProvider(runner=failing_runner)
    result = provider.get_context(FakeRepo(tmp_path), [FakeDiff()], _config(tmp_path))

    assert result.by_file == {}
    assert result.warnings
    assert "Graphify context unavailable" in result.warnings[0]


def test_graph_context_is_bounded(tmp_path):
    graph_dir = tmp_path / ".evalops" / "graphify"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text(
        json.dumps({"nodes": [{"file": "app.py", "detail": "x " * 500}]}),
        encoding="utf-8",
    )
    provider = GraphifyContextProvider()

    context = provider._context_for_file(
        provider._graph_text(graph_dir),
        "app.py",
        max_tokens=10,
    )

    assert "app.py" in context
    assert "Trimmed" in context


def test_review_prompt_includes_graph_context_only_when_available():
    cfg = ProjectConfig(**ProjectConfig._read_bundled_defaults())

    without_graph = render_string(
        cfg.prompt,
        input="diff",
        file_lines="",
        graph_context=None,
        **cfg.prompt_vars,
    )
    with_graph = render_string(
        cfg.prompt,
        input="diff",
        file_lines="",
        graph_context="app.py depends on lib.py",
        **cfg.prompt_vars,
    )

    assert "REPOSITORY GRAPH NEIGHBORHOOD" not in without_graph
    assert "REPOSITORY GRAPH NEIGHBORHOOD" in with_graph
    assert "app.py depends on lib.py" in with_graph
