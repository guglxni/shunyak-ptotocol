# Codebase Review + Security Audit Report

**Repository:** `shunyak-ptotocol`  
**Date:** 2026-04-16  
**Scope:** `api/`, `agent/`, `contracts/`, `frontend/`, runtime/config files

## 1. Executive Summary

This review found **material security and reliability issues** in the current codebase, including:

1. **Critical consent-integrity gap** in the on-chain contract path (proof not cryptographically enforced on-chain).
2. **Critical abuse path** in unauthenticated settlement execution APIs.
3. **High-severity operational breakages** (syntax/runtime errors in consent APIs).

The project has strong architectural intent (workflow gating, capability policy, audit logging, fail-closed toggles), but current implementation still permits high-impact abuse and runtime failure in important paths.

---

## 2. Requested Skill Packs Used

I used the requested skill sources and mapped them to this repo's stack:

| Requested source | How it was used in this audit | Applicability |
|---|---|---|
| `algorand-devrel/algorand-agent-skills` | Algorand-specific review framing + integration expectations | **High** |
| `agamm/claude-code-owasp` | OWASP 2025/2026 checklist for API, authz, error handling, token handling | **High** |
| `OpenZeppelin/openzeppelin-skills` | Secure-contract design heuristics and library-first security patterns | **Medium** (mostly EVM-oriented) |
| `pashov/skills` | Solidity-auditor/x-ray methodology reviewed; checked for Solidity scope | **Low** (no `.sol` files in target repo) |

I also invoked available in-environment skills:
- `algorand-vulnerability-scanner`
- `security-auditor`
- `code-review-expert`
- `security`
- `solidity-auditor`

---

## 3. What Was Executed

### 3.1 Runtime and test checks

- Python compile check on API/agent/contracts:
  - `python -m compileall -q api agent contracts`
  - **Result:** `IndentationError` in `api/consent/status.py` line 41.
- Pytest:
  - `python -m pytest -c pytest.ini -q`
  - **Result:** `2 passed, 1 skipped`.

### 3.2 Dependency checks

- Frontend npm audit:
  - `npm audit --omit=dev --json`
  - **Result:** `1 high` vulnerability (`next`), multiple GH advisories in affected range.
- `pip-audit`:
  - Not available in the project virtualenv.

### 3.3 Static/security analyzers

- Semgrep:
  - CLI present but broken at runtime (`ModuleNotFoundError: opentelemetry._logs`), scan could not be completed.
- Tealer (Algorand):
  - Executed on compiled TEAL artifacts.
  - Reported `rekey-to` and `missing-fee-check` findings; these are likely detector false positives for this **stateful app call** pattern (detectors are more logic-signature oriented), but still noted below for manual confirmation.

---

## 4. Findings (Prioritized)

## 4.1 Critical

### C-01: On-chain consent can be registered without cryptographic proof verification
**Location:** `contracts/shunyak_consent.py:89-112`  
**Details:** `register_consent()` checks proof/input lengths but does not verify proof validity on-chain before `App.box_put`.  
**Impact:** A direct app caller can register consent state without valid identity/claim proof, undermining the core compliance guarantee.  
**Recommendation:** Add explicit on-chain proof or attestation verification gate before state write.

### C-02: Settlement execution endpoint is unauthenticated and caller-controlled
**Location:** `api/agent/execute.py`, `api/agent/stream.py`, `agent/shunyak_agent.py`  
**Details:** No API authn/authz guard; caller controls `amount_microalgo`; no hard spend/rate controls at API boundary.  
**Impact:** Abuse can trigger unauthorized repeated settlement attempts from the signer wallet when consent context passes.  
**Recommendation:** Require authenticated operator identity, bind execution rights to identity + consent subject, enforce max per-request/per-user/per-window limits, add server-side rate limiting.

## 4.2 High

### H-01: Consent status API has syntax error and cannot compile
**Location:** `api/consent/status.py:41`  
**Details:** Indentation mismatch in token-validation branch.  
**Impact:** Endpoint load/runtime failure in critical consent-status path.  
**Recommendation:** Fix indentation; add compile gate in CI (`py_compile`/`compileall`) for all API modules.

### H-02: Runtime `NameError` risk in consent register flow
**Location:** `api/consent/register.py:471`  
**Details:** `box_validation_reason` is referenced but not defined in the source file.  
**Impact:** Successful registration path can fail with 5xx, breaking consent issuance flow.  
**Recommendation:** Initialize and set `box_validation_reason` deterministically, and add integration test for successful register path.

### H-03: Open CORS policy on sensitive API surfaces
**Location:** `api/_common/http.py:12-14`, `api/agent/stream.py:16-18`  
**Details:** `Access-Control-Allow-Origin: *` with broad methods/headers.  
**Impact:** Cross-origin abuse is easier against unauthenticated endpoints and tokenized flows.  
**Recommendation:** Restrict origins by environment allowlist, tighten methods, and require authenticated requests.

