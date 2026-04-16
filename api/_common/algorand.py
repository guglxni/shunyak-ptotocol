from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from typing import Any

from algosdk import abi as sdk_abi
from algosdk import account, encoding, mnemonic
from algosdk.atomic_transaction_composer import AccountTransactionSigner, AtomicTransactionComposer
from algosdk.error import AlgodHTTPError, IndexerHTTPError
from algosdk.transaction import AssetTransferTxn, PaymentTxn, wait_for_confirmation
from algosdk.v2client import algod, indexer

from api._common.constants import (
    ALGOD_SERVER,
    ALGOD_TOKEN,
    INDEXER_SERVER,
    INDEXER_TOKEN,
    SHUNYAK_APP_ID,
    SHUNYAK_CONSENT_REGISTER_METHOD_SIGNATURE,
    SHUNYAK_CONSENT_REQUIRE_BOX_PARITY,
    SHUNYAK_CONSENT_REVOKE_METHOD_SIGNATURE,
    SHUNYAK_CONSENT_SOURCE,
    SHUNYAK_ENABLE_TESTNET_TX,
    SHUNYAK_USDCA_ASA_ID,
    TESTNET_EXPLORER_TX_BASE,
)


class AlgorandOperationError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class AlgorandLookupError(AlgorandOperationError):
    pass


class AlgorandDecodeError(AlgorandOperationError):
    pass


class AlgorandSubmissionError(AlgorandOperationError):
    pass


class AlgorandAppCallError(AlgorandOperationError):
    pass


def _is_not_found_http_error(exc: AlgodHTTPError | IndexerHTTPError) -> bool:
    message = str(exc).lower()
    return "404" in message or "not found" in message


def algod_client() -> algod.AlgodClient:
    return algod.AlgodClient(ALGOD_TOKEN, ALGOD_SERVER)


def indexer_client() -> indexer.IndexerClient:
    return indexer.IndexerClient(INDEXER_TOKEN, INDEXER_SERVER)


def is_valid_algorand_address(value: str) -> bool:
    try:
        return encoding.is_valid_address(value)
    except (TypeError, ValueError):
        return False


def address_from_pubkey_hex(pubkey_hex: str) -> str:
    pubkey_bytes = bytes.fromhex(pubkey_hex)
    if len(pubkey_bytes) != 32:
        raise ValueError("pubkey hex must represent 32 bytes")
    return encoding.encode_address(pubkey_bytes)


def resolve_receiver_address(value: str) -> str:
    candidate = value.strip()
    if is_valid_algorand_address(candidate):
        return candidate

    if len(candidate) == 64:
        return address_from_pubkey_hex(candidate)

    raise ValueError("recipient must be a valid Algorand address or 64-char pubkey hex")


def sender_address_from_mnemonic(mn: str) -> str:
    private_key = mnemonic.to_private_key(mn)
    return account.address_from_private_key(private_key)


def _normalize_hex(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty hex")
    if len(normalized) % 2 != 0:
        raise ValueError(f"{field_name} must have an even number of hex characters")
    try:
        bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be valid hex") from exc
    return normalized


def _execute_app_method(
    *,
    app_id: int,
    method_signature: str,
    sender_mnemonic: str,
    method_args: list[Any],
    boxes: list[tuple[int, bytes]] | None = None,
    rounds_to_wait: int = 8,
) -> dict[str, Any]:
    if app_id <= 0:
        raise ValueError("app_id must be configured for contract app call")

    method = sdk_abi.Method.from_signature(method_signature)
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
        method_args=method_args,
        boxes=boxes,
    )

    try:
        result = composer.execute(algod_client(), rounds_to_wait)
    except (AlgodHTTPError, ConnectionError, OSError, TimeoutError, RuntimeError, ValueError, TypeError) as exc:
        raise AlgorandAppCallError("app_call_execution_failed", str(exc)) from exc

    txid = result.tx_ids[0] if result.tx_ids else ""
    return_value = None
    if result.abi_results:
        return_value = result.abi_results[0].return_value

    return {
        "txid": txid,
        "confirmed_round": int(result.confirmed_round or 0),
        "sender": sender,
        "return_value": return_value,
        "explorer_url": f"{TESTNET_EXPLORER_TX_BASE}{txid}" if txid else None,
    }


