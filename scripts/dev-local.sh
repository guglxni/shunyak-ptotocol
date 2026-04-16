#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-4103}"
WEB_PORT="${WEB_PORT:-4100}"

if ! command -v vercel >/dev/null 2>&1; then
  echo "error: vercel CLI is required" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "error: npm is required" >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/vercel.local.api.json" ]]; then
  echo "error: missing $ROOT_DIR/vercel.local.api.json" >&2
  exit 1
fi

# shellcheck disable=SC1090
if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
  source "$HOME/.nvm/nvm.sh"
  if ! nvm use 20 >/dev/null 2>&1; then
    echo "[local] warning: Node 20 not found in nvm; using current node" >&2
  fi
fi

shutdown() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
}
trap shutdown EXIT INT TERM

echo "[local] starting API runtime on :$API_PORT"
(
  cd "$ROOT_DIR"
  vercel dev --local-config vercel.local.api.json --listen "$API_PORT"
) &
API_PID=$!

echo "[local] starting frontend on :$WEB_PORT (proxy -> http://localhost:$API_PORT)"
(
  cd "$ROOT_DIR/frontend"
  SHUNYAK_LOCAL_API_ORIGIN="http://localhost:$API_PORT" npm run dev -- --port "$WEB_PORT"
) &
WEB_PID=$!

echo "[local] ready: frontend=http://localhost:$WEB_PORT api=http://localhost:$API_PORT"

# macOS ships Bash 3.2, which does not support `wait -n`.
while true; do
  if ! kill -0 "$API_PID" >/dev/null 2>&1; then
    wait "$API_PID" || true
    break
  fi
  if ! kill -0 "$WEB_PID" >/dev/null 2>&1; then
    wait "$WEB_PID" || true
    break
  fi
  sleep 1
done

echo "[local] one process exited; shutting down remaining process"
