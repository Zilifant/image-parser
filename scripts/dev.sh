#!/usr/bin/env bash
# Starts the FastAPI backend and the Vite dev server, opens the browser,
# and shuts both down on Ctrl-C.
set -euo pipefail
cd "$(dirname "$0")/.."

BACKEND_PORT="${IMAGE_PARSER_PORT:-8765}"
FRONTEND_PORT=5173

cleanup() {
  trap - INT TERM EXIT
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT") &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo "Waiting for backend on port $BACKEND_PORT..."
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

URL="http://localhost:$FRONTEND_PORT"
echo "image-parser running at $URL"
if command -v open >/dev/null 2>&1; then
  open "$URL"
fi

wait
