"""Admin password (PBKDF2) and bearer-token session handling.

No hardcoded credentials: `admin_config` starts empty and the API forces a
first-run "set your password" step (see app.py). Tokens are opaque, held only
in memory, and expire after 30 minutes idle - there is nothing worth
persisting across a restart, and forcing re-login after a restart is the
safer default for an admin console physically reachable from a school hallway.
"""

import hashlib
import os
import secrets
import time

PBKDF2_ITERATIONS = 200_000
TOKEN_IDLE_TIMEOUT_SECONDS = 30 * 60

_sessions = {}  # token -> last_seen_monotonic


def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                  PBKDF2_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, hash_hex):
    salt = bytes.fromhex(salt_hex)
    _, computed = hash_password(password, salt)
    return secrets.compare_digest(computed, hash_hex)


def is_configured(conn):
    return conn.execute("SELECT 1 FROM admin_config WHERE id = 1").fetchone() is not None


def set_password(conn, password):
    salt_hex, hash_hex = hash_password(password)
    conn.execute(
        "INSERT INTO admin_config (id, salt_hex, hash_hex) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET salt_hex=excluded.salt_hex, hash_hex=excluded.hash_hex",
        (salt_hex, hash_hex),
    )


def check_password(conn, password):
    row = conn.execute("SELECT salt_hex, hash_hex FROM admin_config WHERE id = 1").fetchone()
    if row is None:
        return False
    return verify_password(password, row["salt_hex"], row["hash_hex"])


def issue_token():
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.monotonic()
    return token


def check_token(token):
    """True and refreshes idle timer if valid; expired/unknown tokens are evicted."""
    if not token:
        return False
    last_seen = _sessions.get(token)
    if last_seen is None:
        return False
    if time.monotonic() - last_seen > TOKEN_IDLE_TIMEOUT_SECONDS:
        del _sessions[token]
        return False
    _sessions[token] = time.monotonic()
    return True


def revoke_token(token):
    _sessions.pop(token, None)
