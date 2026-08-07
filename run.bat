@echo off
REM Windows launcher for running from source (dev/testing only - the school
REM uses the packaged Start-Voting.bat + portable Node + backend .exe from
REM GitHub Actions, not this file). Starts BOTH processes: the FastAPI
REM backend (:8000) and the Next.js frontend (:3000, dev mode).
cd /d "%~dp0"

if not exist ".venv" (
    echo First run: setting up the backend...
    python -m venv .venv
)
.venv\Scripts\pip install -q -r requirements.txt

if not exist "frontend\node_modules" (
    echo First run: installing frontend dependencies...
    pushd frontend
    call npm install
    popd
)

if not exist "ballot.json" (
    echo ERROR: ballot.json not found. Run scripts\extract_symbols.py first.
    pause
    exit /b 1
)

echo Starting backend on http://127.0.0.1:8000 ...
start "C-LABS EVM Backend" .venv\Scripts\python.exe main.py

echo Starting frontend on http://127.0.0.1:3000 ...
pushd frontend
start "C-LABS EVM Frontend" cmd /c "npm run dev -- --port 3000"
popd

echo Waiting for both servers to come up...
powershell -NoProfile -Command ^
    "$ok=$false; for ($i=0; $i -lt 100; $i++) { try { $b=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/state -TimeoutSec 1; $f=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/ -TimeoutSec 1; if ($b.StatusCode -eq 200 -and $f.StatusCode -eq 200) { $ok=$true; break } } catch {}; Start-Sleep -Milliseconds 200 }"

start "" http://127.0.0.1:3000/

echo.
echo C-LABS Digital EVM is running in two separate console windows
echo (Backend and Frontend). Close both of those windows to stop voting.
echo This window can be closed now.
pause
