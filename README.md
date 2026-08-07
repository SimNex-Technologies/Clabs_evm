# C-LABS Digital EVM

Offline voting machine for the Bhashyam High School Elections — one laptop, one
election officer, one student at a time. No internet, no cloud, no installation.

## For the election officer (election day)

**Windows (the real thing):** double-click `C-LABS-EVM.exe`. A console window
opens saying "running" — leave it open all day, it's what's serving the voting
screen. A browser window opens in kiosk mode automatically.

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

The voting kiosk deliberately has no visible link to the admin screen — tap the
school name on the welcome/locked screen **5 times quickly**, or go to
`http://127.0.0.1:8000/admin` directly.

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
- **The console window closed / crashed:** just re-launch `C-LABS-EVM.exe`.
  Every cast vote is already saved to disk; nothing is lost. The Windows
  console window it opens is how you know it's alive - don't close it while
  voting is happening.
- **Wrong candidate got votes / need to redo:** there's no per-vote undo (by
  design - it's a secret ballot). If the whole election needs to be redone,
  use **Reset Election** (Danger Zone). It backs up the current data first,
  then wipes it.

## For developers

### Project layout

```
backend/          FastAPI app: db.py (schema + the atomic cast_ballot
                   transaction), security.py (admin auth), storage.py
                   (Desktop path + Excel/CSV writers), app.py (routes)
frontend/          Vite + React: kiosk (src/kiosk) and officer console
                   (src/admin)
scripts/extract_symbols.py   Regenerates candidates/symbols/ + ballot.json
                              from the ballot PDF - only needed if the
                              candidate roster changes
ballot.json        The roster: posts, candidates, symbol files
candidates/symbols/ The 21 extracted symbol images
tests/             pytest suite - the integrity guarantees, not UI tests
```

### Running from source (macOS/Linux dev)

```
./run.command      # first run creates a venv, installs deps, builds the
                    # frontend, and starts the server at http://127.0.0.1:8000
```

Frontend hot-reload during UI work:
```
python3 main.py --no-browser        # terminal 1 - backend on :8000
cd frontend && npm run dev          # terminal 2 - Vite dev server, proxies
                                     # /api and /symbols to :8000
```

### Tests

```
.venv/bin/pytest tests/ -v
```

These test the integrity guarantees, not the UI: double-submit protection,
locked-machine rejection, stale ballot ids after a re-lock/re-unlock, NOTA
tallying, the poll-time window, reset-then-backup, and concurrent-cast races.
If you change `backend/db.py`, these are what to run.

### Building the Windows .exe

PyInstaller can't cross-compile - a Windows `.exe` has to be built on Windows.
`.github/workflows/build-windows.yml` does this on GitHub's `windows-latest`
runner on every push to `main`, and attaches the `.exe` to a GitHub Release
when you push a tag like `v1.0`:

```
git tag v1.0
git push origin v1.0
```

Download the artifact from the Actions run, or the Release page, and copy
`C-LABS-EVM.exe` to the school's laptop. No installation, no Python, no Node -
it's fully self-contained.

### If the candidate roster changes

Re-run the extractor (only needed if names/symbols/posts change):

```
python3 scripts/extract_symbols.py
```

It re-renders `~/Downloads/ELECTION LOGO.pdf` at 300 DPI, re-crops all 21
symbols, and rewrites `ballot.json`. Check the printed output for any page
flagged as a fallback crop, and open `candidates/symbols/` to confirm every
image still matches its candidate before committing.
