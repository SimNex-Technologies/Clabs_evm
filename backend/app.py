"""C-LABS Digital EVM - FastAPI backend.

This process is a pure JSON API plus the /symbols image files - it serves no
HTML. The Next.js frontend (frontend/) owns the UI entirely and reaches this
API through its own server-side rewrites, so from the browser's point of view
everything is same-origin against the Next.js server; no CORS is configured
here because the browser never talks to this process directly.

Route map:
  GET  /api/state                 public   - machine/polling status, ballot count
  GET  /api/ballot                public   - posts+candidates (only while UNLOCKED)
  POST /api/ballot/cast           public*  - the one atomic vote-casting call
  POST /api/admin/setup           public*  - first-run password creation
  POST /api/admin/login           public   - password -> bearer token
  POST /api/admin/unlock          admin    - open a ballot session for next student
  POST /api/admin/lock            admin    - force-lock, abandon any open ballot
  POST /api/admin/polling         admin    - open/close polling, set window
  POST /api/admin/test-mode       admin    - toggle rehearsal mode
  GET  /api/admin/results         admin    - tallies (blocked while polling OPEN)
  POST /api/admin/results/force   admin    - re-auth password -> results anyway
  POST /api/admin/export          admin    - write votes.xlsx + timestamped backup
  POST /api/admin/reset           admin    - backup, then wipe ballots/votes

* "public" routes that mutate state still can't do anything meaningful without
  matching the server-held ballot/machine state - see db.py's cast_ballot.
"""

import threading
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, security, storage

app = FastAPI(title="C-LABS Digital EVM Backend")

# FastAPI runs sync route functions in a threadpool - different requests can
# land on different threads, and sqlite3 connections are not safe to share
# across threads. A thread-local connection (rather than one shared global)
# avoids that while still reusing a connection within each worker thread.
_local = threading.local()


def get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = db.connect(storage.db_path())
        db.init_db(conn, config.BALLOT_JSON)
        _local.conn = conn
    return conn


def reset_conn_cache_for_tests():
    """Test-only: force the next get_conn() in this thread to reopen, so a
    monkeypatched storage.desktop_path() actually takes effect."""
    _local.conn = None


# ---------------------------------------------------------------- schemas --

class CastRequest(BaseModel):
    ballot_id: str
    selections: Dict[str, Optional[int]]  # post_id (str) -> candidate_id or None (NOTA)


class SetupRequest(BaseModel):
    password: str


class LoginRequest(BaseModel):
    password: str


class UnlockRequest(BaseModel):
    voter_name: str
    is_test: bool = False
    override: bool = False  # true once the officer has confirmed past a duplicate warning


class PollingRequest(BaseModel):
    action: str  # 'open' | 'close'
    poll_start: Optional[str] = None
    poll_end: Optional[str] = None


class TestModeRequest(BaseModel):
    enabled: bool


class ResetRequest(BaseModel):
    confirm: str


class ForceResultsRequest(BaseModel):
    password: str


# ------------------------------------------------------------ admin auth --

