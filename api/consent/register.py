from __future__ import annotations

import base64
import os
import time
from typing import Any

from algosdk import account, encoding, mnemonic
from nacl.signing import SigningKey

from api._common.algorand import (
    register_consent_app_call,
    submit_note_transaction,
    verify_consent_box,
)
from api._common.audit import append_audit_entry
from api._common.constants import (
    DEFAULT_ENTERPRISE_PUBKEY,
    SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY,
    SHUNYAK_ALGOPLONK_SIMULATE_ONLY,
    SHUNYAK_ALGOPLONK_VERIFY_APP_ID,
    SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE,
    SHUNYAK_APP_ID,
    SHUNYAK_CONSENT_REGISTRAR_MNEMONIC,
    SHUNYAK_DIGILOCKER_REDIRECT_URL,
    SHUNYAK_ENABLE_TESTNET_TX,
    SHUNYAK_IDENTITY_PROVIDER,
    SHUNYAK_ZK_BACKEND,
)
from api._common.digilocker import (
    DigiLockerAPIError,
    DigiLockerConfigError,
    create_digilocker_request,
    digilocker_status_value,
    digilocker_is_configured,
    extract_claim_from_aadhaar,
    get_digilocker_aadhaar,
    get_digilocker_status,
    is_digilocker_authenticated,
)
from api._common.http import JSONHandler
from api._common.store import (
    hash_claim,
    register_consent_record,
    to_pubkey_hex,
)
from api._common.token import mint_consent_token
from api._common.zk import (
    bytes32_chunks_from_hex,
    verify_algoplonk_onchain,
)

SUPPORTED_CLAIM_TYPES = {"age_over_18", "indian_citizen"}
SUPPORTED_IDENTITY_PROVIDERS = {"digilocker"}
SUPPORTED_ZK_BACKENDS = {"algoplonk"}


def _build_attestation_message(
    *,
    claim_hash: str,
    user_pubkey: str,
    enterprise_pubkey: str,
    expiry_timestamp: int,
) -> bytes:
    return (
        bytes.fromhex(claim_hash)
        + bytes.fromhex(user_pubkey)
        + bytes.fromhex(enterprise_pubkey)
        + int(expiry_timestamp).to_bytes(8, "big")
    )


def _sign_contract_attestation(
    *,
    registrar_mnemonic: str,
    claim_hash: str,
    user_pubkey: str,
    enterprise_pubkey: str,
    expiry_timestamp: int,
) -> str:
    if not registrar_mnemonic:
        raise ValueError("SHUNYAK_CONSENT_REGISTRAR_MNEMONIC is required for contract attestation")

    private_key = mnemonic.to_private_key(registrar_mnemonic)
    registrar_address = account.address_from_private_key(private_key)
    registrar_pubkey_hex = encoding.decode_address(registrar_address).hex()

    if registrar_pubkey_hex.lower() != enterprise_pubkey.lower():
        raise ValueError(
            "enterprise_pubkey must match the configured registrar signer public key"
        )

    key_material = base64.b64decode(private_key)
    signing_key = SigningKey(key_material[:32])
    message = _build_attestation_message(
        claim_hash=claim_hash,
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        expiry_timestamp=expiry_timestamp,
    )

    return signing_key.sign(message).signature.hex()


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


