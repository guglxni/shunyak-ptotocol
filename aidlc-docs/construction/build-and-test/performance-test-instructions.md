# Performance Test Instructions

## API latency sanity checks

- /api/consent/register should respond under 1.5 seconds in local mode
- /api/agent/execute should respond under 3 seconds in local mode

## Vercel timeout guard

- Ensure total /api/agent/execute runtime remains under configured function maxDuration (60 seconds)
- Keep max agent iterations constrained in future LLM-connected version
