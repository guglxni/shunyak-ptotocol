import json
from pathlib import Path
from typing import Any

from pyteal import (
    App,
    Approve,
    Assert,
    BareCallActions,
    Btoi,
    Bytes,
    BytesZero,
    Concat,
    Expr,
    Extract,
    Global,
    If,
    Int,
    Itob,
    Len,
    OnCompleteAction,
    Router,
    ScratchVar,
    Seq,
    Sha256,
    TealType,
    Txn,
    abi,
)


CONSENT_VERSION_BYTE = Bytes("base16", "01")
BOX_RESERVED_BYTES = Int(23)
REGISTRAR_KEY = Bytes("registrar")


def derive_box_key_expr(user_pubkey: Expr, enterprise_pubkey: Expr) -> Expr:
    return Sha256(
        Concat(
            user_pubkey,
            enterprise_pubkey,
            Itob(Global.current_application_id()),
        )
    )


router = Router(
    "ShunyakConsent",
    BareCallActions(
        no_op=OnCompleteAction.create_only(
            Seq(
                # Registrar account is fixed at creation and is the only writer.
                If(Txn.application_args.length() == Int(1))
                .Then(
                    Seq(
                        Assert(Len(Txn.application_args[0]) == Int(32)),
                        App.globalPut(REGISTRAR_KEY, Txn.application_args[0]),
                    )
                )
                .Else(App.globalPut(REGISTRAR_KEY, Txn.sender())),
                Approve(),
            )
        ),
        opt_in=OnCompleteAction.never(),
        close_out=OnCompleteAction.never(),
        update_application=OnCompleteAction.never(),
        delete_application=OnCompleteAction.never(),
    ),
)


@router.method
def register_consent(
    zk_proof: abi.DynamicBytes,
    public_inputs: abi.DynamicBytes,
    user_pubkey: abi.DynamicBytes,
    enterprise_pubkey: abi.DynamicBytes,
    expiry: abi.Uint64,
) -> Expr:
    box_key = ScratchVar(TealType.bytes)
    consent_hash = ScratchVar(TealType.bytes)

    return Seq(
        Assert(Txn.sender() == App.globalGet(REGISTRAR_KEY)),
        Assert(expiry.get() > Global.latest_timestamp()),
        Assert(Len(zk_proof.get()) > Int(0)),
        Assert(Len(public_inputs.get()) >= Int(32)),
        Assert(Len(user_pubkey.get()) == Int(32)),
        Assert(Len(enterprise_pubkey.get()) == Int(32)),
        box_key.store(derive_box_key_expr(user_pubkey.get(), enterprise_pubkey.get())),
        consent_hash.store(Extract(public_inputs.get(), Int(0), Int(32))),
        App.box_put(
            box_key.load(),
            Concat(
                consent_hash.load(),
                Itob(expiry.get()),
                CONSENT_VERSION_BYTE,
                BytesZero(BOX_RESERVED_BYTES),
            ),
        ),
    )


@router.method
def revoke_consent(user_pubkey: abi.DynamicBytes, enterprise_pubkey: abi.DynamicBytes) -> Expr:
    box_key = ScratchVar(TealType.bytes)

    return Seq(
        Assert(Txn.sender() == App.globalGet(REGISTRAR_KEY)),
        Assert(Len(user_pubkey.get()) == Int(32)),
        Assert(Len(enterprise_pubkey.get()) == Int(32)),
        box_key.store(derive_box_key_expr(user_pubkey.get(), enterprise_pubkey.get())),
        Assert(App.box_delete(box_key.load())),
    )


@router.method
def check_status(
    user_pubkey: abi.DynamicBytes,
    enterprise_pubkey: abi.DynamicBytes,
    *,
    output: abi.Tuple2[abi.Bool, abi.Uint64],
) -> Expr:
    box_key = ScratchVar(TealType.bytes)
    has_valid_consent = abi.Bool()
    expires_at = abi.Uint64()
    maybe_box = App.box_get(box_key.load())

    return Seq(
        Assert(Len(user_pubkey.get()) == Int(32)),
        Assert(Len(enterprise_pubkey.get()) == Int(32)),
        box_key.store(derive_box_key_expr(user_pubkey.get(), enterprise_pubkey.get())),
        maybe_box,
        If(maybe_box.hasValue())
        .Then(
            Seq(
                expires_at.set(Btoi(Extract(maybe_box.value(), Int(32), Int(8)))),
                has_valid_consent.set(expires_at.get() > Global.latest_timestamp()),
            )
        )
        .Else(
            Seq(
                expires_at.set(Int(0)),
                has_valid_consent.set(Int(0)),
            )
        ),
        output.set(has_valid_consent, expires_at),
    )


def build_contract(*, version: int = 10) -> tuple[str, str, dict[str, Any]]:
    approval_program, clear_program, contract = router.compile_program(version=version)
    return approval_program, clear_program, contract.dictify()


def write_contract_artifacts(
    output_dir: Path,
    *,
    version: int = 10,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    approval_program, clear_program, contract = build_contract(version=version)

    approval_path = output_dir / "shunyak_consent_approval.teal"
    clear_path = output_dir / "shunyak_consent_clear.teal"
    contract_path = output_dir / "shunyak_consent.arc32.json"

    approval_path.write_text(approval_program, encoding="utf-8")
    clear_path.write_text(clear_program, encoding="utf-8")
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "approval": approval_path,
        "clear": clear_path,
        "contract": contract_path,
    }


if __name__ == "__main__":
    artifact_dir = Path(__file__).resolve().parent / "artifacts"
    generated = write_contract_artifacts(artifact_dir)
    print("Generated contract artifacts:")
    for name, path in generated.items():
        print(f"- {name}: {path}")
