"""Calls Claude to write the legal report summary (owner: Lucas).

The API key is read from LLM_API_KEY (backend/.env, never committed).
"""

from functools import lru_cache

import anthropic

from app.config import get_settings

MAX_TOKENS = 16000
# Summarizing a handful of given articles needs little reasoning.
EFFORT = "medium"
# If Claude's safety classifiers decline a request, the API retries it on a
# fallback model chosen for that kind of refusal, inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class SummaryError(RuntimeError):
    pass


@lru_cache
def _client(api_key: str) -> anthropic.Anthropic:
    # The analysis runs inside the HTTP request when ASYNC=false, so don't let a
    # slow API hold it for the SDK's default 10 minutes.
    return anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=2)


def write_summary(system_prompt: str, user_message: str) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        raise SummaryError("LLM_API_KEY must be set to generate the legal report")

    response = _client(settings.llm_api_key).beta.messages.create(
        model=settings.llm_model,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
        output_config={"effort": EFFORT},
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )

    if response.stop_reason == "refusal":
        raise SummaryError(f"The model declined to write the summary ({response._request_id})")
    if response.stop_reason == "max_tokens":
        raise SummaryError(f"The summary was cut off ({response._request_id})")

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise SummaryError(f"The model returned no text ({response._request_id})")
    return text
