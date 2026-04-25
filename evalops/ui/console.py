"""Console helpers used by EvalOps CLI output.

This module intentionally keeps the small API shape used by the rest of the
CLI while relying on standard terminal escape sequences and Typer prompts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import typer


class _Style:
    def __init__(self, code: str):
        self.code = code

    def __call__(self, text: Any = "") -> str:
        return f"{self.code}{text}{ui.reset}"

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return self.code

    def __add__(self, other: Any) -> str:
        return str(self) + str(other)

    def __radd__(self, other: Any) -> str:
        return str(other) + str(self)


class UI:
    reset = "\033[0m"
    red = _Style("\033[31m")
    green = _Style("\033[32m")
    yellow = _Style("\033[33m")
    blue = _Style("\033[34m")
    cyan = _Style("\033[36m")
    white = _Style("\033[37m")
    gray = _Style("\033[90m")
    bright = _Style("\033[1m")
    dim = _Style("\033[2m")

    @staticmethod
    def error(message: Any) -> None:
        typer.echo(UI.red(message), err=True)

    @staticmethod
    def warning(message: Any) -> None:
        typer.echo(UI.yellow(message), err=True)

    @staticmethod
    def ask_yn(prompt: str, default: bool = False) -> bool:
        return typer.confirm(prompt, default=default)

    @staticmethod
    def ask_non_empty(prompt: str) -> str:
        value = ""
        while not value:
            value = typer.prompt(prompt).strip()
        return value

    @staticmethod
    def ask_choose(prompt: str, choices: Mapping[Any, str] | Sequence[Any], default: Any = None) -> Any:
        if isinstance(choices, Mapping):
            keys = list(choices.keys())
            labels = [str(choices[key]) for key in keys]
        else:
            keys = list(choices)
            labels = [str(choice) for choice in keys]

        for idx, label in enumerate(labels, start=1):
            typer.echo(f"  {idx}. {label}")

        default_index = None
        if default is not None and default in keys:
            default_index = keys.index(default) + 1

        while True:
            value = typer.prompt(prompt, default=default_index)
            try:
                idx = int(value)
            except (TypeError, ValueError):
                idx = labels.index(str(value)) + 1 if str(value) in labels else -1
            if 1 <= idx <= len(keys):
                return keys[idx - 1]
            typer.echo(f"Please choose a value from 1 to {len(keys)}.")


ui = UI()
