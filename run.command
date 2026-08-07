#!/bin/bash
# Double-click launcher for macOS dev/testing: starts BOTH processes -
# the FastAPI backend (:8000) and the Next.js frontend (:3000, dev mode with
# hot reload) - and opens the browser once both are ready. Safe to double-
# click again any time; each setup step is a no-op once done.
#
# This is for local development only. The school runs the packaged
# Start-Voting.bat (portable Node + PyInstaller backend), not this file.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "First run: setting up the backend..."
  python3 -m venv .venv
fi
./.venv/bin/pip install -q -r requirements.txt

if [ ! -d "frontend/node_modules" ]; then
  echo "First run: installing frontend dependencies..."
  (cd frontend && npm install)
fi

if [ ! -f "ballot.json" ]; then
  echo "ERROR: ballot.json not found. Run scripts/extract_symbols.py first."
  read -p "Press Enter to close..."
  exit 1
fi

cleanup() {
  echo ""
  echo "Stopping C-LABS Digital EVM..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "Starting backend on http://127.0.0.1:8000 ..."
./.venv/bin/python main.py &
BACKEND_PID=$!

echo "Starting frontend on http://127.0.0.1:3000 ..."
(cd frontend && npm run dev -- --port 3000) &
FRONTEND_PID=$!

echo "Waiting for both servers to come up..."
for i in $(seq 1 100); do
  curl -sf http://127.0.0.1:8000/api/state >/dev/null 2>&1 && BACKEND_UP=1
  curl -sf http://127.0.0.1:3000/ >/dev/null 2>&1 && FRONTEND_UP=1
  [ -n "$BACKEND_UP" ] && [ -n "$FRONTEND_UP" ] && break
  sleep 0.2
done

open "http://127.0.0.1:3000/" 2>/dev/null

echo ""
echo "C-LABS Digital EVM is running."
echo "Do not close this window while voting is in progress."
echo "Press Ctrl+C here to stop both servers."
wait
