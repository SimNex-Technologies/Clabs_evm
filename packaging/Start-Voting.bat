@echo off
REM C-LABS Digital EVM - election-day launcher.
REM This file ships inside the release zip alongside Backend\, Frontend\,
REM and node\ (a portable Node.js runtime) - see .github/workflows/build-windows.yml.
REM No installation needed: everything the school PC needs is in this folder.
REM
REM Two-laptop setup: this laptop ("Main") runs both the backend and the
REM voting kiosk. A second "Admin" laptop, on the SAME WiFi/hotspot, reaches
REM the officer console remotely at the address printed below - nothing
REM needs installing on that second laptop, it just needs a browser.
cd /d "%~dp0"

REM --- Guard 1: running from inside the .zip -------------------------------
REM Double-clicking a file inside a zip makes Windows copy that ONE file to a
REM Temp folder and run it there, without Backend\, Frontend\ or node\. The
REM result is a half-started system that looks like it worked, so catch it.
echo %~dp0 | findstr /I "\\AppData\\Local\\Temp\\" >nul
if %errorlevel%==0 (
    echo.
    echo  ============================================================
    echo   STOP - this is running from inside the ZIP file.
    echo  ============================================================
    echo.
    echo   Windows is running this from a temporary folder, so the rest
    echo   of the program is missing and voting will NOT work.
    echo.
    echo   Fix it like this:
    echo     1. Close this window.
    echo     2. Find the downloaded .zip file.
    echo     3. Right-click it and choose "Extract All...".
    echo     4. Open the extracted C-LABS-EVM folder.
    echo     5. Double-click Start-Voting.bat in THAT folder.
    echo.
    pause
    exit /b 1
)

REM --- Guard 2: the pieces we need are actually beside us ------------------
set MISSING=
if not exist "Backend\C-LABS-EVM-Backend.exe" set MISSING=%MISSING% Backend\C-LABS-EVM-Backend.exe
if not exist "Frontend\server.js"            set MISSING=%MISSING% Frontend\server.js
if not exist "node\node.exe"                 set MISSING=%MISSING% node\node.exe
if not "%MISSING%"=="" (
    echo.
    echo  ============================================================
    echo   STOP - part of the program is missing.
    echo  ============================================================
    echo.
    echo   Could not find:%MISSING%
    echo.
    echo   Start-Voting.bat must sit in the same folder as the
    echo   Backend, Frontend and node folders. Extract the whole .zip
    echo   again and keep all of them together, then run this file
    echo   from the extracted folder.
    echo.
    pause
    exit /b 1
)

echo Starting C-LABS Digital EVM backend...
start "C-LABS EVM Backend - DO NOT CLOSE" /min Backend\C-LABS-EVM-Backend.exe

echo Waiting for the backend to come up...
powershell -NoProfile -Command ^
    "for ($i=0; $i -lt 150; $i++) { try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/state -TimeoutSec 1; if ($r.StatusCode -eq 200) { exit } } catch {}; Start-Sleep -Milliseconds 200 }"

echo Starting C-LABS Digital EVM voting kiosk...
set PORT=3000
set HOSTNAME=0.0.0.0
start "C-LABS EVM Frontend - DO NOT CLOSE" /min node\node.exe Frontend\server.js

echo Waiting for the voting kiosk to come up...
powershell -NoProfile -Command ^
    "for ($i=0; $i -lt 150; $i++) { try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000/ -TimeoutSec 1; if ($r.StatusCode -eq 200) { exit } } catch {}; Start-Sleep -Milliseconds 200 }"

echo.
echo ============================================================
echo   C-LABS Digital EVM is running.
echo.
echo   If Windows Firewall just asked about Node.js or Python,
echo   click "Allow access" - otherwise the Admin laptop won't
echo   be able to reach this one.
echo.
REM -notlike (plain wildcards) instead of -notmatch (regex) - regex needs \.
REM and ^ characters that collide with cmd.exe's own ^ escape character when
REM nested this deeply; wildcards need no escaping at all.
REM
REM This lists EVERY candidate address rather than guessing one: if this
REM laptop has a VPN active, one candidate can be a tunnel address that
REM looks fine but isn't reachable from the Admin laptop's WiFi. There's no
REM fully reliable way to tell which is which from here - try each one.
echo   On the Admin laptop, connected to the SAME WiFi/hotspot,
echo   open a browser to one of these (try the first; if it
echo   doesn't load, try the next):
echo.
set FOUNDIP=
for /f "tokens=*" %%A in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress)"') do (
    echo       http://%%A:3000/admin
    set FOUNDIP=1
)
echo.
if not defined FOUNDIP (
    echo   Could not detect a network address - check this laptop
    echo   is connected to WiFi/hotspot before using a second laptop
    echo   for admin.
    echo.
)
echo   The "C-LABS EVM Backend" window ^(minimized in the taskbar^)
echo   prints this same list independently, cross-checked a second
echo   way - open it if none of the addresses above work.
echo ============================================================
echo.

echo Opening the voting kiosk on this laptop...
where msedge >nul 2>nul
if %errorlevel%==0 (
    start "" msedge --kiosk http://127.0.0.1:3000/ --edge-kiosk-type=fullscreen --no-first-run
) else (
    start "" http://127.0.0.1:3000/
)

echo.
echo C-LABS Digital EVM is running in two minimized windows:
echo   "C-LABS EVM Backend"  and  "C-LABS EVM Frontend"
echo DO NOT CLOSE either of those windows while voting is in progress.
echo Closing THIS window is fine - it has already done its job.
pause
