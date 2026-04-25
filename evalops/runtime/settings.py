"""Runtime settings and provider types for EvalOps."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ApiType(StrEnum):
    NONE = "none"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class LLMConfigError(RuntimeError):
    """Raised when the LLM runtime cannot be configured."""


@dataclass
class Settings:
    api_type: ApiType = ApiType.NONE
    api_key: str = ""
    model: str = ""
    max_concurrent_tasks: int | None = None
    dot_env_file: Path | None = None


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

    Legacy environment names are intentionally preserved:
    ``LLM_API_TYPE``, ``LLM_API_KEY``, ``MODEL`` and ``MAX_CONCURRENT_TASKS``.
    """
    global _settings
    path = Path(dot_env_file).expanduser() if dot_env_file else None
    _load_dotenv(path)

    api_type_raw = overrides.get("LLM_API_TYPE") or os.getenv("LLM_API_TYPE") or ApiType.NONE
    try:
        api_type = api_type_raw if isinstance(api_type_raw, ApiType) else ApiType(str(api_type_raw))
    except ValueError as exc:
        raise LLMConfigError(f"Unsupported LLM_API_TYPE: {api_type_raw}") from exc

    max_concurrent = overrides.get("MAX_CONCURRENT_TASKS") or os.getenv("MAX_CONCURRENT_TASKS")
    if max_concurrent in ("", None):
        max_concurrent = None
    else:
        max_concurrent = int(max_concurrent)

    provider_key_env = {
        ApiType.ANTHROPIC: "ANTHROPIC_API_KEY",
        ApiType.OPENAI: "OPENAI_API_KEY",
        ApiType.GOOGLE: "GOOGLE_API_KEY",
    }.get(api_type)
    api_key = (
        overrides.get("LLM_API_KEY")
        or os.getenv("LLM_API_KEY")
        or (os.getenv(provider_key_env) if provider_key_env else "")
        or ""
    )

    _settings = Settings(
        api_type=api_type,
        api_key=str(api_key),
        model=str(overrides.get("MODEL") or os.getenv("MODEL") or ""),
        max_concurrent_tasks=max_concurrent,
        dot_env_file=path,
    )
    return _settings


def settings() -> Settings:
    return _settings


def interactive_setup(dot_env_file: str | Path) -> None:
    """Write a minimal local environment file for interactive CLI usage."""
    from evalops.ui import ui

    api_type = ui.ask_choose(
        "Which language model API should EvalOps use?",
        {
            ApiType.ANTHROPIC: "Anthropic",
            ApiType.OPENAI: "OpenAI",
            ApiType.GOOGLE: "Google",
        },
    )
    api_key = ui.ask_non_empty("Enter your API key")
    model = ui.ask_non_empty("Enter model name")
    path = Path(dot_env_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"LLM_API_TYPE={api_type}\nLLM_API_KEY={api_key}\nMODEL={model}\n",
        encoding="utf-8",
    )
    ui.warning(f"Configuration saved to {path}")
