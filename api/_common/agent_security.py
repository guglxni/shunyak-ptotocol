from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from http.client import HTTPMessage

from api._common.constants import (
    SHUNYAK_MAX_SETTLEMENT_MICROALGO,
    SHUNYAK_OPERATOR_TOKEN,
    SHUNYAK_RATE_LIMIT_MAX_PER_USER,
    SHUNYAK_RATE_LIMIT_MAX_REQUESTS,
    SHUNYAK_RATE_LIMIT_SPEND_MICROALGO,
    SHUNYAK_RATE_LIMIT_WINDOW_SECONDS,
    SHUNYAK_REQUIRE_EXECUTION_TOKEN,
    SHUNYAK_REQUIRE_OPERATOR_AUTH,
)
from api._common.token import validate_demo_operator_token


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    status: int
    error: str | None = None


_LOCK = threading.Lock()
_REQUEST_WINDOWS: dict[str, deque[int]] = defaultdict(deque)
_SPEND_WINDOWS: dict[str, deque[tuple[int, int]]] = defaultdict(deque)


def _extract_client_ip(headers: HTTPMessage, fallback: str) -> str:
    forwarded = headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    return fallback.strip() or "unknown"


def _extract_operator_token(headers: HTTPMessage) -> str:
    authz = headers.get("authorization", "").strip()
    if authz.lower().startswith("bearer "):
        return authz[7:].strip()
    return headers.get("x-shunyak-operator-token", "").strip()


def _prune_count_window(window: deque[int], now_ts: int, window_seconds: int) -> None:
    boundary = now_ts - window_seconds
    while window and window[0] <= boundary:
        window.popleft()


def _prune_spend_window(window: deque[tuple[int, int]], now_ts: int, window_seconds: int) -> None:
    boundary = now_ts - window_seconds
    while window and window[0][0] <= boundary:
        window.popleft()


def _check_count_limit(key: str, now_ts: int, limit: int, window_seconds: int) -> bool:
    window = _REQUEST_WINDOWS[key]
    _prune_count_window(window, now_ts, window_seconds)
    if len(window) >= limit:
        return False
    window.append(now_ts)
    return True


def _check_spend_limit(
    key: str,
    *,
    now_ts: int,
    amount_microalgo: int,
    limit_microalgo: int,
    window_seconds: int,
) -> bool:
    window = _SPEND_WINDOWS[key]
    _prune_spend_window(window, now_ts, window_seconds)
    current_total = sum(entry_amount for _, entry_amount in window)
    if current_total + amount_microalgo > limit_microalgo:
        return False
    window.append((now_ts, amount_microalgo))
    return True


def guard_agent_execution_request(
    *,
    headers: HTTPMessage,
    fallback_client_ip: str,
    user_pubkey: str,
    enterprise_pubkey: str,
    amount_microalgo: int,
    consent_token: str | None,
    endpoint_name: str,
) -> GuardResult:
    operator_token = _extract_operator_token(headers)

    demo_operator_token_valid = False
    if operator_token:
        try:
            demo_operator_token_valid = validate_demo_operator_token(
                operator_token,
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                endpoint_name=endpoint_name,
            )
        except RuntimeError:
            demo_operator_token_valid = False

    static_operator_token_valid = bool(
        SHUNYAK_OPERATOR_TOKEN
        and operator_token
        and hmac.compare_digest(operator_token, SHUNYAK_OPERATOR_TOKEN)
    )

    if SHUNYAK_REQUIRE_OPERATOR_AUTH:
        if not SHUNYAK_OPERATOR_TOKEN:
            if demo_operator_token_valid:
                pass
            else:
                return GuardResult(
                    ok=False,
                    status=503,
                    error="operator_auth_required_but_token_not_configured",
                )
        elif not (static_operator_token_valid or demo_operator_token_valid):
            return GuardResult(
                ok=False,
                status=401,
                error="unauthorized_operator",
            )
    elif SHUNYAK_OPERATOR_TOKEN and operator_token:
        # If an operator token is supplied, it must still be correct.
        if not (static_operator_token_valid or demo_operator_token_valid):
            return GuardResult(ok=False, status=401, error="invalid_operator_token")

    if SHUNYAK_REQUIRE_EXECUTION_TOKEN and not (consent_token or "").strip():
        return GuardResult(ok=False, status=401, error="consent_token_required")

    if amount_microalgo <= 0:
        return GuardResult(ok=False, status=422, error="amount_microalgo_must_be_positive")

    if amount_microalgo > SHUNYAK_MAX_SETTLEMENT_MICROALGO:
        return GuardResult(
            ok=False,
            status=422,
            error=f"amount_microalgo_exceeds_max:{SHUNYAK_MAX_SETTLEMENT_MICROALGO}",
        )

    client_ip = _extract_client_ip(headers, fallback_client_ip)
    now_ts = int(time.time())

    request_scope = f"{endpoint_name}:ip:{client_ip}"
    user_scope = f"{endpoint_name}:user:{user_pubkey}"
    spend_scope = f"{endpoint_name}:spend:{user_pubkey}:{enterprise_pubkey}"

    with _LOCK:
        if not _check_count_limit(
            request_scope,
            now_ts,
            SHUNYAK_RATE_LIMIT_MAX_REQUESTS,
            SHUNYAK_RATE_LIMIT_WINDOW_SECONDS,
        ):
            return GuardResult(ok=False, status=429, error="rate_limit_ip_exceeded")

        if not _check_count_limit(
            user_scope,
            now_ts,
            SHUNYAK_RATE_LIMIT_MAX_PER_USER,
            SHUNYAK_RATE_LIMIT_WINDOW_SECONDS,
        ):
            return GuardResult(ok=False, status=429, error="rate_limit_user_exceeded")

        if not _check_spend_limit(
            spend_scope,
            now_ts=now_ts,
            amount_microalgo=amount_microalgo,
            limit_microalgo=SHUNYAK_RATE_LIMIT_SPEND_MICROALGO,
            window_seconds=SHUNYAK_RATE_LIMIT_WINDOW_SECONDS,
        ):
            return GuardResult(ok=False, status=429, error="spend_limit_window_exceeded")

    return GuardResult(ok=True, status=200, error=None)
