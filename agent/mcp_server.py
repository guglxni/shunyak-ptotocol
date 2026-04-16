from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import yaml

from agent.tools.execute_settlement import CAPABILITIES as SETTLEMENT_CAPABILITIES
from agent.tools.execute_settlement import execute_algo_settlement
from agent.tools.verify_compliance import CAPABILITIES as VERIFY_CAPABILITIES
from agent.tools.verify_compliance import verify_shunyak_compliance
from api._common.constants import ALGOD_SERVER, INDEXER_SERVER


Tool = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ToolRegistration:
    func: Tool
    capabilities: dict[str, Any]


class CapabilityPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class MCPToolExecutionError(RuntimeError):
    tool_name: str
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.tool_name}:{self.code}:{self.detail}"


class ShunyakMCPServer:
    """In-process tool registry matching the two-tool Shunyak demo contract."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {
            "verify_shunyak_compliance": ToolRegistration(
                func=verify_shunyak_compliance,
                capabilities=VERIFY_CAPABILITIES,
            ),
            "execute_algo_settlement": ToolRegistration(
                func=execute_algo_settlement,
                capabilities=SETTLEMENT_CAPABILITIES,
            ),
        }
        self._manifest = self._load_capability_manifest()

    @staticmethod
    def _hostname(value: str) -> str:
        parsed = urlparse(value)
        if parsed.hostname:
            return parsed.hostname.lower()
        return value.strip().split("/")[0].lower()

    @staticmethod
    def _as_set(values: list[Any] | tuple[Any, ...] | None) -> set[str]:
        if not values:
            return set()
        return {
            str(value).strip().lower()
            for value in values
            if str(value).strip()
        }

    def _load_capability_manifest(self) -> dict[str, Any]:
        path = Path(__file__).resolve().parent / "skills" / "shunyak-compliance" / "capabilities.yaml"
        if not path.exists():
            return {}
        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _enforce_capabilities(self, tool_name: str, registration: ToolRegistration) -> None:
        capabilities = registration.capabilities
        network = capabilities.get("network") if isinstance(capabilities, dict) else {}
        filesystem = capabilities.get("filesystem") if isinstance(capabilities, dict) else {}
        dlp_allowed = capabilities.get("dlp_allowed") if isinstance(capabilities, dict) else []

        allowed_domains = self._as_set((network or {}).get("allow_domains", []))
        if not allowed_domains:
            raise CapabilityPolicyError(f"{tool_name} has no allowed network domains")

        fs_read = self._as_set((filesystem or {}).get("read", []))
        fs_write = self._as_set((filesystem or {}).get("write", []))
        if fs_read or fs_write:
            raise CapabilityPolicyError(
                f"{tool_name} requested filesystem access outside Shunyak policy"
            )

        if not isinstance(dlp_allowed, list):
            raise CapabilityPolicyError(f"{tool_name} has invalid dlp_allowed capability type")

        manifest_domains = self._as_set(
            (((self._manifest.get("network") if isinstance(self._manifest, dict) else {}) or {}).get("allow_domains", []))
        )
        if manifest_domains and not allowed_domains.issubset(manifest_domains):
            extra = sorted(allowed_domains - manifest_domains)
            raise CapabilityPolicyError(
                f"{tool_name} allows domains not in manifest: {', '.join(extra)}"
            )

        required_domains = {self._hostname(ALGOD_SERVER)}
        if tool_name == "verify_shunyak_compliance":
            required_domains.add(self._hostname(INDEXER_SERVER))

        if not required_domains.issubset(allowed_domains):
            missing = sorted(required_domains - allowed_domains)
            raise CapabilityPolicyError(
                f"{tool_name} capability policy missing runtime hosts: {', '.join(missing)}"
            )

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def call(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        if tool_name not in self._tools:
            raise KeyError(f"Unknown MCP tool: {tool_name}")
        registration = self._tools[tool_name]
        self._enforce_capabilities(tool_name, registration)
        try:
            return registration.func(**kwargs)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise MCPToolExecutionError(
                tool_name=tool_name,
                code="tool_runtime_error",
                detail=str(exc),
            ) from exc
