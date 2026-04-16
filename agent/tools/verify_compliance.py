from __future__ import annotations

import time
from typing import Any

from api._common.algorand import verify_consent_onchain
from api._common.constants import IS_DEPLOYED_ENV
from api._common.store import get_consent_record
from api._common.token import validate_consent_token


CAPABILITIES = {
    "network": {
        "allow_domains": [
            "testnet-api.algonode.cloud",
            "testnet-idx.algonode.cloud",
        ]
    },
    "filesystem": {"read": [], "write": []},
    "dlp_allowed": [],
}


def verify_shunyak_compliance(
    user_pubkey: str,
    enterprise_pubkey: str,
    consent_token: str | None = None,
) -> dict[str, Any]:
    record = get_consent_record(user_pubkey=user_pubkey, enterprise_pubkey=enterprise_pubkey)
    if not record:
        if consent_token:
            try:
                token_payload = validate_consent_token(
                    consent_token,
                    user_pubkey=user_pubkey,
                    enterprise_pubkey=enterprise_pubkey,
                )
            except RuntimeError as exc:
                return {
                    "valid": False,
                    "expires_at": None,
                    "reason": f"consent_token_secret_invalid:{exc}",
                }
            if token_payload is not None:
                mode = str(token_payload.get("mode", "")).strip()
                consent_txid = str(token_payload.get("consent_txid", "")).strip()
                claim_hash = token_payload.get("claim_hash")

                if mode.startswith("mock"):
                    if IS_DEPLOYED_ENV:
                        return {
                            "valid": False,
                            "expires_at": int(token_payload["expires_at"]),
                            "reason": "mock_consent_token_disallowed",
                        }
                    return {
                        "valid": True,
                        "expires_at": int(token_payload["expires_at"]),
                        "reason": "consent_token_valid_mock",
                    }

                valid_tx, reason, _ = verify_consent_onchain(
                    user_pubkey=user_pubkey,
                    enterprise_pubkey=enterprise_pubkey,
                    claim_hash=claim_hash if isinstance(claim_hash, str) else None,
                    consent_txid=consent_txid or None,
                )
                if valid_tx:
                    return {
                        "valid": True,
                        "expires_at": int(token_payload["expires_at"]),
                        "reason": "consent_onchain_valid",
                    }
                return {
                    "valid": False,
                    "expires_at": int(token_payload["expires_at"]),
                    "reason": reason,
                }
        return {
            "valid": False,
            "expires_at": None,
            "reason": "no_consent_record",
        }

    expiry_timestamp = int(record.get("expiry_timestamp", 0))
    now_ts = int(time.time())
    if expiry_timestamp < now_ts:
        return {
            "valid": False,
            "expires_at": expiry_timestamp,
            "reason": "consent_expired",
        }

    tx_mode = str(record.get("tx_mode", "")).strip()
    if tx_mode.startswith("testnet_onchain"):
        valid_onchain, reason, _ = verify_consent_onchain(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            claim_hash=str(record.get("claim_hash", "") or "") or None,
            consent_txid=str(record.get("txid", "") or "") or None,
        )
        if not valid_onchain:
            return {
                "valid": False,
                "expires_at": expiry_timestamp,
                "reason": reason,
            }

        return {
            "valid": True,
            "expires_at": expiry_timestamp,
            "reason": "consent_onchain_valid",
        }

    return {
        "valid": True,
        "expires_at": expiry_timestamp,
        "reason": "consent_active",
    }
