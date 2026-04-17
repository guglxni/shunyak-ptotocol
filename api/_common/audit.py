from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api._common.constants import AUDIT_LOG_PATH

_LOCK = threading.Lock()
_MAX_REASON_LEN = 800
_VALID_LEVELS = {"info", "warning", "error"}
_LOGGER = logging.getLogger("shunyak.audit")
if not _LOGGER.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(_handler)
    _LOGGER.propagate = False
_LOGGER.setLevel(logging.INFO)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def args_hash(args: dict[str, Any]) -> str:
    payload = json.dumps(args, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_reason(reason: str) -> tuple[str, bool]:
    compact = " ".join(reason.split())
    if len(compact) <= _MAX_REASON_LEN:
        return compact, False
    return f"{compact[:_MAX_REASON_LEN]}…", True


def append_audit_entry(
    *,
    session_id: str,
    event: str,
    tool_name: str,
    args: dict[str, Any],
    policy_decision: str,
    reason: str,
    extra: dict[str, Any] | None = None,
    level: str = "info",
) -> dict[str, Any]:
    normalized_reason, reason_truncated = _normalize_reason(reason)
    normalized_level = level if level in _VALID_LEVELS else "info"
    normalized_extra = dict(extra or {})
    if reason_truncated:
        normalized_extra["reason_truncated"] = True
    entry: dict[str, Any] = {
        "event_id": f"audit-{uuid.uuid4().hex[:12]}",
        "ts": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "level": normalized_level,
        "event": event,
        "tool_name": tool_name,
        "args_hash": args_hash(args),
        "policy_decision": policy_decision,
        "reason": normalized_reason,
    }
    if normalized_extra:
        entry["extra"] = normalized_extra

    _ensure_parent(AUDIT_LOG_PATH)
    line = json.dumps(entry, default=str)
    with _LOCK:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    _LOGGER.info(line)

    return entry


def read_audit_entries(limit: int = 20) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.exists():
        return []

    with _LOCK:
        lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()

    parsed: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(parsed) >= limit:
            break

    return parsed
