---
description: "End-of-session close-out routine. The user's agreed command to wrap up a work session correctly and losslessly. TRIGGER when the user types /end-session, or says 'סוף סשן', 'סיימנו', 'תסגור סשן', 'נגמר הסשן', 'סוגרים', 'end session', 'wrap up', 'close out the session'. Runs the full ordered close-out: external-changes safety check → primer → journal → changelog → version bump → registry commit+push (verified) → Layer-4 memory. Skip individual steps per the per-step skip rules. NEVER trigger mid-task — only when the user signals the session is done."
---

# End Session — Agreed Close-Out Command

## Purpose
One agreed command (`/end-session`) that runs the complete, ordered end-of-session
routine so **zero context is lost** and all persistent stores stay in sync.
This consolidates Iron Rule #3 (docs auto-update), the 5-Layer Memory protocol,
the Session Journal, the Global Project Registry, and the CHANGELOG rules into a
single deterministic sequence — plus the agreed safety/verification additions.

**Trigger model:** user-invoked only. The user types the command (or an equivalent
Hebrew phrase) when *they* decide the session is over. This is NOT a Stop hook and
must NOT fire automatically mid-task.

**Language:** all explanations/summaries to the user in Hebrew. Code, commit
messages, and file content per the global formatting rules.

---

## Pre-flight (run first, before any write)

**P0. Confirm scope.** If the session was read-only / research-only with **zero file
changes and zero project work**, do NOT run the full routine. Say so in Hebrew and
stop. (A pure-question session does not need a journal, registry row, or changelog.)

**P1. Determine the active project.**
- Identify which project folder this session actually worked on
  (`C:\Users\hiya\Documents\<project>\` or another path).
- The workspace `claude-general` is **not a git repo** and is for cross-cutting
  experiments — for it, steps 3 (changelog), 5 (version bump), and the in-project
  git parts of step 4 are normally **N/A**; only the registry repo gets committed.

---

## Ordered routine

> Run the steps **in this order**. After each step, note one line of what was done
> (or why skipped). At the end, present the Hebrew summary in the format at the bottom.

### Step 1 — External-changes safety check (ADDED)
*Goal: never overwrite work done in parallel via another channel (Telegram bot,
Codex/Cursor, Railway agent, manual edits) before the final commit.*

Only if the **active project** is a git repo with an upstream:
1. `git fetch` (timeout ~8s).
2. `git status` — surface any uncommitted local changes.
3. `git rev-list --count HEAD..@{u}` — if > 0, run `git log --oneline HEAD..@{u}`
   and show the user what changed.
4. Resolve before committing:
   - clean local + remote ahead → propose fast-forward `git pull`.
   - diverged → show both sides and **ask the user** how to proceed (merge/rebase/cherry-pick).
5. Only continue once the tree is in a known-good state.

If not a git repo / no upstream → skip silently.

### Step 2 — Primer (Layer 2) — SHORT, points to journal (DEDUP)
File: `<project>/docs/memory/primer.md`

Keep the primer a **concise state snapshot**, not a duplicate of the journal:
- **Last updated:** date + one-line headline.
- **Current focus** (1–2 lines).
- **This session (short):** 3–6 bullets — done / state / next / blockers.
- **Link** to the full journal entry from Step 3 instead of re-pasting detail.

The Stop hook (`session-end.sh`) will auto-append a git snapshot afterward — don't
duplicate that.

If `docs/memory/primer.md` is missing → `bash ~/.claude/scripts/memory/bootstrap.sh`
first.

### Step 3 — Session Journal (full detail)
File: `~/.claude/skills/session-journal/logs/YYYY-MM-DD-<project>.md`
(append if an entry for today already exists).

Full log per the `session-journal` format:
- Completed · Current State · **Next Steps (priority order)** · Open Issues ·
  Key Decisions (with WHY) · Files Changed · Notes.

**Pending-tasks sweep (ADDED):** before writing Next Steps, scan this session for
*anything the user mentioned or that was planned but not finished*, and make sure
each appears in Next Steps. This section is tomorrow's todo list — nothing planned
may silently drop.

### Step 4 — CHANGELOG (user-visible changes)
File: `<project>/CHANGELOG.md` → under `[Unreleased]`, in Hebrew, by category
(Added / Changed / Fixed / Removed / Security / Performance).

**Skip rules (made explicit):**
- Skip for docs-only commits, internal-only refactors with no UX change, and
  dependency bumps with no behavior change.
- **`claude-general` / experiment workspaces have no CHANGELOG** — skip without
  deliberation.
- If the project should have a CHANGELOG and none exists → bootstrap it from
  `git log`.

### Step 5 — Version bump (SemVer)
File: `<project>/package.json` (or equivalent) — **only if deployed this session**.
- PATCH = fixes/copy/small UI · MINOR = features/fields/pages · MAJOR = breaking.
- Multiple changes → highest level wins.
- Commit message includes it: `chore: bump version to X.Y.Z`.
- Not deployed → skip.

### Step 6 — Project Registry (commit + push, VERIFIED)
File: `C:\Users\hiya\projects-registry\PROJECTS.md`

1. Read it. If the project exists → append one work-log row (today's date + one-line
   summary). If new → add a section from the template.
2. Bump the project's **last updated** and the file-level **last updated**.
3. Commit + push:
   ```bash
   cd C:/Users/hiya/projects-registry && \
   git add PROJECTS.md && \
   git commit -m "update: <project> — <one-line summary>" && \
   git push
   ```
4. **Verify the push (ADDED):** detect the upstream branch — do **not** assume
   `main` (this repo is on `master`). Use:
   ```bash
   UP=$(git rev-parse --abbrev-ref --symbolic-full-name @{u})  # e.g. origin/master
   git log "$UP"..HEAD --oneline          # must be empty
   test -z "$(git status --porcelain)"    # tree must be clean
   ```
   If the push failed (auth/conflict), surface it to the user with the exact
   error — do **not** report success.

### Step 7 — Layer-4 behavioral memory
Only if this session produced a **correction or a confirmed reusable pattern**:
- Add/update a memory file under
  `C:\Users\hiya\.claude\projects\...\memory\` (one fact per file, with frontmatter)
  and a one-line pointer in `MEMORY.md`.
- Check for an existing file that already covers it — update rather than duplicate.
- Nothing new behaviorally → skip.

---

## Final delivery (Hebrew)

Present a compact checklist of what ran vs. skipped, then a 1–2 sentence summary:

```
✅ סוף סשן — <project>

1. External check ....... <בוצע / N/A — לא git repo>
2. Primer ............... <עודכן / N/A>
3. Journal .............. <נכתב: <שם הקובץ>>
4. CHANGELOG ............ <עודכן / דולג — <סיבה>>
5. Version bump ......... <X.Y.Z / לא נפרס>
6. Registry ............. <commit+push אומת ✓ / נכשל — <שגיאה>>
7. Memory L4 ............ <נשמר: <slug> / אין חדש>

סיכום: <משפט-שניים>
פתוחים למחר: <bullet הכי קריטי מ-Next Steps>
```

---

## Rules
- **User-invoked only** — never run as part of mid-task work.
- **Order matters** — safety check (Step 1) is always first; registry push (Step 6)
  is last among writes so it captures everything.
- **Per-step skip is allowed and expected** — note the reason, don't force a step
  that doesn't apply (especially in `claude-general`).
- **Never report a push as successful without verifying it** (Step 6.4).
- **Never drop a planned/pending task** — it must land in Next Steps (Step 3).
- **No CHANGELOG/version churn** for experiments, docs-only, or no-UX-change work.
