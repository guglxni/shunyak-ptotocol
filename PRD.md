# PRD.md — Shunyak Protocol
**Project:** Shunyak Protocol  
**Stage:** Hackathon MVP with Live Demo  
**Author:** Aaryan Guglani  
**Version:** 2.2 — DigiLocker + AlgoPlonk Real-Mode Edition  
**Deployment Target:** Vercel (frontend + API) + Algorand Testnet  

---

## 1. Executive Summary

Shunyak Protocol is a Zero-Knowledge governed consent layer built natively on Algorand. Autonomous AI agents must cryptographically verify user consent on-chain before executing any data processing or financial settlement, enforcing India's DPDP Act at the infrastructure level, not the policy level.

The MVP now runs in real-mode identity and proof wiring:

- `digilocker` identity via Setu sandbox request creation, consent redirection, status polling, and Aadhaar-backed claim checks
- `algoplonk` proof/public-input ingestion with optional on-chain verifier app checks on Algorand

The agent layer is built on `guglxni/dolios-agent` (hardened branch), which provides structural enforcement of tool ordering via DAG workflow policy, credential boundary injection, and append-only audit logging — making the compliance guarantee architectural rather than prompt-based.

The demo is a full-stack web application deployed on Vercel that walks judges through the complete consent lifecycle in real time against Algorand Testnet.

---

## 2. The Problem

Indian enterprises deploying autonomous AI agents face a structural compliance gap under the DPDP Act 2023: agents cannot legally process user data or initiate financial transactions without verifiable, purpose-limited, revocable consent. Centralized KYC databases are a data-leak liability. Existing solutions are:

- **Audit-after-the-fact**: Log what happened, verify later. Insufficient for DPDP.
- **Prompt-level guardrails**: The agent is *told* to check consent. Can be bypassed.
- **Centralized consent stores**: Single point of failure, honeypot risk.

Shunyak inverts this: the agent is *structurally incapable* of executing without a valid on-chain consent record. The enforcement is at the code level via dolios-agent's WorkflowPolicy DAG, not at the prompt level.

---

## 3. Why Algorand

| Property | Why It Matters for Shunyak |
|----------|---------------------------|
| AVM v10 ZK compatibility | Optional AlgoPlonk verifier app-call path, while contract enforces registrar attestation and consent anchoring |
| Sub-3-second finality | Agent governance checks don't block the execution loop |
| 0.001 ALGO fees | High-frequency consent queries are economically viable |
| Box Storage | Per-user consent records without global state bloat |
| PyTeal + AlgoKit 4.0 | Native Python — compatible with dolios-agent's Python stack |

---

## 4. Why Dolios Agent (Hardened Branch)

The hardened branch adds five IronClaw-inspired security features that are directly relevant to Shunyak's compliance story:

| Feature | Shunyak Relevance |
|---------|------------------|
| WorkflowPolicy DAG | `execute_algo_settlement` is structurally blocked until `verify_shunyak_compliance` returns True — enforced at code level |
| CredentialVault | Agent's Algorand signing key never enters LLM context. Injected only at settlement call boundary |
| AuditLogger | Every compliance check, every settlement, every blocked call logged as append-only JSON lines — the DPDP audit trail |
| DLPScanner | Outbound tool arguments scanned for Aadhaar, PAN, private key patterns before dispatch |
| Per-tool Capabilities | `verify_shunyak_compliance` whitelisted to Algod/Indexer endpoints only. `execute_algo_settlement` gets signing key injection. Nothing bleeds across |

---

## 5. Target Personas

**Data Fiduciaries (Indian Enterprises):** Need an immutable, timestamped, mathematically provable audit trail of user consent to present to the Data Protection Board upon request. The AuditLogger + Algorand immutability provides this.

**AI Agents (Dolios instances):** Need a binary governance signal before executing tasks. The `verify_shunyak_compliance` MCP tool provides exactly this — True/False with reason.

