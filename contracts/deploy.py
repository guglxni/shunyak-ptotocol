from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any

from algosdk import account, encoding, logic, mnemonic, transaction
from algosdk.v2client.algod import AlgodClient

from api._common.constants import ALGOD_SERVER, ALGOD_TOKEN
from contracts.shunyak_consent import build_contract, write_contract_artifacts


def _algod_client() -> AlgodClient:
    return AlgodClient(ALGOD_TOKEN, ALGOD_SERVER)


def _resolve_deployer_mnemonic() -> str:
    deployer = os.getenv("SHUNYAK_DEPLOYER_MNEMONIC", "").strip()
    if deployer:
        return deployer

    fallback = os.getenv("SHUNYAK_AGENT_MNEMONIC", "").strip()
    if fallback:
        return fallback

    raise RuntimeError(
        "Set SHUNYAK_DEPLOYER_MNEMONIC (or SHUNYAK_AGENT_MNEMONIC) before deploying"
    )


def _resolve_registrar_address(*, default_address: str) -> str:
    configured_address = os.getenv("SHUNYAK_CONSENT_REGISTRAR_ADDRESS", "").strip()
    if configured_address:
        if not encoding.is_valid_address(configured_address):
            raise RuntimeError("SHUNYAK_CONSENT_REGISTRAR_ADDRESS must be a valid Algorand address")
        return configured_address

    registrar_mnemonic = os.getenv("SHUNYAK_CONSENT_REGISTRAR_MNEMONIC", "").strip()
    if registrar_mnemonic:
        registrar_private_key = mnemonic.to_private_key(registrar_mnemonic)
        return account.address_from_private_key(registrar_private_key)

    return default_address


def _compile_program(client: AlgodClient, teal_source: str) -> bytes:
    compiled = client.compile(teal_source)
    result_b64 = str(compiled.get("result", "")).strip()
    if not result_b64:
        raise RuntimeError("Algod compile response did not include result bytes")
    return base64.b64decode(result_b64)


def deploy_contract(
    *,
    output_dir: Path,
    version: int = 10,
    extra_pages: int = 0,
) -> dict[str, Any]:
    deployer_mnemonic = _resolve_deployer_mnemonic()
    private_key = mnemonic.to_private_key(deployer_mnemonic)
    sender = account.address_from_private_key(private_key)
    registrar_address = _resolve_registrar_address(default_address=sender)

    approval_teal, clear_teal, contract = build_contract(version=version)
    artifacts = write_contract_artifacts(output_dir, version=version)

    client = _algod_client()
    approval_program = _compile_program(client, approval_teal)
    clear_program = _compile_program(client, clear_teal)

    params = client.suggested_params()
    create_txn = transaction.ApplicationCreateTxn(
        sender=sender,
        sp=params,
        on_complete=transaction.OnComplete.NoOpOC.real,
        approval_program=approval_program,
        clear_program=clear_program,
        global_schema=transaction.StateSchema(num_uints=0, num_byte_slices=1),
        local_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        extra_pages=extra_pages,
        app_args=[],
    )

    signed = create_txn.sign(private_key)
    txid = client.send_transaction(signed)
    confirmed = transaction.wait_for_confirmation(client, txid, 10)

    app_id = int(confirmed.get("application-index", 0) or 0)
    if app_id <= 0:
        raise RuntimeError("Deployment transaction confirmed but application-index is missing")

    app_address = logic.get_application_address(app_id)
    app_fund_microalgo = int(
        os.getenv("SHUNYAK_APP_MIN_BALANCE_FUND_MICROALGO", "1000000") or "1000000"
    )
    app_fund_txid = None
    app_fund_round = 0
    if app_fund_microalgo > 0:
        fund_txn = transaction.PaymentTxn(
            sender=sender,
            sp=client.suggested_params(),
            receiver=app_address,
            amt=app_fund_microalgo,
            note=b"shunyak-app-min-balance",
        )
        signed_fund = fund_txn.sign(private_key)
        app_fund_txid = client.send_transaction(signed_fund)
        fund_confirmed = transaction.wait_for_confirmation(client, app_fund_txid, 10)
        app_fund_round = int(fund_confirmed.get("confirmed-round", 0) or 0)

    result = {
        "txid": txid,
        "app_id": app_id,
        "app_address": app_address,
        "sender": sender,
        "registrar_address": registrar_address,
        "app_fund_microalgo": app_fund_microalgo,
        "app_fund_txid": app_fund_txid,
        "app_fund_confirmed_round": app_fund_round,
        "algod_server": ALGOD_SERVER,
        "contract_methods": [method.get("name") for method in contract.get("methods", [])],
        "artifacts": {name: str(path) for name, path in artifacts.items()},
    }

    result_path = output_dir / "deployment-result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    result["result_path"] = str(result_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy Shunyak consent app to Algorand")
    parser.add_argument(
        "--output-dir",
        default="contracts/artifacts",
        help="Directory to write contract and deployment artifacts",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=10,
        help="TEAL version for compilation",
    )
    parser.add_argument(
        "--extra-pages",
        type=int,
        default=0,
        help="Extra app pages for large programs",
    )
    parser.add_argument(
        "--write-artifacts-only",
        action="store_true",
        help="Only write TEAL/ARC32 artifacts without submitting a deploy transaction",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()

    if args.write_artifacts_only:
        generated = write_contract_artifacts(output_dir, version=args.version)
        print("Contract artifacts generated:")
        for name, path in generated.items():
            print(f"- {name}: {path}")
        return

    result = deploy_contract(
        output_dir=output_dir,
        version=args.version,
        extra_pages=args.extra_pages,
    )

    print("Deployment successful")
    print(f"- APP_ID: {result['app_id']}")
    print(f"- APP_ADDRESS: {result['app_address']}")
    print(f"- TXID: {result['txid']}")
    print(f"- RESULT: {result['result_path']}")


if __name__ == "__main__":
    main()