def register_consent_app_call(
    *,
    sender_mnemonic: str,
    proof_hex: str,
    public_inputs_hex: str,
    enterprise_pubkey: str,
    expiry_timestamp: int,
    user_pubkey: str | None = None,
    app_id: int = SHUNYAK_APP_ID,
    method_signature: str = SHUNYAK_CONSENT_REGISTER_METHOD_SIGNATURE,
) -> dict[str, Any]:
    normalized_proof = _normalize_hex(proof_hex, "algoplonk_proof_hex")
    normalized_inputs = _normalize_hex(public_inputs_hex, "algoplonk_public_inputs_hex")
    normalized_enterprise = _normalize_hex(enterprise_pubkey, "enterprise_pubkey")
    normalized_user = _normalize_hex(user_pubkey, "user_pubkey") if user_pubkey else None

    method = sdk_abi.Method.from_signature(method_signature)
    arg_count = len(method.args)
    if arg_count == 4:
        method_args: list[Any] = [
            bytes.fromhex(normalized_proof),
            bytes.fromhex(normalized_inputs),
            bytes.fromhex(normalized_enterprise),
            int(expiry_timestamp),
        ]
    elif arg_count == 5:
        if not normalized_user:
            raise ValueError(
                "register method signature expects user_pubkey argument, but user_pubkey is missing"
            )
        method_args = [
            bytes.fromhex(normalized_proof),
            bytes.fromhex(normalized_inputs),
            bytes.fromhex(normalized_user),
            bytes.fromhex(normalized_enterprise),
            int(expiry_timestamp),
        ]
    else:
        raise ValueError(
            "Unsupported register method signature. Expected 4 or 5 ABI args for register_consent"
        )

    return _execute_app_method(
        app_id=app_id,
        method_signature=method_signature,
        sender_mnemonic=sender_mnemonic,
        method_args=method_args,
        boxes=[(0, derive_consent_box_key(normalized_user, normalized_enterprise, app_id))]
        if normalized_user
        else None,
    )


def revoke_consent_app_call(
    *,
    sender_mnemonic: str,
    enterprise_pubkey: str,
    user_pubkey: str | None = None,
    app_id: int = SHUNYAK_APP_ID,
    method_signature: str = SHUNYAK_CONSENT_REVOKE_METHOD_SIGNATURE,
) -> dict[str, Any]:
    normalized_enterprise = _normalize_hex(enterprise_pubkey, "enterprise_pubkey")
    normalized_user = _normalize_hex(user_pubkey, "user_pubkey") if user_pubkey else None

    method = sdk_abi.Method.from_signature(method_signature)
    arg_count = len(method.args)
    if arg_count == 1:
        method_args: list[Any] = [bytes.fromhex(normalized_enterprise)]
    elif arg_count == 2:
        if not normalized_user:
            raise ValueError(
                "revoke method signature expects user_pubkey argument, but user_pubkey is missing"
            )
        method_args = [
            bytes.fromhex(normalized_user),
            bytes.fromhex(normalized_enterprise),
        ]
    else:
        raise ValueError(
            "Unsupported revoke method signature. Expected 1 or 2 ABI args for revoke_consent"
        )

    return _execute_app_method(
        app_id=app_id,
        method_signature=method_signature,
        sender_mnemonic=sender_mnemonic,
        method_args=method_args,
        boxes=[(0, derive_consent_box_key(normalized_user, normalized_enterprise, app_id))]
        if normalized_user
        else None,
    )


def derive_consent_box_key(user_pubkey: str, enterprise_pubkey: str, app_id: int = SHUNYAK_APP_ID) -> bytes:
    return hashlib.sha256(
        bytes.fromhex(user_pubkey) + bytes.fromhex(enterprise_pubkey) + app_id.to_bytes(8, "big")
    ).digest()


