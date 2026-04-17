# SPEC.md — Shunyak Protocol Technical Specification
**Version:** 2.2 — DigiLocker + AlgoPlonk Real-Mode Edition  
**Stack:** Algorand + dolios-agent (hardened) + Next.js + Vercel  
**Deployment:** Vercel (frontend + API serverless functions)  

---

## 1. Architecture Overview

```
+------------------------------------------------------------------+
|                    VERCEL DEPLOYMENT                             |
|                                                                  |
|  +------------------------+   +------------------------------+  |
|  |   Next.js Frontend     |   |  Python Serverless API       |  |
|  |  (Demo UI / 4 screens) |   |  /api/consent/register       |  |
|  |                        |   |  /api/consent/status         |  |
|  |                        |   |  /api/consent/revoke         |  |
|  |  React + Tailwind      |   |  /api/agent/execute          |  |
|  |  Real-time SSE updates |   |  /api/agent/stream           |  |
|  |                        |   |  /api/audit/log              |  |
|  +----------+-------------+   +----------+-------------------+  |
|             |                            |                       |
+-------------|----------------------------|----------------------+
              |                            |
              v                            v
+------------------------+    +----------------------------------+
|  Identity + ZK Adapters|    |  dolios-agent (hardened)        |
|  (Python serverless)   |    |  Agent execution layer          |
|  Provider: digilocker     |    |  WorkflowPolicy DAG             |
|  ZK: algoplonk            |   |  CredentialVault                |
|  Setu API integration  |    |  AuditLogger                    |
+----------+-------------+    |  DLPScanner                     |
           |                  |  Per-tool capabilities          |
           |                  +------------------+--------------+
           |                                     |
           v                                     v
+------------------------------------------------------------------+
|                    ALGORAND TESTNET                              |
|                                                                  |
|  +------------------------+   +------------------------------+  |
|  |  ShunyakConsent.py     |   |  Algod Client / Indexer      |  |
|  |  (AlgoKit 4.0 / PyTeal)|   |  testnet-api.algonode.cloud  |  |
|  |  register_consent()    |   |                              |  |
|  |  revoke_consent()      |   |  Box Storage queries         |  |
|  |  check_status()        |   |  Transaction broadcast       |  |
|  |  Consent anchor verify |   |                              |  |
|  +------------------------+   +------------------------------+  |
+------------------------------------------------------------------+
```

**Runtime principle:** run real-mode consent by default (`identity_provider=digilocker`, `zk_backend=algoplonk`) with strict on-chain anchoring and optional strict on-chain verifier enforcement.

---

## 2. Repository Structure

```
shunyak-protocol/
├── frontend/                    # Next.js app — deployed to Vercel
│   ├── app/
│   │   ├── page.tsx             # Landing / demo selector
│   │   ├── consent/page.tsx     # Screen 1: Consent registration
│   │   ├── blocked/page.tsx     # Screen 2: Blocked agent path
│   │   ├── authorized/page.tsx  # Screen 3: Authorized settlement
│   │   └── showcase/page.tsx    # Screen 4: SDK + runtime showcase
│   ├── components/
│   │   ├── ConsentFlow.tsx      # Step-by-step consent UI
│   │   ├── AgentTerminal.tsx    # Live agent output stream
│   │   ├── AuditViewer.tsx      # Real-time audit log display
│   │   └── AlgorandTx.tsx      # Transaction status + explorer link
│   └── lib/
│       └── sse.ts               # SSE client for agent streaming
│
├── api/                         # Vercel Python serverless functions
│   ├── _common/
│   │   ├── digilocker.py        # Setu DigiLocker client + status helpers
│   │   └── zk.py                # AlgoPlonk verification adapters
│   ├── consent/
│   │   ├── register.py          # POST: identity attestation + proof path → consent anchor
│   │   ├── status.py            # GET: Check Box Storage status
│   │   └── revoke.py            # POST: Revoke consent on-chain + parity check
│   ├── agent/
│   │   ├── execute.py           # POST: Trigger agent
│   │   └── stream.py            # POST issue stream ticket, GET consume and stream SSE
│   └── audit/
│       └── log.py               # GET: Read recent audit entries
│
├── contracts/                   # Algorand smart contracts
│   ├── shunyak_consent.py       # AlgoKit 4.0 / PyTeal contract
│   ├── deploy.py                # Testnet deployment script
│   └── tests/
│       └── test_consent.py      # Pytest contract tests
│
├── agent/                       # Dolios agent integration
│   ├── shunyak_agent.py         # Agent bootstrap + MCP tool wiring
│   ├── mcp_server.py            # MCP server exposing 2 tools
│   ├── tools/
│   │   ├── verify_compliance.py # verify_shunyak_compliance tool
│   │   └── execute_settlement.py # execute_algo_settlement tool
│   └── skills/
│       └── shunyak-compliance/
│           ├── SKILL.md
│           └── capabilities.yaml
│
├── policies/
│   └── workflow.yaml            # DAG: settlement requires compliance
│
├── vercel.json                  # Vercel routing config
├── requirements.txt             # Python deps for Vercel functions
└── .env.example                 # All required env vars
```

