from __future__ import annotations

import json
from typing import Any

from agent.shunyak_agent import ShunyakAgentService
from api._common.agent_security import guard_agent_execution_request
from api._common.constants import SHUNYAK_STREAM_TICKET_TTL_SECONDS
from api._common.http import JSONHandler
from api._common.llm import resolve_litellm_runtime_config
from api._common.stream_tickets import consume_stream_ticket, issue_stream_ticket


class handler(JSONHandler):
    def _set_sse_headers(self) -> bool:
        allowed_origin = self._resolve_cors_origin()
        if self._origin_requested() and not allowed_origin:
            self.send_response(403)
            self.end_headers()
            return False

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Shunyak-Operator-Token",
        )
        self.end_headers()
        return True

    def _emit_sse(self, payload: dict[str, Any]) -> None:
        frame = f"data: {json.dumps(payload, default=str)}\n\n"
        self.wfile.write(frame.encode("utf-8"))
        self.wfile.flush()

    def _safe_emit_sse(self, payload: dict[str, Any]) -> bool:
        try:
            self._emit_sse(payload)
            return True
        except BrokenPipeError:
            return False
        except (RuntimeError, ValueError, TypeError, OSError):
            return False

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json_body()

        prompt = str(payload.get("prompt", "")).strip()
        user_pubkey = str(payload.get("user_pubkey", "")).strip()
        enterprise_pubkey = str(payload.get("enterprise_pubkey", "")).strip()
        consent_token = str(payload.get("consent_token", "")).strip() or None
        try:
            llm_config = resolve_litellm_runtime_config(payload.get("llm_config"))
        except ValueError as exc:
            self._send_error(str(exc), status=422)
            return
        if llm_config.enabled and llm_config.api_key:
            self._send_error(
                "llm_config.api_key is not supported on stream endpoint; use /api/agent/execute",
                status=422,
            )
            return

        try:
            amount_microalgo = int(payload.get("amount_microalgo", 1_000_000) or 1_000_000)
        except (TypeError, ValueError):
            self._send_error("amount_microalgo must be an integer", status=422)
            return

        if not prompt:
            self._send_error("prompt is required", status=422)
            return
        if not user_pubkey:
            self._send_error("user_pubkey is required", status=422)
            return
        if not enterprise_pubkey:
            self._send_error("enterprise_pubkey is required", status=422)
            return

        guard_result = guard_agent_execution_request(
            headers=self.headers,
            fallback_client_ip=self.client_address[0] if self.client_address else "",
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            amount_microalgo=amount_microalgo,
            consent_token=consent_token,
            endpoint_name="agent_stream",
        )
        if not guard_result.ok:
            self._send_error(guard_result.error or "request_blocked", status=guard_result.status)
            return

        stream_token, expires_at = issue_stream_ticket(
            {
                "prompt": prompt,
                "user_pubkey": user_pubkey,
                "enterprise_pubkey": enterprise_pubkey,
                "consent_token": consent_token,
                "amount_microalgo": amount_microalgo,
                "llm_config": llm_config.public_payload(),
            },
            ttl_seconds=SHUNYAK_STREAM_TICKET_TTL_SECONDS,
        )
        self._send_json(
            {
                "ok": True,
                "stream_token": stream_token,
                "expires_at": expires_at,
                "ttl_seconds": SHUNYAK_STREAM_TICKET_TTL_SECONDS,
            }
        )

    def do_GET(self) -> None:  # noqa: N802
        query = self._query()
        stream_token = "".join(query.get("stream_token", [])).strip()

        if "".join(query.get("consent_token", [])).strip():
            self._send_error("consent_token_in_query_is_not_allowed", status=422)
            return

        if not stream_token:
            self._send_error("stream_token query param is required", status=422)
            return

        payload = consume_stream_ticket(stream_token)
        if not payload:
            self._send_error("stream_token_invalid_or_expired", status=422)
            return

        prompt = str(payload.get("prompt", "")).strip()
        user_pubkey = str(payload.get("user_pubkey", "")).strip()
        enterprise_pubkey = str(payload.get("enterprise_pubkey", "")).strip()
        consent_token = str(payload.get("consent_token", "")).strip() or None
        amount_microalgo = int(payload.get("amount_microalgo", 1_000_000) or 1_000_000)
        try:
            llm_config = resolve_litellm_runtime_config(payload.get("llm_config"))
        except ValueError as exc:
            self._send_error(str(exc), status=422)
            return

        try:
            if not self._set_sse_headers():
                return

            def on_event(event: dict[str, str]) -> None:
                self._emit_sse({"type": "event", "event": event})

            service = ShunyakAgentService(llm_config=llm_config)
            result = service.execute_task(
                prompt=prompt,
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                amount_microalgo=amount_microalgo,
                consent_token=consent_token,
                event_callback=on_event,
            )

            self._emit_sse({"type": "final", "result": result})
        except BrokenPipeError:
            return
        except (RuntimeError, ValueError) as exc:
            self._safe_emit_sse({"type": "error", "error": str(exc)})
        except Exception:
            self._safe_emit_sse({"type": "error", "error": "stream_execution_failed"})
