"""The tests that actually matter: can two people ever cast the same ballot,
can a locked machine be tricked into accepting a vote, does NOTA count right,
does a reset actually clear results after backing up first, and does the
attendance/duplicate-name log ever leak into the ballot secrecy boundary.

These exercise backend/db.py directly (fast, no HTTP) plus a thin layer of
API-level tests via FastAPI's TestClient for the request-shape validation
that lives in app.py.
"""

import concurrent.futures
import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import db as dbmod  # noqa: E402

BALLOT_JSON = Path(__file__).resolve().parent.parent / "ballot.json"


@pytest.fixture()
def conn(tmp_path):
    c = dbmod.connect(tmp_path / "election.db")
    dbmod.init_db(c, BALLOT_JSON)
    dbmod.set_polling(c, "OPEN")
    yield c
    c.close()


def _post_ids(conn):
    return [p["id"] for p in dbmod.get_ballot_structure(conn)]


def _full_nota_selection(conn):
    return {pid: None for pid in _post_ids(conn)}


def _unlock(conn, name="Test Student", is_test=False):
    return dbmod.unlock_for_next_student(conn, name, is_test=is_test)


# --------------------------------------------------------------- casting --

def test_cannot_cast_while_locked(conn):
    selections = _full_nota_selection(conn)
    with pytest.raises(dbmod.MachineLockedError):
        dbmod.cast_ballot(conn, "not-a-real-ballot", selections)
    assert dbmod.ballot_count(conn) == 0


def test_happy_path_cast_and_autolock(conn):
    ballot_id = _unlock(conn)
    assert dbmod.get_machine(conn)["status"] == "UNLOCKED"

    serial = dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))
    assert serial == 1

    m = dbmod.get_machine(conn)
    assert m["status"] == "LOCKED"
    assert m["active_ballot_id"] is None
    assert dbmod.ballot_count(conn) == 1


def test_double_submit_same_ballot_id_only_records_once(conn):
    ballot_id = _unlock(conn)
    selections = _full_nota_selection(conn)

    dbmod.cast_ballot(conn, ballot_id, selections)

    with pytest.raises(dbmod.MachineLockedError):
        dbmod.cast_ballot(conn, ballot_id, selections)

    assert dbmod.ballot_count(conn) == 1


def test_concurrent_double_submit_records_exactly_once(tmp_path):
    """Two threads race to cast the same ballot id at the same instant."""
    path = tmp_path / "election.db"
    setup = dbmod.connect(path)
    dbmod.init_db(setup, BALLOT_JSON)
    dbmod.set_polling(setup, "OPEN")
    ballot_id = _unlock(setup)
    post_ids = _post_ids(setup)
    setup.close()

    results = []

    def attempt():
        c = dbmod.connect(path)
        try:
            serial = dbmod.cast_ballot(c, ballot_id, {pid: None for pid in post_ids})
            return ("ok", serial)
        except (dbmod.MachineLockedError, sqlite3.OperationalError) as e:
            return ("rejected", str(e))
        finally:
            c.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        results = [f.result() for f in futures]

    oks = [r for r in results if r[0] == "ok"]
    assert len(oks) == 1, "exactly one of the two concurrent casts should succeed: %r" % results

    check = dbmod.connect(path)
    assert dbmod.ballot_count(check) == 1
    check.close()


def test_stale_ballot_id_after_relock_and_reunlock_is_rejected(conn):
    ballot_id_1 = _unlock(conn, "Student One")
    dbmod.force_lock(conn)          # officer locks without the student casting
    ballot_id_2 = _unlock(conn, "Student Two")
    assert ballot_id_1 != ballot_id_2

    with pytest.raises(dbmod.MachineLockedError):
        dbmod.cast_ballot(conn, ballot_id_1, _full_nota_selection(conn))
    assert dbmod.ballot_count(conn) == 0

    # the *current* ballot still works
    dbmod.cast_ballot(conn, ballot_id_2, _full_nota_selection(conn))
    assert dbmod.ballot_count(conn) == 1


def test_outside_poll_window_is_rejected(conn):
    dbmod.set_polling(conn, "OPEN", poll_start="2999-01-01T00:00:00Z")  # far future
    ballot_id = _unlock(conn)
    with pytest.raises(dbmod.PollingClosedError):
        dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))


def test_polling_closed_blocks_cast_even_if_unlocked(conn):
    dbmod.set_polling(conn, "CLOSED")
    ballot_id = _unlock(conn)
    with pytest.raises(dbmod.PollingClosedError):
        dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))


# ------------------------------------------------------------------ NOTA --