def _resolve_identity(
    *,
    identity_provider: str,
    claim_type: str,
    digilocker_request_id: str,
    digilocker_redirect_url: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    if identity_provider != "digilocker":
        raise ValueError("Only digilocker identity provider is supported in real mode")

    if not digilocker_is_configured():
        raise ValueError(
            "DigiLocker provider selected but credentials are missing. Configure "
            "SHUNYAK_DIGILOCKER_CLIENT_ID, SHUNYAK_DIGILOCKER_CLIENT_SECRET, and "
            "SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID."
        )

    if not digilocker_request_id:
        created = create_digilocker_request(digilocker_redirect_url)
        request_id = str(created.get("id", "")).strip() or None
        auth_url = str(created.get("url", "")).strip() or None
        pending_response = {
            "provider": "digilocker",
            "status": "pending_digilocker_consent",
            "verified": False,
            "request_id": request_id,
            "auth_url": auth_url,
            "scope": [],
            "digilocker_status": digilocker_status_value(created),
        }
        return pending_response, created, None

    status_payload = get_digilocker_status(digilocker_request_id)
    status_value = digilocker_status_value(status_payload)

    if not is_digilocker_authenticated(status_payload):
        pending_response = {
            "provider": "digilocker",
            "status": "pending_digilocker_consent",
            "verified": False,
            "request_id": digilocker_request_id,
            "auth_url": str(status_payload.get("url", "")).strip() or None,
            "scope": [],
            "digilocker_status": status_value,
        }
        return pending_response, status_payload, None

    aadhaar_payload = get_digilocker_aadhaar(digilocker_request_id)
    claim_ok, claim_reason = extract_claim_from_aadhaar(
        aadhaar_payload,
        claim_type,
        now_ts=int(time.time()),
    )

    if not claim_ok:
        raise ValueError(
            "DigiLocker consent is complete but claim validation failed "
            f"({claim_reason})."
        )

    aadhaar = aadhaar_payload.get("aadhaar") if isinstance(aadhaar_payload.get("aadhaar"), dict) else {}

    return (
        {
            "provider": "digilocker",
            "verified": True,
            "status": "success",
            "claim_reason": claim_reason,
            "scope": [],
            "request_id": digilocker_request_id,
            "auth_url": None,
            "digilocker_status": status_value,
            "aadhaar_masked_number": aadhaar.get("maskedNumber"),
            "aadhaar_generated_at": aadhaar.get("generatedAt"),
        },
        status_payload,
        aadhaar_payload,
    )


def _resolve_zk_artifact(
    *,
    zk_backend: str,
    claim_hash: str,
    proof_hex: str,
    public_inputs_hex: str,
    sender_mnemonic: str,
) -> tuple[str, str, dict[str, Any]]:
    if zk_backend != "algoplonk":
        raise ValueError("Only algoplonk backend is supported in real mode")

    normalized_proof = _normalize_hex(proof_hex, "algoplonk_proof_hex")
    normalized_public_inputs = _normalize_hex(public_inputs_hex, "algoplonk_public_inputs_hex")
    proof_chunks = bytes32_chunks_from_hex(normalized_proof, "algoplonk_proof_hex")
    public_input_chunks = bytes32_chunks_from_hex(
        normalized_public_inputs,
        "algoplonk_public_inputs_hex",
    )
    if not public_input_chunks:
        raise ValueError("algoplonk_public_inputs_hex must contain at least one bytes32 item")

    first_public_input = public_input_chunks[0].hex().lower()
    if first_public_input != claim_hash.lower():
        raise ValueError(
            "algoplonk_public_inputs_hex[0] must equal claim hash so the consent anchor matches the proof"
        )

    onchain_verification: dict[str, Any] | None = None
    onchain_error: str | None = None
    if SHUNYAK_ALGOPLONK_SIMULATE_ONLY:
        onchain_error = "algoplonk_simulation_only_enabled"
    elif SHUNYAK_ALGOPLONK_VERIFY_APP_ID > 0 and sender_mnemonic:
        try:
            onchain_verification = verify_algoplonk_onchain(
                app_id=SHUNYAK_ALGOPLONK_VERIFY_APP_ID,
                method_signature=SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE,
                sender_mnemonic=sender_mnemonic,
                proof_hex=normalized_proof,
                public_inputs_hex=normalized_public_inputs,
            )
        except Exception as exc:
            onchain_error = str(exc)
    elif not sender_mnemonic:
        onchain_error = "sender_mnemonic_missing_for_algoplonk_verify"
    else:
        onchain_error = "algoplonk_verifier_app_not_configured"

    if SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY and (
        not onchain_verification or not onchain_verification.get("verified")
    ):
        reason = onchain_error or "algoplonk_onchain_verification_failed"
        raise ValueError(f"AlgoPlonk on-chain verification required but unavailable: {reason}")

    verified = bool(onchain_verification and onchain_verification.get("verified"))
    verification_mode = "onchain_verified" if verified else "shape_verified"
    return (
        normalized_proof,
        normalized_public_inputs,
        {
            "backend": "algoplonk",
            "verification_mode": verification_mode,
            "verified": True,
            "proof_chunk_count": len(proof_chunks),
            "public_input_chunk_count": len(public_input_chunks),
            "onchain_verification": onchain_verification,
            "onchain_error": onchain_error,
        },
    )


class handler(JSONHandler):
    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json_body()

        user_id = str(payload.get("user_id", "")).strip()
        claim_type = str(payload.get("claim_type", "age_over_18")).strip() or "age_over_18"
        enterprise_pubkey = str(
            payload.get("enterprise_pubkey", DEFAULT_ENTERPRISE_PUBKEY)
        ).strip()
        expiry_days = int(payload.get("expiry_days", 30) or 30)
        identity_provider = (
            str(payload.get("identity_provider", SHUNYAK_IDENTITY_PROVIDER)).strip().lower()
            or SHUNYAK_IDENTITY_PROVIDER
        )
        zk_backend = (
            str(payload.get("zk_backend", SHUNYAK_ZK_BACKEND)).strip().lower() or SHUNYAK_ZK_BACKEND
        )
        digilocker_request_id = str(payload.get("digilocker_request_id", "")).strip()
        digilocker_redirect_url = (
            str(payload.get("digilocker_redirect_url", SHUNYAK_DIGILOCKER_REDIRECT_URL)).strip()
            or SHUNYAK_DIGILOCKER_REDIRECT_URL
        )
        algoplonk_proof_hex = str(payload.get("algoplonk_proof_hex", "")).strip()
        algoplonk_public_inputs_hex = str(payload.get("algoplonk_public_inputs_hex", "")).strip()

        if not user_id:
            self._send_error("user_id is required", status=422)
            return

        if claim_type not in SUPPORTED_CLAIM_TYPES:
            allowed = ", ".join(sorted(SUPPORTED_CLAIM_TYPES))
            self._send_error(f"claim_type must be one of: {allowed}", status=422)
            return

        if len(enterprise_pubkey) != 64:
            self._send_error("enterprise_pubkey must be 64 hex chars", status=422)
            return
        try:
            bytes.fromhex(enterprise_pubkey)
        except ValueError:
            self._send_error("enterprise_pubkey must be valid hex", status=422)
            return

        if identity_provider not in SUPPORTED_IDENTITY_PROVIDERS:
            allowed = ", ".join(sorted(SUPPORTED_IDENTITY_PROVIDERS))
            self._send_error(f"identity_provider must be one of: {allowed}", status=422)
            return

        if zk_backend not in SUPPORTED_ZK_BACKENDS:
            allowed = ", ".join(sorted(SUPPORTED_ZK_BACKENDS))
            self._send_error(f"zk_backend must be one of: {allowed}", status=422)
            return

        user_pubkey = to_pubkey_hex(user_id)
        claim_hash = hash_claim(user_id, claim_type, enterprise_pubkey)

        try:
            identity_meta, digilocker_payload, aadhaar_payload = _resolve_identity(
                identity_provider=identity_provider,
                claim_type=claim_type,
                digilocker_request_id=digilocker_request_id,
                digilocker_redirect_url=digilocker_redirect_url,
            )
        except (ValueError, DigiLockerConfigError, DigiLockerAPIError) as exc:
            self._send_error(str(exc), status=422)
            return

        aadhaar_trace_id = str((aadhaar_payload or {}).get("traceId", "")).strip() or None

        if identity_meta.get("status") == "pending_digilocker_consent":
            self._send_json(
                {
                    "ok": True,
                    "status": "pending_digilocker_consent",
                    "user_pubkey": user_pubkey,
                    "enterprise_pubkey": enterprise_pubkey,
                    "claim_type": claim_type,
                    "claim_hash": claim_hash,
                    "identity_provider": identity_provider,
                    "digilocker": {
                        "request_id": identity_meta.get("request_id"),
                        "auth_url": identity_meta.get("auth_url"),
                        "status": (
                            str((digilocker_payload or {}).get("status", "unauthenticated")).strip().upper()
                            or "PENDING"
                        ),
                        "scope": identity_meta.get("scope", []),
                    },
                    "steps": [
                        "identity provider selected: digilocker",
                        "consent request created or status polled",
                        "user authorization pending in DigiLocker sandbox",
                        "resubmit with digilocker_request_id after user grants consent",
                    ],
                }
            )
            return

        if not algoplonk_proof_hex or not algoplonk_public_inputs_hex:
            self._send_error(
                "algoplonk_proof_hex and algoplonk_public_inputs_hex are required once DigiLocker consent is authenticated",
                status=422,
            )
            return

        sender_mnemonic = SHUNYAK_CONSENT_REGISTRAR_MNEMONIC
        try:
            algoplonk_proof, public_inputs_hex, zk_meta = _resolve_zk_artifact(
                zk_backend=zk_backend,
                claim_hash=claim_hash,
                proof_hex=algoplonk_proof_hex,
                public_inputs_hex=algoplonk_public_inputs_hex,
                sender_mnemonic=sender_mnemonic,
            )
        except ValueError as exc:
            self._send_error(str(exc), status=422)
            return

        now_ts = int(time.time())
        expiry_timestamp = now_ts + (expiry_days * 24 * 60 * 60)

        if not SHUNYAK_ENABLE_TESTNET_TX:
            self._send_error(
                "SHUNYAK_ENABLE_TESTNET_TX must be true in real mode",
                status=422,
            )
            return

        if not sender_mnemonic:
            self._send_error(
                "SHUNYAK_CONSENT_REGISTRAR_MNEMONIC is required in real mode for on-chain consent anchoring",
                status=422,
            )
            return

        try:
            contract_attestation_signature = _sign_contract_attestation(
                registrar_mnemonic=sender_mnemonic,
                claim_hash=claim_hash,
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                expiry_timestamp=expiry_timestamp,
            )
        except ValueError as exc:
            self._send_error(str(exc), status=422)
            return

        if SHUNYAK_APP_ID <= 0:
            self._send_error(
                "SHUNYAK_APP_ID must be configured for real contract app-call consent registration",
                status=422,
            )
            return

        try:
            contract_onchain = register_consent_app_call(
                sender_mnemonic=sender_mnemonic,
                proof_hex=contract_attestation_signature,
                public_inputs_hex=public_inputs_hex,
                enterprise_pubkey=enterprise_pubkey,
                expiry_timestamp=expiry_timestamp,
                user_pubkey=user_pubkey,
                app_id=SHUNYAK_APP_ID,
            )
        except Exception as exc:
            self._send_error(f"contract consent registration failed: {exc}", status=502)
            return

        contract_txid = str(contract_onchain.get("txid", "")).strip()
        if not contract_txid:
            self._send_error("contract consent registration returned empty txid", status=502)
            return
        contract_explorer_url = str(contract_onchain.get("explorer_url", "")).strip()
        contract_confirmed_round = int(contract_onchain.get("confirmed_round", 0) or 0)

        consent_note = {
            "kind": "shunyak-consent-v1",
            "user_pubkey": user_pubkey,
            "enterprise_pubkey": enterprise_pubkey,
            "claim_hash": claim_hash,
            "expiry_timestamp": expiry_timestamp,
            "claim_type": claim_type,
            "identity_provider": identity_provider,
            "zk_backend": zk_backend,
            "issued_at": now_ts,
            "contract_txid": contract_txid,
        }
        note_txid: str | None = None
        note_explorer_url: str | None = None
        note_anchor_error: str | None = None
        try:
            note_onchain = submit_note_transaction(
                sender_mnemonic=sender_mnemonic,
                note_payload=consent_note,
                amount_microalgo=0,
            )
        except Exception as exc:
            note_anchor_error = str(exc)
        else:
            note_txid = str(note_onchain.get("txid", "")).strip() or None
            note_explorer_url = str(note_onchain.get("explorer_url", "")).strip() or None

        box_valid, box_reason, _ = verify_consent_box(
            user_pubkey=user_pubkey,
            enterprise_pubkey=enterprise_pubkey,
            claim_hash=claim_hash,
            app_id=SHUNYAK_APP_ID,
        )
        if not box_valid:
            self._send_error(
                f"contract consent write did not produce an active consent box: {box_reason}",
                status=502,
            )
            return

        txid = contract_txid
        explorer_url = contract_explorer_url or (note_explorer_url or "")
        confirmed_round = contract_confirmed_round
        tx_mode = "testnet_onchain_contract"
        consent_source = "app_box"

        try:
            consent_token = mint_consent_token(
                user_pubkey=user_pubkey,
                enterprise_pubkey=enterprise_pubkey,
                expires_at=expiry_timestamp,
                consent_txid=note_txid or txid,
                claim_hash=claim_hash,
                mode=tx_mode,
                consent_source=consent_source,
                app_id=SHUNYAK_APP_ID if SHUNYAK_APP_ID > 0 else None,
                identity_provider=identity_provider,
                zk_backend=zk_backend,
            )
        except RuntimeError as exc:
            self._send_error(f"consent token minting unavailable: {exc}", status=503)
            return

        record = {
            "user_id": user_id,
            "user_pubkey": user_pubkey,
            "enterprise_pubkey": enterprise_pubkey,
            "claim_type": claim_type,
            "claim_hash": claim_hash,
            "proof": algoplonk_proof,
            "public_inputs_hex": public_inputs_hex,
            "contract_attestation_signature": contract_attestation_signature,
            "consent_hash": claim_hash,
            "expiry_timestamp": expiry_timestamp,
            "txid": txid,
            "contract_txid": contract_txid,
            "note_txid": note_txid,
            "note_anchor_error": note_anchor_error,
            "tx_mode": tx_mode,
            "consent_source": consent_source,
            "confirmed_round": confirmed_round,
            "identity_provider": identity_provider,
            "identity_attestation": identity_meta,
            "zk_backend": zk_meta.get("backend"),
            "zk_verification_mode": zk_meta.get("verification_mode"),
            "zk_onchain_verification": zk_meta.get("onchain_verification"),
            "zk_onchain_error": zk_meta.get("onchain_error"),
            "box_validation_reason": box_reason,
            "aadhaar_trace_id": aadhaar_trace_id,
            "created_at": now_ts,
        }
        register_consent_record(record)

        session_id = f"consent-{now_ts}"
        append_audit_entry(
            session_id=session_id,
            event="tool_allowed",
            tool_name="register_consent",
            args={"user_pubkey": user_pubkey, "enterprise_pubkey": enterprise_pubkey},
            policy_decision="allowed",
            reason="Consent record registered",
        )

        self._send_json(
            {
                "ok": True,
                "txid": txid,
                "explorer_url": explorer_url,
                "contract_txid": contract_txid,
                "note_txid": note_txid,
                "proof": algoplonk_proof,
                "claim_hash": claim_hash,
                "user_pubkey": user_pubkey,
                "enterprise_pubkey": enterprise_pubkey,
                "expires_at": expiry_timestamp,
                "consent_token": consent_token,
                "status": "consent_registered",
                "identity_provider": identity_provider,
                "identity_attestation": identity_meta,
                "digilocker": {
                    "request_id": identity_meta.get("request_id"),
                    "scope": identity_meta.get("scope", []),
                    "status": str((digilocker_payload or {}).get("status", "authenticated")).strip().upper(),
                    "aadhaar_masked_number": identity_meta.get("aadhaar_masked_number"),
                },
                "aadhaar": {
                    "generated_at": identity_meta.get("aadhaar_generated_at"),
                    "trace_id": aadhaar_trace_id,
                },
                "zk_backend": zk_meta.get("backend"),
                "zk_verification_mode": zk_meta.get("verification_mode"),
                "algoplonk": {
                    "proof_chunk_count": zk_meta.get("proof_chunk_count"),
                    "public_input_chunk_count": zk_meta.get("public_input_chunk_count"),
                    "onchain_verification": zk_meta.get("onchain_verification"),
                    "onchain_error": zk_meta.get("onchain_error"),
                    "onchain_required": SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY,
                    "simulate_only": SHUNYAK_ALGOPLONK_SIMULATE_ONLY,
                    "contract_attestation_signed": True,
                    "verify_app_id": SHUNYAK_ALGOPLONK_VERIFY_APP_ID
                    if SHUNYAK_ALGOPLONK_VERIFY_APP_ID > 0
                    else None,
                    "verify_method": SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE,
                },
                "tx_mode": tx_mode,
                "consent_source": consent_source,
                "confirmed_round": confirmed_round,
                "fallback_reason": note_anchor_error,
                "steps": [
                    f"identity provider: {identity_provider}",
                    f"claim extracted: {claim_type}",
                    "DigiLocker Aadhaar claim validated",
                    "AlgoPlonk proof accepted",
                    f"zk verification mode: {zk_meta.get('verification_mode')}",
                    "registrar attestation signature generated",
                    "consent contract method invoked on Algorand TestNet",
                    (
                        f"supplemental consent note anchor submitted: {note_txid}"
                        if note_txid
                        else "supplemental note anchor unavailable"
                    ),
                    f"consent verification source: {consent_source}",
                    f"transaction id: {txid}",
                ],
            }
        )
