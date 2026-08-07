#!/bin/bash
# Double-click launcher for macOS: sets up everything on first run, then just
# starts the server. Safe to double-click again any time - each step is a
# no-op once done.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "First run: setting up C-LABS Digital EVM..."
  python3 -m venv .venv
fi

./.venv/bin/pip install -q -r requirements.txt

if [ ! -d "frontend/dist" ]; then
  echo "Building voting kiosk interface..."
  if [ ! -d "frontend/node_modules" ]; then
    (cd frontend && npm install)
  fi
  (cd frontend && npm run build)
fi

if [ ! -f "ballot.json" ]; then
  echo "ERROR: ballot.json not found. Run scripts/extract_symbols.py first."
  read -p "Press Enter to close..."
  exit 1
fi

echo "Starting C-LABS Digital EVM..."
echo "Do not close this window while voting is in progress."
./.venv/bin/python main.py
