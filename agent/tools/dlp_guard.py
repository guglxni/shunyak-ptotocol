from __future__ import annotations

import re
from typing import Any


_AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

_SENSITIVE_KEYWORDS = (
    "mnemonic",
    "private_key",
    "privatekey",
    "seed",
    "secret",
    "passphrase",
    "api_key",
    "token",
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def scan_tool_args(tool_name: str, payload: dict[str, Any]) -> tuple[bool, str]:
    for raw_key, raw_value in payload.items():
        key = str(raw_key).lower()
        value = _stringify(raw_value).strip()
        if not value:
            continue

        normalized = value.upper()
        if _AADHAAR_RE.search(value):
            return False, f"{tool_name}:aadhaar_pattern_detected"
        if _PAN_RE.search(normalized):
            return False, f"{tool_name}:pan_pattern_detected"
        if _PRIVATE_KEY_RE.search(value):
            return False, f"{tool_name}:private_key_blocked"

        if any(keyword in key for keyword in _SENSITIVE_KEYWORDS):
            if value.lower() not in {"true", "false", "none", "null", "0"}:
                return False, f"{tool_name}:sensitive_field_blocked:{key}"

        words = [word for word in re.split(r"\s+", value) if word]
        if 20 <= len(words) <= 30 and all(word.isalpha() for word in words):
            return False, f"{tool_name}:possible_mnemonic_phrase"

    return True, ""
