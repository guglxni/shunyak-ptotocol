# Shunyak Protocol

Shunyak Protocol is a consent-gated agentic execution demo aligned to the DPDP workflow described in PRD and SPEC.

This repository is configured to use:
- AI-DLC workflow instructions for GitHub Copilot
- Dolios Agent hardened security concepts (workflow policy, vault, audit, DLP)
- Vercel deployment with Next.js frontend and Python serverless APIs
- Algorand DevRel agent skill pack for Algorand-focused assistant guidance

## Repository Layout

- frontend: Next.js demo interface (4 screens)
- api: Python serverless endpoints for consent, agent execution, and audit logs
- agent: Dolios wiring + tools for compliance check and settlement
- contracts: Algorand consent contract skeleton and tests
- external/algorand-agent-skills: upstream Algorand agent skill references
- policies: Workflow DAG policy for tool ordering
- aidlc-docs: AI-DLC generated documentation (created during workflow runs)

## Hosted Deployment (Vercel)

1) Install dependencies

cd frontend
npm install
pip install -r requirements.txt

2) Configure environment

cp .env.example .env

3) Authenticate and link the project

vercel whoami
vercel link

4) Set required runtime variables in Vercel

vercel env add SHUNYAK_APP_ID preview
vercel env add SHUNYAK_APP_ID production
vercel env add SHUNYAK_AGENT_MNEMONIC preview
vercel env add SHUNYAK_AGENT_MNEMONIC production

5) Deploy preview

vercel deploy --yes

6) Deploy production

vercel deploy --prod --yes

Current production alias:

https://shunyak-protocol.vercel.app

## Local Development (Optional)

1) Run full local stack (single command)

./scripts/dev-local.sh

This split local workflow avoids a current Vercel CLI local runtime regression on mixed Next + Python manual builder configs (`ERR_INVALID_ARG_TYPE` in `deserializeOutput`).
On the first API hit, Vercel may need to build Python functions locally; if you see a transient proxy `500`/`ECONNRESET`, retry once after the build finishes.

The script starts:
- API runtime at http://localhost:4103
- Frontend at http://localhost:4100 (with `/api/*` proxied to the local API runtime)

Press Ctrl+C to stop both processes.

2) Run scoped Python tests

/Volumes/MacExt/shunyak-ptotocol/.venv/bin/python -m pytest -c pytest.ini -q

## Full TestNet Demo Mode

For true on-chain consent + settlement behavior, configure these environment variables:

- SHUNYAK_CONSENT_REGISTRAR_MNEMONIC: funded TestNet mnemonic allowed to register/revoke consent on contract
- SHUNYAK_AGENT_MNEMONIC: optional fallback signer mnemonic
- SHUNYAK_APP_ID: deployed consent app id (required for box or hybrid verification)
- SHUNYAK_CONSENT_SOURCE: note | box | hybrid (recommended: hybrid)
- SHUNYAK_IDENTITY_PROVIDER: digilocker
- SHUNYAK_ZK_BACKEND: algoplonk
- ALGOD_SERVER: https://testnet-api.algonode.cloud
- INDEXER_SERVER: https://testnet-idx.algonode.cloud
- SHUNYAK_ENABLE_TESTNET_TX: true
- SHUNYAK_USDCA_ASA_ID: optional ASA id for stablecoin-style settlement path
- SHUNYAK_SIGNER_BALANCE_WARN_MICROALGO: warning threshold for signer wallet balance (default: 1000000)

Required for deployed environments:

- SHUNYAK_DEMO_SECRET: consent token signing secret (must be non-default)
- SHUNYAK_STREAM_TICKET_SECRET: stream-ticket signing secret (recommended; falls back to SHUNYAK_DEMO_SECRET)
- SHUNYAK_REQUIRE_HARDENED: set to true for fail-closed production mode
- SHUNYAK_REQUIRE_OPERATOR_AUTH: require operator token for `/api/agent/execute` and stream ticket issuance
- SHUNYAK_OPERATOR_TOKEN: shared operator token accepted via `Authorization: Bearer` or `X-Shunyak-Operator-Token`
- SHUNYAK_REQUIRE_EXECUTION_TOKEN: require consent token for agent execution endpoints
- SHUNYAK_ALLOWED_ORIGINS: comma-separated CORS allowlist (recommended in deployed environments)

DigiLocker sandbox credentials (required only when SHUNYAK_IDENTITY_PROVIDER=digilocker):

