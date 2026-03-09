"""
OpenRouter (LiteLLM) completion for manim workflow.
Uses OPENROUTER_API_KEY; returns content, usage, and reasoning like manim-generator.
"""

import os
import time
from typing import Any

import litellm
from litellm import completion
from litellm.cost_calculator import completion_cost

litellm.drop_params = True


def _extract_completion_details(raw_details: Any) -> dict[str, int]:
    if raw_details is None:
        return {}
    keys = ["text_tokens", "reasoning_tokens", "accepted_prediction_tokens", "rejected_prediction_tokens"]
    out: dict[str, int] = {}
    for key in keys:
        if isinstance(raw_details, dict):
            v = raw_details.get(key)
        else:
            v = getattr(raw_details, key, None)
        if v is not None:
            out[key] = int(v)
    return out


def _extract_provider_cost(usage: Any) -> float | None:
    if usage is None:
        return None
    raw = usage.get("cost") if isinstance(usage, dict) else getattr(usage, "cost", None)
    if raw is None:
        return None
    try:
        c = float(raw)
        return c if c >= 0 else None
    except (TypeError, ValueError):
        return None


def _build_usage_info(model: str, usage: Any, cost: float, llm_time: float) -> dict[str, Any]:
    prompt_tokens = int((usage.get("prompt_tokens") if isinstance(usage, dict) else getattr(usage, "prompt_tokens", None)) or 0)
    completion_tokens = int((usage.get("completion_tokens") if isinstance(usage, dict) else getattr(usage, "completion_tokens", None)) or 0)
    total_tokens = int((usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, "total_tokens", None)) or 0)
    details_raw = usage.get("completion_tokens_details") if isinstance(usage, dict) else getattr(usage, "completion_tokens_details", None)
    details = _extract_completion_details(details_raw)
    reasoning_tokens = int(details.get("reasoning_tokens", 0) or 0)
    text_tokens = details.get("text_tokens")
    if text_tokens is not None:
        answer_tokens = int(text_tokens)
    elif reasoning_tokens:
        answer_tokens = max(completion_tokens - reasoning_tokens, 0)
    else:
        answer_tokens = completion_tokens
    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens or (prompt_tokens + completion_tokens),
        "reasoning_tokens": reasoning_tokens,
        "answer_tokens": answer_tokens,
        "cost": cost,
        "llm_time": llm_time,
    }


def get_completion(
    model: str,
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    timeout: int = 120,
) -> tuple[str, dict[str, Any], str | None]:
    """
    Call OpenRouter (LiteLLM) and return (content, usage_info, reasoning_content).
    Expects OPENROUTER_API_KEY in the environment; model should be e.g. openrouter/google/gemini-2.0-flash-001.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "timeout": timeout,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    start = time.time()
    response = completion(**kwargs)
    llm_time = time.time() - start

    msg = response["choices"][0]["message"]
    content = msg.get("content") or ""
    usage_raw = getattr(response, "usage", None)
    provider_cost = _extract_provider_cost(usage_raw) if usage_raw else None
    if model.startswith("openrouter/") and provider_cost is not None:
        cost = provider_cost
    else:
        try:
            cost = completion_cost(response)
        except Exception:
            cost = 0.0
    usage_info = _build_usage_info(model, usage_raw, cost, llm_time)

    reasoning_content = None
    if isinstance(msg, dict):
        reasoning_content = msg.get("reasoning_content") or msg.get("reasoning")
    else:
        reasoning_content = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    if reasoning_content and not isinstance(reasoning_content, str):
        reasoning_content = str(reasoning_content)

    return content, usage_info, reasoning_content
