from __future__ import annotations

import importlib.metadata
import os
import subprocess

from api._common.algorand import algod_client, sdk_showcase_snapshot, sender_address_from_mnemonic
from api._common.constants import (
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


class handler(JSONHandler):
    def do_GET(self) -> None:  # noqa: N802
        try:
            sdk_snapshot = sdk_showcase_snapshot()
        except Exception as exc:
            self._send_json(
                {
                    "ok": False,
                    "error": "sdk_snapshot_failed",
                    "detail": str(exc),
                },
                status=500,
            )
            return

        cli_available = False
        cli_version: str | None = None
        try:
            result = subprocess.run(
                ["algokit", "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                cli_available = True
                cli_version = (result.stdout or result.stderr).strip() or None
        except Exception:
            cli_available = False

        utils_available = False
        utils_version: str | None = None
        try:
            utils_version = importlib.metadata.version("algokit-utils")
            utils_available = True
        except importlib.metadata.PackageNotFoundError:
            utils_available = False

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

        self._send_json(
            {
                "ok": True,
                "sdk_snapshot": sdk_snapshot,
                "algokit": {
                    "cli_available": cli_available,
                    "cli_version": cli_version,
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
            }
        )
