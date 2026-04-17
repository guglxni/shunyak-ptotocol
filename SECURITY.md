# Security Policy

## Supported Scope

Security support is provided for the default `main` branch and current deployment configuration.

| Branch | Supported |
| --- | --- |
| `main` | Yes |
| Historical branches/tags | Best effort |

## Reporting a Vulnerability

If you find a security issue, please report it responsibly.

Preferred path:
1. Use GitHub private vulnerability reporting for this repository.
2. Include reproduction steps, affected files/endpoints, and impact.
3. Include mitigation suggestions if available.

Please avoid opening public issues for unpatched vulnerabilities.

## What to Include in Reports

- Type of issue (auth bypass, key leakage, injection, etc.)
- Impact and attack preconditions
- Affected components (API route, agent tool, contract function)
- Proof-of-concept details
- Suggested fix or defensive direction

## Security Baselines in This Repo

- Consent and stream token signing secrets are required in deployed mode.
- Operator and execution-token controls are available for execution endpoints.
- Settlement and rate limits are configurable with fail-closed options.
- Registrar-gated contract writes are enforced for consent state mutation.

## Security Hardening References

- `HARDENED.md`
- `docs/security-audit-remediation-2026-04-16.md`
- `docs/codebase-review-security-audit-2026-04-16.md`

## Disclosure Process

After receiving a report:
1. We triage and confirm impact.
2. We prepare and test a fix.
3. We release patch notes and mitigation guidance.
4. We credit reporters when appropriate.