- SHUNYAK_DIGILOCKER_BASE_URL (default: https://dg-sandbox.setu.co)
- SHUNYAK_DIGILOCKER_REDIRECT_URL
- SHUNYAK_DIGILOCKER_CLIENT_ID
- SHUNYAK_DIGILOCKER_CLIENT_SECRET
- SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID

AlgoPlonk verification knobs (required only when SHUNYAK_ZK_BACKEND=algoplonk):

- SHUNYAK_ALGOPLONK_VERIFY_APP_ID: deployed AlgoPlonk verifier app id
- SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE (default: verify(byte[32][],byte[32][])bool)
- SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY: fail registration unless verifier returns true
- SHUNYAK_ALGOPLONK_SIMULATE_ONLY: skip live on-chain verifier calls while testing payload shape
- SHUNYAK_CONSENT_REGISTER_METHOD_SIGNATURE (default: register_consent(byte[],byte[],byte[],byte[],uint64)void)
- SHUNYAK_CONSENT_REVOKE_METHOD_SIGNATURE (default: revoke_consent(byte[],byte[])void)
- SHUNYAK_CONSENT_REQUIRE_BOX_PARITY: enforce box state as source of truth for revoke/status parity

Settlement safety knob:

- SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK: set false for production/demo environments to block mock settlement fallback

Consent token policy:

- Mock consent tokens are rejected in deployed environments.
- Consent token mint/validation requires a non-default SHUNYAK_DEMO_SECRET in deployed environments.
- Local insecure fallback secret is disabled by default; opt-in only with SHUNYAK_ALLOW_INSECURE_DEMO_SECRET=true.

Execution safety policy:

- `amount_microalgo` is bounded by SHUNYAK_MAX_SETTLEMENT_MICROALGO.
- Request rate and spend windows are enforced via SHUNYAK_RATE_LIMIT_* runtime settings.
- Agent stream now uses short-lived server-issued stream tickets; consent tokens are not sent in URL query strings.
- Stream tickets are signed and stateless, so POST/GET stream hops remain valid across serverless instances.

In real mode, SHUNYAK_CONSENT_REGISTRAR_MNEMONIC and SHUNYAK_ENABLE_TESTNET_TX=true are mandatory.

### Identity Providers


- digilocker: Setu DigiLocker consent flow
	- first submit returns pending_digilocker_consent with request id + auth url
	- complete authorization in DigiLocker
	- resubmit using digilocker_request_id to finalize consent registration using Aadhaar-backed claim checks

### ZK Backends


- algoplonk:
	- submit algoplonk_proof_hex and algoplonk_public_inputs_hex
	- first public input must match backend claim hash anchor
	- optional verifier app call runs when app id + mnemonic are configured
	- set SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY=true to enforce hard fail if verifier does not return true

### Consent Verification Modes

- note: validates consent from on-chain note transaction payload
- box: validates consent from app box storage only
- hybrid: attempts box verification first, then falls back to note verification

Round 2 recommendation: use hybrid to maximize reliability during demo while still supporting app box verification when deployed.

When SHUNYAK_CONSENT_REQUIRE_BOX_PARITY=true and SHUNYAK_APP_ID is configured, consent status and agent authorization require an active app-box record (revoked boxes remain revoked even if historical note tx exists).

### Settlement Modes

- ALGO payment mode: default when SHUNYAK_USDCA_ASA_ID is not set
- ASA settlement mode: enabled automatically when SHUNYAK_USDCA_ASA_ID is configured

Round 2 recommendation: keep ALGO mode as baseline and enable ASA mode only after the receiver account has opted into the configured asset.

### CLI Wallet + TestNet Funding (AlgoKit)

You can provision a fresh wallet and fund it directly from CLI using the AlgoKit TestNet dispenser:

1) Install AlgoKit CLI (if not already installed)

brew install algorandfoundation/tap/algokit

2) Generate a new wallet/account (writes mnemonic + address to a local file)

algokit task vanity-address SHY --match start --output file --file-path /tmp/shunyak_wallet.txt

3) Authenticate dispenser access (interactive device login)

algokit dispenser login --ci -o file -f /tmp/algokit_ci_token.txt

4) Fund the generated address on TestNet

export ALGOKIT_DISPENSER_ACCESS_TOKEN="$(tr -d '\n' < /tmp/algokit_ci_token.txt)"
ADDRESS="<your_generated_address>"
algokit dispenser fund -r "$ADDRESS" -a 2 --whole-units

5) Check remaining daily limit

algokit dispenser limit --whole-units

6) Use this wallet in deployed runtime

Set SHUNYAK_AGENT_MNEMONIC in Vercel Preview/Production with the generated mnemonic, then redeploy.

### Demo Screens

- /consent: registers consent and submits an on-chain note tx when funded
	- supports identity_provider=digilocker and zk_backend=algoplonk
	- contract app-call write is required when SHUNYAK_APP_ID is configured
- /blocked: runs blocked path for non-consented user
- /authorized: runs authorized settlement path using consent token validation
- /showcase: live Algorand SDK + AlgoKit runtime showcase

Agent stream hardening:

- `POST /api/agent/stream` issues a short-lived `stream_token` after guard checks.
- `GET /api/agent/stream?stream_token=...` consumes the ticket and streams events.
- `consent_token` in stream query params is explicitly rejected.

