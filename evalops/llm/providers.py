"""LangChain provider factory."""

from __future__ import annotations

from evalops.runtime import ApiType, LLMConfigError, settings


def make_chat_model():
    cfg = settings()
    if cfg.api_type == ApiType.NONE:
        raise LLMConfigError("LLM_API_TYPE is not configured.")
    if not cfg.model:
        raise LLMConfigError("MODEL is not configured.")

    if cfg.api_type == ApiType.OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=cfg.model, api_key=cfg.api_key or None)

    if cfg.api_type == ApiType.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=cfg.model, api_key=cfg.api_key or None)

    if cfg.api_type == ApiType.GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=cfg.model, google_api_key=cfg.api_key or None)

    raise LLMConfigError(f"Unsupported LLM_API_TYPE: {cfg.api_type}")