---

## 3. Module A: `shunyak-contracts`

### 3.1 Contract: `ShunyakConsent` (AlgoKit 4.0 / PyTeal)

**Box Key Schema:**
```
box_key = SHA256(user_pubkey + enterprise_pubkey + app_id)
```

**Box Value Schema (64 bytes):**
```
[0:32]  consent_hash     — SHA256 of consent parameters
[32:40] expiry_timestamp — Unix timestamp (uint64)
[40:41] consent_version  — Schema version byte
[41:64] reserved         — Zero-padded
```

**Methods:**

```python
@app.external
def register_consent(
  zk_proof: Bytes,        # Registrar attestation signature (ed25519)
  public_inputs: Bytes,   # Public inputs with claim hash at index 0
  user_pubkey: Bytes,
    enterprise_pubkey: Bytes,
    expiry: UInt64,
) -> None:
  # 1. Assert Txn.sender == registrar key configured at app creation
  # 2. Build attestation message = claim_hash + user_pubkey + enterprise_pubkey + expiry
  # 3. Verify attestation with Ed25519Verify_Bare against enterprise_pubkey
  # 4. Write consent hash + expiry to Box Storage

@app.external  
def revoke_consent(user_pubkey: Bytes, enterprise_pubkey: Bytes) -> None:
  # 1. Assert Txn.sender == registrar
  # 2. Derive box key from user + enterprise + app_id
  # 3. Delete box — instantly kills agent authorization

@app.external(read_only=True)
def check_status(
    user_pubkey: Bytes,
    enterprise_pubkey: Bytes,
) -> Tuple[Bool, UInt64]:
    # 1. Derive box key
    # 2. Check if box exists
    # 3. Check expiry against Global.latest_timestamp
    # 4. Return (is_valid: bool, expires_at: uint64)
```

**ZK Proof Verification (current strategy):**

The registration pipeline uses AlgoPlonk proof/public-input payload validation with optional verifier app call. Strict mode can be enabled so registration fails unless verifier execution returns `True`.

Contract-level consent anchoring remains mandatory in real mode.

### 3.2 Deployment

```bash
algokit bootstrap
algokit deploy --network testnet
# Outputs: APP_ID, APP_ADDRESS — add to .env
```

---

## 4. Module B: `identity + zk adapters`

### 4.1 Identity Provider Modes

Consent registration uses DigiLocker provider mode:

- `digilocker`: Setu DigiLocker sandbox integration

DigiLocker flow is stateful in a single endpoint:

1. First request without `digilocker_request_id` creates DigiLocker request and returns `status: pending_digilocker_consent`.
2. User completes authorization at returned URL.
3. Client re-submits with `digilocker_request_id`.
4. Backend polls `/api/digilocker/{id}/status`; if authenticated, Aadhaar data is fetched for claim extraction.

### 4.2 ZK Backend Modes

Proof validation uses AlgoPlonk payload ingestion:

- consumes externally generated `algoplonk_proof_hex` and `algoplonk_public_inputs_hex`.

`algoplonk` processing enforces:

- both fields must be valid hex
- both fields must decode into `byte[32][]` flat arrays
- first public input must equal backend `claim_hash` (consent anchor integrity)

Optional verifier call:

- if `SHUNYAK_ALGOPLONK_VERIFY_APP_ID` and signer mnemonic are configured, backend attempts method call
- method defaults to `verify(byte[32][],byte[32][])bool`
- strict mode can be enabled with `SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY=true`

### 4.3 `/api/consent/register` Request Contract

