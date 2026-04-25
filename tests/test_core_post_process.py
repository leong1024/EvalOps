from evalops.core import _run_post_process


def test_run_post_process_filters_issues_without_framework_global():
    issues = {
        "file.py": [
            {"confidence": 1, "severity": 3},
            {"confidence": 2, "severity": 3},
            {"confidence": 1, "severity": 4},
        ]
    }
    code = """
for fn in issues:
    issues[fn] = [
        i for i in issues[fn]
        if i["confidence"] == 1 and i["severity"] <= 3
    ]
"""

    _run_post_process(code, issues=issues)

    assert issues == {"file.py": [{"confidence": 1, "severity": 3}]}
