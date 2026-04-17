from __future__ import annotations

from typing import Any

from agent.tools import execute_settlement


class _EmptyVault:
    def has(self, _: str) -> bool:
        return False

    def inject(self, _: str) -> str:
        raise KeyError("missing")


def test_execute_algo_settlement_uses_registrar_secret_when_agent_env_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv("SHUNYAK_AGENT_MNEMONIC", raising=False)
    monkeypatch.setattr(execute_settlement, "SHUNYAK_ENABLE_TESTNET_TX", True)
    monkeypatch.setattr(execute_settlement, "SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK", False)
    monkeypatch.setattr(execute_settlement, "SHUNYAK_USDCA_ASA_ID", 0)
    monkeypatch.setattr(
        execute_settlement,
        "SHUNYAK_CONSENT_REGISTRAR_MNEMONIC",
        "registrar-seed-words",
    )

    captured: dict[str, Any] = {}

    def _fake_submit_payment_transaction(
        *,
        sender_mnemonic: str,
        receiver: str,
        amount_microalgo: int,
        memo: str,
    ) -> dict[str, Any]:
        captured["sender_mnemonic"] = sender_mnemonic
        captured["receiver"] = receiver
        captured["amount_microalgo"] = amount_microalgo
        captured["memo"] = memo
        return {
            "txid": "TEST_TX",
            "confirmed_round": 1,
            "explorer_url": "https://example.invalid/tx/TEST_TX",
            "receiver": receiver,
        }

    monkeypatch.setattr(
        execute_settlement,
        "submit_payment_transaction",
        _fake_submit_payment_transaction,
    )

    result = execute_settlement.execute_algo_settlement(
        recipient_address="RECIPIENT",
        amount_microalgo=1_000,
        memo="demo",
        vault=_EmptyVault(),
    )

    assert captured["sender_mnemonic"] == "registrar-seed-words"
    assert result["mode"] == "testnet_onchain"
    assert result["txid"] == "TEST_TX"
