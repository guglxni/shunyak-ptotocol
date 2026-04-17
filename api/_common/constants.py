from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    from algosdk import account, encoding, mnemonic
except Exception:  # pragma: no cover - best-effort helper import
    account = None
    encoding = None
    mnemonic = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    values: list[str] = []
    for part in raw.split(","):
        item = part.strip()
        if item:
            values.append(item)
    return values


def _pubkey_hex_from_mnemonic(seed_phrase: str) -> str | None:
    if not seed_phrase or account is None or encoding is None or mnemonic is None:
        return None
    try:
        private_key = mnemonic.to_private_key(seed_phrase)
        address = account.address_from_private_key(private_key)
        return encoding.decode_address(address).hex()
    except Exception:
        return None


def _normalize_public_base_url(raw: str) -> str:
    candidate = raw.strip()
    if not candidate:
        return ""

    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _default_digilocker_redirect_url() -> str:
    for raw_base in (
        os.getenv("SHUNYAK_PUBLIC_BASE_URL", ""),
        os.getenv("VERCEL_PROJECT_PRODUCTION_URL", ""),
        os.getenv("VERCEL_URL", ""),
    ):
        normalized = _normalize_public_base_url(raw_base)
        if normalized:
            return f"{normalized}/consent"

    return "http://localhost:3000/consent"


def _runtime_file_path(env_name: str, filename: str) -> Path:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return Path(configured)
    runtime_dir = Path(tempfile.gettempdir()) / "shunyak-runtime"
    return runtime_dir / filename


_VERCEL_ENV = os.getenv("VERCEL_ENV", "").strip().lower()
IS_DEPLOYED_ENV = os.getenv("VERCEL", "").strip() == "1" or _VERCEL_ENV in {
    "preview",
    "production",
}

SHUNYAK_ALLOWED_ORIGINS = tuple(_env_csv("SHUNYAK_ALLOWED_ORIGINS"))
SHUNYAK_OPERATOR_TOKEN = os.getenv("SHUNYAK_OPERATOR_TOKEN", "").strip()
SHUNYAK_REQUIRE_OPERATOR_AUTH = _env_bool("SHUNYAK_REQUIRE_OPERATOR_AUTH", IS_DEPLOYED_ENV)
SHUNYAK_REQUIRE_EXECUTION_TOKEN = _env_bool("SHUNYAK_REQUIRE_EXECUTION_TOKEN", IS_DEPLOYED_ENV)
SHUNYAK_MAX_SETTLEMENT_MICROALGO = int(
    os.getenv("SHUNYAK_MAX_SETTLEMENT_MICROALGO", "5000000") or "5000000"
)
SHUNYAK_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("SHUNYAK_RATE_LIMIT_WINDOW_SECONDS", "60") or "60"
)
SHUNYAK_RATE_LIMIT_MAX_REQUESTS = int(
    os.getenv("SHUNYAK_RATE_LIMIT_MAX_REQUESTS", "20") or "20"
)
SHUNYAK_RATE_LIMIT_MAX_PER_USER = int(
    os.getenv("SHUNYAK_RATE_LIMIT_MAX_PER_USER", "8") or "8"
)
SHUNYAK_RATE_LIMIT_SPEND_MICROALGO = int(
    os.getenv("SHUNYAK_RATE_LIMIT_SPEND_MICROALGO", "20000000") or "20000000"
)
SHUNYAK_STREAM_TICKET_TTL_SECONDS = int(
    os.getenv("SHUNYAK_STREAM_TICKET_TTL_SECONDS", "90") or "90"
)

ALGOD_SERVER = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
ALGOD_TOKEN = os.getenv("ALGOD_TOKEN", "")
INDEXER_SERVER = os.getenv("INDEXER_SERVER", "https://testnet-idx.algonode.cloud")
INDEXER_TOKEN = os.getenv("INDEXER_TOKEN", "")
SHUNYAK_APP_ID = int(os.getenv("SHUNYAK_APP_ID", "0") or "0")
SHUNYAK_CONSENT_SOURCE = os.getenv("SHUNYAK_CONSENT_SOURCE", "hybrid").strip().lower() or "hybrid"
SHUNYAK_IDENTITY_PROVIDER = os.getenv("SHUNYAK_IDENTITY_PROVIDER", "digilocker").strip().lower() or "digilocker"
SHUNYAK_ZK_BACKEND = os.getenv("SHUNYAK_ZK_BACKEND", "algoplonk").strip().lower() or "algoplonk"
SHUNYAK_ENABLE_TESTNET_TX = _env_bool("SHUNYAK_ENABLE_TESTNET_TX", True)
SHUNYAK_USDCA_ASA_ID = int(os.getenv("SHUNYAK_USDCA_ASA_ID", "0") or "0")
SHUNYAK_SIGNER_BALANCE_WARN_MICROALGO = int(
    os.getenv("SHUNYAK_SIGNER_BALANCE_WARN_MICROALGO", "1000000") or "1000000"
)
SHUNYAK_REQUIRE_HARDENED = _env_bool("SHUNYAK_REQUIRE_HARDENED", IS_DEPLOYED_ENV)
SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK = _env_bool(
    "SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK",
    not IS_DEPLOYED_ENV,
)

