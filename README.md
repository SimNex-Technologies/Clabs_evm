# C-LABS Digital EVM

Offline voting machine for the Bhashyam High School Elections — one election
officer, one student at a time. No internet, no cloud, no installation. Runs
on one laptop, or two: a "Main" laptop that students vote on, and an optional
second "Admin" laptop the officer controls it from over the same WiFi/hotspot.

## For the election officer (election day)

**Windows (the real thing):** double-click `Start-Voting.bat` in the unzipped
`C-LABS-EVM` folder. It starts two small console windows in the background
("Backend" and "Frontend") and then opens the voting kiosk in the browser
automatically. Leave both console windows open all day — closing either one
stops voting.

**First run only:** you'll be asked to set an admin password. Write it down
somewhere safe — there's no password reset, only a full election Reset.

### Running the election

1. Open the officer console (see "Reaching the officer console" below), log in.
2. Press **Open Polling**.
3. Call the first student up, check them off the paper roll as usual, then
   press **Unlock For Next Student**.
4. The student votes on the kiosk screen and presses Cast Vote. The machine
   locks itself immediately — no one can vote twice without you unlocking again.
5. Repeat step 3 for every student.
6. When voting ends, press **Lock Voting** then **Close Polling**. Results stay
   hidden until polling is closed (so nobody's early count influences later
   voters).
7. Press **View Results** to see who's winning per post, and **Export Excel**
   to save a spreadsheet copy.

**Rehearsing beforehand?** Turn on **Test Mode** first — those ballots are
counted separately and excluded from real results, so you can practice with
students without touching the actual count. Turn it back off before the real
election.

### Reaching the officer console

**From the Main (voting) laptop itself:** the kiosk deliberately has no visible
link to the admin screen — tap the school name on the welcome/locked screen
**5 times quickly**, or go to `http://127.0.0.1:3000/admin` directly.

**From a second Admin laptop, over WiFi/hotspot:** when `Start-Voting.bat`
starts, it prints one or more addresses like `http://192.168.1.42:3000/admin`
— open that on the Admin laptop's browser (same WiFi/hotspot as the Main
laptop, nothing to install). If more than one address is printed, try them in
order; see "Two-laptop setup" below for why there can be more than one.

### Two-laptop setup

The Main laptop runs everything (backend + voting kiosk) and is what students
vote on. The Admin laptop is optional — it's just a browser pointed at the
Main laptop's `/admin` over the network; nothing runs on it.

- **Both laptops must be on the same WiFi network or the same phone hotspot.**
  Use a private hotspot with a password only you know, not the school's open
  guest WiFi — see "Security note" below for why.
- **Windows Firewall will likely prompt** the first time you run
  `Start-Voting.bat` ("Allow Node.js/Python to communicate on this network?").
  Click **Allow access** — otherwise the Admin laptop can't reach the Main one.
- **If the printed address doesn't load:** `Start-Voting.bat` prints every
  network address it can find, most-likely-first, because there's no fully
  reliable way to guess correctly if this laptop also has a VPN active (a VPN
  can make one candidate address look valid but not actually be reachable from
  the same WiFi). Try each printed address in turn. The minimized
  "C-LABS EVM Backend" console window prints its own, independently
  cross-checked version of the same list if you need a second opinion.

**Security note:** exposing `/admin` to the network necessarily also exposes
the voting page (`/`) itself to any device on that same WiFi/hotspot — they're
the same server. The officer's one-student-at-a-time **Unlock For Next
Student** control is still what actually gates casting a vote (nothing can be
cast without an active unlock), but during that brief unlocked window, a
device on the network could in principle load the voting page too. Running
this on a private hotspot the officer controls, rather than an open network,
is the mitigation — treat that hotspot like the polling booth itself.

**Running on just one laptop?** Everything above still works — just skip the
Admin laptop and use `http://127.0.0.1:3000/admin` on the same machine, same
as before.

### Where the data goes

Nothing leaves the laptop. Everything is under:

```
Desktop/
└── C-LABS Digital EVM/
    ├── Database/election.db     the real record of every vote
    ├── Excel/votes.xlsx         readable results, regenerated after every vote
    └── Backup/
        ├── journal.csv          append-only log, one line per vote per post
        └── backup-*.xlsx/.db    timestamped snapshots (made on Export and Reset)
```

### If something goes wrong

- **Machine says "Voting Locked" and won't do anything:** that's correct
  between students — press Unlock For Next Student from the officer console.
- **One of the console windows closed / crashed:** just re-run
  `Start-Voting.bat`. Every cast vote is already saved to disk; nothing is
  lost. The two minimized console windows ("Backend" and "Frontend") are how
  you know both halves are alive - don't close either while voting is
  happening.
- **Wrong candidate got votes / need to redo:** there's no per-vote undo (by
  design - it's a secret ballot). If the whole election needs to be redone,
  use **Reset Election** (Danger Zone). It backs up the current data first,
  then wipes it.

