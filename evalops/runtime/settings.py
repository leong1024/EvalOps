"""Runtime settings and provider types for EvalOps."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from evalops.constants import DEFAULT_LLM_MODEL


class ApiType(StrEnum):
    NONE = "none"
    GOOGLE = "google"


class LLMConfigError(RuntimeError):
    """Raised when the LLM runtime cannot be configured."""


@dataclass
class Settings:
    api_type: ApiType = ApiType.GOOGLE
    api_key: str = ""
    model: str = ""
    max_concurrent_tasks: int | None = None
    dot_env_file: Path | None = None
    prompt_templates_path: list[Path] = field(default_factory=list)


_settings = Settings()


def _load_dotenv(path: Path | None) -> None:
    if not path or not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def configure(dot_env_file: str | Path | None = None, **overrides) -> Settings:
    """Load environment-backed settings.

    Gemini is the only supported provider. ``EVALOPS_DISABLE_LLM=1`` is
    accepted for tests and non-LLM commands.
    """
    global _settings
    path = Path(dot_env_file).expanduser() if dot_env_file else None
    _load_dotenv(path)

    disabled = str(overrides.get("EVALOPS_DISABLE_LLM") or os.getenv("EVALOPS_DISABLE_LLM")).lower()
    api_type_raw = ApiType.NONE if disabled in {"1", "true", "yes"} else ApiType.GOOGLE
    try:
        api_type = api_type_raw if isinstance(api_type_raw, ApiType) else ApiType(str(api_type_raw))
    except ValueError as exc:
        raise LLMConfigError(f"Unsupported Gemini provider setting: {api_type_raw}") from exc

    max_concurrent = overrides.get("MAX_CONCURRENT_TASKS") or os.getenv("MAX_CONCURRENT_TASKS")
    if max_concurrent in ("", None):
        max_concurrent = None
    else:
        max_concurrent = int(max_concurrent)

    api_key = overrides.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""

    prompt_templates_path = overrides.get("PROMPT_TEMPLATES_PATH") or []
    if isinstance(prompt_templates_path, (str, Path)):
        prompt_templates_path = [prompt_templates_path]

    _settings = Settings(
        api_type=api_type,
        api_key=str(api_key),
        model=DEFAULT_LLM_MODEL,
        max_concurrent_tasks=max_concurrent,
        dot_env_file=path,
        prompt_templates_path=[Path(p) for p in prompt_templates_path],
    )
    return _settings


def settings() -> Settings:
    return _settings


def interactive_setup(dot_env_file: str | Path) -> None:
    """Write a minimal local environment file for interactive CLI usage."""
    from evalops.ui import ui

    api_key = ui.ask_non_empty("Enter your Gemini API key")
    model = DEFAULT_LLM_MODEL
    path = Path(dot_env_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"GOOGLE_API_KEY={api_key}\nMODEL={model}\n",
        encoding="utf-8",
    )
    ui.warning(f"Configuration saved to {path}")
