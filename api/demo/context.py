from __future__ import annotations

import os
import time
from typing import Any

from api._common.algorand import verify_consent_onchain
from api._common.constants import (
    DEFAULT_ENTERPRISE_PUBKEY,
    SHUNYAK_APP_ID,
    SHUNYAK_DIGILOCKER_REDIRECT_URL,
    SHUNYAK_IDENTITY_PROVIDER,
    SHUNYAK_REQUIRE_EXECUTION_TOKEN,
    SHUNYAK_REQUIRE_OPERATOR_AUTH,
    SHUNYAK_ZK_BACKEND,
)
from api._common.http import JSONHandler
from api._common.llm import resolve_litellm_runtime_config
from api._common.store import hash_claim, to_pubkey_hex
from api._common.token import mint_consent_token, mint_demo_operator_token


def _build_blocked_context(
    *,
    enterprise_pubkey: str,
    claim_type: str,
    now_ts: int,
    token_warnings: list[str],
) -> dict[str, Any]:
    blocked_user_id = os.getenv("SHUNYAK_DEMO_BLOCKED_USER_ID", "demo-user-999").strip() or "demo-user-999"
    user_pubkey = to_pubkey_hex(blocked_user_id)

    consent_token: str | None = None
    operator_token: str | None = None

    try:
        consent_token = mint_consent_token(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            expires_at=now_ts + 15 * 60,
            consent_txid=f"demo-blocked-{now_ts}",
            claim_hash=hash_claim(blocked_user_id, claim_type, enterprise_pubkey),
            mode="testnet_onchain_contract",
            consent_source="app_box",
            app_id=SHUNYAK_APP_ID if SHUNYAK_APP_ID > 0 else None,
            identity_provider=SHUNYAK_IDENTITY_PROVIDER,
            zk_backend=SHUNYAK_ZK_BACKEND,
        )
    except RuntimeError as exc:
        token_warnings.append(f"blocked_consent_token_unavailable:{exc}")

    try:
        operator_token = mint_demo_operator_token(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            endpoint_scope="agent",
            ttl_seconds=15 * 60,
        )
    except RuntimeError as exc:
        token_warnings.append(f"blocked_operator_token_unavailable:{exc}")

    ready = True
    if SHUNYAK_REQUIRE_EXECUTION_TOKEN and not consent_token:
        ready = False
    if SHUNYAK_REQUIRE_OPERATOR_AUTH and not operator_token:
        ready = False

    return {
        "user_id": blocked_user_id,
        "user_pubkey": user_pubkey,
        "enterprise_pubkey": enterprise_pubkey,
        "prompt": "Process financial history for user-999 and issue micro-loan",
        "consent_token": consent_token,
        "operator_token": operator_token,
        "ready": ready,
        "reason": "demo_blocked_context_ready" if ready else "demo_blocked_context_incomplete",
    }


