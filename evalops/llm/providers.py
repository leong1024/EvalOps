"""LangChain provider factory."""

from __future__ import annotations

from evalops.runtime import ApiType, LLMConfigError, settings


def make_chat_model():
    cfg = settings()
    if cfg.api_type == ApiType.NONE:
        raise LLMConfigError("Gemini is disabled for this run.")
    if not cfg.model:
        raise LLMConfigError("MODEL is not configured.")

    if cfg.api_type == ApiType.GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=cfg.model, google_api_key=cfg.api_key or None)

    raise LLMConfigError(f"Unsupported Gemini provider setting: {cfg.api_type}")
