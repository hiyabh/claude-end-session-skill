---
description: "End-of-session close-out routine - the agreed command to wrap up a work session losslessly: tidies the working folder, updates the state snapshot, journal and your knowledge files, changelog and version, then commits and pushes the project (verified; creates a private GitHub remote after a secrets scan), and makes sure no agent or process it started is left running. TRIGGER when the user types /end-session, or says 'סוף סשן', 'סיימנו', 'תסגור סשן', 'נגמר הסשן', 'סוגרים', 'end session', 'wrap up', 'close out the session'. NEVER trigger mid-task - only when the user signals the session is done."
---

# End Session - Agreed Close-Out Command

One agreed command (`/end-session`) that runs the complete, ordered end-of-session routine so
**zero context is lost** and every persistent store stays in sync: a tidy folder, a state
snapshot, a journal, knowledge files, changelog, version, git remote and memory.

**Trigger model:** user-invoked only - when *the user* decides the session is over. Not a hook,
never mid-task.

**Language:** talk to the user in their own language (the summary template at the bottom is in
Hebrew - translate it if the user works in another language). Code and commit messages in English.

**How to run it:** step by step, in this order. After each step note one line - done, or skipped
and why. Skipping a step that does not apply is expected. End with the summary at the bottom.

---

## Pre-flight

**P0. Scope.** A read-only / research session with zero file changes gets no close-out - say so
and stop. Exception: step 5 (knowledge files) still runs if the user stated a new fact worth keeping.

**P1. Active project.** Identify the folder this session actually worked on, plus any output
folders it created elsewhere. A scratch workspace that is not a git repo skips the changelog,
version and project-push steps, but still gets the folder tidy and the journal.

---

## Ordered routine

### 1. External-changes safety check
*Goal: never overwrite work done in parallel through another channel (a bot, another editor or
agent, a teammate, manual edits).*

Only if the project is a git repo with an upstream: `git fetch` (~8s timeout), `git status`,
`git rev-list --count HEAD..@{u}` (if > 0, show `git log --oneline HEAD..@{u}`).
- Clean local + remote ahead: propose `git pull --ff-only`.
- Diverged: show both sides and **ask the user** (merge / rebase / cherry-pick). Never merge
  diverged history silently.

Continue only from a known-good tree. Not a git repo / no upstream: skip silently.

### 2. Folder tidy (automatic)
*Goal: the folder looks finished, not like a workbench.* Scope: the project folder and output
folders created this session.

**Delete - known technical junk only:** `nul` (a Windows `> NUL` accident), `__pycache__/`,
`*.pyc`, `*.tmp`, `Thumbs.db`, orphaned `~$*` Office lock files, and intermediate files *you*
created this session (test renders, scratch scripts, debug output) that are not deliverables.

**Move and rename:**
- Loose files in the root (video, images, zip, PDF, DOCX, exports) go into the folder of the task
  that produced them, or a type folder (`video/`, `images/`, `docs/`, `archives/` - in the user's
  language if the project is in Hebrew).
- Deliverables get a descriptive name that matches their title.
- Unclear where a file belongs: move it to `_לבדיקה/` (`_to-review/`) in the root. Never delete it.

**Never touch:**
- A file referenced by code, config or docs. Grep the full file name first; if it is referenced,
  leave it - unless you moved it this session, then update the reference. (A generic name such
  as `nul` matches `>nul` in scripts; that is not a real reference.)
- Tracked source layout, `.git`, `node_modules`, `.env*`, the memory/journal folders, and raw
  archives kept verbatim on purpose.
- Tool-owned root files: `package.json`, `*-lock.json` / `*.lock`, `.gitignore`, `*.config.*`,
  `README*`, `CLAUDE.md`, `CHANGELOG.md`.
- A file with a live `~$` lock beside it (the user has it open).

