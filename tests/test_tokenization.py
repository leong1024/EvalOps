from evalops.tokenization import count_tokens, fit_to_token_size


def test_count_tokens_returns_positive_count():
    assert count_tokens("hello world") > 0


def test_fit_to_token_size_preserves_order_and_reports_removed_items():
    items = ["short", "another short item", "x" * 1000]
    kept, removed = fit_to_token_size(items, max_tokens=count_tokens(items[0]) + 1)

    assert kept == [items[0]]
    assert removed == 2
