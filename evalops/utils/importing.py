"""Import helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Callable


def resolve_callable(path: str) -> Callable:
    """Resolve ``module.attr`` or ``module:attr`` into a callable."""
    module_name, _, attr = path.replace(":", ".").rpartition(".")
    if not module_name or not attr:
        raise ValueError(f"Invalid callable path: {path}")
    obj = getattr(import_module(module_name), attr)
    if not callable(obj):
        raise TypeError(f"Resolved object is not callable: {path}")
    return obj
