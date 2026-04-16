from __future__ import annotations

from api._common.audit import read_audit_entries
from api._common.http import JSONHandler


class handler(JSONHandler):
    def do_GET(self) -> None:  # noqa: N802
        query = self._query()
        raw_limit = "".join(query.get("limit", []))
        try:
            limit = max(1, min(100, int(raw_limit))) if raw_limit else 20
        except ValueError:
            limit = 20

        items = read_audit_entries(limit=limit)
        self._send_json({"ok": True, "items": items})
