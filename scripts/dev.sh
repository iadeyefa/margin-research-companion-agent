#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting API on http://127.0.0.1:3000"
(
  cd "$ROOT/backend"
  python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 3000
) &

echo "Starting frontend on http://127.0.0.1:5173"
(
  cd "$ROOT/frontend"
  npm run dev -- --host 127.0.0.1 --port 5173
) &

wait