MCP + capability policy enforcement:

- Agent tool execution is routed via in-process MCP registry (`verify_shunyak_compliance`, `execute_algo_settlement`).
- Tool capabilities are enforced before dispatch using `agent/skills/shunyak-compliance/capabilities.yaml`.

Consent revoke API (status parity helper):

- POST /api/consent/revoke with user_pubkey and enterprise_pubkey

## Deploy

Use the Hosted Deployment (Vercel) section above.

Contract deployment (real app-call path):

1) Generate artifacts only:

/Volumes/MacExt/shunyak-ptotocol/.venv/bin/python contracts/deploy.py --write-artifacts-only

2) Deploy to Algorand TestNet:

export SHUNYAK_DEPLOYER_MNEMONIC="<funded 25-word mnemonic>"
export SHUNYAK_CONSENT_REGISTRAR_MNEMONIC="<funded 25-word mnemonic used by register/revoke>"
/Volumes/MacExt/shunyak-ptotocol/.venv/bin/python contracts/deploy.py --output-dir contracts/artifacts

Optional: set `SHUNYAK_CONSENT_REGISTRAR_ADDRESS` to pin registrar separately from mnemonic derivation.

3) Set emitted APP_ID in runtime env:

SHUNYAK_APP_ID=<deployment APP_ID>

Quick commands:

vercel deploy --yes
vercel deploy --prod --yes

## Judge Demo Runbook (Round 2)

1) Pre-flight checks

- Open /showcase and confirm signer account is configured
- Confirm low_balance_warning is false or top up wallet
- Confirm consent source mode and settlement mode are as intended

2) Consent flow

- Open /consent
- Register consent for demo user
- Verify tx_mode is testnet_onchain
- Keep the generated consent token in browser local storage

3) Blocked flow

- Open /blocked
- Execute with non-consented user
- Verify outcome is DPDP Compliance Failure
- Verify audit contains workflow_blocked

4) Authorized flow

- Open /authorized
- Execute with consented user
- Verify live stream events in terminal panel
- Verify settlement txid and explorer link
- Verify settlement mode (testnet_onchain or testnet_onchain_asa)

5) Audit proof

- In Audit Log panel, verify workflow and tool events are readable JSON entries

## Hackathon Submission Checklist

- Repository URL added to DoraHacks submission
- Demo video attached (UI -> blockchain interaction -> tx confirmation)
- README runbook included
- Environment variables documented in .env.example
- At least one complete end-to-end user flow validated on TestNet
- Scoped tests passing: /Volumes/MacExt/shunyak-ptotocol/.venv/bin/python -m pytest -c pytest.ini -q

Optional live on-chain integration test (requires funded signer + deployed app):

- SHUNYAK_RUN_ONCHAIN_INTEGRATION=1 /Volumes/MacExt/shunyak-ptotocol/.venv/bin/python -m pytest -c pytest.ini -q -m integration

## Algorand SDK + Kit Showcase

The API endpoint /api/algorand/showcase exposes:

- Algod status and suggested params (py-algorand-sdk)
- TEAL compile check via algod.compile("int 1")
- Indexer health check
- AlgoKit CLI availability detection
- algokit-utils package detection and version
- configured sender account address/balance snapshot
- low-balance warning metadata for the configured signer account
- consent engine mode (note/box/hybrid) and app id visibility
- identity engine mode and DigiLocker credential readiness
- zk engine mode and AlgoPlonk verifier settings
- settlement engine mode (ALGO vs ASA) and configured asset id visibility

## Using algorand-agent-skills

The upstream repository is cloned under external/algorand-agent-skills.
To sync the skills into this project for your coding assistant workflows:

cp -r external/algorand-agent-skills/skills ./skills
cp external/algorand-agent-skills/setups/AGENTS.md ./AGENTS.algorand.md

Primary skill references used in this repo:

- skills/algorand-python/SKILL.md
- skills/algorand-project-setup/SKILL.md
- skills/algorand-frontend/SKILL.md

## Additional Documentation

- docs/algobharat-round2-mvp-decisions.md: official-source-based Round 2 decisions and demo checklist
- HARDENED.md: runtime guardrails and fail-closed production settings
- aidlc-docs/aidlc-state.md: workflow stage state and latest execution notes
- aidlc-docs/audit.md: chronological prompt/action audit trail

## Notes

- Runtime is configured for real DigiLocker + AlgoPlonk flow; no local mock consent fallback is used in registration.
- Provide a valid signer mnemonic and (optionally) a deployed AlgoPlonk verifier app id for strict on-chain proof checks.
- AI-DLC rule details are present under .aidlc-rule-details and active Copilot instructions are in .github/copilot-instructions.md.
- AI-DLC execution state and audit history are tracked under aidlc-docs/.
