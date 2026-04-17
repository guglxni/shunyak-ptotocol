from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent.dolios_bridge import load_dolios_components
from agent.mcp_server import CapabilityPolicyError, MCPToolExecutionError, ShunyakMCPServer
from agent.tools.dlp_guard import scan_tool_args
from api._common.audit import append_audit_entry, read_audit_entries
from api._common.llm import LiteLLMRuntimeConfig, resolve_litellm_runtime_config


CALLBACK_EXCEPTIONS = (
    BrokenPipeError,
    ConnectionError,
    RuntimeError,
    ValueError,
    TypeError,
    OSError,
)


@dataclass(frozen=True)
class AgentRuntimeFailure:
    code: str
    phase: str
    detail: str

    def reason(self) -> str:
        return f"{self.code}:{self.detail}"


class ShunyakAgentService:
    """Consent-gated execution service using Dolios hardened primitives where available."""

    def __init__(self, *, llm_config: LiteLLMRuntimeConfig | None = None) -> None:
        components = load_dolios_components()
        self._source = components["source"]
        self._config_cls = components["config_cls"]
        self._vault_cls = components["vault_cls"]
        self._workflow_policy_cls = components["workflow_policy_cls"]

        self.session_id = f"shunyak-{uuid.uuid4().hex[:12]}"

        self.config = self._load_config()
        self._llm_config = llm_config or resolve_litellm_runtime_config(None)
        self._configure_dolios_inference()
        self.workflow = self._workflow_policy_cls(self.config)

        self.vault = self._vault_cls()
        mnemonic_key = "SHUNYAK_AGENT_MNEMONIC"
        if os.getenv(mnemonic_key):
            self.vault.load_from_env(mnemonic_key, label=mnemonic_key)

        self.mcp = ShunyakMCPServer()

    def _configure_dolios_inference(self) -> None:
        if not self._llm_config.enabled:
            return
        if not hasattr(self.config, "inference"):
            return
        inference = getattr(self.config, "inference")
        if not hasattr(inference, "providers"):
            return

        providers = getattr(inference, "providers")
        if not isinstance(providers, dict):
            return

        provider_profile = self._llm_config.dolios_provider_profile()
        merged_profile = dict(providers.get(self._llm_config.provider, {}))
        merged_profile.update(provider_profile)
        providers[self._llm_config.provider] = merged_profile

        setattr(inference, "providers", providers)
        if hasattr(inference, "default_provider"):
            setattr(inference, "default_provider", self._llm_config.provider)
        if hasattr(inference, "default_model"):
            setattr(inference, "default_model", self._llm_config.model)

        os.environ["DOLIOS_INFERENCE_PROVIDER"] = self._llm_config.provider
        os.environ["DOLIOS_INFERENCE_MODEL"] = self._llm_config.model
        if self._llm_config.api_base:
            os.environ["OPENAI_API_BASE"] = self._llm_config.api_base
            os.environ["OPENAI_BASE_URL"] = self._llm_config.api_base
        if self._llm_config.api_version:
            os.environ["OPENAI_API_VERSION"] = self._llm_config.api_version
        if self._llm_config.api_key:
            os.environ["OPENAI_API_KEY"] = self._llm_config.api_key

    def _load_config(self) -> Any:
        cfg = self._config_cls.load(Path.cwd())

        workflow_file = os.getenv("SHUNYAK_WORKFLOW_POLICY_FILE", "policies/workflow.yaml")
        if hasattr(cfg, "workflow"):
            setattr(cfg.workflow, "enabled", True)
            setattr(cfg.workflow, "policy_file", workflow_file)

        return cfg

    def execute_task(
        self,
        *,
        prompt: str,
        user_pubkey: str,
        enterprise_pubkey: str,
        amount_microalgo: int,
        consent_token: str | None = None,
        event_callback: Callable[[dict[str, str]], None] | None = None,
    ) -> dict[str, Any]:
        self.workflow.reset_session(self.session_id)

        events: list[dict[str, str]] = []
        callback_errors: list[dict[str, str]] = []

        def emit_event(kind: str, phase: str, message: str) -> None:
            event = {
                "kind": kind,
                "phase": phase,
                "message": message,
            }
            events.append(event)
            if event_callback is not None:
                try:
                    event_callback(event)
                except CALLBACK_EXCEPTIONS as exc:
                    # Streaming callback errors must not break core execution.
                    callback_errors.append(
                        {
                            "code": "event_callback_delivery_failed",
                            "phase": phase,
                            "detail": str(exc),
                        }
                    )

        emit_event("info", "startup", f"Dolios runtime source: {self._source}")
        emit_event("info", "task", f"Task received: {prompt}")

        verify_allowed, verify_reason = self.workflow.check(
            self.session_id, "verify_shunyak_compliance"
        )
        if not verify_allowed:
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="verify_shunyak_compliance",
                args={"user_pubkey": user_pubkey, "enterprise_pubkey": enterprise_pubkey},
                policy_decision="blocked",
                reason=verify_reason,
            )
            emit_event("error", "workflow", verify_reason)
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "Workflow blocked before compliance check",
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
            }

        verify_args = {
            "user_pubkey": user_pubkey,
            "enterprise_pubkey": enterprise_pubkey,
            "consent_token_present": bool(consent_token),
        }
        verify_dlp_allowed, verify_dlp_reason = scan_tool_args(
            "verify_shunyak_compliance",
            verify_args,
        )
        if not verify_dlp_allowed:
            append_audit_entry(
                session_id=self.session_id,
                event="dlp_blocked",
                tool_name="verify_shunyak_compliance",
                args=verify_args,
                policy_decision="blocked",
                reason=verify_dlp_reason,
            )
            emit_event(
                "error",
                "dlp",
                f"DLP Compliance Failure before compliance check: {verify_dlp_reason}",
            )
            return {
                "ok": True,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "DLP Compliance Failure",
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
            }

        try:
            compliance = self.mcp.call(
                "verify_shunyak_compliance",
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                consent_token=consent_token,
            )
        except CapabilityPolicyError as exc:
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="verify_shunyak_compliance",
                args=verify_args,
                policy_decision="blocked",
                reason=f"capability_policy_failed:{exc}",
            )
            emit_event(
                "error",
                "capability",
                f"Capability policy blocked verify_shunyak_compliance: {exc}",
            )
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "Capability policy blocked compliance verification",
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
            }
        except MCPToolExecutionError as exc:
            failure = AgentRuntimeFailure(
                code="verify_tool_runtime_error",
                phase="compliance",
                detail=f"{exc.code}:{exc.detail}",
            )
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="verify_shunyak_compliance",
                args=verify_args,
                policy_decision="blocked",
                reason=failure.reason(),
            )
            emit_event("error", failure.phase, "Compliance verification execution failed")
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "Compliance verification execution failed",
                "error_code": failure.code,
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
                "telemetry": {"event_callback_errors": callback_errors},
            }

        append_audit_entry(
            session_id=self.session_id,
            event="tool_allowed",
            tool_name="verify_shunyak_compliance",
            args=verify_args,
            policy_decision="allowed",
            reason=compliance["reason"],
        )

        self.workflow.record_outcome(
            self.session_id,
            "verify_shunyak_compliance",
            success=bool(compliance["valid"]),
        )

        emit_event(
            "success" if compliance["valid"] else "error",
            "compliance",
            "Compliance valid"
            if compliance["valid"]
            else f"Compliance failure: {compliance['reason']}",
        )

        if not compliance["valid"]:
            if self._llm_config.enabled:
                emit_event(
                    "info",
                    "llm",
                    "Dolios inference skipped because consent compliance failed",
                )
            settle_allowed, settle_reason = self.workflow.check(
                self.session_id, "execute_algo_settlement"
            )
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="execute_algo_settlement",
                args={"user_pubkey": user_pubkey, "enterprise_pubkey": enterprise_pubkey},
                policy_decision="blocked",
                reason=settle_reason if not settle_allowed else "compliance_not_valid",
            )

            emit_event("error", "settlement", "DPDP Compliance Failure. Settlement blocked.")

            return {
                "ok": True,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "DPDP Compliance Failure",
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
                "telemetry": {"event_callback_errors": callback_errors},
            }

        if self._llm_config.enabled:
            emit_event(
                "info",
                "llm",
                (
                    "Dolios inference route configured: "
                    f"{self._llm_config.provider}/{self._llm_config.model}"
                ),
            )
        else:
            emit_event("info", "llm", "Dolios inference route: runtime defaults")

        settle_allowed, settle_reason = self.workflow.check(
            self.session_id, "execute_algo_settlement"
        )
        if not settle_allowed:
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="execute_algo_settlement",
                args={"user_pubkey": user_pubkey, "enterprise_pubkey": enterprise_pubkey},
                policy_decision="blocked",
                reason=settle_reason,
            )
            emit_event("error", "workflow", settle_reason)
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "Workflow prevented settlement",
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
                "telemetry": {"event_callback_errors": callback_errors},
            }

        settlement_args = {
            "recipient_address": user_pubkey,
            "amount_microalgo": amount_microalgo,
            "memo": "shunyak-micro-loan",
        }
        settlement_dlp_allowed, settlement_dlp_reason = scan_tool_args(
            "execute_algo_settlement",
            settlement_args,
        )
        if not settlement_dlp_allowed:
            append_audit_entry(
                session_id=self.session_id,
                event="dlp_blocked",
                tool_name="execute_algo_settlement",
                args=settlement_args,
                policy_decision="blocked",
                reason=settlement_dlp_reason,
            )
            emit_event(
                "error",
                "dlp",
                f"DLP Compliance Failure before settlement: {settlement_dlp_reason}",
            )
            return {
                "ok": True,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "DLP Compliance Failure",
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
                "telemetry": {"event_callback_errors": callback_errors},
            }

        if hasattr(self.vault, "has") and self.vault.has("SHUNYAK_AGENT_MNEMONIC"):
            append_audit_entry(
                session_id=self.session_id,
                event="credential_injected",
                tool_name="execute_algo_settlement",
                args={"recipient_address": user_pubkey},
                policy_decision="injected",
                reason="CredentialVault injected SHUNYAK_AGENT_MNEMONIC at execution boundary",
                extra={"label": "SHUNYAK_AGENT_MNEMONIC"},
            )

        try:
            settlement = self.mcp.call(
                "execute_algo_settlement",
                recipient_address=user_pubkey,
                amount_microalgo=amount_microalgo,
                memo=settlement_args["memo"],
                vault=self.vault,
            )
        except CapabilityPolicyError as exc:
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="execute_algo_settlement",
                args=settlement_args,
                policy_decision="blocked",
                reason=f"capability_policy_failed:{exc}",
            )
            emit_event(
                "error",
                "capability",
                f"Capability policy blocked execute_algo_settlement: {exc}",
            )
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "Capability policy blocked settlement",
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
            }
        except MCPToolExecutionError as exc:
            failure = AgentRuntimeFailure(
                code="settlement_tool_runtime_error",
                phase="settlement",
                detail=f"{exc.code}:{exc.detail}",
            )
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="execute_algo_settlement",
                args=settlement_args,
                policy_decision="blocked",
                reason=failure.reason(),
            )
            emit_event("error", failure.phase, "Settlement execution failed")
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "Settlement execution failed",
                "error_code": failure.code,
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
                "telemetry": {"event_callback_errors": callback_errors},
            }
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            failure = AgentRuntimeFailure(
                code="settlement_runtime_error",
                phase="settlement",
                detail=str(exc),
            )
            append_audit_entry(
                session_id=self.session_id,
                event="workflow_blocked",
                tool_name="execute_algo_settlement",
                args=settlement_args,
                policy_decision="blocked",
                reason=failure.reason(),
            )
            emit_event("error", failure.phase, "Settlement execution failed")
            return {
                "ok": False,
                "session_id": self.session_id,
                "status": "blocked",
                "outcome_message": "Settlement execution failed",
                "error_code": failure.code,
                "events": events,
                "audit_entries": read_audit_entries(limit=8),
                "telemetry": {"event_callback_errors": callback_errors},
            }

        append_audit_entry(
            session_id=self.session_id,
            event="tool_allowed",
            tool_name="execute_algo_settlement",
            args=settlement_args,
            policy_decision="allowed",
            reason="Workflow dependency satisfied and settlement executed",
        )

        self.workflow.record_outcome(
            self.session_id,
            "execute_algo_settlement",
            success=True,
        )

        emit_event(
            "success",
            "settlement",
            f"Settlement broadcast ({settlement.get('mode', 'unknown')}): {settlement['txid']}",
        )

        return {
            "ok": True,
            "session_id": self.session_id,
            "status": "authorized",
            "outcome_message": "Micro-loan disbursed",
            "events": events,
            "settlement": settlement,
            "audit_entries": read_audit_entries(limit=8),
            "telemetry": {"event_callback_errors": callback_errors},
        }
