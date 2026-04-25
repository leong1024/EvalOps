"""Token counting and budget fitting helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _encoding():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def count_tokens(text: Any) -> int:
    value = str(text)
    enc = _encoding()
    if enc is None:
        return max(1, len(value) // 4)
    return len(enc.encode(value))


def fit_to_token_size(parts: Iterable[Any], max_tokens: int | None) -> tuple[list[Any], int]:
    items = list(parts)
    if max_tokens is None:
        return items, 0

    kept: list[Any] = []
    used = 0
    for item in items:
        item_tokens = count_tokens(item)
        if kept and used + item_tokens > max_tokens:
            break
        if not kept and item_tokens > max_tokens:
            text = str(item)
            ratio = max_tokens / max(item_tokens, 1)
            kept.append(text[: max(1, int(len(text) * ratio))])
            return kept, len(items) - 1
        kept.append(item)
        used += item_tokens
    return kept, len(items) - len(kept)
