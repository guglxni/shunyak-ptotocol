from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid

import pytest
from algosdk import account, encoding, mnemonic
from nacl.signing import SigningKey

from agent.shunyak_agent import ShunyakAgentService
from api._common.algorand import (
    lookup_transaction,
    register_consent_app_call,
    revoke_consent_app_call,
    submit_note_transaction,
    verify_consent_box,
    verify_consent_onchain,
)
from api._common.constants import DEFAULT_ENTERPRISE_PUBKEY, SHUNYAK_APP_ID
from api._common.store import hash_claim
from api._common.token import mint_consent_token


TRUTHY = {"1", "true", "yes", "on"}


def _integration_enabled() -> bool:
    return os.getenv("SHUNYAK_RUN_ONCHAIN_INTEGRATION", "0").strip().lower() in TRUTHY


@pytest.mark.integration
def test_full_consent_blocked_authorized_onchain_flow() -> None:
    if not _integration_enabled():
        pytest.skip("Set SHUNYAK_RUN_ONCHAIN_INTEGRATION=1 to run live on-chain integration tests")

    sender_mnemonic = (
        os.getenv("SHUNYAK_CONSENT_REGISTRAR_MNEMONIC", "").strip()
        or os.getenv("SHUNYAK_AGENT_MNEMONIC", "").strip()
    )
    if not sender_mnemonic:
        pytest.skip(
            "SHUNYAK_CONSENT_REGISTRAR_MNEMONIC (or SHUNYAK_AGENT_MNEMONIC) is required"
        )

    sender_private_key = mnemonic.to_private_key(sender_mnemonic)
    sender_address = account.address_from_private_key(sender_private_key)

    if SHUNYAK_APP_ID <= 0:
        pytest.skip("SHUNYAK_APP_ID must be configured for on-chain integration tests")

    enterprise_pubkey = os.getenv(
        "SHUNYAK_ENTERPRISE_PUBKEY",
        encoding.decode_address(sender_address).hex(),
    ).strip().lower()
    if len(enterprise_pubkey) != 64:
        pytest.skip("SHUNYAK_ENTERPRISE_PUBKEY must be 64 hex chars")

    # Step 1: blocked path (no consent yet)
    user_seed = f"integration-user-{uuid.uuid4().hex}"
    user_pubkey = hashlib.sha256(user_seed.encode("utf-8")).hexdigest()[:64]

    blocked_service = ShunyakAgentService()
    blocked_result = blocked_service.execute_task(
        prompt="Process financial history and issue micro-loan",
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        amount_microalgo=1_000,
        consent_token=None,
    )
    assert blocked_result["status"] == "blocked"
    assert "DPDP Compliance Failure" in blocked_result["outcome_message"]

    # Step 2: on-chain consent registration via contract app-call + note anchor
    user_id = f"integration-{uuid.uuid4().hex[:12]}"
    claim_hash = hash_claim(user_id, "age_over_18", enterprise_pubkey)
    public_inputs_hex = claim_hash
    expiry_timestamp = int(time.time()) + 3600

    attestation_message = (
        bytes.fromhex(claim_hash)
        + bytes.fromhex(user_pubkey)
        + bytes.fromhex(enterprise_pubkey)
        + expiry_timestamp.to_bytes(8, "big")
    )
    signing_key = SigningKey(base64.b64decode(sender_private_key)[:32])
    proof_hex = signing_key.sign(attestation_message).signature.hex()

    register_txn = register_consent_app_call(
        sender_mnemonic=sender_mnemonic,
        proof_hex=proof_hex,
        public_inputs_hex=public_inputs_hex,
        enterprise_pubkey=enterprise_pubkey,
        expiry_timestamp=expiry_timestamp,
        user_pubkey=user_pubkey,
    )
    assert register_txn.get("txid")

    note_payload = {
        "kind": "shunyak-consent-v1",
        "user_pubkey": user_pubkey,
        "enterprise_pubkey": enterprise_pubkey,
        "claim_hash": claim_hash,
        "expiry_timestamp": expiry_timestamp,
        "issued_at": int(time.time()),
        "contract_txid": register_txn["txid"],
    }
    note_txn = submit_note_transaction(
        sender_mnemonic=sender_mnemonic,
        note_payload=note_payload,
        amount_microalgo=0,
    )
    assert note_txn.get("txid")

    box_valid, _, _ = verify_consent_box(
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        claim_hash=claim_hash,
        app_id=SHUNYAK_APP_ID,
    )
    assert box_valid is True

    onchain_valid, _, _ = verify_consent_onchain(
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        claim_hash=claim_hash,
        consent_txid=note_txn["txid"],
    )
    assert onchain_valid is True

    consent_token = mint_consent_token(
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        expires_at=expiry_timestamp,
        consent_txid=note_txn["txid"],
        claim_hash=claim_hash,
        mode="testnet_onchain_contract",
        consent_source="app_box",
        app_id=SHUNYAK_APP_ID,
        identity_provider="digilocker",
        zk_backend="algoplonk",
    )

    # Step 3: authorized path should now execute real settlement
    authorized_service = ShunyakAgentService()
    authorized_result = authorized_service.execute_task(
        prompt="Process financial history and issue micro-loan",
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        amount_microalgo=1_000,
        consent_token=consent_token,
    )
    assert authorized_result["status"] == "authorized"
    settlement = authorized_result.get("settlement") or {}
    assert settlement.get("txid")
    assert str(settlement.get("mode", "")).startswith("testnet_onchain")

    settlement_tx = lookup_transaction(str(settlement["txid"]))
    assert settlement_tx is not None

    # Step 4: revoke consent and assert status parity
    revoke_txn = revoke_consent_app_call(
        sender_mnemonic=sender_mnemonic,
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        app_id=SHUNYAK_APP_ID,
    )
    assert revoke_txn.get("txid")

    box_valid_after_revoke, _, _ = verify_consent_box(
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        claim_hash=claim_hash,
        app_id=SHUNYAK_APP_ID,
    )
    assert box_valid_after_revoke is False

    valid_after_revoke, reason_after_revoke, _ = verify_consent_onchain(
        user_pubkey=user_pubkey,
        enterprise_pubkey=enterprise_pubkey,
        claim_hash=claim_hash,
        consent_txid=note_txn["txid"],
    )
    assert valid_after_revoke is False
    assert reason_after_revoke.startswith("consent_box_")
