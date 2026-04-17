# Diagram Index and Standards

This directory contains presentation-grade HTML exports used in demos and external submissions.

## Diagram Catalog

| Diagram | File | Source of Truth |
| --- | --- | --- |
| System context | `shunyak-system-context.html` | Mermaid blocks in `README.md` and `docs/architecture.md` |
| Consent registration flow | `shunyak-consent-flow.html` | Mermaid blocks in `docs/architecture.md` and `docs/dorahacks-buidl-description.md` |
| Guarded execution flow | `shunyak-guardrail-flow.html` | Mermaid blocks in `README.md`, `docs/architecture.md`, and `docs/dorahacks-buidl-description.md` |

## Validation Policy

- Keep Mermaid source diagrams in versioned markdown files for reviewable diffs.
- Include text alternatives after each non-trivial diagram.
- Regenerate HTML exports when diagram logic changes.
- Validate Mermaid syntax before commit.

## Last Validation

- Date: 2026-04-17
- Method: Rendered all Mermaid blocks from README and docs using Mermaid renderer.
- Result: All diagrams parsed and rendered successfully.
