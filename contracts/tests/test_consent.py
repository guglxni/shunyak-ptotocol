from __future__ import annotations

import pytest

pytest.importorskip("pyteal")

from contracts.shunyak_consent import build_contract


def _method_signatures(contract: dict) -> set[str]:
    signatures: set[str] = set()
    for method in contract.get("methods", []):
        name = str(method.get("name", "")).strip()
        args = method.get("args", [])
        arg_types = ",".join(str(arg.get("type", "")).strip() for arg in args)
        return_type = str((method.get("returns") or {}).get("type", "")).strip()
        signatures.add(f"{name}({arg_types}){return_type}")
    return signatures


def test_contract_compiles_and_exports_abi_methods() -> None:
    approval, clear, contract = build_contract(version=10)

    assert approval.strip()
    assert clear.strip()

    signatures = _method_signatures(contract)
    assert "register_consent(byte[],byte[],byte[],byte[],uint64)void" in signatures
    assert "revoke_consent(byte[],byte[])void" in signatures
    assert any(signature.startswith("check_status(byte[],byte[])") for signature in signatures)


def test_contract_metadata_name() -> None:
    _, _, contract = build_contract(version=10)
    assert contract.get("name") == "ShunyakConsent"