### H-04: Known high-severity Next.js dependency advisories
**Location:** `frontend/package.json` (`next@^14.2.35`)  
**Details:** npm audit reports high-severity advisories affecting current range.  
**Impact:** Exposure to known DoS/request-handling weaknesses depending on deployment/runtime behavior.  
**Recommendation:** Upgrade to patched Next.js release range and verify compatibility.

## 4.3 Medium

### M-01: Consent token sent in URL query for SSE flow
**Location:** `frontend/lib/api.ts:235-241`, `api/agent/stream.py:31`  
**Details:** `consent_token` included in query string.  
**Impact:** Token leakage via logs/history/proxies/analytics; replay risk until expiry.  
**Recommendation:** Move token to header or POST body; never place bearer-style tokens in URLs.

### M-02: Default demo signing secret for non-deployed environments
**Location:** `api/_common/token.py:13-33`  
**Details:** Falls back to `"shunyak-demo-secret"` when not deployed and env secret unset.  
**Impact:** Token forgery in misconfigured shared/staging-like environments.  
**Recommendation:** Require explicit high-entropy secret in all environments except isolated local dev.

### M-03: Broad exception handling may mask security-relevant failures
**Location:** multiple (`api/_common/algorand.py`, `api/agent/stream.py`, `agent/shunyak_agent.py`)  
**Details:** Multiple `except Exception` with generic fallback behavior.  
**Impact:** Security signal loss, degraded detection of active abuse/misconfiguration.  
**Recommendation:** Narrow exception types and preserve structured error reason telemetry.

## 4.4 Low / Informational

### L-01: Semgrep environment broken, reducing automated coverage
**Details:** Semgrep fails with missing `opentelemetry._logs` module in environment.  
**Impact:** Automated SAST depth reduced for this run.  
**Recommendation:** Repair semgrep runtime or run in isolated CI container.

### L-02: Requested Solidity-focused audit path not applicable to repo scope
**Details:** No `.sol` files present; Pashov Solidity auditor/x-ray methods are largely N/A here.  
**Impact:** No issue in code itself; just methodology mismatch for this stack (PyTeal/Python/Next.js).  
**Recommendation:** Keep Algorand-native scanners and Python/TS SAST as primary gates.

---

## 5. Algorand-Specific Review Matrix (11-pattern scanner alignment)

| Pattern | Status | Notes |
|---|---|---|
| Rekeying field validation | **N/A/Flagged by tool** | Tealer flagged on generated TEAL; likely false positive for this stateful app path, still review manually. |
| Missing fee checks | **N/A/Flagged by tool** | Similar caveat as above. |
| CloseRemainderTo / AssetCloseTo | **N/A** | Contract methods are app calls, not direct payment/asset transfer handlers. |
| Group size / ordering | **N/A** | No grouped cross-txn assumptions in contract methods. |
| Access controls (update/delete) | **Pass** | `OnCompleteAction.never()` for update/delete. |
| Asset ID checks / opt-in DoS / inner fee | **N/A** | No asset movement in contract logic itself. |
| Clear state misuse | **Pass/N/A** | Controlled via router bare-call config. |

Most important Algorand risk here is **not** one of the generic 11 checklist items; it is the missing cryptographic verification in `register_consent` before writing consent state.

---

## 6. Positive Security Controls Observed

1. Workflow policy DAG enforces settlement-after-compliance ordering (`policies/workflow.yaml`).
2. Capability policy enforcement in MCP wrapper (`agent/mcp_server.py`).
3. Credential injection boundary pattern with vault handling (`agent/shunyak_agent.py`).
4. Audit log writes hash tool args instead of raw sensitive payload (`api/_common/audit.py`).
5. Deployed-environment guardrails for token secret and hardened runtime requirement (`api/_common/token.py`, `api/_common/constants.py`, `agent/dolios_bridge.py`).

---

## 7. Priority Remediation Plan

1. **Immediate (blocker):**
   - Fix `api/consent/status.py` indentation and `api/consent/register.py` undefined variable.
   - Add CI compile gate for all Python API modules.
2. **Security-critical hardening:**
   - Enforce real on-chain proof/attestation verification inside contract before consent write.
   - Add API authentication/authorization + rate/spend limits for agent execution endpoints.
3. **Exposure reduction:**
   - Remove wildcard CORS for sensitive APIs.
   - Move consent tokens out of query strings.
4. **Dependency and tooling:**
   - Upgrade Next.js to patched range.
   - Repair semgrep runtime in CI and add repeatable SAST gate.

---

## 8. Overall Rating

**Current production-readiness security rating: _Needs major fixes before production_.**  
The architecture is promising, but the consent-proof integrity gap and unauthenticated execution surface are high-priority blockers.

