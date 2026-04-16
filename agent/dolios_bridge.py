from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _is_deployed_environment() -> bool:
    vercel_env = os.getenv("VERCEL_ENV", "").strip().lower()
    return os.getenv("VERCEL", "").strip() == "1" or vercel_env in {
        "preview",
        "production",
    }


def _require_hardened_runtime() -> bool:
    raw = os.getenv("SHUNYAK_REQUIRE_HARDENED")
    if raw is None:
        return _is_deployed_environment()
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap_dolios_path() -> None:
    root = Path(__file__).resolve().parent.parent
    dolios_path = root / "external" / "dolios-agent"
    if dolios_path.exists() and str(dolios_path) not in sys.path:
        sys.path.insert(0, str(dolios_path))


@dataclass
class FallbackWorkflowConfig:
    enabled: bool = True
    policy_file: str = "policies/workflow.yaml"


@dataclass
class FallbackConfig:
    workflow: FallbackWorkflowConfig = field(default_factory=FallbackWorkflowConfig)

    @classmethod
    def load(cls, project_dir: Path | None = None) -> "FallbackConfig":
        _ = project_dir
        cfg = cls()
        policy_override = os.getenv("SHUNYAK_WORKFLOW_POLICY_FILE")
        if policy_override:
            cfg.workflow.policy_file = policy_override
        return cfg


class FallbackCredentialVault:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def load_from_env(self, key_name: str, label: str) -> None:
        if _is_deployed_environment():
            raise RuntimeError(
                "Fallback credential vault is not permitted in deployed environments"
            )
        value = os.getenv(key_name, "")
        self._store[label] = value
        # Keep process env intact so warm serverless invocations can continue
        # loading credentials on subsequent requests.

    def inject(self, label: str) -> str:
        if label not in self._store:
            raise KeyError(f"No credential loaded for label: {label}")
        return self._store[label]

    def has(self, label: str) -> bool:
        return label in self._store and bool(self._store[label])


class FallbackWorkflowPolicy:
    def __init__(self, config: FallbackConfig) -> None:
        self._enabled = config.workflow.enabled
        self._rules: dict[str, list[dict[str, str]]] = {}
        self._sessions: dict[str, dict[str, bool]] = {}

        policy_path = Path(config.workflow.policy_file)
        if policy_path.exists():
            import yaml

            data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
            for entry in data.get("policies", []):
                tool = entry.get("tool")
                if tool:
                    self._rules[tool] = entry.get("requires", [])

    def reset_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def record_outcome(self, session_id: str, tool_name: str, *, success: bool) -> None:
        self._sessions.setdefault(session_id, {})[tool_name] = success

    def check(self, session_id: str, tool_name: str) -> tuple[bool, str]:
        if not self._enabled:
            return True, ""

        requirements = self._rules.get(tool_name, [])
        session_state = self._sessions.get(session_id, {})

        for requirement in requirements:
            dep_tool = requirement.get("tool", "")
            required_status = requirement.get("status", "success")
            dep_success = session_state.get(dep_tool)
            if dep_success is None:
                return (
                    False,
                    f"Tool '{tool_name}' requires '{dep_tool}' to run first (status={required_status})",
                )
            if required_status == "success" and dep_success is not True:
                return (
                    False,
                    f"Tool '{tool_name}' requires '{dep_tool}' to have succeeded",
                )

        return True, ""


def load_dolios_components() -> dict[str, Any]:
    _bootstrap_dolios_path()

    try:
        from dolios.config import DoliosConfig
        from dolios.security.vault import CredentialVault
        from dolios.security.workflow import WorkflowPolicy

        return {
            "config_cls": DoliosConfig,
            "vault_cls": CredentialVault,
            "workflow_policy_cls": WorkflowPolicy,
            "source": "dolios-hardened",
        }
    except Exception as exc:
        require_hardened = _require_hardened_runtime()
        if require_hardened:
            raise RuntimeError(
                "SHUNYAK_REQUIRE_HARDENED is enabled, but dolios-hardened runtime failed to load"
            ) from exc
        return {
            "config_cls": FallbackConfig,
            "vault_cls": FallbackCredentialVault,
            "workflow_policy_cls": FallbackWorkflowPolicy,
            "source": "fallback",
        }