def test_nota_recorded_as_null_candidate_and_tallied(conn):
    ballot_id = _unlock(conn)
    dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))

    rows = conn.execute("SELECT candidate_id FROM votes WHERE ballot_id=?",
                         (ballot_id,)).fetchall()
    assert all(r["candidate_id"] is None for r in rows)

    tally = dbmod.tally(conn)
    for post in tally:
        assert post["nota"] == 1
        assert all(c["count"] == 0 for c in post["candidates"])


def test_vote_count_matches_five_posts_per_ballot(conn):
    for i in range(3):
        ballot_id = _unlock(conn, "Student %d" % i)
        dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))

    n_posts = len(_post_ids(conn))
    total_votes = conn.execute("SELECT COUNT(*) AS n FROM votes").fetchone()["n"]
    assert total_votes == 3 * n_posts


# --------------------------------------------------------------- lifecycle --

def test_reset_wipes_ballots_and_votes(conn):
    ballot_id = _unlock(conn)
    dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))
    assert dbmod.ballot_count(conn) == 1

    dbmod.reset_election(conn)

    assert dbmod.ballot_count(conn) == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM ballots").fetchone()["n"] == 0
    assert conn.execute("SELECT COUNT(*) AS n FROM votes").fetchone()["n"] == 0
    m = dbmod.get_machine(conn)
    assert m["status"] == "LOCKED"
    assert m["polling"] == "NOT_STARTED"


def test_test_mode_ballots_excluded_from_results(conn):
    real_ballot = _unlock(conn, "Real Student", is_test=False)
    dbmod.cast_ballot(conn, real_ballot, _full_nota_selection(conn))

    test_ballot = _unlock(conn, "Test Student", is_test=True)
    dbmod.cast_ballot(conn, test_ballot, _full_nota_selection(conn))

    assert dbmod.ballot_count(conn, include_test=False) == 1
    assert dbmod.ballot_count(conn, include_test=True) == 2

    tally = dbmod.tally(conn, include_test=False)
    assert all(post["nota"] == 1 for post in tally)  # only the real ballot counted


def test_unlock_is_idempotent_while_already_unlocked(conn):
    """Calling unlock twice in a row (e.g. a double-tapped officer button)
    must not silently abandon the in-progress ballot or create two sessions."""
    ballot_id_1 = _unlock(conn, "Student One")
    ballot_id_2 = _unlock(conn, "Student Two")  # ignored - machine already unlocked
    assert ballot_id_1 == ballot_id_2
    assert dbmod.ballot_count(conn) == 0


def test_force_lock_abandons_open_ballot(conn):
    ballot_id = _unlock(conn)
    dbmod.force_lock(conn)

    state = conn.execute("SELECT state FROM ballots WHERE id=?", (ballot_id,)).fetchone()
    assert state["state"] == "ABANDONED"

    with pytest.raises(dbmod.MachineLockedError):
        dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))


# ------------------------------------------------------------------ roster --

def test_ballot_structure_has_21_candidates_across_5_posts(conn):
    structure = dbmod.get_ballot_structure(conn)
    assert len(structure) == 5
    total = sum(len(p["candidates"]) for p in structure)
    assert total == 21


# ------------------------------------------------------------- attendance --
# The attendance log exists to warn about duplicate names - it must never
# become a way to link a completed vote back to a voter's identity.

def test_unlock_logs_attendance_and_sets_current_voter_name(conn):
    ballot_id = _unlock(conn, "Harshavardhan A")
    m = dbmod.get_machine(conn)
    assert m["current_voter_name"] == "Harshavardhan A"

    row = conn.execute("SELECT * FROM attendance WHERE name = ?",
                        ("Harshavardhan A",)).fetchone()
    assert row is not None
    assert row["name_normalized"] == "harshavardhan a"


def test_current_voter_name_cleared_on_cast(conn):
    ballot_id = _unlock(conn, "Harshavardhan A")
    dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))
    assert dbmod.get_machine(conn)["current_voter_name"] is None


def test_current_voter_name_cleared_on_force_lock(conn):
    _unlock(conn, "Harshavardhan A")
    dbmod.force_lock(conn)
    assert dbmod.get_machine(conn)["current_voter_name"] is None


def test_find_attendance_by_name_matches_case_and_whitespace_insensitively(conn):
    _unlock(conn, "Harshavardhan A")
    dbmod.force_lock(conn)  # free the machine up for the next student

    assert dbmod.find_attendance_by_name(conn, "  harshavardhan   a ") is not None
    assert dbmod.find_attendance_by_name(conn, "HARSHAVARDHAN A") is not None
    assert dbmod.find_attendance_by_name(conn, "Someone Else") is None


