import json

from evalops import core
from evalops.context import Context
from evalops.project_config import ProjectConfig
from evalops.report_struct import Report


def test_make_cr_summary_serializes_registered_issues(monkeypatch):
    report = Report(summary="")
    report.register_issue(
        "app.py",
        {
            "title": "Bug",
            "details": "Details",
            "severity": 2,
            "confidence": 1,
            "tags": ["bug"],
            "affected_lines": [],
        },
    )
    ctx = Context(
        report=report,
        config=ProjectConfig(summary_prompt="{{ issues | tojson }}"),
        diff=["diff --git a/app.py b/app.py"],
        repo=None,
    )
    monkeypatch.setattr(core, "invoke", lambda prompt, **kwargs: prompt)

    rendered = core.make_cr_summary(ctx)
    payload = json.loads(rendered)

    assert payload["app.py"][0]["title"] == "Bug"
