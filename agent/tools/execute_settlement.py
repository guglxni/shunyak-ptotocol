from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from api._common.algorand import submit_asset_transfer_transaction, submit_payment_transaction
from api._common.constants import SHUNYAK_ENABLE_TESTNET_TX
from api._common.constants import SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK
from api._common.constants import SHUNYAK_USDCA_ASA_ID
from api._common.constants import TESTNET_EXPLORER_TX_BASE


CAPABILITIES = {
    "network": {"allow_domains": ["testnet-api.algonode.cloud"]},
    "filesystem": {"read": [], "write": []},
    "dlp_allowed": [],
}


def execute_algo_settlement(
    recipient_address: str,
    amount_microalgo: int,
    memo: str,
    *,
    vault: Any | None = None,
    vault_label: str = "SHUNYAK_AGENT_MNEMONIC",
) -> dict[str, Any]:
    if amount_microalgo <= 0:
        raise ValueError("amount_microalgo must be positive")

    if not recipient_address:
        raise ValueError("recipient_address is required")

    secret_seed = ""
    if vault is not None:
        if hasattr(vault, "has") and vault.has(vault_label):
            secret_seed = vault.inject(vault_label)
        elif hasattr(vault, "inject"):
            try:
                secret_seed = vault.inject(vault_label)
            except (KeyError, RuntimeError, ValueError, TypeError, OSError):
                secret_seed = ""

    if not secret_seed:
        secret_seed = os.getenv(vault_label, "")

    if not secret_seed:
        if not SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK:
            raise RuntimeError(
                "SHUNYAK_AGENT_MNEMONIC is missing and mock settlement fallback is disabled"
            )
        # Deterministic mock fallback is only allowed in non-production demo mode.
        secret_seed = "shunyak-demo-settlement-seed"

    if SHUNYAK_ENABLE_TESTNET_TX and secret_seed != "shunyak-demo-settlement-seed":
        try:
            if SHUNYAK_USDCA_ASA_ID > 0:
                onchain = submit_asset_transfer_transaction(
                    sender_mnemonic=secret_seed,
                    receiver=recipient_address,
                    amount_base_units=amount_microalgo,
                    asset_id=SHUNYAK_USDCA_ASA_ID,
                    memo=memo,
                )
                return {
                    "txid": onchain["txid"],
                    "confirmed_round": onchain["confirmed_round"],
                    "explorer_url": onchain["explorer_url"],
                    "mode": "testnet_onchain_asa",
                    "receiver": onchain.get("receiver"),
                    "asset_id": onchain.get("asset_id"),
                }

            onchain = submit_payment_transaction(
                sender_mnemonic=secret_seed,
                receiver=recipient_address,
                amount_microalgo=amount_microalgo,
                memo=memo,
            )
            return {
                "txid": onchain["txid"],
                "confirmed_round": onchain["confirmed_round"],
                "explorer_url": onchain["explorer_url"],
                "mode": "testnet_onchain",
                "receiver": onchain.get("receiver"),
            }
        except Exception as exc:
            if not SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK:
                raise RuntimeError(f"on-chain settlement failed: {exc}") from exc
            fallback_reason = str(exc)
        else:
            fallback_reason = None
    else:
        if not SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK:
            raise RuntimeError(
                "on-chain settlement is unavailable and mock settlement fallback is disabled"
            )
        fallback_reason = None

    seed = f"{recipient_address}:{amount_microalgo}:{memo}:{secret_seed}:{time.time_ns()}"
    txid = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:52]

    return {
        "txid": txid,
        "confirmed_round": int(time.time()) % 100000 + 45000,
        "explorer_url": f"{TESTNET_EXPLORER_TX_BASE}{txid}",
        "mode": "mock_fallback",
        "fallback_reason": fallback_reason,
    }
