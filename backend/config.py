"""Locates bundled resources (ballot.json, symbol images, frontend build) in
both dev (running from source) and packaged (PyInstaller onefile) modes."""

import sys
from pathlib import Path


def resource_root():
    """Root for read-only bundled assets: ballot.json, candidates/, frontend/dist.

    PyInstaller's --onefile mode unpacks bundled data into a temp dir at
    startup and exposes it as sys._MEIPASS. In dev, the project root is two
    levels up from this file (backend/config.py -> project root).
    """
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


BALLOT_JSON = resource_root() / "ballot.json"
SYMBOLS_DIR = resource_root() / "candidates" / "symbols"
FRONTEND_DIST = resource_root() / "frontend" / "dist"

HOST = "127.0.0.1"
PORT = 8000
