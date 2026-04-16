# Hardened Deployment Notes

## Vercel Runtime Constraints

NemoClaw sandbox primitives (Landlock/seccomp) are not available in Vercel serverless runtime.
For this deployment target, sandbox is disabled and security posture relies on:

- WorkflowPolicy DAG ordering (settlement requires successful compliance check)
- CredentialVault boundary injection pattern
- DLP pre-dispatch argument scanner for sensitive patterns
- Append-only audit logging semantics
- Per-tool capability declarations
- MCP capability policy enforcement before tool dispatch
- Signed stateless consent tokens for cross-function authorization continuity
- Hybrid on-chain consent verification (app box + note fallback strategy)
- Operator-token authentication + consent-token requirement for execution endpoints
- In-memory request-rate and spend-window throttles for settlement calls
- Signed stateless stream-ticket handshake for SSE (consent token removed from URL query transport)
- Registrar-gated contract write methods with on-chain attestation signature checks

## Guardrail Mapping

- Tool ordering: policies/workflow.yaml
- Credential handling: agent/shunyak_agent.py + agent/tools/execute_settlement.py
- Audit trail: api/_common/audit.py
- Capability surface: agent/skills/shunyak-compliance/capabilities.yaml
- Stateless consent token mint/verify: api/_common/token.py
- DLP scanner: agent/tools/dlp_guard.py
- On-chain consent verifiers: api/_common/algorand.py + agent/tools/verify_compliance.py

## Migration to full hardened runtime

For non-serverless Linux environments, re-enable sandbox in dolios.yaml and validate policy bridge against generated NemoClaw policy output.

## Production fail-closed mode

Set `SHUNYAK_REQUIRE_HARDENED=true` to disable fallback runtime behavior. In this mode,
the API returns an initialization error if the hardened Dolios runtime cannot be loaded.

Deployed environments (`VERCEL=1` or `VERCEL_ENV in {preview, production}`) now enforce
this fail-closed behavior automatically.

## Settlement fallback policy

Set `SHUNYAK_SETTLEMENT_ALLOW_MOCK_FALLBACK=false` for demo/production to prevent
mock settlement tx ids from being emitted when real on-chain settlement fails.

## Agent execution endpoint policy

- Set `SHUNYAK_REQUIRE_OPERATOR_AUTH=true` and configure `SHUNYAK_OPERATOR_TOKEN`.
- Set `SHUNYAK_REQUIRE_EXECUTION_TOKEN=true` to require subject-bound consent tokens for execution.
- Bound transfer amounts with `SHUNYAK_MAX_SETTLEMENT_MICROALGO`.
- Enforce request/spend windows with `SHUNYAK_RATE_LIMIT_WINDOW_SECONDS`,
  `SHUNYAK_RATE_LIMIT_MAX_REQUESTS`, `SHUNYAK_RATE_LIMIT_MAX_PER_USER`,
  and `SHUNYAK_RATE_LIMIT_SPEND_MICROALGO`.

## Stream ticket signing policy

Set `SHUNYAK_STREAM_TICKET_SECRET` in deployed environments. If unset, stream
ticket signing falls back to `SHUNYAK_DEMO_SECRET`. Both should be non-default
values in deployed environments.

## CORS policy

Configure `SHUNYAK_ALLOWED_ORIGINS` in deployed environments to explicit trusted origins.
If unset in deployed mode, CORS responses fail closed (no permissive wildcard).

## Consent token signing policy

Set `SHUNYAK_DEMO_SECRET` to a non-default secret in deployed environments.
Deployed runtimes fail closed for consent token mint/validation when the secret is
missing or still set to the default demo value.

In non-deployed environments, insecure fallback token secret is disabled by default;
set `SHUNYAK_ALLOW_INSECURE_DEMO_SECRET=true` only for isolated local demos.
