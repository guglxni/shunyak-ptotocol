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

_DEFAULT_STREAM_TICKET_SECRET = "shunyak-demo-stream-ticket-secret"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _resolve_stream_ticket_secret() -> bytes:
    configured = os.getenv("SHUNYAK_STREAM_TICKET_SECRET", "").strip()
    fallback = os.getenv("SHUNYAK_DEMO_SECRET", "").strip()

    if configured:
        if IS_DEPLOYED_ENV and configured == _DEFAULT_STREAM_TICKET_SECRET:
            raise RuntimeError(
                "SHUNYAK_STREAM_TICKET_SECRET must not use the default value in deployed environments"
            )
        return configured.encode("utf-8")

    if fallback:
        return fallback.encode("utf-8")

    if IS_DEPLOYED_ENV:
        raise RuntimeError(
            "SHUNYAK_STREAM_TICKET_SECRET (or SHUNYAK_DEMO_SECRET) must be configured in deployed environments"
        )

    return _DEFAULT_STREAM_TICKET_SECRET.encode("utf-8")


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
