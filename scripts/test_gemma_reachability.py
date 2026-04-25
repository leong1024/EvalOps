"""Simple connectivity check for the pinned Gemma model.

Usage:
    python scripts/test_gemma_reachability.py
"""

from __future__ import annotations

import os
import sys

from langchain_google_genai import ChatGoogleGenerativeAI

MODEL = "gemma-4-31b-it"
PROMPT = "Hi what is 1+1"


def main() -> int:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY is not set.", file=sys.stderr)
        return 2

    llm = ChatGoogleGenerativeAI(model=MODEL, google_api_key=api_key)
    try:
        response = llm.invoke(PROMPT)
    except Exception as exc:
        print(f"Failed to reach {MODEL}: {exc}", file=sys.stderr)
        return 1

    text = str(getattr(response, "content", response)).strip()
    print(f"Model: {MODEL}")
    print(f"Prompt: {PROMPT}")
    print(f"Response: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