def lookup_consent_box(
    *,
    user_pubkey: str,
    enterprise_pubkey: str,
    app_id: int = SHUNYAK_APP_ID,
) -> tuple[bool, str, dict[str, Any] | None]:
    if app_id <= 0:
        return False, "consent_app_not_configured", None

    try:
        box_key = derive_consent_box_key(user_pubkey, enterprise_pubkey, app_id)
    except ValueError:
        return False, "consent_box_pubkey_invalid", None

    try:
        payload = algod_client().application_box_by_name(app_id, box_key)
    except AlgodHTTPError as exc:
        if _is_not_found_http_error(exc):
            return False, "consent_box_not_found", None
        return False, "consent_box_lookup_http_error", None
    except (ConnectionError, OSError, TimeoutError, RuntimeError, ValueError, TypeError) as exc:
        error = AlgorandLookupError("consent_box_lookup_failed", str(exc))
        return False, error.code, None

    value_base64 = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(value_base64, str) or not value_base64:
        return False, "consent_box_empty", None

    try:
        raw = base64.b64decode(value_base64 + "===")
    except (binascii.Error, ValueError, TypeError) as exc:
        error = AlgorandDecodeError("consent_box_decode_failed", str(exc))
        return False, error.code, None

    if len(raw) < 40:
        return False, "consent_box_value_too_short", None

    consent_hash = raw[0:32].hex()
    expiry_timestamp = int.from_bytes(raw[32:40], "big")
    version = int(raw[40]) if len(raw) > 40 else 0

    return True, "consent_box_found", {
        "app_id": app_id,
        "box_key": box_key.hex(),
        "consent_hash": consent_hash,
        "expiry_timestamp": expiry_timestamp,
        "consent_version": version,
    }


def verify_consent_box(
    *,
    user_pubkey: str,
    enterprise_pubkey: str,
    claim_hash: str | None = None,
    app_id: int = SHUNYAK_APP_ID,
) -> tuple[bool, str, dict[str, Any] | None]:
    found, reason, box = lookup_consent_box(
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        app_id=app_id,
    )
    if not found:
        return False, reason, box

    if box is None:
        return False, "consent_box_missing", None

    expiry_timestamp = int(box.get("expiry_timestamp", 0) or 0)
    if expiry_timestamp < int(time.time()):
        return False, "consent_box_expired", box

    if claim_hash and str(box.get("consent_hash", "")).lower() != claim_hash.lower():
        return False, "consent_box_claim_hash_mismatch", box

    return True, "consent_box_active", box


