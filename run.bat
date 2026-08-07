@echo off
REM Windows launcher for running from source (dev/testing only - the school
REM uses the packaged C-LABS-EVM.exe from GitHub Actions, not this file).
cd /d "%~dp0"

if not exist ".venv" (
    echo First run: setting up C-LABS Digital EVM...
    python -m venv .venv
)

.venv\Scripts\pip install -q -r requirements.txt

if not exist "frontend\dist" (
    echo Building voting kiosk interface...
    if not exist "frontend\node_modules" (
        pushd frontend
        call npm install
        popd
    )
    pushd frontend
    call npm run build
    popd
)

if not exist "ballot.json" (
    echo ERROR: ballot.json not found. Run scripts\extract_symbols.py first.
    pause
    exit /b 1
)

echo Starting C-LABS Digital EVM...
echo Do not close this window while voting is in progress.
.venv\Scripts\python main.py
pause
