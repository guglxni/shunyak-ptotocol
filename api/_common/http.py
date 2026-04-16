from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from api._common.constants import IS_DEPLOYED_ENV, SHUNYAK_ALLOWED_ORIGINS


class JSONHandler(BaseHTTPRequestHandler):
    def _origin_requested(self) -> bool:
        return bool(self.headers.get("Origin", "").strip())

    def _resolve_cors_origin(self) -> str | None:
        origin = self.headers.get("Origin", "").strip()
        if SHUNYAK_ALLOWED_ORIGINS:
            if origin and origin in SHUNYAK_ALLOWED_ORIGINS:
                return origin
            return None

        if IS_DEPLOYED_ENV:
            # Fail closed for deployed env unless allowlist is explicitly configured.
            return None

        # Local/dev convenience: preserve permissive behavior.
        return "*"

    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        allowed_origin = self._resolve_cors_origin()
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            if allowed_origin != "*":
                self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Shunyak-Operator-Token",
        )
        self.end_headers()

    def _send_json(self, payload: dict, status: int = 200) -> None:
        self._set_headers(status=status)
        self.wfile.write(json.dumps(payload, default=str).encode("utf-8"))

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"ok": False, "error": message}, status=status)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}

        raw = self.rfile.read(content_length)
        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _query(self) -> dict[str, list[str]]:
        query = urlparse(self.path).query
        return parse_qs(query)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self._origin_requested() and not self._resolve_cors_origin():
            self.send_response(403)
            self.end_headers()
            return
        self._set_headers(status=204)
