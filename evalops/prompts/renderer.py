"""Prompt and template rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


class PromptRenderer:
    def __init__(self, template_paths: list[str | Path] | None = None):
        package_tpl = Path(__file__).resolve().parents[1] / "tpl"
        self.template_paths = [Path(p) for p in (template_paths or [package_tpl])]
        self.env = Environment(
            loader=FileSystemLoader([str(p) for p in self.template_paths]),
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def render_string(self, template: str, **variables: Any) -> str:
        return self.env.from_string(template).render(**variables)

    def render_file(self, template_name: str, **variables: Any) -> str:
        return self.env.get_template(template_name).render(**variables)


_renderer = PromptRenderer()


def configure_template_paths(template_paths: list[str | Path]) -> None:
    global _renderer
    _renderer = PromptRenderer(template_paths)


def renderer() -> PromptRenderer:
    return _renderer


def render_string(template: str, **variables: Any) -> str:
    return _renderer.render_string(template, **variables)


def render_file(template_name: str, **variables: Any) -> str:
    return _renderer.render_file(template_name, **variables)
