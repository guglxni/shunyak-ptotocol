from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")
_PROVIDER_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"{field_name} must be a boolean")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    raise ValueError(f"{field_name} must be a boolean")


def _clean_text(value: Any, *, max_len: int, field_name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if len(cleaned) > max_len:
        raise ValueError(f"{field_name} must be <= {max_len} characters")
    return cleaned


def _parse_optional_float(value: Any, *, field_name: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    if parsed < 0 or parsed > 2:
        raise ValueError(f"{field_name} must be between 0 and 2")
    return parsed


def _parse_optional_int(value: Any, *, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed <= 0 or parsed > 65536:
        raise ValueError(f"{field_name} must be between 1 and 65536")
    return parsed


def _validate_api_base(api_base: str) -> str:
    if not api_base:
        return ""
    parsed = urlparse(api_base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("llm_config.api_base must be a valid http(s) URL")
    return api_base.rstrip("/")


def _derive_provider(provider: str, model: str) -> str:
    candidate = provider.strip().lower()
    if candidate:
        return candidate
    if "/" in model:
        return model.split("/", 1)[0].strip().lower()
    return "custom"


def _normalize_model_for_provider(model: str, provider: str) -> str:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()
    if normalized_provider == "groq" and normalized_model.startswith("groq/"):
        return normalized_model.split("/", 1)[1]
    return normalized_model


def _default_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


@dataclass(frozen=True)
class LiteLLMRuntimeConfig:
    enabled: bool
    provider: str
    model: str
    api_key: str
    api_base: str
    api_version: str
    temperature: float | None = None
    max_tokens: int | None = None

    def request_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "api_version": self.api_version,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def public_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider or None,
            "model": self.model or None,
            "api_base": self.api_base or None,
            "api_version": self.api_version or None,
            "api_key_configured": bool(self.api_key),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def dolios_provider_profile(self) -> dict[str, str]:
        return {
            "base_url": self.api_base,
            "model": self.model,
            "api_key_env": "OPENAI_API_KEY",
        }


def resolve_litellm_runtime_config(raw_config: Any) -> LiteLLMRuntimeConfig:
    env_enabled = _default_bool("SHUNYAK_LLM_BYOK_ENABLED", False)
    env_provider = os.getenv("SHUNYAK_LLM_PROVIDER", "").strip().lower()
    env_model = (
        os.getenv("SHUNYAK_LLM_MODEL", "").strip()
        or os.getenv("DOLIOS_INFERENCE_MODEL", "").strip()
        or "openai/gpt-4o-mini"
    )
    env_api_key = os.getenv("SHUNYAK_LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    env_api_base = (
        os.getenv("SHUNYAK_LLM_API_BASE", "").strip()
        or os.getenv("OPENAI_API_BASE", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
    )
    env_api_version = (
        os.getenv("SHUNYAK_LLM_API_VERSION", "").strip()
        or os.getenv("OPENAI_API_VERSION", "").strip()
    )

    enabled = env_enabled
    provider = env_provider
    model = env_model
    api_key = env_api_key
    api_base = env_api_base
    api_version = env_api_version
    temperature: float | None = None
    max_tokens: int | None = None

    if raw_config is not None:
        if not isinstance(raw_config, dict):
            raise ValueError("llm_config must be an object")
        if "enabled" in raw_config:
            enabled = _parse_bool(raw_config.get("enabled"), field_name="llm_config.enabled")
        if "provider" in raw_config:
            provider = _clean_text(raw_config.get("provider"), max_len=64, field_name="llm_config.provider").lower()
        if "model" in raw_config:
            model = _clean_text(raw_config.get("model"), max_len=256, field_name="llm_config.model")
        if "api_key" in raw_config:
            api_key = _clean_text(raw_config.get("api_key"), max_len=512, field_name="llm_config.api_key")
        if "api_base" in raw_config:
            api_base = _clean_text(raw_config.get("api_base"), max_len=256, field_name="llm_config.api_base")
        if "api_version" in raw_config:
            api_version = _clean_text(
                raw_config.get("api_version"), max_len=64, field_name="llm_config.api_version"
            )
        if "temperature" in raw_config:
            temperature = _parse_optional_float(raw_config.get("temperature"), field_name="llm_config.temperature")
        if "max_tokens" in raw_config:
            max_tokens = _parse_optional_int(raw_config.get("max_tokens"), field_name="llm_config.max_tokens")

    if enabled:
        if not model:
            raise ValueError("llm_config.model is required when llm_config.enabled=true")
        if not _MODEL_RE.match(model):
            raise ValueError(
                "llm_config.model must be LiteLLM-compatible (letters, numbers, ., _, :, /, -)"
            )

        provider = _derive_provider(provider, model)
        model = _normalize_model_for_provider(model, provider)
        if not _PROVIDER_RE.match(provider):
            raise ValueError(
                "llm_config.provider must contain only letters, numbers, ., _, and -"
            )

        api_base = _validate_api_base(api_base)
    else:
        provider = _derive_provider(provider, model)
        model = _normalize_model_for_provider(model, provider)
        api_base = _validate_api_base(api_base) if api_base else ""

    return LiteLLMRuntimeConfig(
        enabled=enabled,
        provider=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
        api_version=api_version,
        temperature=temperature,
        max_tokens=max_tokens,
    )
