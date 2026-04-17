from __future__ import annotations

import os
from typing import Any

from agent.shunyak_agent import ShunyakAgentService
from api._common.llm import resolve_litellm_runtime_config


class _DummyMCP:
    def __init__(self, *, compliance_valid: bool) -> None:
        self._compliance_valid = compliance_valid

    def call(self, tool_name: str, **_: Any) -> dict[str, Any]:
        if tool_name == "verify_shunyak_compliance":
            return {
                "valid": self._compliance_valid,
                "reason": "consent_active" if self._compliance_valid else "no_consent_record",
            }

        if tool_name == "execute_algo_settlement":
            if not self._compliance_valid:
                raise AssertionError("Settlement must not execute when compliance is invalid")
            return {
                "txid": "TEST_TXID",
                "confirmed_round": 1,
                "explorer_url": "https://example.invalid/tx/TEST_TXID",
                "mode": "testnet_onchain",
            }

        raise AssertionError(f"unexpected tool call: {tool_name}")


def test_execute_task_skips_dolios_inference_when_consent_invalid(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DOLIOS_INFERENCE_PROVIDER", raising=False)
    monkeypatch.delenv("DOLIOS_INFERENCE_MODEL", raising=False)

    llm_config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "provider": "openai",
            "model": "openai/gpt-4o-mini",
            "api_key": "sk-test-key",
        }
    )

    service = ShunyakAgentService(llm_config=llm_config)
    service.mcp = _DummyMCP(compliance_valid=False)

    result = service.execute_task(
        prompt="Process financial history for user-999 and issue micro-loan",
        user_pubkey="a" * 64,
        enterprise_pubkey="b" * 64,
        amount_microalgo=1_000,
        consent_token=None,
    )

    assert result["status"] == "blocked"
    assert "DPDP Compliance Failure" in result["outcome_message"]
    assert os.environ.get("DOLIOS_INFERENCE_PROVIDER") == "openai"
    assert os.environ.get("DOLIOS_INFERENCE_MODEL") == "openai/gpt-4o-mini"
    assert any(
        event.get("phase") == "llm"
        and "dolios inference skipped" in str(event.get("message", "")).lower()
        for event in result.get("events", [])
    )


def test_execute_task_emits_dolios_route_after_valid_compliance(
    monkeypatch,
) -> None:
    llm_config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "provider": "openai",
            "model": "openai/gpt-4o-mini",
            "api_key": "sk-test-key",
        }
    )

    service = ShunyakAgentService(llm_config=llm_config)
    service.mcp = _DummyMCP(compliance_valid=True)

    result = service.execute_task(
        prompt="Process financial history for demo-user-001 and issue micro-loan",
        user_pubkey="c" * 64,
        enterprise_pubkey="d" * 64,
        amount_microalgo=1_000,
        consent_token="token",
    )

    assert result["status"] == "authorized"
    assert result.get("settlement", {}).get("txid") == "TEST_TXID"
    assert any(
        event.get("phase") == "llm"
        and "dolios inference route configured" in str(event.get("message", "")).lower()
        for event in result.get("events", [])
    )


def test_service_sets_dolios_inference_env_from_llm_config(monkeypatch) -> None:
    monkeypatch.delenv("DOLIOS_INFERENCE_PROVIDER", raising=False)
    monkeypatch.delenv("DOLIOS_INFERENCE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_VERSION", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    llm_config = resolve_litellm_runtime_config(
        {
            "enabled": True,
            "provider": "openai",
            "model": "openai/gpt-4o-mini",
            "api_base": "https://api.openai.com/v1",
            "api_version": "2024-02-15-preview",
            "api_key": "sk-config-only",
        }
    )

    ShunyakAgentService(llm_config=llm_config)

    assert os.environ.get("DOLIOS_INFERENCE_PROVIDER") == "openai"
    assert os.environ.get("DOLIOS_INFERENCE_MODEL") == "openai/gpt-4o-mini"
    assert os.environ.get("OPENAI_API_BASE") == "https://api.openai.com/v1"
    assert os.environ.get("OPENAI_BASE_URL") == "https://api.openai.com/v1"
    assert os.environ.get("OPENAI_API_VERSION") == "2024-02-15-preview"
    assert os.environ.get("OPENAI_API_KEY") == "sk-config-only"