SHUNYAK_DIGILOCKER_BASE_URL = (
    os.getenv("SHUNYAK_DIGILOCKER_BASE_URL", "https://dg-sandbox.setu.co").strip()
    or "https://dg-sandbox.setu.co"
)
SHUNYAK_DIGILOCKER_REDIRECT_URL = (
    os.getenv("SHUNYAK_DIGILOCKER_REDIRECT_URL", _default_digilocker_redirect_url()).strip()
    or _default_digilocker_redirect_url()
)
SHUNYAK_DIGILOCKER_CLIENT_ID = os.getenv("SHUNYAK_DIGILOCKER_CLIENT_ID", "").strip()
SHUNYAK_DIGILOCKER_CLIENT_SECRET = os.getenv("SHUNYAK_DIGILOCKER_CLIENT_SECRET", "").strip()
SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID = os.getenv("SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID", "").strip()
SHUNYAK_DIGILOCKER_TIMEOUT_SECONDS = float(
    os.getenv("SHUNYAK_DIGILOCKER_TIMEOUT_SECONDS", "15") or "15"
)

SHUNYAK_ALGOPLONK_VERIFY_APP_ID = int(os.getenv("SHUNYAK_ALGOPLONK_VERIFY_APP_ID", "0") or "0")
SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE = (
    os.getenv("SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE", "verify(byte[32][],byte[32][])bool").strip()
    or "verify(byte[32][],byte[32][])bool"
)
SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY = _env_bool(
    "SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY",
    IS_DEPLOYED_ENV,
)
SHUNYAK_ALGOPLONK_SIMULATE_ONLY = _env_bool("SHUNYAK_ALGOPLONK_SIMULATE_ONLY", False)

SHUNYAK_CONSENT_REGISTRAR_MNEMONIC = (
    os.getenv("SHUNYAK_CONSENT_REGISTRAR_MNEMONIC", "").strip()
    or os.getenv("SHUNYAK_AGENT_MNEMONIC", "").strip()
)

SHUNYAK_CONSENT_REGISTER_METHOD_SIGNATURE = (
    os.getenv(
        "SHUNYAK_CONSENT_REGISTER_METHOD_SIGNATURE",
        "register_consent(byte[],byte[],byte[],byte[],uint64)void",
    ).strip()
    or "register_consent(byte[],byte[],byte[],byte[],uint64)void"
)
SHUNYAK_CONSENT_REVOKE_METHOD_SIGNATURE = (
    os.getenv(
        "SHUNYAK_CONSENT_REVOKE_METHOD_SIGNATURE",
        "revoke_consent(byte[],byte[])void",
    ).strip()
    or "revoke_consent(byte[],byte[])void"
)
SHUNYAK_CONSENT_REQUIRE_BOX_PARITY = _env_bool(
    "SHUNYAK_CONSENT_REQUIRE_BOX_PARITY",
    SHUNYAK_APP_ID > 0,
)

CONSENT_STORE_PATH = _runtime_file_path("SHUNYAK_CONSENT_STORE", "consent-store.json")
AUDIT_LOG_PATH = _runtime_file_path("DOLIOS_AUDIT_LOG", "audit.jsonl")

TESTNET_EXPLORER_TX_BASE = os.getenv(
    "ALGORAND_EXPLORER_TX_BASE", "https://lora.algokit.io/testnet/transaction/"
)

_FALLBACK_ENTERPRISE_PUBKEY = "7368756e79616b2d656e74657270726973650000000000000000000000000000"
_DERIVED_ENTERPRISE_PUBKEY = _pubkey_hex_from_mnemonic(SHUNYAK_CONSENT_REGISTRAR_MNEMONIC or "")

DEFAULT_ENTERPRISE_PUBKEY = os.getenv(
    "SHUNYAK_ENTERPRISE_PUBKEY",
    _DERIVED_ENTERPRISE_PUBKEY or _FALLBACK_ENTERPRISE_PUBKEY,
)
