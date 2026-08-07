"""Locates bundled resources (ballot.json, symbol images) in both dev (running
from source) and packaged (PyInstaller onefile) modes. The frontend is a
separate Next.js process now - this backend ships no HTML/JS of its own."""

import socket
import sys
from pathlib import Path


def resource_root():
    """Root for read-only bundled assets: ballot.json, candidates/.

    PyInstaller's --onefile mode unpacks bundled data into a temp dir at
    startup and exposes it as sys._MEIPASS. In dev, the project root is two
    levels up from this file (backend/config.py -> project root).
    """
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


BALLOT_JSON = resource_root() / "ballot.json"
SYMBOLS_DIR = resource_root() / "candidates" / "symbols"

# 0.0.0.0: this machine is the "Main" voting laptop and also hosts the API a
# second "Admin" laptop reaches over the same WiFi/hotspot - see
# packaging/Start-Voting.bat. That deliberately also makes the voting kiosk
# page reachable from any device on that network, not just this laptop; the
# officer's one-student-at-a-time unlock is what actually gates casting a
# vote, and the operational mitigation is running this on a private
# hotspot/WiFi the officer controls, not an open school network.
HOST = "0.0.0.0"
PORT = 8000
FRONTEND_PORT = 3000  # fixed by convention - see packaging/Start-Voting.bat


def lan_ips():
    """Best-effort list of this machine's LAN-reachable IPv4 addresses, most
    likely candidate first - for printing "try these on the Admin laptop" at
    startup.

    There is no fully reliable way to pick the *one* right answer from pure
    stdlib: if a VPN is active, the usual "connect a UDP socket outward and
    read back the chosen interface" trick can return the VPN tunnel's
    address instead of the real WiFi/Ethernet one - confirmed by hand while
    building this, on a machine with a split-tunnel VPN. That address is
    real but useless for a second laptop on the same WiFi to reach. Rather
    than silently guess wrong, this returns every plausible candidate and
    lets the (human) officer try them - see the startup banner.
    """
    candidates = []

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        candidates.append(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()

    try:
        _, _, addrs = socket.gethostbyname_ex(socket.gethostname())
        candidates.extend(addrs)
    except OSError:
        pass

    seen = set()
    result = []
    for ip in candidates:
        if ip in seen or ip.startswith("127.") or ip.startswith("169.254."):
            continue
        seen.add(ip)
        result.append(ip)
    return result or ["127.0.0.1"]
