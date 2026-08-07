"""SQLite schema + the one transaction that must never be wrong: cast_ballot().

Integrity is enforced by the database, not application logic:
  - `votes` has UNIQUE(ballot_id, post_id) - a bug in the API layer cannot
    produce two votes for the same post on the same ballot.
  - `machine` has exactly one row (CHECK id = 1) and is the single source of
    truth for lock state - the client is never trusted with it.
  - Every write to `machine`/`ballots`/`votes` happens inside cast_ballot's own
    BEGIN IMMEDIATE transaction, so concurrent requests serialize instead of
    racing.
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS machine (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL DEFAULT 'LOCKED',       -- 'LOCKED' | 'UNLOCKED'
    polling TEXT NOT NULL DEFAULT 'NOT_STARTED', -- 'NOT_STARTED' | 'OPEN' | 'CLOSED'
    active_ballot_id TEXT,
    poll_start TEXT,
    poll_end TEXT,
    test_mode INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    display_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id),
    name TEXT NOT NULL,
    symbol_file TEXT NOT NULL,
    ballot_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ballots (
    id TEXT PRIMARY KEY,
    serial INTEGER UNIQUE,
    opened_at TEXT NOT NULL,
    submitted_at TEXT,
    state TEXT NOT NULL DEFAULT 'OPEN',  -- 'OPEN' | 'CAST' | 'ABANDONED'
    is_test INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY,
    ballot_id TEXT NOT NULL REFERENCES ballots(id),
    post_id INTEGER NOT NULL REFERENCES posts(id),
    candidate_id INTEGER REFERENCES candidates(id),  -- NULL = NOTA
    UNIQUE (ballot_id, post_id)
);

CREATE TABLE IF NOT EXISTS admin_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    salt_hex TEXT NOT NULL,
    hash_hex TEXT NOT NULL
);
"""


class MachineLockedError(Exception):
    """Raised when a ballot action is attempted while the machine won't allow it."""


class PollingClosedError(Exception):
    pass


def connect(db_path):
    """Open the election DB with settings safe for a single always-on kiosk."""
    conn = sqlite3.connect(str(db_path), timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")   # a power cut must not lose a cast ballot
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn, ballot_json_path):
    """Create tables if missing, seed posts/candidates from ballot.json if empty."""
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO machine (id) VALUES (1)")

    row = conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()
    if row["n"] == 0:
        ballot = json.loads(Path(ballot_json_path).read_text())
        for p_order, post in enumerate(ballot["posts"], start=1):
            cur = conn.execute(
                "INSERT INTO posts (code, title, display_order) VALUES (?, ?, ?)",
                (post["code"], post["title"], p_order),
            )
            post_id = cur.lastrowid
            for cand in post["candidates"]:
                conn.execute(
                    "INSERT INTO candidates (post_id, name, symbol_file, ballot_order) "
                    "VALUES (?, ?, ?, ?)",
                    (post_id, cand["name"], cand["symbol_file"], cand["ballot_order"]),
                )


def get_machine(conn):
    return conn.execute("SELECT * FROM machine WHERE id = 1").fetchone()


def get_ballot_structure(conn):
    """Posts with their candidates, in display/ballot order - what the kiosk renders."""
    posts = conn.execute(
        "SELECT * FROM posts ORDER BY display_order"
    ).fetchall()
    result = []
    for post in posts:
        candidates = conn.execute(
            "SELECT * FROM candidates WHERE post_id = ? ORDER BY ballot_order",
            (post["id"],),
        ).fetchall()
        result.append({
            "id": post["id"],
            "code": post["code"],
            "title": post["title"],
            "candidates": [
                {"id": c["id"], "name": c["name"], "symbol_file": c["symbol_file"]}
                for c in candidates
            ],
        })
    return result


