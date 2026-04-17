# Shunyak Protocol Documentation

This directory is the canonical documentation set for architecture, deployment, security posture, and demo operations.

## Documentation Catalog

| Document | Audience | Purpose |
| --- | --- | --- |
| `architecture.md` | Engineers, reviewers | Runtime topology, execution flows, trust boundaries, data model |
| `deployment.md` | DevOps, demo operators | End-to-end deployment and smoke testing runbook |
| `testnet-deployment.md` | Auditors, maintainers | Verified TestNet snapshot and on-chain references |
| `well-architected-checklist.md` | Engineering leads, reviewers | Security/reliability/operations checklist and release gates |
| `diagrams/README.md` | Writers, maintainers | Diagram index, source-of-truth mapping, and validation policy |
| `diagrams/shunyak-system-context.html` | Stakeholders, judges | Presentation-grade system context diagram |
| `diagrams/shunyak-consent-flow.html` | Stakeholders, judges | Consent registration sequence diagram |
| `diagrams/shunyak-guardrail-flow.html` | Stakeholders, judges | Guarded execution branch diagram |
| `security-audit-remediation-2026-04-16.md` | Security reviewers | Security fixes and implementation evidence |
| `codebase-review-security-audit-2026-04-16.md` | Security reviewers | Findings and risk analysis |
| `algobharat-round2-mvp-decisions.md` | Product + engineering | MVP tradeoffs and round-specific decisions |

## Root Documents

- `../README.md` - project overview and quick-start
- `../PRD.md` - product requirements and scope
- `../SPEC.md` - technical specification and implementation contracts
- `../HARDENED.md` - hardening and security controls
- `../CHANGELOG.md` - release-oriented history

## Reading Paths by Goal

### New contributor onboarding
1. `../README.md`
2. `architecture.md`
3. `deployment.md`
4. `../HARDENED.md`

### Security review
1. `architecture.md`
2. `../HARDENED.md`
3. `security-audit-remediation-2026-04-16.md`
4. `codebase-review-security-audit-2026-04-16.md`
5. `well-architected-checklist.md`

### Demo operation
1. `deployment.md`
2. `testnet-deployment.md`
3. `../README.md` (Demo Walkthrough section)

## Documentation Standards

When updating docs:
- keep architecture diagrams in Mermaid for in-repo diffability
- include text alternatives for non-trivial diagrams
- update `Last updated` metadata when topology or deployment changes
- validate diagrams before merge and refresh HTML exports when source diagrams change
