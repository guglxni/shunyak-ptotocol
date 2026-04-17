# Contributing

Thanks for contributing to Shunyak Protocol.

## 1. Development Setup

1. Clone the repository.
2. Install frontend dependencies.
3. Create and activate Python virtual environment.
4. Install Python dependencies.

```bash
git clone https://github.com/guglxni/shunyak-ptotocol.git
cd shunyak-ptotocol
cd frontend && npm install && cd ..
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Branching and Commits

- Use a dedicated branch per change.
- Keep commit messages clear and scoped.
- Recommended format:
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `chore: ...`

## 3. Pull Request Checklist

Before opening a PR:

- [ ] Frontend builds successfully (`frontend`)
- [ ] Python tests pass (scoped project tests)
- [ ] No secrets or credentials are committed
- [ ] Documentation is updated for behavior/config changes
- [ ] Risky runtime/security changes include rationale

## 4. Testing Commands

```bash
# Frontend build
cd frontend && npm run build

# Python tests (project-scoped)
cd ..
.venv/bin/python -m pytest -c pytest.ini -q
```

## 5. Security and Secrets

- Never commit real mnemonics, API keys, or Vercel tokens.
- Use `.env` for local secrets and Vercel environment variables for deployed secrets.
- Follow `SECURITY.md` for vulnerability handling.

## 6. Documentation Expectations

If your change affects behavior, update at least one of:
- `README.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/testnet-deployment.md`

## 7. What to Include in PR Description

- Problem statement
- What changed
- How it was tested
- Any migrations, env var changes, or rollout steps