**End Users:** Need to prove identity criteria (age, citizenship) to enterprises without exposing raw personal data. DigiLocker sandbox consent + selective claim attestation creates a practical bridge toward production selective disclosure.

**Hackathon Judges:** Need to see the full lifecycle working live in a browser within 3 minutes. The Vercel demo provides this.

---

## 6. MVP Scope — Three Track Architecture

### Track 3 — RegTech (The Base Layer)
User authenticates via the Shunyak web portal through Setu DigiLocker sandbox request creation, redirect-based consent, and status polling. Once authenticated, Aadhaar response data is used for claim checks (e.g., age and country).

The proof path uses AlgoPlonk payload ingestion with shape validation and optional on-chain verifier call.

Consent metadata is then anchored to Algorand Testnet (note transaction and optional app-box verification in hybrid mode), producing a verifiable consent record for agent gating.

### Track 2 — Agentic Commerce (The Middle Layer)
An enterprise operator prompts the Dolios agent via the web interface: "Process User X's financial history and issue a micro-loan if they qualify." The dolios-agent's WorkflowPolicy DAG structurally forces `verify_shunyak_compliance` to be called first. The MCP server queries Algorand Box Storage. If no valid record exists, the agent is blocked. The AuditLogger records the blocked event.

### Track 1 — Future of Finance (The Execution Layer)
When consent is valid, the agent calls `execute_algo_settlement`. The CredentialVault injects the signing key at the execution boundary. An Algorand Atomic Transfer is constructed and broadcast to Testnet — USDCa disbursement. The AuditLogger records the settlement with transaction ID.

---

## 7. Demo Flow (What Judges See)

The Vercel web app walks through four screens in sequence:

**Screen 1 — Consent Registration:**
User enters identity claim and chooses identity + zk backend modes.

- If DigiLocker is selected with no request id yet, UI returns `pending_digilocker_consent` and shows auth URL.
- After user completes DigiLocker consent, re-submit with request id to finalize.

Portal then shows proof handling and the Algorand transaction submission with Testnet explorer link.

**Screen 2 — Agent Execution (Blocked Path):**
Operator types a prompt with a user who has NO consent record. Shows the dolios-agent's WorkflowPolicy blocking the settlement call. Shows the AuditLogger entry: `event: workflow_blocked`. Shows the agent's response: "DPDP Compliance Failure."

**Screen 3 — Agent Execution (Authorized Path):**
Same prompt with the user from Screen 1 who HAS a valid consent record. Shows `verify_shunyak_compliance` returning True. Shows the Atomic Transfer being constructed and broadcast. Displays the settlement transaction ID on Testnet. Shows AuditLogger: `event: tool_allowed`, `event: credential_injected`.

**Screen 4 — SDK + Runtime Showcase:**
Displays live Algod/Indexer snapshot, signer balance readiness, consent/identity/zk runtime configuration, and settlement mode metadata.

Total demo runtime: under 3 minutes.

---

## 8. Success Metrics

- DigiLocker sandbox flow reaches authenticated state and maps to Aadhaar-backed claim attestation
- `algoplonk` payload path validates proof/public-input structure and claim-hash anchoring
- Optional AlgoPlonk on-chain verifier call succeeds when verifier app is configured
- Dolios agent halts and returns "DPDP Compliance Failure" for missing/expired consent
- Dolios agent successfully broadcasts an Atomic Transfer to Algorand Testnet for valid consent
- Full lifecycle visible in the Vercel demo within 3 minutes
- AuditLogger produces readable JSON lines entries for every event in the demo

---

## 9. Out of Scope for MVP

- Universal production zkTLS implementation (Reclaim Protocol / TLSNotary) across providers
- Trusted setup lifecycle operations and deterministic proof generation pipeline hosting for AlgoPlonk
- Production DPDP regulatory filing integration
- Multi-enterprise consent routing
- Consent expiry cron jobs
- Mobile interface
