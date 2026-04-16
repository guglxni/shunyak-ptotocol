from __future__ import annotations

import time

from api._common.algorand import verify_consent_onchain
from api._common.constants import SHUNYAK_APP_ID
from api._common.constants import DEFAULT_ENTERPRISE_PUBKEY
from api._common.http import JSONHandler
from api._common.store import get_consent_record
from api._common.token import validate_consent_token


class handler(JSONHandler):
    def do_GET(self) -> None:  # noqa: N802
        query = self._query()

        user_pubkey = "".join(query.get("user_pubkey", [])).strip()
        enterprise_pubkey = "".join(query.get("enterprise_pubkey", [])).strip()
        consent_token = "".join(query.get("consent_token", [])).strip()
        consent_txid = "".join(query.get("consent_txid", [])).strip()
        claim_hash = "".join(query.get("claim_hash", [])).strip().lower()
        if not enterprise_pubkey:
            enterprise_pubkey = DEFAULT_ENTERPRISE_PUBKEY

        if not user_pubkey:
            self._send_error("user_pubkey query param is required", status=422)
            return

        record = get_consent_record(user_pubkey, enterprise_pubkey)
        if not record:
            if consent_token:
                try:
                    token_payload = validate_consent_token(
                        consent_token,
                        user_pubkey=user_pubkey,
                        enterprise_pubkey=enterprise_pubkey,
                    )
                except RuntimeError as exc:
                    self._send_error(f"consent token validation unavailable: {exc}", status=503)
                    return
                if token_payload is not None:
                    mode = str(token_payload.get("mode", "")).strip()
                    consent_txid = str(token_payload.get("consent_txid", "")).strip()

                    if not mode.startswith("testnet_onchain"):
                        self._send_json(
                            {
                                "ok": True,
                                "valid": False,
                                "reason": "consent_token_mode_not_onchain",
                                "expires_at": int(token_payload.get("expires_at", 0) or 0),
                                "consent_hash": token_payload.get("claim_hash"),
                                "consent_source": token_payload.get("consent_source"),
                                "identity_provider": token_payload.get("identity_provider"),
                                "zk_backend": token_payload.get("zk_backend"),
                            }
                        )
                        return

                    valid_tx, reason, _ = verify_consent_onchain(
                        user_pubkey=user_pubkey,
                        enterprise_pubkey=enterprise_pubkey,
                        claim_hash=str(token_payload.get("claim_hash", "") or "") or None,
                        consent_txid=consent_txid or None,
                    )
                    if valid_tx:
                        self._send_json(
                            {
                                "ok": True,
                                "valid": True,
                                "reason": "consent_onchain_valid",
                                "expires_at": int(token_payload.get("expires_at", 0) or 0),
                                "consent_hash": token_payload.get("claim_hash"),
                                "consent_source": token_payload.get("consent_source"),
                                "identity_provider": token_payload.get("identity_provider"),
                                "zk_backend": token_payload.get("zk_backend"),
                            }
                        )
                        return

                    self._send_json(
                        {
                            "ok": True,
                            "valid": False,
                            "reason": reason,
                            "expires_at": int(token_payload.get("expires_at", 0) or 0),
                            "consent_hash": token_payload.get("claim_hash"),
                            "consent_source": token_payload.get("consent_source"),
                            "identity_provider": token_payload.get("identity_provider"),
                            "zk_backend": token_payload.get("zk_backend"),
                        }
                    )
                    return

            # On-chain parity path for stateless runtime: allow status checks without
            # local /tmp records when caller provides tx metadata or when app-box
            # verification is configured.
            if claim_hash or consent_txid or SHUNYAK_APP_ID > 0:
                valid_onchain, reason, _ = verify_consent_onchain(
                    user_pubkey=user_pubkey,
                    enterprise_pubkey=enterprise_pubkey,
                    claim_hash=claim_hash or None,
                    consent_txid=consent_txid or None,
                )
                self._send_json(
                    {
                        "ok": True,
                        "valid": valid_onchain,
                        "reason": reason,
                        "expires_at": None,
                        "consent_hash": claim_hash or None,
                    }
                )
                return

            self._send_json(
                {
                    "ok": True,
                    "valid": False,
                    "reason": "no_consent_record",
                    "expires_at": None,
                    "consent_hash": None,
                }
            )
            return

        expiry_timestamp = int(record.get("expiry_timestamp", 0))
        now_ts = int(time.time())
        is_valid = expiry_timestamp >= now_ts

        tx_mode = str(record.get("tx_mode", "")).strip()
        if is_valid and tx_mode.startswith("testnet_onchain"):
            valid_onchain, reason, _ = verify_consent_onchain(
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                claim_hash=str(record.get("claim_hash", "") or "") or None,
                consent_txid=str(record.get("txid", "") or "") or None,
            )
            is_valid = valid_onchain
            onchain_reason = reason
        else:
            onchain_reason = None

        self._send_json(
            {
                "ok": True,
                "valid": is_valid,
                "reason": (
                    onchain_reason
                    if onchain_reason is not None
                    else ("consent_active" if is_valid else "consent_expired")
                ),
                "expires_at": expiry_timestamp,
                "consent_hash": record.get("consent_hash"),
                "claim_type": record.get("claim_type"),
                "consent_source": record.get("consent_source"),
                "identity_provider": record.get("identity_provider"),
                "zk_backend": record.get("zk_backend"),
                "zk_verification_mode": record.get("zk_verification_mode"),
            }
        )
