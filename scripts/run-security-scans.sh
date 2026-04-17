#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${REPORT_DIR:-security-reports}"
SCAN_VENV="${SCAN_VENV:-$ROOT_DIR/.tmp-security-venv}"
SEMGREP_BIN="${SEMGREP_BIN:-}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required to run security scans." >&2
  exit 1
fi

mkdir -p "$REPORT_DIR"

echo "[1/6] Preparing isolated scan virtual environment"
if [[ ! -d "$SCAN_VENV" ]]; then
  python3 -m venv "$SCAN_VENV"
fi
"$SCAN_VENV/bin/python" -m pip install --quiet --upgrade pip
"$SCAN_VENV/bin/python" -m pip install --quiet bandit detect-secrets pip-audit

if [[ -z "$SEMGREP_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/pysemgrep" ]]; then
    SEMGREP_BIN="$ROOT_DIR/.venv/bin/pysemgrep"
  elif command -v pysemgrep >/dev/null 2>&1; then
    SEMGREP_BIN="$(command -v pysemgrep)"
  else
    "$SCAN_VENV/bin/python" -m pip install --quiet --only-binary=:all: "semgrep==1.159.0"
    SEMGREP_BIN="$SCAN_VENV/bin/pysemgrep"
  fi
fi

if [[ ! -x "$SEMGREP_BIN" ]]; then
  echo "Error: could not resolve a working pysemgrep executable." >&2
  exit 1
fi

echo "[2/6] Running Bandit (first-party Python code)"
"$SCAN_VENV/bin/python" -m bandit -r api agent contracts -x contracts/tests -f json -o "$REPORT_DIR/bandit.json" || true

echo "[3/6] Running pip-audit"
"$SCAN_VENV/bin/python" -m pip_audit -r requirements.txt -f json -o "$REPORT_DIR/pip-audit.json" || true

echo "[4/6] Running npm audit (frontend)"
if [[ -f "frontend/package.json" ]]; then
  (
    cd frontend
    npm audit --json > "../$REPORT_DIR/npm-audit.json"
  ) || true
else
  echo "frontend/package.json not found; skipping npm audit"
fi

echo "[5/6] Running tracked-files secret scan"
git ls-files -z \
  | xargs -0 "$SCAN_VENV/bin/python" -m detect_secrets scan \
  > "$REPORT_DIR/detect-secrets-tracked.json"

echo "[6/6] Running Semgrep OWASP + secrets"
"$SEMGREP_BIN" --metrics=off --config p/owasp-top-ten \
  --exclude external --exclude .venv --exclude .venv-audit --exclude aidlc-docs \
  --exclude docs/diagrams --exclude contracts/artifacts \
  --json --output "$REPORT_DIR/semgrep-owasp.json" .
"$SEMGREP_BIN" --metrics=off --config p/secrets \
  --exclude external --exclude .venv --exclude .venv-audit --exclude aidlc-docs \
  --exclude docs/diagrams --exclude contracts/artifacts \
  --json --output "$REPORT_DIR/semgrep-secrets.json" .

if command -v jq >/dev/null 2>&1; then
  echo
  echo "Security summary:"
  jq '{bandit_findings:(.results|length), bandit_medium:([.results[]?|select(.issue_severity=="MEDIUM")]|length), bandit_high:([.results[]?|select(.issue_severity=="HIGH")]|length)}' "$REPORT_DIR/bandit.json"
  jq '{pip_vuln_dependencies:(.dependencies|map(select((.vulns|length)>0))|length), pip_total_vulns:([.dependencies[]?.vulns[]?]|length)}' "$REPORT_DIR/pip-audit.json"
  jq '{detect_secrets_files:(.results|keys|length)}' "$REPORT_DIR/detect-secrets-tracked.json"
  jq '{semgrep_owasp_findings:(.results|length)}' "$REPORT_DIR/semgrep-owasp.json"
  jq '{semgrep_secret_findings:(.results|length)}' "$REPORT_DIR/semgrep-secrets.json"
fi

echo "Security scan reports written to $REPORT_DIR"
