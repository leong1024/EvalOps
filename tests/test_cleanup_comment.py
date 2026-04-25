from evalops.commands.gh_react_to_comment import cleanup_comment_addressed_to_evalops


def test_remove_comment_prefixes():
    test_cases = [
        "evalops please help me with this",
        "AI, can you assist?",
        "Bot what should I do?",
        "@evalops please check this out",
        "@ai please review",
        "@bot, run the tests",
        "EVALOPS, this is urgent ",
        "@AI help needed",
        " evalops, please fix the bug",
        "Normal text without prefixes",
        "evalops,    extra spaces here",
        "  AI  ,  with leading spaces",
        "This has @evalops in the middle",  # Should NOT be removed
        "Text with @ai somewhere",  # Should NOT be removed
        "",
    ]
    expected_outputs = [
        "please help me with this",
        "can you assist?",
        "what should I do?",
        "please check this out",
        "please review",
        "run the tests",
        "this is urgent",
        "help needed",
        "please fix the bug",
        "Normal text without prefixes",
        "extra spaces here",
        "with leading spaces",
        "This has @evalops in the middle",  # Should NOT be removed
        "Text with @ai somewhere",  # Should NOT be removed
        "",
    ]
    for text, expected in zip(test_cases, expected_outputs):
        assert cleanup_comment_addressed_to_evalops(text) == expected, f"Failed for: {text}"
