from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess  # nosec B404
from typing import Any

from api._common.algorand import algod_client, sdk_showcase_snapshot, sender_address_from_mnemonic
from api._common.constants import (
    IS_DEPLOYED_ENV,
    SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY,
    SHUNYAK_ALGOPLONK_SIMULATE_ONLY,
    SHUNYAK_ALGOPLONK_VERIFY_APP_ID,
    SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE,
    SHUNYAK_APP_ID,
    SHUNYAK_CONSENT_SOURCE,
    SHUNYAK_IDENTITY_PROVIDER,
    SHUNYAK_SIGNER_BALANCE_WARN_MICROALGO,
    SHUNYAK_USDCA_ASA_ID,
    SHUNYAK_ZK_BACKEND,
)
from api._common.http import JSONHandler
from api._common.llm import resolve_litellm_runtime_config


def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return None


class handler(JSONHandler):
    def _build_payload(
        self,
        *,
        llm_config_override: Any = None,
        llm_api_key_configured_override: bool | None = None,
    ) -> dict[str, Any]:
        try:
            sdk_snapshot = sdk_showcase_snapshot()
        except Exception as exc:
            return {
                "ok": False,
                "error": "sdk_snapshot_failed",
                "detail": str(exc),
            }

        cli_available = False
        cli_path = shutil.which("algokit")
        cli_version: str | None = None
        cli_reason: str | None = None
        try:
            if not cli_path:
                raise FileNotFoundError("algokit binary not found on PATH")
            result = subprocess.run(
                [cli_path, "--version"],  # nosec B603
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                cli_available = True
                cli_version = (result.stdout or result.stderr).strip() or None
            else:
                cli_reason = (
                    (result.stderr or result.stdout).strip()
                    or f"algokit exited with status {result.returncode}"
                )
        except FileNotFoundError:
            cli_available = False
            cli_reason = (
                "AlgoKit CLI is not bundled in serverless runtime; using algokit-utils SDK checks instead"
                if IS_DEPLOYED_ENV
                else "algokit binary not found on PATH"
            )
        except (RuntimeError, ValueError, OSError) as exc:
            cli_available = False
            cli_reason = f"algokit check failed: {exc}"

        cli_status = "available"
        if not cli_available:
            if IS_DEPLOYED_ENV:
                cli_status = "not_applicable"
            else:
                cli_status = "unavailable"

        utils_available = False
        utils_version: str | None = None
        try:
            utils_version = importlib.metadata.version("algokit-utils")
            utils_available = True
        except importlib.metadata.PackageNotFoundError:
            utils_available = False

        litellm_available = False
        litellm_version: str | None = None
        try:
            litellm_version = importlib.metadata.version("litellm")
            litellm_available = True
        except importlib.metadata.PackageNotFoundError:
            litellm_available = False

        try:
            llm_payload = resolve_litellm_runtime_config(llm_config_override).public_payload()
            if llm_api_key_configured_override is not None:
                llm_payload["api_key_configured"] = bool(llm_api_key_configured_override)
        except ValueError as exc:
            llm_payload = {
                "enabled": False,
                "provider": None,
                "model": None,
                "api_base": None,
                "api_version": None,
                "api_key_configured": False,
                "error": str(exc),
            }

        sender_configured = False
        sender_address: str | None = None
        sender_balance: int | None = None
        low_balance_warning = False
        warning_message: str | None = None
        sender_mnemonic = os.getenv("SHUNYAK_AGENT_MNEMONIC", "").strip()
        if sender_mnemonic:
            sender_configured = True
            try:
                sender_address = sender_address_from_mnemonic(sender_mnemonic)
                info = algod_client().account_info(sender_address)
                sender_balance = int(info.get("amount", 0) or 0)
                low_balance_warning = sender_balance < SHUNYAK_SIGNER_BALANCE_WARN_MICROALGO
                if low_balance_warning:
                    warning_message = (
                        "Signer wallet balance is below the recommended threshold "
                        f"({SHUNYAK_SIGNER_BALANCE_WARN_MICROALGO} microALGO)."
                    )
            except Exception:
                sender_address = None
                sender_balance = None

        return {
            "ok": True,
            "sdk_snapshot": sdk_snapshot,
            "algokit": {
                "runtime": "serverless" if IS_DEPLOYED_ENV else "local",
                "cli_expected": not IS_DEPLOYED_ENV,
                "cli_status": cli_status,
                "cli_available": cli_available,
                "cli_version": cli_version,
                "cli_path": cli_path,
                "cli_reason": cli_reason,
                "utils_available": utils_available,
                "utils_version": utils_version,
            },
            "sender_account": {
                "configured": sender_configured,
                "address": sender_address,
                "balance_microalgo": sender_balance,
                "warning_threshold_microalgo": SHUNYAK_SIGNER_BALANCE_WARN_MICROALGO,
                "low_balance_warning": low_balance_warning,
                "warning_message": warning_message,
            },
            "consent_engine": {
                "source_mode": SHUNYAK_CONSENT_SOURCE,
                "app_id": SHUNYAK_APP_ID if SHUNYAK_APP_ID > 0 else None,
            },
            "identity_engine": {
                "provider": SHUNYAK_IDENTITY_PROVIDER,
                "digilocker_configured": bool(
                    os.getenv("SHUNYAK_DIGILOCKER_CLIENT_ID", "").strip()
                    and os.getenv("SHUNYAK_DIGILOCKER_CLIENT_SECRET", "").strip()
                    and os.getenv("SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID", "").strip()
                ),
            },
            "zk_engine": {
                "backend": SHUNYAK_ZK_BACKEND,
                "verify_app_id": (
                    SHUNYAK_ALGOPLONK_VERIFY_APP_ID if SHUNYAK_ALGOPLONK_VERIFY_APP_ID > 0 else None
                ),
                "verify_method": SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE,
                "onchain_required": SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY,
                "simulate_only": SHUNYAK_ALGOPLONK_SIMULATE_ONLY,
            },
            "settlement_engine": {
                "asset_id": SHUNYAK_USDCA_ASA_ID if SHUNYAK_USDCA_ASA_ID > 0 else None,
                "asset_mode": "asa" if SHUNYAK_USDCA_ASA_ID > 0 else "algo",
            },
            "llm_engine": {
                **llm_payload,
                "litellm_installed": litellm_available,
                "litellm_version": litellm_version,
            },
        }

    def do_GET(self) -> None:  # noqa: N802
        payload = self._build_payload()
        status = 200 if payload.get("ok") else 500
        self._send_json(payload, status=status)

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_json_body()
        payload = self._build_payload(
            llm_config_override=body.get("llm_config"),
            llm_api_key_configured_override=_coerce_optional_bool(body.get("llm_api_key_configured")),
        )
        status = 200 if payload.get("ok") else 500
        self._send_json(payload, status=status)
