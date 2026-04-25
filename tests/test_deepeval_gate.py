import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from evalops.context import Context
from evalops.project_config import ProjectConfig
from evalops.quality import deepeval_gate
from evalops.report_struct import ProcessingWarning, Report, ReviewTarget


class ExampleJudgeResponse(BaseModel):
    score: float
    reason: str


def test_quality_gate_records_warning_score_and_renders(monkeypatch):
    cfg = ProjectConfig(
        quality_gate_enabled=True,
        quality_gate_min_score=0.7,
        quality_gate_metrics=["grounding", "relevance"],
        report_template_md=(
            "{% set gate = report.pipeline_out.quality_gate %}"
            "DeepEval {{ gate.status }} {{ '%.2f'|format(gate.score) }}"
        ),
    )
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
    ctx = Context(report=report, config=cfg, diff=["diff --git a/app.py b/app.py"], repo=None)

    def fake_measure(name, criteria, ctx):
        return deepeval_gate.MetricResult(score=0.55, reason=f"{name} needs work", status="warn")

    monkeypatch.setattr(deepeval_gate, "_measure_metric", fake_measure)

    result = deepeval_gate.run_quality_gate(ctx)
    report.pipeline_out = ctx.pipeline_out

    assert result["status"] == "warn"
    assert result["score"] == 0.55
    assert set(result["metrics"]) == {"grounding", "relevance"}
    assert "DeepEval warn 0.55" in report.render(cfg)


def test_schema_response_accepts_fenced_json():
    response = """```json
{"score": 0.8, "reason": "grounded"}
```"""

    parsed = deepeval_gate._coerce_schema_response(response, ExampleJudgeResponse)

    assert parsed.score == 0.8
    assert parsed.reason == "grounded"


def test_schema_response_accepts_json_with_surrounding_text():
    response = 'Here is the result:\n{"score": 0.9, "reason": "relevant"}'

    parsed = deepeval_gate._coerce_schema_response(response, ExampleJudgeResponse)

    assert parsed.score == 0.9
    assert parsed.reason == "relevant"


def test_quality_gate_fails_open_when_deepeval_errors(monkeypatch):
    cfg = ProjectConfig(quality_gate_enabled=True, quality_gate_metrics=["grounding"])
    ctx = Context(report=Report(summary="Summary"), config=cfg, diff=["diff"], repo=None)

    def raise_measure(name, criteria, ctx):
        raise RuntimeError("no judge available")

    monkeypatch.setattr(deepeval_gate, "_measure_metric", raise_measure)

    result = deepeval_gate.run_quality_gate(ctx)

    assert result["status"] == "skipped"
    assert result["score"] == 0.0
    assert "no judge available" in result["reason"]
    assert ctx.pipeline_out["quality_gate"] == result


def test_report_output_serializes_processing_warnings():
    cfg = ProjectConfig()
    report = Report(
        summary="Summary",
        processing_warnings=[ProcessingWarning(message="Skipped file", file="app.py")],
    )
    ctx = Context(report=report, config=cfg, diff=["diff"], repo=None)

    payload = json.loads(deepeval_gate._report_output(ctx))

    assert payload["processing_warnings"] == [
        {"message": "Skipped file", "file": "app.py"}
    ]


@pytest.mark.asyncio
async def test_review_runs_quality_gate_after_summary_and_saves_metadata(tmp_path, monkeypatch):
    from evalops import core

    class FakeRepo:
        working_tree_dir = str(tmp_path)

    class FakeFileDiff:
        path = "app.py"
        target_file = "b/app.py"
        is_added_file = False

        def __str__(self):
            return "diff --git a/app.py b/app.py"

    cfg = ProjectConfig(
        prompt="{{ input }}",
        summary_prompt="summary",
        quality_gate_enabled=True,
    )
    diff = [FakeFileDiff()]
    lines = {"app.py": "1: print('hello')"}
    monkeypatch.setattr(core, "_prepare", lambda **kwargs: (FakeRepo(), cfg, diff, lines))

    async def fake_invoke_parallel(*args, **kwargs):
        return [
            [
                {
                    "title": "Bug",
                    "details": "Details",
                    "severity": 2,
                    "confidence": 1,
                    "tags": ["bug"],
                    "affected_lines": [],
                }
            ]
        ]

    monkeypatch.setattr(core, "invoke_parallel", fake_invoke_parallel)
    monkeypatch.setattr(core, "make_cr_summary", lambda ctx: "Summary created")
    monkeypatch.setattr(core.Report, "to_cli", lambda self: None)

    def fake_quality_gate(ctx):
        assert ctx.report.summary == "Summary created"
        return {
            "status": "warn",
            "mode": "soft",
            "score": 0.4,
            "min_score": 0.7,
            "reason": "low grounding",
            "metrics": {},
        }

    monkeypatch.setattr(core, "run_quality_gate", fake_quality_gate)

    await core.review(ReviewTarget(), repo=FakeRepo(), out_folder=tmp_path)

    report = json.loads((Path(tmp_path) / "code-review-report.json").read_text())
    assert report["summary"] == "Summary created"
    assert report["pipeline_out"]["quality_gate"]["status"] == "warn"
