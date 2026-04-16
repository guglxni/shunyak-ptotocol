from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from api._common.constants import (
    SHUNYAK_DIGILOCKER_BASE_URL,
    SHUNYAK_DIGILOCKER_CLIENT_ID,
    SHUNYAK_DIGILOCKER_CLIENT_SECRET,
    SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID,
    SHUNYAK_DIGILOCKER_REDIRECT_URL,
    SHUNYAK_DIGILOCKER_TIMEOUT_SECONDS,
)


class DigiLockerConfigError(RuntimeError):
    """Raised when DigiLocker credentials are missing."""


class DigiLockerAPIError(RuntimeError):
    """Raised when DigiLocker API requests fail."""


AUTHENTICATED_STATUSES = {"authenticated", "success"}


def digilocker_is_configured() -> bool:
    return all(
        [
            SHUNYAK_DIGILOCKER_CLIENT_ID,
            SHUNYAK_DIGILOCKER_CLIENT_SECRET,
            SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID,
        ]
    )


def _headers() -> dict[str, str]:
    if not digilocker_is_configured():
        raise DigiLockerConfigError(
            "DigiLocker is not configured. Set SHUNYAK_DIGILOCKER_CLIENT_ID, "
            "SHUNYAK_DIGILOCKER_CLIENT_SECRET, and SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID."
        )

    return {
        "x-client-id": SHUNYAK_DIGILOCKER_CLIENT_ID,
        "x-client-secret": SHUNYAK_DIGILOCKER_CLIENT_SECRET,
        "x-product-instance-id": SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID,
        "Content-Type": "application/json",
    }


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or "unknown_error"

    for key in ("error", "message", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return str(payload)


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{SHUNYAK_DIGILOCKER_BASE_URL.rstrip('/')}{path}"
    try:
        response = httpx.request(
            method=method,
            url=url,
            headers=_headers(),
            json=payload,
            timeout=SHUNYAK_DIGILOCKER_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise DigiLockerAPIError(f"DigiLocker request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        raise DigiLockerAPIError(
            f"DigiLocker API error ({response.status_code}) on {path}: {detail}"
        )

    try:
        parsed = response.json()
    except ValueError as exc:
        raise DigiLockerAPIError("DigiLocker returned non-JSON response") from exc

    if not isinstance(parsed, dict):
        raise DigiLockerAPIError("DigiLocker returned unexpected payload shape")

    return parsed


def create_digilocker_request(redirect_url: str | None = None) -> dict[str, Any]:
    redirect = (redirect_url or SHUNYAK_DIGILOCKER_REDIRECT_URL).strip() or SHUNYAK_DIGILOCKER_REDIRECT_URL
    return _request("POST", "/api/digilocker", payload={"redirectUrl": redirect})


def get_digilocker_status(request_id: str) -> dict[str, Any]:
    if not request_id.strip():
        raise DigiLockerAPIError("request_id is required to fetch DigiLocker status")
    return _request("GET", f"/api/digilocker/{request_id.strip()}/status")


def revoke_digilocker(request_id: str) -> dict[str, Any]:
    if not request_id.strip():
        raise DigiLockerAPIError("request_id is required to revoke DigiLocker request")
    path = f"/api/digilocker/{request_id.strip()}/revoke"
    # Setu quickstart documents this as GET, but older integrations may use POST.
    try:
        return _request("GET", path)
    except DigiLockerAPIError as exc:
        if "(405)" not in str(exc):
            raise
        return _request("POST", path)


def get_digilocker_aadhaar(request_id: str) -> dict[str, Any]:
    if not request_id.strip():
        raise DigiLockerAPIError("request_id is required to fetch Aadhaar data")
    return _request("GET", f"/api/digilocker/{request_id.strip()}/aadhaar")


def digilocker_status_value(status_payload: dict[str, Any]) -> str:
    return str(status_payload.get("status", "")).strip().lower() or "unknown"


def is_digilocker_authenticated(status_payload: dict[str, Any]) -> bool:
    return digilocker_status_value(status_payload) in AUTHENTICATED_STATUSES


def _parse_dob(date_text: str) -> datetime | None:
    normalized = (date_text or "").strip()
    if not normalized:
        return None

    for pattern in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(normalized, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _age_years(dob: datetime, at: datetime) -> int:
    years = at.year - dob.year
    if (at.month, at.day) < (dob.month, dob.day):
        years -= 1
    return years


def extract_claim_from_aadhaar(
    aadhaar_payload: dict[str, Any],
    claim_type: str,
    *,
    now_ts: int | None = None,
) -> tuple[bool, str]:
    aadhaar = aadhaar_payload.get("aadhaar")
    if not isinstance(aadhaar, dict):
        return False, "aadhaar_payload_missing"

    if claim_type == "indian_citizen":
        address = aadhaar.get("address") if isinstance(aadhaar.get("address"), dict) else {}
        country = str(address.get("country", "")).strip().lower()
        is_indian = country in {"india", "in", "bharat"}
        return is_indian, "aadhaar_country_check"

    if claim_type == "age_over_18":
        dob_text = str(aadhaar.get("dateOfBirth", "")).strip()
        dob = _parse_dob(dob_text)
        if dob is None:
            return False, "aadhaar_dob_missing_or_invalid"

        at = datetime.fromtimestamp(now_ts, tz=UTC) if now_ts is not None else datetime.now(UTC)
        age = _age_years(dob, at)
        return age >= 18, "aadhaar_dob_age_check"

    return False, "unsupported_claim_type"