On Windows `nul` (like `con`, `prn`, `aux`) is a reserved device name that plain `rm` /
`os.remove` miss: delete it with the `\\?\` prefix, building the backslashes with `chr(92)` to
dodge shell escaping - `python -c "import os;B=chr(92);os.remove(B+B+'?'+B+r'<abs path>')"`.

Move, never overwrite (add ` (2)` on a name clash). On Windows keep every path under 260
characters - count characters, not bytes (a Hebrew letter is 2 bytes in UTF-8). Keep a
"moved → to" list for the journal and the summary. A second run must change nothing.

### 3. Primer (short state snapshot)
File: `<project>/docs/memory/primer.md` (create it if the project keeps none). If it is loaded
into every new session, its size costs context every time - keep it small.
- **Last updated:** date + one-line headline. **Current focus:** 1-2 lines.
- **This session:** 3-6 bullets (done / state / next / blockers) + a link to the journal entry.
- **Enforce the size:** keep only the **5 most recent** session entries - older ones already live
  in the journal, delete them. If a hook appends auto-generated blocks (git snapshots and the
  like), keep only the newest one.

### 4. Session journal (full detail)
File: `docs/journal/YYYY-MM-DD.md` in the project (or your existing journal location; append if
today's entry exists).

Sections: Completed, Current State, **Next Steps (priority order)**, Open Issues, Key Decisions
(with the WHY), Files Changed, Folder tidy (moved → to), Notes.

**Pending-tasks sweep:** before writing Next Steps, scan the whole session for anything the user
mentioned or that was planned but not finished. Each item lands in Next Steps - nothing planned
may silently drop.

### 5. Knowledge files (OPTIONAL)
Only if the user keeps knowledge files - for example a company facts file (projects, numbers,
statuses, team) or a personal details file (family, contacts, institutions). Find them in the
user's `CLAUDE.md` or memory. Otherwise skip.

Sweep the whole session (the user's messages, documents read, decisions) for **new facts** that
belong in one of them:
- Update the right section, tag the source and the date (`[user, 2026-11-13]`,
  `[document X]`), and add a row to the file's change log if it keeps one.
- **A contradiction with an existing value is never decided silently** - record it as an open
  question and show it to the user.
- **Privacy:** the values never go into the journal, primer, changelog, a commit message or any
  file that is pushed. The summary names only the section that changed.

Nothing new: one line, "no new fact".

### 6. CHANGELOG (user-visible changes)
`<project>/CHANGELOG.md`, under `[Unreleased]`, grouped as Added / Changed / Fixed / Removed /
Security / Performance (Keep a Changelog style), in the project's language, one line per change.
Skip for docs-only commits, internal refactors with no user-visible change, dependency bumps and
scratch workspaces. The project should have one but none exists: bootstrap it from `git log`.

### 7. Version bump (SemVer)
`package.json` (or the ecosystem's equivalent) - **only if deployed or released this session**.
PATCH = fixes / copy / small UI; MINOR = features; MAJOR = breaking; the highest level wins.
Move the `[Unreleased]` entries under the new version heading; commit
`chore: bump version to X.Y.Z`. Not deployed: skip.

### 8. Project commit + push (VERIFIED)
Skip only if not a git repo, or the tree is clean **and** nothing is unpushed. A commit that never
leaves the machine is not a backup.

1. **Ensure a remote exists.** No `origin`: offer to create a **private** GitHub repo (needs the
   `gh` CLI, logged in):
   ```bash
   gh repo create <owner>/<name> --private --source=. --push --description "<short description>"
   ```
   **Mandatory scan BEFORE the first push** - a push publishes the *entire history*, and a
   `.gitignore` added later does not clean old commits:
   - File names across all history: `git log --all --pretty=format: --name-only | sort -u`
     against `.env`, `credentials.json`, `token.json`, `*.pem`, `*.key`, `*.db`, `*.sqlite`.
   - Contents across all history: `git grep -I -E '<secret patterns>' $(git rev-list --all)` -
     e.g. `sk-`, `ghp_`, `AKIA`, `AIza`, bot tokens like `\d{8,10}:AA`, `BEGIN .* PRIVATE KEY`.
   - Personal data by content, not only by path (medical, financial, private names).
   - **A finding = stop.** Show what was found and where; the user decides. A private repo is
     not encryption.
2. **Commit whatever remains** (including steps 2-7) as atomic conventional commits - never one
   `wip`.
3. **Push, then verify** - never report success on the exit code alone:
   ```bash
   git push
   git rev-list --count @{u}..HEAD     # must print 0
   test -z "$(git status --porcelain)" # tree must be clean
   ```
   A failed push: surface the exact error, do not report success.
4. Changed runtime code in a deployed project: say plainly whether the deploy ran. A pushed
   commit is not a deployed one.

### 9. Projects registry (OPTIONAL)
Only if the user keeps a central projects registry (for example a `PROJECTS.md` in its own repo).
Edit **only this project's section** - never a whole-file regex, which can silently change another
project's entry. Keep the file's line endings (CRLF vs LF). Append one work-log row, bump the
section's "last updated" (and the file-level one), then commit, push and verify as in 8.3. A second
run must not add a duplicate row.

### 10. Claude config repo (OPTIONAL)
Only if `~/.claude` is itself a git repo and this session changed something in it (skills, hooks,
`CLAUDE.md`, settings). Check `git -C ~/.claude status --porcelain` and
`git -C ~/.claude rev-list --count @{u}..HEAD`; commit only the files this session touched,
push, verify both are empty. Make sure no personal file (details, credentials) appears in
`git status` - it must be gitignored.

### 11. Behavioral memory
Only for a **correction or a confirmed reusable pattern** (a stated preference, a mistake to
avoid, a workflow that worked): one fact per file in Claude Code's memory directory for the
project, plus a one-line pointer in its `MEMORY.md`. Update an existing file rather than duplicate.

### 12. Leftover agents and processes
*Goal: nothing this session started keeps running on the user's computer after it ends.* Runs on
every close-out.

**a. Agents inside the session (Claude's own tools):**
- `ListAgents`: any subagent or fork this session spawned that still runs. If it's not needed, `TaskStop`.
- Background tasks: Bash with `run_in_background`, `Monitor`, `Workflow`. Anything still active gets `TaskStop`.
- `CronList`: a cron this session created only for itself gets `CronDelete`. A standing cron the user
  asked for stays, and is named in the summary.
- An active `/loop`: `ScheduleWakeup` with `stop: true`.
- Never touch what isn't this session's: other Claude sessions, the OS's scheduled tasks, hooks.

**b. Processes on the computer.** Killing a shell doesn't always kill what it started: on Windows,
grandchildren survive their parent. On macOS/Linux they are re-parented to `init`/`launchd`. So a dev
server, `ffmpeg`, a headless browser or a background `python` can outlive the session. Run the
bundled script (`python3` on macOS/Linux, `python` on Windows):
```bash
python3 ~/.claude/skills/end-session/scripts/leftover_procs.py
```
It finds this session's Claude process (via `~/.claude/sessions/<pid>.json`, or the nearest
`claude` ancestor). Then it lists that process's live descendants, plus orphans of known types
(node, python, ffmpeg, shells, headless Chromium) started after the session began.
- `mcp_servers` end with the session. They're info only.
- Each item in `leftovers` has `pid`, `minutes`, `cmd` and `inner`, which is what runs under the
  wrapper shell.

To stop what isn't needed:
`python3 ~/.claude/skills/end-session/scripts/leftover_procs.py --kill <pid> [<pid>...]`. It kills
the whole tree and refuses any PID that isn't a leftover of this session. Then it re-scans. Exit 0
means clean.
- Something kept on purpose (a server the user is using) is named in the summary with its PID.
- Other Claude sessions' processes are excluded by the script. Never kill them by hand.
- No Python available: skip part b and say so in the summary.

### 13. Last checks (one line each)
- **A first production deploy** this session: the public link works and has a proper share
  preview (`og:title`, `og:description`, a 1200x630 `og:image`).

---

## Final delivery

```
✅ סוף סשן - <project>