```json
{
  "user_id": "demo-user-001",
  "claim_type": "age_over_18",
  "enterprise_pubkey": "<64-hex>",
  "expiry_days": 30,
  "identity_provider": "digilocker",
  "digilocker_request_id": "optional",
  "digilocker_redirect_url": "optional",
  "zk_backend": "algoplonk",
  "algoplonk_proof_hex": "required when zk_backend=algoplonk",
  "algoplonk_public_inputs_hex": "required when zk_backend=algoplonk"
}
```

### 4.4 `/api/consent/register` Response States

**Pending DigiLocker**

```json
{
  "ok": true,
  "status": "pending_digilocker_consent",
  "digilocker": {
    "request_id": "...",
    "auth_url": "https://dg-sandbox.setu.co/...",
    "status": "PENDING"
  }
}
```

**Consent Registered**

```json
{
  "ok": true,
  "status": "consent_registered",
  "txid": "...",
  "consent_token": "...",
  "identity_provider": "digilocker",
  "zk_backend": "algoplonk",
  "zk_verification_mode": "shape_verified|onchain_verified"
}
```

---

## 5. Module C: `shunyak-agent`

### 5.1 Dolios Agent Integration

The agent layer uses `dolios-agent` hardened branch as a library, not as a CLI process. The Vercel serverless function at `/api/agent/execute` bootstraps a lightweight Dolios orchestrator per-request, runs the agent loop for the specific task, streams events via SSE, and tears down.

**Critical Vercel constraint:** Vercel functions have a 60-second timeout on Pro (10 seconds on Hobby). The agent must complete within this window. Configure `max_iterations=5` for the demo — the task is simple (check consent → settle or block), not multi-step reasoning.

```python
# api/agent/execute.py
from dolios.orchestrator import DoliosOrchestrator
from dolios.config import DoliosConfig

async def handler(request):
    config = DoliosConfig.load()
    config.sandbox.enabled = False  # No NemoClaw on Vercel (no Landlock/seccomp on cloud)
    
    orchestrator = DoliosOrchestrator(config)
    # Run single-task agent with MCP tools
    result = await orchestrator.run_task(
        task=request.json["prompt"],
        mcp_tools=["verify_shunyak_compliance", "execute_algo_settlement"],
        stream_callback=sse_emit,
        max_iterations=5,
    )
    return result
```

**NemoClaw sandbox note:** Landlock and seccomp are Linux kernel features unavailable in Vercel's Lambda environment. Disable the NemoClaw sandbox layer for Vercel deployment. The security enforcement instead comes from: WorkflowPolicy DAG (pure Python, works anywhere), CredentialVault (pure Python, works anywhere), AuditLogger (pure Python, works anywhere), and Vercel's own network egress controls. Document this explicitly in HARDENED.md.

### 5.2 MCP Server and Tools

The MCP server runs in-process within the Vercel function (no separate server). Tools are registered as Python callables.

**Tool 1: `verify_shunyak_compliance`**

```python
# agent/tools/verify_compliance.py

CAPABILITIES = {
    "network": {"allow_domains": ["testnet-api.algonode.cloud"]},
    "filesystem": {"read": [], "write": []},
    "dlp_allowed": [],  # No sensitive data expected in args
}

async def verify_shunyak_compliance(
    user_pubkey: str,
    enterprise_pubkey: str,
) -> dict:
    """
    Query Algorand Box Storage to check if a valid consent record exists.
    Returns: {"valid": bool, "expires_at": int | None, "reason": str}
    """
    algod = AlgodClient("", "https://testnet-api.algonode.cloud")
    app_id = int(os.environ["SHUNYAK_APP_ID"])
    
    # Derive box key
    box_key = sha256(
        bytes.fromhex(user_pubkey) + 
        bytes.fromhex(enterprise_pubkey) + 
        app_id.to_bytes(8, "big")
    ).digest()
    
    try:
        box_data = algod.application_box_by_name(app_id, box_key)
        value = base64.b64decode(box_data["value"])
        expiry = int.from_bytes(value[32:40], "big")
        
        if expiry < int(time.time()):
            return {"valid": False, "expires_at": expiry, "reason": "consent_expired"}
        
        return {"valid": True, "expires_at": expiry, "reason": "consent_active"}
    
    except AlgodHTTPError:
        return {"valid": False, "expires_at": None, "reason": "no_consent_record"}
```

**Tool 2: `execute_algo_settlement`**