def require_admin(authorization: Optional[str] = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    if not security.check_token(token):
        raise HTTPException(401, "Admin session expired or missing. Please log in again.")


# ---------------------------------------------------------------- public --

@app.get("/api/state")
def api_state():
    conn = get_conn()
    m = db.get_machine(conn)
    return {
        "status": m["status"],
        "polling": m["polling"],
        "poll_start": m["poll_start"],
        "poll_end": m["poll_end"],
        "test_mode": bool(m["test_mode"]),
        "ballot_count": db.ballot_count(conn),
        "admin_configured": security.is_configured(conn),
        # The currently-unlocked student's name, for the kiosk's welcome-screen
        # greeting. Cleared back to null the instant the ballot is cast or the
        # machine is force-locked - see db.py's attendance table comment for
        # why this is never linked to the vote itself.
        "current_voter_name": m["current_voter_name"],
    }


@app.get("/api/ballot")
def api_ballot():
    conn = get_conn()
    m = db.get_machine(conn)
    if m["status"] != "UNLOCKED":
        raise HTTPException(409, "Voting is locked. Please contact the election officer.")
    return {
        "ballot_id": m["active_ballot_id"],
        "posts": db.get_ballot_structure(conn),
    }


@app.post("/api/ballot/cast")
def api_cast(body: CastRequest):
    conn = get_conn()
    structure = db.get_ballot_structure(conn)
    valid_posts = {p["id"]: {c["id"] for c in p["candidates"]} for p in structure}

    if set(int(k) for k in body.selections.keys()) != set(valid_posts.keys()):
        raise HTTPException(400, "Ballot must include a selection for every post.")

    selections = {}
    for post_id_str, candidate_id in body.selections.items():
        post_id = int(post_id_str)
        if candidate_id is not None and candidate_id not in valid_posts[post_id]:
            raise HTTPException(400, "Candidate does not belong to that post.")
        selections[post_id] = candidate_id

    try:
        serial = db.cast_ballot(conn, body.ballot_id, selections)
    except (db.MachineLockedError, db.PollingClosedError) as e:
        raise HTTPException(409, str(e))

    m = db.get_machine(conn)
    ballot_row = conn.execute(
        "SELECT is_test FROM ballots WHERE serial = ?", (serial,)
    ).fetchone()
    is_test = bool(ballot_row["is_test"]) if ballot_row else False

    for post in structure:
        cand_id = selections[post["id"]]
        cand_name = next((c["name"] for c in post["candidates"] if c["id"] == cand_id), None)
        storage.append_journal(serial, post["title"], cand_name, is_test)

    if not is_test:
        rows = db.tally(conn)
        storage.write_results_xlsx(rows, db.ballot_count(conn))

    return {"serial": serial}


@app.post("/api/admin/setup")
def api_admin_setup(body: SetupRequest):
    conn = get_conn()
    if security.is_configured(conn):
        raise HTTPException(409, "Admin password already set.")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    security.set_password(conn, body.password)
    return {"token": security.issue_token()}


@app.post("/api/admin/login")
def api_admin_login(body: LoginRequest):
    conn = get_conn()
    if not security.is_configured(conn):
        raise HTTPException(409, "No admin password set yet.")
    if not security.check_password(conn, body.password):
        raise HTTPException(401, "Incorrect password.")
    return {"token": security.issue_token()}


# ----------------------------------------------------------------- admin --

@app.post("/api/admin/unlock")
def api_admin_unlock(body: UnlockRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    voter_name = body.voter_name.strip()
    if not voter_name:
        raise HTTPException(400, "Enter the student's name before unlocking.")

    conn = get_conn()

    if not body.override:
        existing = db.find_attendance_by_name(conn, voter_name)
        if existing is not None:
            raise HTTPException(409, detail={
                "duplicate": True,
                "name": existing["name"],
                "unlocked_at": existing["unlocked_at"],
            })

    ballot_id = db.unlock_for_next_student(conn, voter_name, is_test=body.is_test)
    return {"ballot_id": ballot_id}


@app.post("/api/admin/lock")
def api_admin_lock(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    db.force_lock(get_conn())
    return {"ok": True}


@app.post("/api/admin/polling")
def api_admin_polling(body: PollingRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if body.action not in ("open", "close"):
        raise HTTPException(400, "action must be 'open' or 'close'.")
    db.set_polling(get_conn(), "OPEN" if body.action == "open" else "CLOSED",
                   body.poll_start, body.poll_end)
    return {"ok": True}


@app.post("/api/admin/test-mode")
def api_admin_test_mode(body: TestModeRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    db.set_test_mode(get_conn(), body.enabled)
    return {"ok": True}


@app.get("/api/admin/results")
def api_admin_results(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_conn()
    m = db.get_machine(conn)
    if m["polling"] == "OPEN":
        raise HTTPException(403, "Results are hidden while polling is open.")
    return {"tally": db.tally(conn), "ballot_count": db.ballot_count(conn)}


@app.post("/api/admin/results/force")
def api_admin_results_force(body: ForceResultsRequest,
                             authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_conn()
    if not security.check_password(conn, body.password):
        raise HTTPException(401, "Incorrect password.")
    return {"tally": db.tally(conn), "ballot_count": db.ballot_count(conn)}


@app.post("/api/admin/export")
def api_admin_export(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_conn()
    rows = db.tally(conn)
    path = storage.write_results_xlsx(rows, db.ballot_count(conn))
    storage.backup_snapshot()
    return {"path": str(path)}


@app.post("/api/admin/reset")
def api_admin_reset(body: ResetRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if body.confirm != "RESET":
        raise HTTPException(400, "Type RESET to confirm.")
    storage.backup_snapshot()
    db.reset_election(get_conn())
    return {"ok": True}


# --------------------------------------------------------- symbol images --

if config.SYMBOLS_DIR.exists():
    app.mount("/symbols", StaticFiles(directory=str(config.SYMBOLS_DIR)), name="symbols")


def main():
    # No browser-opening here: with two processes now (this API + the Next.js
    # frontend), the launcher script is what waits for both to come up and
    # opens the browser at the frontend's URL - see run.command/run.bat and
    # the packaged Start-Voting.bat (which prints its own, more prominent
    # version of these URLs once the frontend is also up).
    ips = config.lan_ips()
    print("=" * 64)
    print("C-LABS Digital EVM - backend starting")
    print("  Voting kiosk (this laptop): http://127.0.0.1:%d/" % config.FRONTEND_PORT)
    print("  Admin console - on the Admin laptop, same WiFi/hotspot, try:")
    for ip in ips:
        print("    http://%s:%d/admin" % (ip, config.FRONTEND_PORT))
    if len(ips) > 1:
        print("  (More than one address found - if the first doesn't load,")
        print("   try the others. A VPN on this laptop can make one of them wrong.)")
    print("=" * 64)
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
