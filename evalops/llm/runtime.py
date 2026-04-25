"""LangChain-backed LLM invocation helpers."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable

from evalops.runtime import settings

from .errors import LLMContextLengthExceededError
from .providers import make_chat_model


def _content_part_text(part: Any) -> str | None:
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return None

    part_type = str(part.get("type", "")).lower()
    if part_type in {"thinking", "reasoning"}:
        return None
    if "text" in part and (not part_type or part_type in {"text", "output_text"}):
        return str(part["text"])
    return None


def _text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts = [
            text
            for part in content
            if (text := _content_part_text(part)) is not None
        ]
        return "\n".join(parts)
    return str(content)


def _looks_like_context_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(term in msg for term in ("context length", "maximum context", "too many tokens"))


def _extract_json(text: str) -> Any:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    return json.loads(value)


def _parse(text: str, parse_json: dict | bool | None) -> Any:
    if not parse_json:
        return text
    parsed = _extract_json(text)
    if isinstance(parse_json, dict) and (validator := parse_json.get("validator")):
        validator(parsed)
    return parsed


def _retrying(retries: int):
    from tenacity import retry, stop_after_attempt, wait_exponential

    return retry(
        reraise=True,
        stop=stop_after_attempt(max(1, retries)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )


def invoke(
    prompt: str,
    *,
    retries: int = 3,
    parse_json: dict | bool | None = None,
    callback: Callable[[str], None] | None = None,
) -> Any:
    model = make_chat_model()

    @_retrying(retries)
    def _call():
        try:
            response = model.invoke(prompt)
        except Exception as exc:
            if _looks_like_context_error(exc):
                raise LLMContextLengthExceededError(str(exc)) from exc
            raise
        text = _text(response)
        if callback:
            callback(text)
        return _parse(text, parse_json)

    return _call()


async def invoke_parallel(
    prompts: list[str],
    *,
    retries: int = 3,
    parse_json: dict | bool | None = None,
    allow_failures: bool = False,
) -> list[Any]:
    model = make_chat_model()
    max_tasks = settings().max_concurrent_tasks or len(prompts) or 1
    semaphore = asyncio.Semaphore(max_tasks)

    async def _one(prompt: str):
        async with semaphore:
            @_retrying(retries)
            async def _call():
                try:
                    response = await model.ainvoke(prompt)
                except Exception as exc:
                    if _looks_like_context_error(exc):
                        raise LLMContextLengthExceededError(str(exc)) from exc
                    raise
                return _parse(_text(response), parse_json)

            try:
                return await _call()
            except Exception as exc:
                if allow_failures:
                    return exc
                raise

    return await asyncio.gather(*[_one(prompt) for prompt in prompts])