```python
# agent/tools/execute_settlement.py

CAPABILITIES = {
    "network": {"allow_domains": ["testnet-api.algonode.cloud"]},
    "filesystem": {"read": [], "write": []},
    "dlp_allowed": [],
}

async def execute_algo_settlement(
    recipient_address: str,
    amount_microalgo: int,
    memo: str,
) -> dict:
    """
    Construct and broadcast an Algorand payment transaction.
    Signing key is injected by CredentialVault — never in LLM context.
    Returns: {"txid": str, "confirmed_round": int}
    """
    # CredentialVault injects SHUNYAK_AGENT_MNEMONIC at this boundary
    mnemonic = vault.inject("SHUNYAK_AGENT_MNEMONIC")
    private_key = mnemonic_to_private_key(mnemonic)
    
    algod = AlgodClient("", "https://testnet-api.algonode.cloud")
    params = algod.suggested_params()
    
    txn = PaymentTxn(
        sender=account_from_mnemonic(mnemonic).address,
        sp=params,
        receiver=recipient_address,
        amt=amount_microalgo,
        note=memo.encode(),
    )
    signed = txn.sign(private_key)
    txid = algod.send_transaction(signed)
    
    result = wait_for_confirmation(algod, txid, 4)
    return {"txid": txid, "confirmed_round": result["confirmed-round"]}
```

### 5.3 WorkflowPolicy DAG

```yaml
# policies/workflow.yaml
version: "1.0"
policies:
  - tool: execute_algo_settlement
    requires:
      - tool: verify_shunyak_compliance
        status: success
    description: >
      Settlement is structurally blocked until compliance check passes.
      This is enforced at code level — the agent cannot bypass this via prompt.
```

This YAML is read by dolios-agent's `WorkflowPolicy` class. The `execute_algo_settlement` tool call is rejected at the dispatcher level if `verify_shunyak_compliance` has not returned `success` in the current session. The rejection is logged by `AuditLogger` with `event: workflow_blocked`.

### 5.4 CredentialVault Configuration

```python
# agent/shunyak_agent.py

vault = CredentialVault()
vault.load_from_env("SHUNYAK_AGENT_MNEMONIC", label="SHUNYAK_AGENT_MNEMONIC")
# After this call, SHUNYAK_AGENT_MNEMONIC is removed from os.environ
# The LLM context never sees the mnemonic value
```

### 5.5 Skill Capability Manifest

```yaml
# agent/skills/shunyak-compliance/capabilities.yaml
version: "1.0"
tool: shunyak-compliance
network:
  allow_domains:
    - testnet-api.algonode.cloud
    - testnet-idx.algonode.cloud
filesystem:
  read: []
  write: []
dlp_allowed: []
description: >
  Shunyak compliance skill. Network access restricted to Algorand testnet
  Algod/Indexer endpoints only. No PII or credential types expected in arguments.
```

---

## 6. Vercel Deployment Architecture

### 6.1 vercel.json

```json
{
  "framework": "nextjs",
  "functions": {
    "api/**/*.py": {
      "runtime": "vercel-python@4.x",
      "maxDuration": 60
    }
  },
  "routes": [
    { "src": "/api/(.*)", "dest": "/api/$1" },
    { "src": "/(.*)", "dest": "/frontend/$1" }
  ]
}
```

### 6.2 Environment Variables (Vercel Dashboard)