def unlock_for_next_student(conn, is_test=False):
    """Officer action: open exactly one new ballot session. Returns the ballot id."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        machine = get_machine(conn)
        if machine["status"] == "UNLOCKED":
            conn.execute("COMMIT")
            return machine["active_ballot_id"]

        ballot_id = str(uuid.uuid4())
        next_serial = conn.execute(
            "SELECT COALESCE(MAX(serial), 0) + 1 AS n FROM ballots"
        ).fetchone()["n"]
        conn.execute(
            "INSERT INTO ballots (id, serial, opened_at, state, is_test) "
            "VALUES (?, ?, ?, 'OPEN', ?)",
            (ballot_id, next_serial, _now(), 1 if is_test else 0),
        )
        conn.execute(
            "UPDATE machine SET status='UNLOCKED', active_ballot_id=? WHERE id=1",
            (ballot_id,),
        )
        conn.execute("COMMIT")
        return ballot_id
    except Exception:
        conn.execute("ROLLBACK")
        raise


def force_lock(conn):
    """Officer action: lock immediately, abandoning any open ballot."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        machine = get_machine(conn)
        if machine["active_ballot_id"]:
            conn.execute(
                "UPDATE ballots SET state='ABANDONED' WHERE id=? AND state='OPEN'",
                (machine["active_ballot_id"],),
            )
        conn.execute(
            "UPDATE machine SET status='LOCKED', active_ballot_id=NULL WHERE id=1"
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def cast_ballot(conn, ballot_id, selections):
    """Atomically record one student's full ballot and re-lock the machine.

    `selections` is {post_id: candidate_id_or_None}. None means NOTA. Every
    post in the roster must be present as a key (a post can be explicitly
    skipped, but the caller must say so) - see app.py for the request-shape
    validation that guarantees this before we get here.

    Raises MachineLockedError / PollingClosedError on any state mismatch:
    wrong ballot id, machine already re-locked, polling not open, outside the
    poll window. Every one of these maps to a 409 at the API layer.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        machine = get_machine(conn)

        if machine["status"] != "UNLOCKED" or machine["active_ballot_id"] != ballot_id:
            raise MachineLockedError("This ballot session is no longer active.")

        if machine["polling"] != "OPEN":
            raise PollingClosedError("Polling is not open.")

        now = _now()
        if machine["poll_start"] and now < machine["poll_start"]:
            raise PollingClosedError("Polling has not started yet.")
        if machine["poll_end"] and now > machine["poll_end"]:
            raise PollingClosedError("Polling has closed.")

        ballot = conn.execute(
            "SELECT * FROM ballots WHERE id = ?", (ballot_id,)
        ).fetchone()
        if ballot is None or ballot["state"] != "OPEN":
            raise MachineLockedError("This ballot has already been cast or abandoned.")

        for post_id, candidate_id in selections.items():
            conn.execute(
                "INSERT INTO votes (ballot_id, post_id, candidate_id) VALUES (?, ?, ?)",
                (ballot_id, post_id, candidate_id),
            )

        conn.execute(
            "UPDATE ballots SET state='CAST', submitted_at=? WHERE id=?",
            (now, ballot_id),
        )
        conn.execute(
            "UPDATE machine SET status='LOCKED', active_ballot_id=NULL WHERE id=1"
        )
        conn.execute("COMMIT")
        return ballot["serial"]
    except (MachineLockedError, PollingClosedError):
        conn.execute("ROLLBACK")
        raise
    except sqlite3.IntegrityError as e:
        # UNIQUE(ballot_id, post_id) tripped - a second attempt at the same
        # ballot slipped past the state checks above (e.g. a racing duplicate
        # request). Treat it the same as an already-cast ballot.
        conn.execute("ROLLBACK")
        raise MachineLockedError("This ballot has already been cast.") from e
    except Exception:
        conn.execute("ROLLBACK")
        raise


def set_polling(conn, polling, poll_start=None, poll_end=None):
    assert polling in ("NOT_STARTED", "OPEN", "CLOSED")
    conn.execute(
        "UPDATE machine SET polling=?, poll_start=COALESCE(?, poll_start), "
        "poll_end=COALESCE(?, poll_end) WHERE id=1",
        (polling, poll_start, poll_end),
    )


def set_test_mode(conn, enabled):
    conn.execute("UPDATE machine SET test_mode=? WHERE id=1", (1 if enabled else 0,))


def ballot_count(conn, include_test=False):
    clause = "" if include_test else "WHERE is_test = 0"
    return conn.execute(
        "SELECT COUNT(*) AS n FROM ballots WHERE state='CAST'"
        + (" AND is_test = 0" if not include_test else "")
    ).fetchone()["n"]


def tally(conn, include_test=False):
    """Per-post, per-candidate counts, including a NOTA count. Cast ballots only."""
    test_clause = "" if include_test else "AND b.is_test = 0"
    posts = conn.execute("SELECT * FROM posts ORDER BY display_order").fetchall()
    results = []
    for post in posts:
        candidates = conn.execute(
            "SELECT * FROM candidates WHERE post_id = ? ORDER BY ballot_order",
            (post["id"],),
        ).fetchall()
        counts = {}
        for c in candidates:
            row = conn.execute(
                f"SELECT COUNT(*) AS n FROM votes v "
                f"JOIN ballots b ON b.id = v.ballot_id "
                f"WHERE v.post_id=? AND v.candidate_id=? AND b.state='CAST' {test_clause}",
                (post["id"], c["id"]),
            ).fetchone()
            counts[c["id"]] = {"name": c["name"], "symbol_file": c["symbol_file"],
                                "count": row["n"]}
        nota_row = conn.execute(
            f"SELECT COUNT(*) AS n FROM votes v "
            f"JOIN ballots b ON b.id = v.ballot_id "
            f"WHERE v.post_id=? AND v.candidate_id IS NULL AND b.state='CAST' {test_clause}",
            (post["id"],),
        ).fetchone()
        results.append({
            "post_code": post["code"],
            "post_title": post["title"],
            "candidates": list(counts.values()),
            "nota": nota_row["n"],
        })
    return results


def reset_election(conn):
    """Wipe all ballots/votes and reset machine state. Caller must back up first."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM votes")
        conn.execute("DELETE FROM ballots")
        conn.execute(
            "UPDATE machine SET status='LOCKED', polling='NOT_STARTED', "
            "active_ballot_id=NULL, poll_start=NULL, poll_end=NULL WHERE id=1"
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _now():
    """ISO-8601 UTC timestamp, string-sortable for the poll-window comparisons."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
