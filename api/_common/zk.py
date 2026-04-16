from __future__ import annotations

import hashlib
from typing import Any

from algosdk import abi, account, mnemonic
from algosdk.atomic_transaction_composer import AccountTransactionSigner, AtomicTransactionComposer

from api._common.algorand import algod_client


def generate_mock_p256_proof(public_inputs_hex: str, oracle_private_key_hex: str) -> str:
    seed = f"{public_inputs_hex.lower()}:{oracle_private_key_hex.lower()}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


def verify_mock_p256_proof(
    proof_hex: str,
    public_inputs_hex: str,
    oracle_private_key_hex: str,
) -> bool:
    expected = generate_mock_p256_proof(public_inputs_hex, oracle_private_key_hex)
    return expected == proof_hex.lower()


def _hex_to_bytes(value: str, field_name: str) -> bytes:
    normalized = value.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]

    if not normalized:
        raise ValueError(f"{field_name} must be non-empty hex")

    if len(normalized) % 2 != 0:
        raise ValueError(f"{field_name} must have an even number of hex characters")

    try:
        return bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be valid hex") from exc


def bytes32_chunks_from_hex(value: str, field_name: str) -> list[bytes]:
    blob = _hex_to_bytes(value, field_name)
    if len(blob) % 32 != 0:
        raise ValueError(f"{field_name} must be a multiple of 32 bytes")

    return [blob[idx : idx + 32] for idx in range(0, len(blob), 32)]


def verify_algoplonk_onchain(
    *,
    app_id: int,
    method_signature: str,
    sender_mnemonic: str,
    proof_hex: str,
    public_inputs_hex: str,
    rounds_to_wait: int = 4,
) -> dict[str, Any]:
    if app_id <= 0:
        raise ValueError("verify app_id must be a positive integer")

    proof_chunks = bytes32_chunks_from_hex(proof_hex, "algoplonk_proof_hex")
    public_input_chunks = bytes32_chunks_from_hex(public_inputs_hex, "algoplonk_public_inputs_hex")

    method = abi.Method.from_signature(method_signature)
    private_key = mnemonic.to_private_key(sender_mnemonic)
    sender = account.address_from_private_key(private_key)
    signer = AccountTransactionSigner(private_key)

    composer = AtomicTransactionComposer()
    composer.add_method_call(
        app_id=app_id,
        method=method,
        sender=sender,
        sp=algod_client().suggested_params(),
        signer=signer,
        method_args=[proof_chunks, public_input_chunks],
    )

    result = composer.execute(algod_client(), rounds_to_wait)

    verified = False
    return_value = None
    if result.abi_results:
        return_value = result.abi_results[0].return_value
        verified = bool(return_value)

    return {
        "verified": verified,
        "return_value": return_value,
        "tx_ids": list(result.tx_ids),
        "confirmed_round": result.confirmed_round,
        "proof_chunk_count": len(proof_chunks),
        "public_input_chunk_count": len(public_input_chunks),
    }
