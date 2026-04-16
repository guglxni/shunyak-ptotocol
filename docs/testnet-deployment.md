# Verified TestNet Deployment State

Last verified: 2026-04-16

## Deployed Smart Contract

| Field | Value |
|-------|-------|
| App ID | 758909516 |
| App Address | MBC3GSLWOUXTW7EPC4X5AOA2WFSLUEGLNKHHMQ3YEM3SZ4QF2OIXXBI2YE |
| Creator / Signer | SHYFV65OX2KCXPFBKZBZNSYL6RE4PFAWHVWL2RIAR4QMULX7FS3NJJ7CFU |
| Network | Algorand TestNet |
| Algod | https://testnet-api.algonode.cloud |
| Indexer | https://testnet-idx.algonode.cloud |
| Deploy Txid | 37V5ZNDZ4EJUNPJCVQEEUEGBTKWNFGWK5NWLVTGKSJ62SR6PHI5A |

Contract Methods: `register_consent`, `revoke_consent`, `check_status`

## On-Chain Consent State

5 consent boxes stored in Box Storage:

| Box Key (truncated) | Expiry | Status |
|---------------------|--------|--------|
| 2d1b0ab594de5ded... | 1776354395 | ACTIVE |
| 287354147de6277b... | 1776354211 | ACTIVE |
| 728dd8f96787c6cb... | 1776350324 | EXPIRED |
| bce6e62d63f6dffe... | 1776350281 | EXPIRED |
| 0e8e176104319051... | 1776350165 | EXPIRED |

Box value schema: `[consent_hash: 32B][expiry: 8B uint64][version: 1B][reserved: 23B]`

Box key derivation: `SHA256(user_pubkey + enterprise_pubkey + app_id.to_bytes(8, "big"))`

## Account Balances

| Account | Balance | Min-Balance | Spendable |
|---------|---------|-------------|-----------|
| Signer (SHYFV65O...) | 5.566 ALGO | 0.550 ALGO | 5.016 ALGO |
| App (MBC3GS...) | 0.310 ALGO | 0.305 ALGO | 0.006 ALGO |

Signer has created 3 apps on TestNet, confirming iterative development history.

## Transaction History

10+ confirmed transactions on the signer account, mix of `pay` (funding, settlement) and `appl` (contract create, consent register/revoke) types.

## Deployment Architecture

```
Vercel (shunyak-protocol.vercel.app)
  |
  +-- Next.js 16 Frontend (static pages)
  |     /consent, /blocked, /authorized, /showcase
  |
  +-- Python Serverless Functions (@vercel/python 4.6.0)
        /api/consent/register
        /api/consent/status
        /api/consent/revoke
        /api/agent/execute
        /api/agent/stream (SSE)
        /api/algorand/showcase
        /api/audit/log
            |
            v
        Algorand TestNet
        (App 758909516 / Box Storage / PaymentTxn)
```

## Verification Commands

Check app exists:

```bash
python3 -c "
from algosdk.v2client.algod import AlgodClient
c = AlgodClient('', 'https://testnet-api.algonode.cloud')
print(c.application_info(758909516))
"
```

Check consent boxes:

```bash
python3 -c "
from algosdk.v2client.algod import AlgodClient
c = AlgodClient('', 'https://testnet-api.algonode.cloud')
print(c.application_boxes(758909516))
"
```

Check signer balance:

```bash
python3 -c "
from algosdk.v2client.algod import AlgodClient
c = AlgodClient('', 'https://testnet-api.algonode.cloud')
info = c.account_info('SHYFV65OX2KCXPFBKZBZNSYL6RE4PFAWHVWL2RIAR4QMULX7FS3NJJ7CFU')
print(f'{info[\"amount\"]/1e6:.4f} ALGO')
"
```

## Architecture Diagram

See `docs/architecture.drawio` for the full system architecture and consent-gated execution flow diagrams (open with draw.io or diagrams.net).