def submit_note_transaction(
    *,
    sender_mnemonic: str,
    note_payload: dict[str, Any],
    amount_microalgo: int = 0,
) -> dict[str, Any]:
    if not SHUNYAK_ENABLE_TESTNET_TX:
        raise RuntimeError("SHUNYAK_ENABLE_TESTNET_TX is disabled")

    client = algod_client()
    private_key = mnemonic.to_private_key(sender_mnemonic)
    sender = account.address_from_private_key(private_key)
    params = client.suggested_params()

    note_bytes = json.dumps(note_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    txn = PaymentTxn(
        sender=sender,
        sp=params,
        receiver=sender,
        amt=amount_microalgo,
        note=note_bytes,
    )

    signed_txn = txn.sign(private_key)
    txid = client.send_transaction(signed_txn)
    confirmed = wait_for_confirmation(client, txid, 10)

    return {
        "txid": txid,
        "confirmed_round": int(confirmed.get("confirmed-round", 0) or 0),
        "sender": sender,
        "explorer_url": f"{TESTNET_EXPLORER_TX_BASE}{txid}",
    }


def submit_payment_transaction(
    *,
    sender_mnemonic: str,
    receiver: str,
    amount_microalgo: int,
    memo: str,
) -> dict[str, Any]:
    if not SHUNYAK_ENABLE_TESTNET_TX:
        raise RuntimeError("SHUNYAK_ENABLE_TESTNET_TX is disabled")

    if amount_microalgo <= 0:
        raise ValueError("amount_microalgo must be positive")

    resolved_receiver = resolve_receiver_address(receiver)

    client = algod_client()
    private_key = mnemonic.to_private_key(sender_mnemonic)
    sender = account.address_from_private_key(private_key)
    params = client.suggested_params()

    txn = PaymentTxn(
        sender=sender,
        sp=params,
        receiver=resolved_receiver,
        amt=amount_microalgo,
        note=memo.encode("utf-8"),
    )
    signed_txn = txn.sign(private_key)
    txid = client.send_transaction(signed_txn)
    confirmed = wait_for_confirmation(client, txid, 10)

    return {
        "txid": txid,
        "confirmed_round": int(confirmed.get("confirmed-round", 0) or 0),
        "sender": sender,
        "receiver": resolved_receiver,
        "explorer_url": f"{TESTNET_EXPLORER_TX_BASE}{txid}",
    }


def submit_asset_transfer_transaction(
    *,
    sender_mnemonic: str,
    receiver: str,
    amount_base_units: int,
    asset_id: int = SHUNYAK_USDCA_ASA_ID,
    memo: str = "",
) -> dict[str, Any]:
    if not SHUNYAK_ENABLE_TESTNET_TX:
        raise RuntimeError("SHUNYAK_ENABLE_TESTNET_TX is disabled")

    if asset_id <= 0:
        raise ValueError("asset_id must be configured for ASA transfer")

    if amount_base_units <= 0:
        raise ValueError("amount_base_units must be positive")

    resolved_receiver = resolve_receiver_address(receiver)

    client = algod_client()
    private_key = mnemonic.to_private_key(sender_mnemonic)
    sender = account.address_from_private_key(private_key)
    params = client.suggested_params()

    txn = AssetTransferTxn(
        sender=sender,
        sp=params,
        receiver=resolved_receiver,
        amt=amount_base_units,
        index=asset_id,
        note=memo.encode("utf-8"),
    )

    signed_txn = txn.sign(private_key)
    txid = client.send_transaction(signed_txn)
    confirmed = wait_for_confirmation(client, txid, 10)

    return {
        "txid": txid,
        "confirmed_round": int(confirmed.get("confirmed-round", 0) or 0),
        "sender": sender,
        "receiver": resolved_receiver,
        "asset_id": asset_id,
        "explorer_url": f"{TESTNET_EXPLORER_TX_BASE}{txid}",
    }


def _decode_note(note_base64: str | None) -> dict[str, Any] | None:
    if not note_base64:
        return None
    try:
        raw = base64.b64decode(note_base64 + "===")
        return json.loads(raw.decode("utf-8"))
    except (binascii.Error, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def lookup_transaction(txid: str) -> dict[str, Any] | None:
    # Primary path: indexer transaction lookup.
    try:
        client = indexer_client()
        result = client.lookup_transaction_by_id(txid).do()
    except (AlgodHTTPError, IndexerHTTPError):
        result = None
    except (ConnectionError, OSError, TimeoutError, RuntimeError, ValueError, TypeError):
        result = None

    if isinstance(result, dict):
        txn = result.get("transaction")
        if isinstance(txn, dict):
            note_payload = _decode_note(txn.get("note"))
            return {
                "txid": txid,
                "confirmed_round": int(txn.get("confirmed-round", 0) or 0),
                "sender": txn.get("sender"),
                "receiver": (txn.get("payment-transaction") or {}).get("receiver"),
                "note_payload": note_payload,
            }

    # Fallback path: algod pending tx lookup is often available sooner.
    try:
        pending = algod_client().pending_transaction_info(txid)
    except (AlgodHTTPError, ConnectionError, OSError, TimeoutError, RuntimeError, ValueError, TypeError):
        return None

    confirmed_round = int(pending.get("confirmed-round", 0) or 0)
    if confirmed_round <= 0:
        return None

    txn_container = pending.get("txn") or {}
    txn = txn_container.get("txn") if isinstance(txn_container, dict) else {}
    if not isinstance(txn, dict):
        return None

    note_payload = _decode_note(txn.get("note"))
    return {
        "txid": txid,
        "confirmed_round": confirmed_round,
        "sender": txn.get("snd"),
        "receiver": txn.get("rcv"),
        "note_payload": note_payload,
    }


def verify_consent_transaction(
    *,
    txid: str,
    user_pubkey: str,
    enterprise_pubkey: str,
    claim_hash: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    tx = None
    # Indexer can lag a few seconds behind algod confirmation on TestNet.
    # Retry briefly so freshly confirmed consent notes can be validated.
    for attempt in range(6):
        tx = lookup_transaction(txid)
        if tx is not None:
            break
        if attempt < 5:
            time.sleep(1)

    if tx is None:
        return False, "consent_tx_not_found", None

    note_payload = tx.get("note_payload")
    if not isinstance(note_payload, dict):
        return False, "consent_note_missing", tx

    if note_payload.get("kind") != "shunyak-consent-v1":
        return False, "consent_note_kind_mismatch", tx

    if note_payload.get("user_pubkey") != user_pubkey:
        return False, "consent_note_user_mismatch", tx

    if note_payload.get("enterprise_pubkey") != enterprise_pubkey:
        return False, "consent_note_enterprise_mismatch", tx

    if claim_hash and note_payload.get("claim_hash") != claim_hash:
        return False, "consent_note_claim_hash_mismatch", tx

    return True, "consent_tx_valid", tx


def verify_consent_onchain(
    *,
    user_pubkey: str,
    enterprise_pubkey: str,
    claim_hash: str | None = None,
    consent_txid: str | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    source = SHUNYAK_CONSENT_SOURCE

    if source in {"box", "hybrid"}:
        valid_box, box_reason, box_meta = verify_consent_box(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            claim_hash=claim_hash,
        )
        if valid_box:
            return True, box_reason, box_meta
        # Box parity keeps revoke/register/status behavior consistent by not
        # resurrecting revoked consent from historical note transactions.
        if source == "box" or (source == "hybrid" and SHUNYAK_CONSENT_REQUIRE_BOX_PARITY):
            return False, box_reason, box_meta

    if source in {"note", "hybrid"}:
        if not consent_txid:
            return False, "consent_txid_missing", None
        return verify_consent_transaction(
            txid=consent_txid,
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            claim_hash=claim_hash,
        )

    return False, "consent_source_invalid", None


def sdk_showcase_snapshot() -> dict[str, Any]:
    algo = algod_client()
    idx = indexer_client()

    status = algo.status()
    params = algo.suggested_params()
    compile_result = algo.compile("int 1")

    # algosdk indexer health response differs by version: either immediate dict
    # or a request object exposing .do(). Handle both to keep endpoint portable.
    indexer_health_result = idx.health()
    if hasattr(indexer_health_result, "do"):
        indexer_health_result = indexer_health_result.do()

    latest_round = int(status.get("last-round", 0) or 0)
    latest_block = algo.block_info(latest_round) if latest_round else {}

    return {
        "algod_server": ALGOD_SERVER,
        "indexer_server": INDEXER_SERVER,
        "status": {
            "last_round": latest_round,
            "time_since_last_round": status.get("time-since-last-round"),
            "catchup_time": status.get("catchup-time"),
        },
        "suggested_params": {
            "fee": params.fee,
            "first": params.first,
            "last": params.last,
            "genesis_hash": params.gh,
            "genesis_id": params.gen,
            "min_fee": params.min_fee,
        },
        "teal_compile": {
            "hash": compile_result.get("hash"),
            "result_len": len(compile_result.get("result", "")),
        },
        "latest_block": {
            "round": latest_round,
            "txn_counter": (latest_block.get("block") or {}).get("tc"),
            "timestamp": (latest_block.get("block") or {}).get("ts"),
        },
        "indexer_health": bool(indexer_health_result),
    }
