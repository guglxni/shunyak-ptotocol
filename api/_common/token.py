from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from api._common.constants import IS_DEPLOYED_ENV


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _derive_insecure_local_token_key() -> bytes:
    # Local-only fallback key material to keep isolated demos working
    # when explicit secrets are intentionally not provisioned.
    material = ":".join(
        [
            "shunyak-local-insecure-token-key",
            os.getenv("USER", "local"),
            os.getenv("HOSTNAME", "localhost"),
            os.getcwd(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).digest()


def _resolve_token_secret() -> bytes:
    configured = os.getenv("SHUNYAK_DEMO_SECRET", "").strip()
    allow_insecure = _env_bool("SHUNYAK_ALLOW_INSECURE_DEMO_SECRET", False)

    if IS_DEPLOYED_ENV:
        if not configured:
            raise RuntimeError(
                "SHUNYAK_DEMO_SECRET must be configured in deployed environments"
            )
        if configured.lower() in {"shunyak-demo-secret", "demo-secret", "changeme"}:
            raise RuntimeError(
                "SHUNYAK_DEMO_SECRET must not use placeholder values in deployed environments"
            )
        return configured.encode("utf-8")

    if configured:
        return configured.encode("utf-8")

    if allow_insecure:
        return _derive_insecure_local_token_key()

    raise RuntimeError(
        "SHUNYAK_DEMO_SECRET must be configured. "
        "Set SHUNYAK_ALLOW_INSECURE_DEMO_SECRET=true only for isolated local demos."
    )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign_payload(payload: dict[str, Any]) -> str:
    secret = _resolve_token_secret()
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)
    signature = hmac.new(secret, payload_part.encode("utf-8"), hashlib.sha256).digest()
    sig_part = _b64url_encode(signature)
    return f"{payload_part}.{sig_part}"


def _verify_payload(token: str) -> dict[str, Any] | None:
    secret = _resolve_token_secret()
    try:
        payload_part, sig_part = token.split(".", 1)
    except ValueError:
        return None

    expected = hmac.new(secret, payload_part.encode("utf-8"), hashlib.sha256).digest()
    try:
        provided = _b64url_decode(sig_part)
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(expected, provided):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_part))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def mint_consent_token(
    *,
    user_pubkey: str,
    enterprise_pubkey: str,
    expires_at: int,
    consent_txid: str | None = None,
    claim_hash: str | None = None,
    mode: str = "local",
    consent_source: str | None = None,
    app_id: int | None = None,
    identity_provider: str | None = None,
    zk_backend: str | None = None,
) -> str:
    payload = {
        "user_pubkey": user_pubkey,
        "enterprise_pubkey": enterprise_pubkey,
        "expires_at": int(expires_at),
        "iat": int(time.time()),
        "mode": mode,
        "kind": "consent",
    }
    if consent_txid:
        payload["consent_txid"] = consent_txid
    if claim_hash:
        payload["claim_hash"] = claim_hash
    if consent_source:
        payload["consent_source"] = consent_source
    if app_id and app_id > 0:
        payload["app_id"] = int(app_id)
    if identity_provider:
        payload["identity_provider"] = identity_provider
    if zk_backend:
        payload["zk_backend"] = zk_backend
    return _sign_payload(payload)


def mint_demo_operator_token(
    *,
    user_pubkey: str,
    enterprise_pubkey: str,
    endpoint_scope: str = "agent",
    ttl_seconds: int = 300,
) -> str:
    now_ts = int(time.time())
    payload = {
        "kind": "demo_operator",
        "user_pubkey": user_pubkey,
        "enterprise_pubkey": enterprise_pubkey,
        "endpoint_scope": endpoint_scope,
        "iat": now_ts,
        "expires_at": now_ts + max(30, int(ttl_seconds)),
    }
    return _sign_payload(payload)


def validate_demo_operator_token(
    token: str,
    *,
    user_pubkey: str,
    enterprise_pubkey: str,
    endpoint_name: str,
) -> bool:
    payload = _verify_payload(token)
    if payload is None:
        return False

    if payload.get("kind") != "demo_operator":
        return False
    if payload.get("user_pubkey") != user_pubkey:
        return False
    if payload.get("enterprise_pubkey") != enterprise_pubkey:
        return False

    expires_at = int(payload.get("expires_at", 0) or 0)
    if expires_at < int(time.time()):
        return False

    scope = str(payload.get("endpoint_scope", "")).strip().lower()
    if scope in {"*", "agent", "agent_all"}:
        return True
    return scope == endpoint_name.strip().lower()


def validate_consent_token(
    token: str,
    *,
    user_pubkey: str,
    enterprise_pubkey: str,
) -> dict[str, Any] | None:
    payload = _verify_payload(token)
    if payload is None:
        return None

    if payload.get("kind") not in {None, "consent"}:
        return None

    if payload.get("user_pubkey") != user_pubkey:
        return None
    if payload.get("enterprise_pubkey") != enterprise_pubkey:
        return None

    expires_at = int(payload.get("expires_at", 0) or 0)
    if expires_at < int(time.time()):
        return None

    return payload
