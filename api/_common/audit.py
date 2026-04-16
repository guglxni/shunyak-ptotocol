from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api._common.constants import AUDIT_LOG_PATH

_LOCK = threading.Lock()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def args_hash(args: dict[str, Any]) -> str:
    payload = json.dumps(args, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def append_audit_entry(
    *,
    session_id: str,
    event: str,
    tool_name: str,
    args: dict[str, Any],
    policy_decision: str,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "event": event,
        "tool_name": tool_name,
        "args_hash": args_hash(args),
        "policy_decision": policy_decision,
        "reason": reason,
    }
    if extra:
        entry["extra"] = extra

    _ensure_parent(AUDIT_LOG_PATH)
    line = json.dumps(entry, default=str)
    with _LOCK:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")

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
