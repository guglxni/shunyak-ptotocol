# Integration Test Instructions

1) Run local environment

vercel dev

2) Validate consent registration flow

- Open /consent
- Submit demo-user-001
- Confirm tx id and audit entry

3) Validate blocked execution flow

- Open /blocked
- Execute with user-999
- Confirm status blocked and workflow_blocked audit event

4) Validate authorized execution flow

- Open /authorized
- Execute with demo-user-001
- Confirm settlement tx id and credential_injected + tool_allowed audit events
