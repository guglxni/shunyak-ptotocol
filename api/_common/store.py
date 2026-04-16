from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from api._common.constants import CONSENT_STORE_PATH

_LOCK = threading.Lock()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_store() -> dict[str, Any]:
    _ensure_parent(CONSENT_STORE_PATH)
    if not CONSENT_STORE_PATH.exists():
        return {"records": {}}

    with CONSENT_STORE_PATH.open("r", encoding="utf-8") as fp:
        try:
            payload = json.load(fp)
        except json.JSONDecodeError:
            return {"records": {}}

    if not isinstance(payload, dict):
        return {"records": {}}

    payload.setdefault("records", {})
    return payload


def _save_store(payload: dict[str, Any]) -> None:
    _ensure_parent(CONSENT_STORE_PATH)
    with CONSENT_STORE_PATH.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, sort_keys=True)


def to_pubkey_hex(seed: str) -> str:
    # Deterministic MVP mapping: utf-8 bytes to hex, padded/truncated to 32 bytes.
    return seed.encode("utf-8").hex()[:64].ljust(64, "0")


def consent_key(user_pubkey: str, enterprise_pubkey: str) -> str:
    return f"{user_pubkey}:{enterprise_pubkey}"


def hash_claim(user_id: str, claim_type: str, enterprise_pubkey: str) -> str:
    payload = f"{user_id}:{claim_type}:{enterprise_pubkey}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_mock_proof(claim_hash: str, oracle_private_key_hex: str) -> str:
    payload = f"{claim_hash}:{oracle_private_key_hex}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_txid(seed: dict[str, Any]) -> str:
    encoded = json.dumps(seed, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(encoded + str(time.time_ns()).encode("utf-8")).hexdigest()
    return digest[:52]


def register_consent_record(record: dict[str, Any]) -> None:
    key = consent_key(record["user_pubkey"], record["enterprise_pubkey"])
    with _LOCK:
        payload = _load_store()
        payload["records"][key] = record
        _save_store(payload)


def get_consent_record(user_pubkey: str, enterprise_pubkey: str) -> dict[str, Any] | None:
    key = consent_key(user_pubkey, enterprise_pubkey)
    with _LOCK:
        payload = _load_store()
        return payload["records"].get(key)


def remove_consent_record(user_pubkey: str, enterprise_pubkey: str) -> bool:
    key = consent_key(user_pubkey, enterprise_pubkey)
    with _LOCK:
        payload = _load_store()
        if key not in payload["records"]:
            return False
        payload["records"].pop(key, None)
        _save_store(payload)
        return True


def has_active_consent(user_pubkey: str, enterprise_pubkey: str, now_ts: int | None = None) -> bool:
    now = now_ts if now_ts is not None else int(time.time())
    record = get_consent_record(user_pubkey, enterprise_pubkey)
    if not record:
        return False
    return int(record.get("expiry_timestamp", 0)) >= now


def list_consents() -> list[dict[str, Any]]:
    with _LOCK:
        payload = _load_store()
        return list(payload["records"].values())
