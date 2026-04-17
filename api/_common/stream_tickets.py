from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from api._common.constants import IS_DEPLOYED_ENV


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _derive_insecure_local_ticket_key() -> bytes:
    material = ":".join(
        [
            "shunyak-local-insecure-stream-ticket-key",
            os.getenv("USER", "local"),
            os.getenv("HOSTNAME", "localhost"),
            os.getcwd(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).digest()


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _resolve_stream_ticket_secret() -> bytes:
    configured = os.getenv("SHUNYAK_STREAM_TICKET_SECRET", "").strip()
    fallback = os.getenv("SHUNYAK_DEMO_SECRET", "").strip()
    allow_insecure = _env_bool("SHUNYAK_ALLOW_INSECURE_DEMO_SECRET", False)

    if configured:
        if IS_DEPLOYED_ENV and configured.lower() in {
            "shunyak-demo-stream-ticket-secret",
            "shunyak-demo-secret",
            "demo-secret",
            "changeme",
        }:
            raise RuntimeError(
                "SHUNYAK_STREAM_TICKET_SECRET must not use placeholder values in deployed environments"
            )
        return configured.encode("utf-8")

    if fallback:
        if IS_DEPLOYED_ENV and fallback.lower() in {
            "shunyak-demo-secret",
            "demo-secret",
            "changeme",
        }:
            raise RuntimeError(
                "SHUNYAK_DEMO_SECRET must not use placeholder values in deployed environments"
            )
        return fallback.encode("utf-8")

    if IS_DEPLOYED_ENV:
        raise RuntimeError(
            "SHUNYAK_STREAM_TICKET_SECRET (or SHUNYAK_DEMO_SECRET) must be configured in deployed environments"
        )

    if allow_insecure:
        return _derive_insecure_local_ticket_key()

    raise RuntimeError(
        "SHUNYAK_STREAM_TICKET_SECRET or SHUNYAK_DEMO_SECRET must be configured. "
        "Set SHUNYAK_ALLOW_INSECURE_DEMO_SECRET=true only for isolated local demos."
    )


def issue_stream_ticket(payload: dict[str, Any], *, ttl_seconds: int) -> tuple[str, int]:
    now_ts = int(time.time())
    expires_at = now_ts + max(ttl_seconds, 5)
    envelope = {
        "payload": payload,
        "expires_at": expires_at,
        "nonce": secrets.token_urlsafe(12),
    }
    body = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_part = _b64url_encode(body)
    secret = _resolve_stream_ticket_secret()
    signature = hmac.new(secret, body_part.encode("utf-8"), hashlib.sha256).digest()
    token = f"{body_part}.{_b64url_encode(signature)}"

    return token, expires_at


def consume_stream_ticket(token: str) -> dict[str, Any] | None:
    if not token:
        return None

    try:
        body_part, sig_part = token.split(".", 1)
    except ValueError:
        return None

    try:
        provided_signature = _b64url_decode(sig_part)
        secret = _resolve_stream_ticket_secret()
        expected_signature = hmac.new(secret, body_part.encode("utf-8"), hashlib.sha256).digest()
    except (RuntimeError, ValueError, TypeError, OSError):
        return None

    if not hmac.compare_digest(expected_signature, provided_signature):
        return None

    try:
        envelope = json.loads(_b64url_decode(body_part))
    except (ValueError, json.JSONDecodeError):
        return None

    expires_at = int(envelope.get("expires_at", 0) or 0)
    if expires_at <= int(time.time()):
        return None

    payload = envelope.get("payload")
    if isinstance(payload, dict):
        return payload
    return None
