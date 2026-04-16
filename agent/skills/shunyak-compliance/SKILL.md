# Shunyak Compliance Skill

This skill enforces DPDP consent checks before any settlement execution.

## Tools

- verify_shunyak_compliance
- execute_algo_settlement

## Guardrails

- Settlement is blocked unless compliance verification succeeds in the same session.
- Signing credential is injected at execution boundary only.
- Audit entries are appended for every allow/block/injection event.
