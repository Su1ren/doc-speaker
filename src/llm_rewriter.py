"""
llm_rewriter.py – Pluggable LLM rewrite step for Markdown → spoken SSML.
"""

import os
from typing import Optional

from src.prompt_builder import build_chat_messages


class LLMConfigError(RuntimeError):
    """Raised when LLM configuration (API keys, model names) is missing."""


class LLMServiceError(RuntimeError):
    """Raised when the upstream LLM API fails."""


def rewrite_with_openai(
    markdown: str,
    model: Optional[str] = None,
    locale: str = "zh",
    temperature: float = 0.4,
) -> str:
    """Rewrite Markdown into SSML using the OpenAI Chat Completions API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMConfigError("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise LLMConfigError("The 'openai' package is required for rewrite_with_openai.") from exc

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    messages = build_chat_messages(markdown, locale=locale)
    model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
        )
    except Exception as exc:  # pragma: no cover - upstream network failure
        raise LLMServiceError(str(exc)) from exc

    content = completion.choices[0].message.content
    if not content:
        raise LLMServiceError("LLM returned an empty response.")
    return content