## For developers

### Architecture

Two processes, always on the same machine:

```
Browser (kiosk + admin UI)
    |
    v
Next.js server  :3000   <- what the browser talks to; owns all HTML/JS/CSS
    | (server-side rewrites: /api/*, /symbols/* -> below)
    v
FastAPI backend :8000   <- pure JSON API + symbol images, no HTML of its own
    |
    v
SQLite (election.db) + Excel/CSV writers, all under ~/Desktop/C-LABS Digital EVM/
```

The browser only ever talks to the Next.js server (port 3000). Next.js's own
`rewrites()` config (`frontend/next.config.mjs`) silently forwards `/api/*` and
`/symbols/*` requests to FastAPI server-side, so there's no CORS to configure
and the frontend's `fetch()` calls use the exact same relative paths either way.
That server-side forward always happens over loopback (both processes are on
the Main laptop), regardless of what address the browser itself used to reach
Next.js - so a second Admin laptop reaching in over WiFi works with zero
changes to the rewrite destination.

In the packaged build, both processes bind `0.0.0.0` (all interfaces) so a
second laptop on the same WiFi/hotspot can reach port 3000 - see "Two-laptop
setup" above and `backend/config.py`'s `HOST`/`lan_ips()`. The dev launchers
(`run.command`/`run.bat`) intentionally stay on `127.0.0.1` - single-machine
only, since that's all local development needs.

### Project layout

```
backend/          FastAPI app: db.py (schema + the atomic cast_ballot
                   transaction), security.py (admin auth), storage.py
                   (Desktop path + Excel/CSV writers), app.py (routes)
frontend/          Next.js (App Router): src/app (routes: / and /admin),
                   src/components/kiosk, src/components/admin
scripts/extract_symbols.py   Regenerates candidates/symbols/ + ballot.json
                              from the ballot PDF - only needed if the
                              candidate roster changes
ballot.json        The roster: posts, candidates, symbol files
candidates/symbols/ The 21 extracted symbol images
tests/             pytest suite - the integrity guarantees, not UI tests
packaging/Start-Voting.bat   Election-day launcher template, copied into
                              the release zip by the CI workflow
```

### Running from source (macOS/Linux dev)

```
./run.command      # first run creates a venv + installs frontend deps;
                    # starts BOTH the backend (:8000) and the Next.js dev
                    # server (:3000), then opens the kiosk in your browser.
                    # Ctrl+C stops both.
```

`run.bat` does the same on Windows (dev/testing only - the school uses the
packaged `Start-Voting.bat`, not this one).

### Tests

```
.venv/bin/pytest tests/ -v
```

These test the integrity guarantees, not the UI: double-submit protection,
locked-machine rejection, stale ballot ids after a re-lock/re-unlock, NOTA
tallying, the poll-time window, reset-then-backup, and concurrent-cast races.
If you change `backend/db.py`, these are what to run.

### Building the Windows package

PyInstaller can't cross-compile - a Windows `.exe` has to be built on Windows,
and a Next.js production server needs a Node.js runtime, which the school's PC
doesn't have. `.github/workflows/build-windows.yml` handles both on GitHub's
`windows-latest` runner on every push to `main`:

1. Builds the Next.js frontend with `output: 'standalone'` (a minimal
   `server.js` + only the `node_modules` it actually needs - no full install
   required on the school PC).
2. Builds `C-LABS-EVM-Backend.exe` with PyInstaller (FastAPI + SQLite +
   `ballot.json` + `candidates/symbols`, no frontend files - those are separate
   now).
3. Downloads the latest Node.js 20 LTS Windows build as a **portable runtime**
   (just the extracted zip, no installer).
4. Zips it all together with `packaging/Start-Voting.bat` into
   `C-LABS-EVM-windows.zip`.

Pushing a tag like `v1.0` also attaches that zip to a GitHub Release:

```
git tag v1.0
git push origin v1.0
```

Download the artifact from the Actions run (or the Release page), unzip it on
the school's laptop, and double-click `Start-Voting.bat`. No installation, no
Python, no globally-installed Node - everything needed is in the folder:

```
C-LABS-EVM/
├── Backend/C-LABS-EVM-Backend.exe   PyInstaller-built FastAPI backend
├── Frontend/                         Next.js standalone server + build output
├── node/                             portable Node.js runtime (win-x64)
└── Start-Voting.bat                  double-click this
```

### If the candidate roster changes

Re-run the extractor (only needed if names/symbols/posts change):

```
python3 scripts/extract_symbols.py
```

It re-renders `~/Downloads/ELECTION LOGO.pdf` at 300 DPI, re-crops all 21
symbols, and rewrites `ballot.json`. Check the printed output for any page
flagged as a fallback crop, and open `candidates/symbols/` to confirm every
image still matches its candidate before committing.
