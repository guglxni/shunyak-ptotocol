from __future__ import annotations

from email.message import Message

import pytest

import api._common.agent_security as agent_security


def _headers(*, bearer: str | None = None, forwarded_for: str | None = None) -> Message:
    headers = Message()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    return headers


@pytest.fixture(autouse=True)
def _guard_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_security._REQUEST_WINDOWS.clear()
    agent_security._SPEND_WINDOWS.clear()

    monkeypatch.setattr(agent_security, "SHUNYAK_REQUIRE_OPERATOR_AUTH", True)
    monkeypatch.setattr(agent_security, "SHUNYAK_OPERATOR_TOKEN", "operator-secret")
    monkeypatch.setattr(agent_security, "SHUNYAK_REQUIRE_EXECUTION_TOKEN", True)
    monkeypatch.setattr(agent_security, "SHUNYAK_MAX_SETTLEMENT_MICROALGO", 5_000_000)
    monkeypatch.setattr(agent_security, "SHUNYAK_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(agent_security, "SHUNYAK_RATE_LIMIT_MAX_REQUESTS", 10)
    monkeypatch.setattr(agent_security, "SHUNYAK_RATE_LIMIT_MAX_PER_USER", 10)
    monkeypatch.setattr(agent_security, "SHUNYAK_RATE_LIMIT_SPEND_MICROALGO", 20_000_000)


def test_guard_rejects_missing_operator_token() -> None:
    result = agent_security.guard_agent_execution_request(
        headers=_headers(),
        fallback_client_ip="127.0.0.1",
        user_pubkey="u1",
        enterprise_pubkey="e1",
        amount_microalgo=1_000_000,
        consent_token="consent",
        endpoint_name="agent_execute",
    )

    assert result.ok is False
    assert result.status == 401
    assert result.error == "unauthorized_operator"


def test_guard_rejects_missing_consent_token_when_required() -> None:
    result = agent_security.guard_agent_execution_request(
        headers=_headers(bearer="operator-secret"),
        fallback_client_ip="127.0.0.1",
        user_pubkey="u1",
        enterprise_pubkey="e1",
        amount_microalgo=1_000_000,
        consent_token=None,
        endpoint_name="agent_execute",
    )

    assert result.ok is False
    assert result.status == 401
    assert result.error == "consent_token_required"


def test_guard_enforces_max_amount() -> None:
    result = agent_security.guard_agent_execution_request(
        headers=_headers(bearer="operator-secret"),
        fallback_client_ip="127.0.0.1",
        user_pubkey="u1",
        enterprise_pubkey="e1",
        amount_microalgo=9_000_000,
        consent_token="consent",
        endpoint_name="agent_execute",
    )

    assert result.ok is False
    assert result.status == 422
    assert result.error == "amount_microalgo_exceeds_max:5000000"


def test_guard_rate_limits_by_ip_window() -> None:
    # Make per-IP limit strict to verify endpoint abuse throttling.
    agent_security.SHUNYAK_RATE_LIMIT_MAX_REQUESTS = 1

    first = agent_security.guard_agent_execution_request(
        headers=_headers(bearer="operator-secret", forwarded_for="203.0.113.10"),
        fallback_client_ip="127.0.0.1",
        user_pubkey="u1",
        enterprise_pubkey="e1",
        amount_microalgo=1_000_000,
        consent_token="consent",
        endpoint_name="agent_stream",
    )
    second = agent_security.guard_agent_execution_request(
        headers=_headers(bearer="operator-secret", forwarded_for="203.0.113.10"),
        fallback_client_ip="127.0.0.1",
        user_pubkey="u1",
        enterprise_pubkey="e1",
        amount_microalgo=1_000_000,
        consent_token="consent",
        endpoint_name="agent_stream",
    )

    assert first.ok is True
    assert second.ok is False
    assert second.status == 429
    assert second.error == "rate_limit_ip_exceeded"


def test_guard_rate_limits_spend_window() -> None:
    # Keep request counters permissive so spend budget is the limiting factor.
    agent_security.SHUNYAK_RATE_LIMIT_MAX_REQUESTS = 10
    agent_security.SHUNYAK_RATE_LIMIT_MAX_PER_USER = 10
    agent_security.SHUNYAK_RATE_LIMIT_SPEND_MICROALGO = 1_500_000

    first = agent_security.guard_agent_execution_request(
        headers=_headers(bearer="operator-secret"),
        fallback_client_ip="127.0.0.1",
        user_pubkey="u1",
        enterprise_pubkey="e1",
        amount_microalgo=1_000_000,
        consent_token="consent",
        endpoint_name="agent_execute",
    )
    second = agent_security.guard_agent_execution_request(
        headers=_headers(bearer="operator-secret"),
        fallback_client_ip="127.0.0.1",
        user_pubkey="u1",
        enterprise_pubkey="e1",
        amount_microalgo=600_000,
        consent_token="consent",
        endpoint_name="agent_execute",
    )

    assert first.ok is True
    assert second.ok is False
    assert second.status == 429
    assert second.error == "spend_limit_window_exceeded"