```
# Algorand
SHUNYAK_APP_ID=<deployed_contract_app_id>
SHUNYAK_CONSENT_SOURCE=hybrid
SHUNYAK_IDENTITY_PROVIDER=digilocker
SHUNYAK_ZK_BACKEND=algoplonk
ALGOD_TOKEN=                              # Empty for AlgoNode public endpoint
ALGOD_SERVER=https://testnet-api.algonode.cloud

# Agent wallet (testnet only — funded with test ALGO)
SHUNYAK_AGENT_MNEMONIC=<25 word mnemonic>

# Inference (for dolios-agent)
OPENROUTER_API_KEY=<key>

# Oracle
ORACLE_PRIVATE_KEY_HEX=<p256_private_key>
ORACLE_PUBLIC_KEY_HEX=<p256_public_key>   # Also registered in contract

# DigiLocker (Setu sandbox)
SHUNYAK_DIGILOCKER_BASE_URL=https://dg-sandbox.setu.co
SHUNYAK_DIGILOCKER_REDIRECT_URL=https://shunyak-protocol.vercel.app/consent
SHUNYAK_DIGILOCKER_CLIENT_ID=<setu_client_id>
SHUNYAK_DIGILOCKER_CLIENT_SECRET=<setu_client_secret>
SHUNYAK_DIGILOCKER_PRODUCT_INSTANCE_ID=<setu_product_instance_id>

# AlgoPlonk verifier integration
SHUNYAK_ALGOPLONK_VERIFY_APP_ID=<optional_verifier_app_id>
SHUNYAK_ALGOPLONK_VERIFY_METHOD_SIGNATURE=verify(byte[32][],byte[32][])bool
SHUNYAK_ALGOPLONK_REQUIRE_ONCHAIN_VERIFY=false
SHUNYAK_ALGOPLONK_SIMULATE_ONLY=false

# Feature flags
DOLIOS_SANDBOX_DISABLED=true              # Required on Vercel
DOLIOS_AIDLC_ENABLED=false               # Not needed for demo
DOLIOS_AUDIT_LOG=/tmp/shunyak-audit.jsonl # Ephemeral on Vercel — streamed to client
```

### 6.3 Python Runtime Requirements

```
# requirements.txt
py-algorand-sdk>=2.7.0
algosdk>=2.7.0
cryptography>=42.0
httpx>=0.27
pyyaml>=6.0
pydantic>=2.0
python-dotenv>=1.0

# dolios-agent hardened (local path for Vercel)
# Add as git dependency or copy dolios/ package into api/
```

### 6.4 Deployment Steps

```bash
# 1. Deploy Algorand contract
cd contracts/
algokit bootstrap
algokit deploy --network testnet
# Copy APP_ID to Vercel env vars

# 2. Fund agent wallet on testnet
# Use Algorand Testnet Dispenser: https://bank.testnet.algorand.network

# 3. Deploy to Vercel
vercel --prod
# Set all env vars in Vercel dashboard

# 4. Verify demo flow
# Open Vercel URL → run all 4 screens → confirm Testnet TXIDs and runtime status
```

---

## 7. Frontend Architecture

### 7.1 Tech Stack

- **Next.js 16** (App Router)
- **Tailwind CSS** — dark theme, minimal
- **Server-Sent Events** — real-time agent output streaming
- **AlgoExplorer links** — transaction confirmation visibility

### 7.2 Screen Designs

**Screen 1 — Consent Registration**
```
[Shunyak Protocol] — DPDP Consent Demo

User Identity Claim
  User ID: [demo-user-001          ]
  Claim:   [Age over 18  ▼        ]
  Identity Provider: [digilocker]
  zk Backend: [algoplonk]
  
  [Generate ZK Proof & Register Consent]

--- Live Output ---
  ✓ claim extracted: age_over_18
  ✓ identity provider check completed
  ✓ proof pipeline completed

  Branch A (digilocker first request)
  • status: pending_digilocker_consent
  • request_id + auth_url returned
  • user authorizes in DigiLocker and retries

  Branch B (registration complete)
  ✓ Submitting to Algorand Testnet...
  ✓ Transaction confirmed: [TXID link ↗]
  ✓ Consent token minted (stored in browser)
```

**Screen 2 — Blocked Path**
```
[Shunyak Protocol] — Agent Execution Demo

Agent Prompt:
  "Process financial history for user-999 and issue micro-loan"

  [Execute Agent →]

--- Agent Output (live) ---
  Δ Dolios ready. Running task...
  → Calling: verify_shunyak_compliance
    user_pubkey: ADDR1234...
    enterprise_pubkey: AAAA...
  ← Result: { valid: false, reason: "no_consent_record" }
  
  ✗ WorkflowPolicy: execute_algo_settlement BLOCKED
    Reason: verify_shunyak_compliance must succeed first
  
  Δ DPDP Compliance Failure. No active consent record found
    for user-999. Settlement blocked.

--- Audit Log ---
  { ts: "2026-04-15T...", event: "tool_allowed",   tool: "verify_shunyak_compliance" }
  { ts: "2026-04-15T...", event: "workflow_blocked", tool: "execute_algo_settlement" }
```

