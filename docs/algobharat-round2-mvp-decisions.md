# AlgoBharat Round 2 MVP Decisions

## Official Source Snapshot

Primary sources reviewed:

- https://algobharat.in/hack-series3/
- https://dorahacks.io/hackathon/hack-series-3
- https://dorahacks.io/hackathon/hack-series-3/detail
- https://dorahacks.io/hackathon/hack-series-3/tracks

Key signals:

- Round 2 requires one core feature implemented end-to-end with full functionality.
- Required flow: UI -> blockchain interaction -> transaction confirmation.
- Submission requires repository link and demo video.
- "Working product, not a prototype" is explicitly required.

## Engineering Decisions

### 1. Consent Verification Strategy

Decision: `SHUNYAK_CONSENT_SOURCE=hybrid` for Round 2.

Rationale:

- Supports app-box verification when contract/app is configured.
- Falls back to note-based on-chain verification to preserve demo reliability.
- Keeps direct Algorand integration and transaction confirmation intact.

### 2. Settlement Strategy

Decision: default ALGO settlement with optional ASA mode via `SHUNYAK_USDCA_ASA_ID`.

Rationale:

- ALGO path is robust for live demo conditions.
- ASA path can be enabled when recipient opt-in and asset config are confirmed.

### 3. Hardened Runtime Policy

Decision: enable `SHUNYAK_REQUIRE_HARDENED=true` in production demo environment.

Rationale:

- Fail-closed behavior prevents silent fallback at demo time.
- Improves credibility for security/compliance judges.

### 4. Runtime Observability

Decision: expose engine configuration in `/api/algorand/showcase`.

Rationale:

- Judges can verify consent source mode and settlement mode quickly.
- Reduces ambiguity during live walkthrough.

## Demo-Readiness Checklist

- Signer account funded and warning flag clear in `/showcase`.
- Consent flow returns `tx_mode: testnet_onchain`.
- Blocked path returns DPDP compliance failure.
- Authorized path returns settlement txid and explorer link.
- SSE stream visible in agent terminal output.
- Scoped tests pass via `python -m pytest -c pytest.ini -q`.

## Deferred for Round 3 Hardening

- Strict box-only consent mode as default in all environments.
- Full contract deployment + typed client automation in CI pipeline.
- Comprehensive negative/security test suite for DLP and policy bypass attempts.
