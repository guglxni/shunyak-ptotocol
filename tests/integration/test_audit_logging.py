from __future__ import annotations

from api._common import audit


def test_append_audit_entry_adds_event_metadata_and_truncates_reason(
    monkeypatch,
    tmp_path,
) -> None:
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", log_path)

    long_reason = "x" * 2000
    entry = audit.append_audit_entry(
        session_id="session-1",
        event="workflow_blocked",
        tool_name="litellm_inference",
        args={"provider": "groq"},
        policy_decision="blocked",
        reason=long_reason,
        level="error",
    )

    assert entry["event_id"].startswith("audit-")
    assert entry["level"] == "error"
    assert len(entry["reason"]) < len(long_reason)
    assert entry["extra"]["reason_truncated"] is True


def test_append_audit_entry_normalizes_invalid_level(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", log_path)

    entry = audit.append_audit_entry(
        session_id="session-2",
        event="tool_allowed",
        tool_name="verify_shunyak_compliance",
        args={"user_pubkey": "abc"},
        policy_decision="allowed",
        reason="ok",
        level="unexpected",
    )

    assert entry["level"] == "info"