def test_reset_wipes_attendance_log_too(conn):
    ballot_id = _unlock(conn, "Harshavardhan A")
    dbmod.cast_ballot(conn, ballot_id, _full_nota_selection(conn))

    dbmod.reset_election(conn)

    assert conn.execute("SELECT COUNT(*) AS n FROM attendance").fetchone()["n"] == 0
    assert dbmod.find_attendance_by_name(conn, "Harshavardhan A") is None


def test_attendance_has_no_foreign_key_path_to_votes(conn):
    """Structural guarantee: the attendance table cannot be joined to votes/
    ballots through any declared foreign key. If this ever changes, the
    ballot-secrecy design has been broken."""
    fks = conn.execute("PRAGMA foreign_key_list(attendance)").fetchall()
    assert fks == []


# -------------------------------------------------------------- API layer --

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from backend import storage as storagemod

    fake_desktop = tmp_path / "Desktop"
    fake_desktop.mkdir()
    monkeypatch.setattr(storagemod, "desktop_path", lambda: fake_desktop)

    from backend import app as appmod
    appmod.reset_conn_cache_for_tests()  # force a fresh connection against the patched path

    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def _login(client, password="letmein123"):
    client.post("/api/admin/setup", json={"password": password})
    r = client.post("/api/admin/login", json={"password": password})
    token = r.json()["token"]
    return {"Authorization": "Bearer %s" % token}


def test_api_cast_requires_every_post(client):
    r = client.get("/api/state")
    assert r.json()["status"] == "LOCKED"

    headers = _login(client)
    client.post("/api/admin/polling", json={"action": "open"}, headers=headers)
    client.post("/api/admin/unlock", json={"voter_name": "Test Student"}, headers=headers)

    ballot = client.get("/api/ballot").json()
    partial = {str(ballot["posts"][0]["id"]): None}  # missing the other 4 posts

    r = client.post("/api/ballot/cast", json={"ballot_id": ballot["ballot_id"],
                                               "selections": partial})
    assert r.status_code == 400


def test_api_admin_routes_reject_missing_token(client):
    assert client.post("/api/admin/lock").status_code == 401
    assert client.get("/api/admin/results").status_code == 401


def test_api_unlock_requires_nonempty_name(client):
    headers = _login(client)
    client.post("/api/admin/polling", json={"action": "open"}, headers=headers)

    r = client.post("/api/admin/unlock", json={"voter_name": "   "}, headers=headers)
    assert r.status_code == 400


def test_api_duplicate_name_warns_but_override_proceeds(client):
    headers = _login(client)
    client.post("/api/admin/polling", json={"action": "open"}, headers=headers)

    r1 = client.post("/api/admin/unlock", json={"voter_name": "Harshavardhan A"}, headers=headers)
    assert r1.status_code == 200
    client.post("/api/admin/lock", headers=headers)  # student didn't vote; free the machine

    # same name again, no override - should warn, not unlock
    r2 = client.post("/api/admin/unlock", json={"voter_name": "harshavardhan a"}, headers=headers)
    assert r2.status_code == 409
    assert r2.json()["detail"]["duplicate"] is True

    state = client.get("/api/state").json()
    assert state["status"] == "LOCKED"

    # with override, it proceeds anyway
    r3 = client.post("/api/admin/unlock",
                      json={"voter_name": "harshavardhan a", "override": True},
                      headers=headers)
    assert r3.status_code == 200
    state = client.get("/api/state").json()
    assert state["status"] == "UNLOCKED"
    assert state["current_voter_name"] == "harshavardhan a"


def test_api_results_hidden_while_polling_open(client):
    headers = _login(client)

    client.post("/api/admin/polling", json={"action": "open"}, headers=headers)
    assert client.get("/api/admin/results", headers=headers).status_code == 403

    client.post("/api/admin/polling", json={"action": "close"}, headers=headers)
    assert client.get("/api/admin/results", headers=headers).status_code == 200


def test_api_full_vote_cycle_including_refresh_replay(client):
    headers = _login(client)
    client.post("/api/admin/polling", json={"action": "open"}, headers=headers)
    client.post("/api/admin/unlock", json={"voter_name": "Test Student"}, headers=headers)

    ballot = client.get("/api/ballot").json()
    selections = {str(p["id"]): None for p in ballot["posts"]}
    body = {"ballot_id": ballot["ballot_id"], "selections": selections}

    r1 = client.post("/api/ballot/cast", json=body)
    assert r1.status_code == 200

    # simulate the student hitting Back/refresh and re-submitting the same POST
    r2 = client.post("/api/ballot/cast", json=body)
    assert r2.status_code == 409

    state = client.get("/api/state").json()
    assert state["ballot_count"] == 1
    assert state["status"] == "LOCKED"
    assert state["current_voter_name"] is None
