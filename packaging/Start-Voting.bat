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
