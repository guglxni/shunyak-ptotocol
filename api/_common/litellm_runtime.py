from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from litellm import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    completion,
)
from openai import OpenAIError

from api._common.llm import LiteLLMRuntimeConfig

_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
_GROQ_KEY_RE = re.compile(r"gsk_[A-Za-z0-9_-]{8,}")
_MULTISPACE_RE = re.compile(r"\s+")
_MAX_DETAIL_LEN = 500


@dataclass(frozen=True)
class LiteLLMInvocationError(RuntimeError):
    code: str
    detail: str
    hint: str | None = None
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}:{self.detail}"


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _extract_text_from_response(response: Any) -> str:
    choices: Any = None
    if isinstance(response, dict):
        choices = response.get("choices")
    else:
        choices = getattr(response, "choices", None)

    if not isinstance(choices, list) or not choices:
        raise LiteLLMInvocationError("litellm_empty_response", "response had no choices")

    first_choice = choices[0]
    message: Any = None
    if isinstance(first_choice, dict):
        message = first_choice.get("message")
    else:
        message = getattr(first_choice, "message", None)

    content: Any = None
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)

    text = _stringify_content(content)
    if not text:
        raise LiteLLMInvocationError("litellm_empty_response", "response message content was empty")
    return text


def _redact_error_detail(detail: str, *, api_key: str) -> str:
    redacted = detail
    if api_key:
        redacted = redacted.replace(api_key, "[redacted]")
    redacted = _OPENAI_KEY_RE.sub("sk-[redacted]", redacted)
    redacted = _GROQ_KEY_RE.sub("gsk_[redacted]", redacted)
    redacted = _MULTISPACE_RE.sub(" ", redacted).strip()
    if len(redacted) > _MAX_DETAIL_LEN:
        return f"{redacted[:_MAX_DETAIL_LEN]}…"
    return redacted


def _looks_like_model_not_found(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "model" in lowered
        and ("does not exist" in lowered or "not found" in lowered or "unknown model" in lowered)
    )


def _looks_like_auth_error(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "invalid api key" in lowered
        or "authentication" in lowered
        or "unauthorized" in lowered
        or "permission denied" in lowered
        or "invalid_api_key" in lowered
    )


def _looks_like_rate_limit(detail: str) -> bool:
    lowered = detail.lower()
    return "rate limit" in lowered or "too many requests" in lowered or "429" in lowered


def _classify_litellm_exception(
    exc: BaseException, *, llm_config: LiteLLMRuntimeConfig
) -> LiteLLMInvocationError:
    safe_detail = _redact_error_detail(str(exc), api_key=llm_config.api_key)

    if isinstance(exc, NotFoundError) or _looks_like_model_not_found(safe_detail):
        return LiteLLMInvocationError(
            code="litellm_model_not_found",
            detail=safe_detail,
            hint=(
                "Model not available for provider/account. For Groq, use provider='groq' and model "
                "without prefix, e.g. 'meta-llama/llama-4-scout-17b-16e-instruct'."
            ),
            retryable=False,
        )
    if isinstance(exc, AuthenticationError) or _looks_like_auth_error(safe_detail):
        return LiteLLMInvocationError(
            code="litellm_authentication_failed",
            detail=safe_detail,
            hint="Check BYOK API key and API base URL for the selected provider.",
            retryable=False,
        )
    if isinstance(exc, RateLimitError) or _looks_like_rate_limit(safe_detail):
        return LiteLLMInvocationError(
            code="litellm_rate_limited",
            detail=safe_detail,
            hint="Provider rate limit reached. Retry later or switch to another model/provider.",
            retryable=True,
        )
    if isinstance(exc, (Timeout, APIConnectionError, ServiceUnavailableError, InternalServerError)):
        return LiteLLMInvocationError(
            code="litellm_provider_unavailable",
            detail=safe_detail,
            hint="Transient provider/network error. Retry the request.",
            retryable=True,
        )
    if isinstance(exc, BadRequestError):
        return LiteLLMInvocationError(
            code="litellm_bad_request",
            detail=safe_detail,
            hint="Invalid model or request payload for the selected provider.",
            retryable=False,
        )
    return LiteLLMInvocationError(
        code="litellm_call_failed",
        detail=safe_detail,
        hint="Unexpected LiteLLM provider error.",
        retryable=False,
    )


def run_litellm_task_brief(llm_config: LiteLLMRuntimeConfig, *, prompt: str) -> str:
    if not llm_config.enabled:
        return ""
    if not llm_config.api_key:
        raise LiteLLMInvocationError("litellm_api_key_missing", "Provide api_key in BYOK settings")

    request_kwargs: dict[str, Any] = {
        "model": llm_config.model,
        "api_key": llm_config.api_key,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an execution planner for a consent-gated fintech agent. "
                    "Return one concise sentence describing what the agent should do next."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    if llm_config.api_base:
        request_kwargs["api_base"] = llm_config.api_base
    if llm_config.api_version:
        request_kwargs["api_version"] = llm_config.api_version
    if llm_config.temperature is not None:
        request_kwargs["temperature"] = llm_config.temperature
    if llm_config.max_tokens is not None:
        request_kwargs["max_tokens"] = llm_config.max_tokens

    try:
        response = completion(**request_kwargs)
    except (
        AuthenticationError,
        BadRequestError,
        NotFoundError,
        APIConnectionError,
        Timeout,
        RateLimitError,
        ServiceUnavailableError,
        InternalServerError,
        OpenAIError,
        ValueError,
        TypeError,
        OSError,
    ) as exc:
        raise _classify_litellm_exception(exc, llm_config=llm_config) from exc

    return _extract_text_from_response(response)