**Screen 3 — Authorized Path**
```
[Shunyak Protocol] — Agent Execution Demo

Agent Prompt:
  "Process financial history for user-001 and issue micro-loan"

  [Execute Agent →]

--- Agent Output (live) ---
  Δ Dolios ready. Running task...
  → Calling: verify_shunyak_compliance
    user_pubkey: ADDR5678...
  ← Result: { valid: true, expires_at: 1747... }
  
  ✓ WorkflowPolicy: execute_algo_settlement AUTHORIZED
  → Calling: execute_algo_settlement
    recipient: ADDR5678...
    amount: 1000000 microALGO (1 ALGO)
  ✓ CredentialVault: signing key injected at boundary
  ← Result: { txid: "ABC123...", confirmed_round: 45821 }
  
  Δ Micro-loan disbursed. [View on Testnet ↗]

--- Audit Log ---
  { ts: "...", event: "tool_allowed",       tool: "verify_shunyak_compliance" }
  { ts: "...", event: "credential_injected", label: "SHUNYAK_AGENT_MNEMONIC" }
  { ts: "...", event: "tool_allowed",       tool: "execute_algo_settlement" }
```

---

## 8. Implementation Roadmap

### Day 1 — Contracts + Consent Anchor
- Write `ShunyakConsent.py` with AlgoKit 4.0
- Implement `register_consent`, `revoke_consent`, `check_status` with Box Storage
- Implement consent claim hashing and consent note anchoring
- Add verifier-app integration plan for strict AlgoPlonk checks
- Deploy to Algorand Testnet, note APP_ID
- Write contract tests with `pytest`

### Day 2 — Agent Layer
- Configure dolios-agent hardened branch as library
- Write `verify_shunyak_compliance` MCP tool with algosdk
- Write `execute_algo_settlement` MCP tool
- Write `policies/workflow.yaml` DAG constraint
- Write `capabilities.yaml` for shunyak-compliance skill
- Wire CredentialVault for mnemonic injection
- Test agent loop end-to-end locally (blocked path + authorized path)
- Confirm AuditLogger output for both paths

### Day 3 — Vercel + Frontend
- Scaffold Next.js app with Tailwind
- Implement `/api/consent/register.py` with identity provider and zk backend switches
- Add Setu DigiLocker adapters (`api/_common/digilocker.py`)
- Add zk adapters (`api/_common/zk.py`) with optional AlgoPlonk verifier call
- Implement `/api/agent/execute.py` with SSE streaming
- Implement `/api/audit/log.py`
- Extend consent UI for pending DigiLocker + AlgoPlonk payload input
- Wire SSE client in React components
- Configure `vercel.json`

### Day 4 — Integration + Deploy
- Set all env vars in Vercel dashboard
- Fund agent wallet from Testnet Dispenser
- Configure DigiLocker sandbox credentials (when provider is enabled)
- Configure AlgoPlonk verifier app id (when strict verification is enabled)
- Full end-to-end test against Testnet from Vercel URL
- Fix any timeout issues (tune `max_iterations`)
- Record demo walkthrough video as backup
- Submit

---

## 9. Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| AlgoPlonk verifier opcode budget limits on testnet | Medium | Keep fallback mode (`shape_verified`) for demo and enable strict mode only when verifier app path is proven |
| DigiLocker sandbox outages or expired auth links during demo | Medium | Pre-generate fresh request IDs and verify sandbox health before demo window |
| Vercel 60s timeout exceeded by agent loop | Medium | Set `max_iterations=5`, pre-warm with simple task |
| NemoClaw sandbox unavailable on Vercel Lambda | Certain | Disable sandbox, compensate with WorkflowPolicy + CredentialVault + AuditLogger |
| Algod public endpoint rate limits during demo | Low | Use AlgoNode (generous free tier), add retry logic |
| dolios-agent hardened library import issues on Vercel | Medium | Copy `dolios/security/` directly into `api/` if path resolution fails |
| Agent mnemonic accidentally logged | Low | CredentialVault clears env var, AuditLogger hashes args — belt and suspenders |

---

## 10. Key URLs for Demo

- Algorand Testnet Dispenser: `https://bank.testnet.algorand.network`
- Testnet Block Explorer: `https://lora.algokit.io/testnet`
- AlgoNode Testnet Algod: `https://testnet-api.algonode.cloud`
- AlgoKit docs: `https://developer.algorand.org/docs/get-started/algokit`
- Vercel Python runtime: `https://vercel.com/docs/functions/runtimes/python`
- Setu DigiLocker docs: `https://docs.setu.co`
- AlgoPlonk repository: `https://github.com/giuliop/AlgoPlonk`
