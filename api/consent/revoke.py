from __future__ import annotations

import time

from api._common.algorand import revoke_consent_app_call, verify_consent_box
from api._common.audit import append_audit_entry
from api._common.constants import (
    DEFAULT_ENTERPRISE_PUBKEY,
    SHUNYAK_APP_ID,
    SHUNYAK_CONSENT_REGISTRAR_MNEMONIC,
    SHUNYAK_ENABLE_TESTNET_TX,
)
from api._common.http import JSONHandler
from api._common.store import remove_consent_record


class handler(JSONHandler):
    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json_body()

        user_pubkey = str(payload.get("user_pubkey", "")).strip().lower()
        enterprise_pubkey = str(
            payload.get("enterprise_pubkey", DEFAULT_ENTERPRISE_PUBKEY)
        ).strip().lower()

        if not user_pubkey:
            self._send_error("user_pubkey is required", status=422)
            return

        if len(user_pubkey) != 64:
            self._send_error("user_pubkey must be 64 hex chars", status=422)
            return

        if len(enterprise_pubkey) != 64:
            self._send_error("enterprise_pubkey must be 64 hex chars", status=422)
            return

        try:
            bytes.fromhex(user_pubkey)
            bytes.fromhex(enterprise_pubkey)
        except ValueError:
            self._send_error("user_pubkey and enterprise_pubkey must be valid hex", status=422)
            return

        if not SHUNYAK_ENABLE_TESTNET_TX:
            self._send_error("SHUNYAK_ENABLE_TESTNET_TX must be true in real mode", status=422)
            return

        if SHUNYAK_APP_ID <= 0:
            self._send_error("SHUNYAK_APP_ID must be configured for revoke flow", status=422)
            return

        sender_mnemonic = SHUNYAK_CONSENT_REGISTRAR_MNEMONIC
        if not sender_mnemonic:
            self._send_error(
                "SHUNYAK_CONSENT_REGISTRAR_MNEMONIC is required for revoke flow",
                status=422,
            )
            return

        try:
            onchain = revoke_consent_app_call(
                sender_mnemonic=sender_mnemonic,
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                app_id=SHUNYAK_APP_ID,
            )
        except Exception as exc:
            self._send_error(f"contract consent revoke failed: {exc}", status=502)
            return

        still_valid, reason, _ = verify_consent_box(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            claim_hash=None,
            app_id=SHUNYAK_APP_ID,
        )
        if still_valid:
            self._send_error(
                "contract revoke transaction confirmed but consent box is still active",
                status=502,
            )
            return

        removed_local = remove_consent_record(user_pubkey, enterprise_pubkey)

        session_id = f"revoke-{int(time.time())}"
        append_audit_entry(
            session_id=session_id,
            event="tool_allowed",
            tool_name="revoke_consent",
            args={"user_pubkey": user_pubkey, "enterprise_pubkey": enterprise_pubkey},
            policy_decision="allowed",
            reason=f"Consent revoked on-chain ({reason})",
            extra={
                "local_record_removed": removed_local,
                "txid": onchain.get("txid"),
            },
        )

        self._send_json(
            {
                "ok": True,
                "status": "consent_revoked",
                "txid": onchain.get("txid"),
                "explorer_url": onchain.get("explorer_url"),
                "confirmed_round": onchain.get("confirmed_round"),
                "local_record_removed": removed_local,
                "box_status": reason,
            }
        )