1. בדיקת שינויים חיצוניים .. <בוצע / N/A - לא git repo>
2. סידור תיקייה ........... <נמחקו N, הועברו M, ל-_לבדיקה K / לא נדרש>
3. Primer ................. <עודכן / N/A>
4. יומן .................. <נכתב: <נתיב מלא>>
5. קובצי ידע ............. <עודכן סעיף X / אין עובדה חדשה / אין קובצי ידע>
6. CHANGELOG .............. <עודכן / דולג - <סיבה>>
7. גרסה .................. <X.Y.Z / לא נפרס>
8. Push לפרויקט ........... <אומת ✓ / N/A - לא git repo / נכשל - <שגיאה>>
9. רישום מרכזי ............ <אומת ✓ / דולג - אין רישום>
10. ריפו ההגדרות .......... <אומת ✓ / לא נגענו / אין>
11. זיכרון ................ <נשמר: <slug> / אין חדש>
12. סוכנים ותהליכים ....... <נקי ✓ / נעצרו N / נשאר בכוונה: <שם> (PID)>
13. בדיקות אחרונות ........ <קישור / לא רלוונטי>

סיכום: <משפט-שניים>
פתוחים למחר: <הפריט הכי קריטי מ-Next Steps>
```
Every file the user should open is written with its full absolute path. A contradiction found in
step 5 appears here as an explicit question.

---

## Rules
- **Order:** the safety check is first; the folder tidy comes before any doc is written, so the
  docs describe the final layout; pushes come after every file is written.
- **No session ends with unpushed work** - and a push is reported only after its verification.
- **Never push past a secrets/PII finding** - stop and ask.
- **No session ends with a forgotten agent or process** it started. What stays on purpose is
  named in the summary; "clean" is reported only after `leftover_procs.py` exits 0.
- **The tidy deletes only known junk.** Everything else is moved; anything unclear goes to
  `_לבדיקה/`.
