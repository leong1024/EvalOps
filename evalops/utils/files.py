"""File display helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def file_link(path: str | Path | Any) -> str:
    """Return a terminal-friendly file path string."""
    try:
        return str(Path(path))
    except TypeError:
        return str(path)
