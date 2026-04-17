from __future__ import annotations

from api._common.agent_security import guard_agent_execution_request
from api._common.http import JSONHandler
from api._common.llm import resolve_litellm_runtime_config
from agent.shunyak_agent import ShunyakAgentService


class handler(JSONHandler):
    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json_body()

        prompt = str(payload.get("prompt", "")).strip()
        user_pubkey = str(payload.get("user_pubkey", "")).strip()
        enterprise_pubkey = str(payload.get("enterprise_pubkey", "")).strip()
        try:
            amount_microalgo = int(payload.get("amount_microalgo", 1_000_000) or 1_000_000)
        except (TypeError, ValueError):
            self._send_error("amount_microalgo must be an integer", status=422)
            return
        consent_token = str(payload.get("consent_token", "")).strip() or None
        try:
            llm_config = resolve_litellm_runtime_config(payload.get("llm_config"))
        except ValueError as exc:
            self._send_error(str(exc), status=422)
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
            endpoint_name="agent_execute",
        )
        if not guard_result.ok:
            self._send_error(guard_result.error or "request_blocked", status=guard_result.status)
            return

        try:
            service = ShunyakAgentService(llm_config=llm_config)
        except Exception as exc:
            self._send_error(f"agent initialization failed: {exc}", status=503)
            return

        result = service.execute_task(
            prompt=prompt,
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            amount_microalgo=amount_microalgo,
            consent_token=consent_token,
        )

        self._send_json(result)