def _build_authorized_context(
    *,
    enterprise_pubkey: str,
    claim_type: str,
    now_ts: int,
    token_warnings: list[str],
) -> dict[str, Any]:
    authorized_user_id = os.getenv("SHUNYAK_DEMO_AUTHORIZED_USER_ID", "demo-user-001").strip() or "demo-user-001"
    user_pubkey = to_pubkey_hex(authorized_user_id)

    consent_token: str | None = None
    operator_token: str | None = None

    onchain_valid = False
    onchain_reason = "consent_not_checked"
    onchain_meta: dict[str, Any] | None = None
    try:
        onchain_valid, onchain_reason, onchain_meta = verify_consent_onchain(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            claim_hash=None,
            consent_txid=None,
        )
    except Exception as exc:  # pragma: no cover - defensive for network/runtime errors
        onchain_valid = False
        onchain_reason = f"consent_check_failed:{exc}"

    expires_at = now_ts + 15 * 60
    claim_hash = hash_claim(authorized_user_id, claim_type, enterprise_pubkey)
    if isinstance(onchain_meta, dict):
        expires_at = int(onchain_meta.get("expiry_timestamp", expires_at) or expires_at)
        claim_hash = str(onchain_meta.get("consent_hash", claim_hash) or claim_hash)

    if onchain_valid:
        try:
            consent_token = mint_consent_token(
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                expires_at=expires_at,
                claim_hash=claim_hash,
                mode="testnet_onchain_contract",
                consent_source="app_box",
                app_id=SHUNYAK_APP_ID if SHUNYAK_APP_ID > 0 else None,
                identity_provider=SHUNYAK_IDENTITY_PROVIDER,
                zk_backend=SHUNYAK_ZK_BACKEND,
            )
        except RuntimeError as exc:
            token_warnings.append(f"authorized_consent_token_unavailable:{exc}")

    try:
        operator_token = mint_demo_operator_token(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            endpoint_scope="agent",
            ttl_seconds=15 * 60,
        )
    except RuntimeError as exc:
        token_warnings.append(f"authorized_operator_token_unavailable:{exc}")

    ready = onchain_valid
    if SHUNYAK_REQUIRE_EXECUTION_TOKEN and not consent_token:
        ready = False
    if SHUNYAK_REQUIRE_OPERATOR_AUTH and not operator_token:
        ready = False

    return {
        "user_id": authorized_user_id,
        "user_pubkey": user_pubkey,
        "enterprise_pubkey": enterprise_pubkey,
        "prompt": "Process financial history for demo-user-001 and issue micro-loan",
        "consent_token": consent_token,
        "operator_token": operator_token,
        "onchain_valid": onchain_valid,
        "onchain_reason": onchain_reason,
        "ready": ready,
        "reason": "demo_authorized_context_ready" if ready else "demo_authorized_context_incomplete",
    }


class handler(JSONHandler):
    def do_GET(self) -> None:  # noqa: N802
        now_ts = int(time.time())
        claim_type = "age_over_18"
        enterprise_pubkey = DEFAULT_ENTERPRISE_PUBKEY
        default_user_id = os.getenv("SHUNYAK_DEMO_CONSENT_USER_ID", "demo-user-001").strip() or "demo-user-001"

        token_warnings: list[str] = []
        llm_payload: dict[str, Any]
        try:
            llm_payload = resolve_litellm_runtime_config(None).public_payload()
        except ValueError as exc:
            llm_payload = {
                "enabled": False,
                "provider": None,
                "model": None,
                "api_base": None,
                "api_version": None,
                "api_key_configured": False,
                "error": str(exc),
            }

        blocked = _build_blocked_context(
            enterprise_pubkey=enterprise_pubkey,
            claim_type=claim_type,
            now_ts=now_ts,
            token_warnings=token_warnings,
        )
        authorized = _build_authorized_context(
            enterprise_pubkey=enterprise_pubkey,
            claim_type=claim_type,
            now_ts=now_ts,
            token_warnings=token_warnings,
        )

        self._send_json(
            {
                "ok": True,
                "generated_at": now_ts,
                "requirements": {
                    "operator_auth_required": SHUNYAK_REQUIRE_OPERATOR_AUTH,
                    "execution_token_required": SHUNYAK_REQUIRE_EXECUTION_TOKEN,
                    "app_id": SHUNYAK_APP_ID if SHUNYAK_APP_ID > 0 else None,
                    "identity_provider": SHUNYAK_IDENTITY_PROVIDER,
                    "zk_backend": SHUNYAK_ZK_BACKEND,
                    "llm_byok_supported": True,
                },
                "llm_defaults": llm_payload,
                "consent": {
                    "user_id": default_user_id,
                    "claim_type": claim_type,
                    "enterprise_pubkey": enterprise_pubkey,
                    "identity_provider": SHUNYAK_IDENTITY_PROVIDER,
                    "zk_backend": SHUNYAK_ZK_BACKEND,
                    "digilocker_redirect_url": SHUNYAK_DIGILOCKER_REDIRECT_URL,
                    "algoplonk_autofill_enabled": True,
                },
                "blocked": blocked,
                "authorized": authorized,
                "token_warnings": token_warnings,
            }
        )
