from __future__ import annotations

import pytest

from api._common.llm import resolve_litellm_runtime_config
from api._common.litellm_runtime import LiteLLMInvocationError, run_litellm_task_brief


def test_resolve_litellm_runtime_config_accepts_byok_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SHUNYAK_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "model": "openrouter/meta-llama/llama-3.1-70b-instruct",
            "api_key": "sk-test-key",
            "api_base": "https://openrouter.ai/api/v1",
            "temperature": 0.2,
            "max_tokens": 512,
        }
    )

    assert config.enabled is True
    assert config.provider == "openrouter"
    assert config.model == "openrouter/meta-llama/llama-3.1-70b-instruct"
    assert config.api_key == "sk-test-key"
    assert config.api_base == "https://openrouter.ai/api/v1"
    assert config.temperature == 0.2
    assert config.max_tokens == 512


def test_resolve_litellm_runtime_config_rejects_invalid_api_base() -> None:
    with pytest.raises(ValueError, match="api_base"):
        resolve_litellm_runtime_config(
            {
                "enabled": True,
                "model": "openai/gpt-4o-mini",
                "api_base": "not-a-url",
            }
        )


def test_resolve_litellm_runtime_config_normalizes_groq_prefixed_model() -> None:
    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "provider": "groq",
            "model": "groq/meta-llama/llama-4-scout-17b-16e-instruct",
        }
    )

    assert config.provider == "groq"
    assert config.model == "meta-llama/llama-4-scout-17b-16e-instruct"


def test_resolve_litellm_runtime_config_defaults_to_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SHUNYAK_LLM_BYOK_ENABLED", raising=False)
    monkeypatch.delenv("SHUNYAK_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOLIOS_INFERENCE_MODEL", raising=False)

    config = resolve_litellm_runtime_config(None)

    assert config.enabled is False
    assert config.model == "openai/gpt-4o-mini"


def test_run_litellm_task_brief_requires_api_key() -> None:
    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "model": "openai/gpt-4o-mini",
            "api_key": "",
        }
    )

    with pytest.raises(LiteLLMInvocationError, match="litellm_api_key_missing"):
        run_litellm_task_brief(config, prompt="test prompt")


def test_run_litellm_task_brief_uses_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "model": "openai/gpt-4o-mini",
            "api_key": "sk-test",
            "api_base": "https://api.openai.com/v1",
            "api_version": "2024-10-21",
            "temperature": 0.1,
            "max_tokens": 32,
        }
    )
    calls: dict[str, object] = {}

    def _fake_completion(**kwargs: object) -> dict[str, object]:
        calls.update(kwargs)
        return {
            "choices": [
                {
                    "message": {
                        "content": "Validate consent first, then execute settlement.",
                    }
                }
            ]
        }

    monkeypatch.setattr("api._common.litellm_runtime.completion", _fake_completion)
    result = run_litellm_task_brief(config, prompt="Issue a micro-loan")

    assert result == "Validate consent first, then execute settlement."
    assert calls["model"] == "openai/gpt-4o-mini"
    assert calls["api_key"] == "sk-test"
    assert calls["api_base"] == "https://api.openai.com/v1"
    assert calls["api_version"] == "2024-10-21"
    assert calls["temperature"] == 0.1
    assert calls["max_tokens"] == 32


def test_run_litellm_task_brief_redacts_api_key_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "model": "openai/gpt-4o-mini",
            "api_key": "sk-secret-test-key",
            "api_base": "https://api.openai.com/v1",
        }
    )

    def _failing_completion(**_: object) -> dict[str, object]:
        raise ValueError("auth failed for key sk-secret-test-key")

    monkeypatch.setattr("api._common.litellm_runtime.completion", _failing_completion)

    with pytest.raises(LiteLLMInvocationError) as exc_info:
        run_litellm_task_brief(config, prompt="Issue a micro-loan")

    assert "sk-secret-test-key" not in str(exc_info.value)
    assert "[redacted]" in str(exc_info.value)


def test_run_litellm_task_brief_classifies_model_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "provider": "groq",
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "api_key": "gsk-secret-test-key",
            "api_base": "https://api.groq.com/openai/v1",
        }
    )

    def _failing_completion(**_: object) -> dict[str, object]:
        raise ValueError("Error code: 404 - {'error': {'message': 'The model `bad-model` does not exist'}}")

    monkeypatch.setattr("api._common.litellm_runtime.completion", _failing_completion)

    with pytest.raises(LiteLLMInvocationError) as exc_info:
        run_litellm_task_brief(config, prompt="Issue a micro-loan")

    assert exc_info.value.code == "litellm_model_not_found"
    assert exc_info.value.hint is not None


def test_run_litellm_task_brief_redacts_groq_key_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "provider": "groq",
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "api_key": "gsk-secret-test-key",
            "api_base": "https://api.groq.com/openai/v1",
        }
    )

    def _failing_completion(**_: object) -> dict[str, object]:
        raise ValueError("auth failed for key gsk-secret-test-key")

    monkeypatch.setattr("api._common.litellm_runtime.completion", _failing_completion)

    with pytest.raises(LiteLLMInvocationError) as exc_info:
        run_litellm_task_brief(config, prompt="Issue a micro-loan")

    assert "gsk-secret-test-key" not in str(exc_info.value)
    assert "[redacted]" in str(exc_info.value)


def test_run_litellm_task_brief_classifies_invalid_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "provider": "groq",
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "api_key": "gsk-secret-test-key",
            "api_base": "https://api.groq.com/openai/v1",
        }
    )

    def _failing_completion(**_: object) -> dict[str, object]:
        raise ValueError("GroqException: invalid_api_key")

    monkeypatch.setattr("api._common.litellm_runtime.completion", _failing_completion)

    with pytest.raises(LiteLLMInvocationError) as exc_info:
        run_litellm_task_brief(config, prompt="Issue a micro-loan")

    assert exc_info.value.code == "litellm_authentication_failed"
