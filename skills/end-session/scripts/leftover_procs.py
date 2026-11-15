"""Find processes a Claude Code session started and left running.

Called by the end-session skill. Report-only by default; Claude decides what
to stop and calls again with --kill. Only PIDs that this very run lists as
leftovers can be killed, so a process of the user's own (or of another
Claude session) can never be hit by mistake. Windows, macOS and Linux;
standard library only.

  python leftover_procs.py                 # report
  python leftover_procs.py --kill 123 456  # stop those trees, then re-scan
Exit code: 0 = clean, 1 = leftovers remain (or a kill was refused/failed).
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = os.name == "nt"
SESSIONS_DIR = Path.home() / ".claude" / "sessions"
CMD_PREVIEW = 120
KILL_GRACE_SECONDS = 1
IGNORED_NAMES = {"conhost", "code", "code helper"}
SHELL_NAMES = {"bash", "sh", "zsh", "fish", "cmd", "powershell", "pwsh"}
ORPHAN_NAMES = SHELL_NAMES | {"node", "python", "python3", "pythonw", "ffmpeg", "ffprobe", "uvicorn",
                              "vite", "chrome", "chromium", "chrome-headless-shell", "google chrome"}
INIT_NAMES = {"init", "systemd", "launchd"}
HEADLESS_MARKS = ("--headless", "ms-playwright", "puppeteer")
MCP_MARK = "mcp"
CLAUDE_CMD = re.compile(r"(^|[/\\\s])claude(\.exe|\.js)?(\s|$)|@anthropic-ai[/\\]claude-code", re.I)
PS_QUERY = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,ParentProcessId,Name,CommandLine,"
            "@{n='Created';e={([DateTimeOffset]$_.CreationDate).ToUnixTimeMilliseconds()}}"
            " | ConvertTo-Json -Compress")


def base(proc: dict) -> str:
    """'C:\\x\\Python.EXE' / '/usr/bin/python3' -> 'python' / 'python3'."""
    name = re.split(r"[/\\]", proc["name"])[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _load_windows() -> dict:
    out = subprocess.run(["powershell", "-NoProfile", "-Command", PS_QUERY],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return {r["ProcessId"]: {"pid": r["ProcessId"], "ppid": r["ParentProcessId"],
                             "name": r["Name"] or "", "cmd": r["CommandLine"] or "",
                             "created": r["Created"] or 0} for r in json.loads(out)}


def _ps_column(column: str) -> dict:
    out = subprocess.run(["ps", "-A", "-o", f"pid=,{column}="], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True).stdout
    return parse_ps_column(out)


def parse_ps_column(out: str) -> dict:
    rows = {}
    for line in out.splitlines():
        pid, _, rest = line.strip().partition(" ")
        if pid.isdigit():
            rows[int(pid)] = rest.strip()
    return rows


def etime_seconds(text: str) -> int:
    """ps etime: [[dd-]hh:]mm:ss."""
    days, _, clock = text.strip().rpartition("-")
    parts = [int(p) for p in clock.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return int(days or 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def _load_posix(now_ms: int) -> dict:
    ppids, etimes, names, cmds = (_ps_column(c) for c in ("ppid", "etime", "comm", "args"))
    return {pid: {"pid": pid, "ppid": int(ppids[pid]), "name": names.get(pid, ""),
                  "cmd": cmds.get(pid, ""), "created": now_ms - etime_seconds(etimes[pid]) * 1000}
            for pid in ppids if pid in etimes and ppids[pid].isdigit()}


def load_processes(now_ms: int) -> dict:
    return _load_windows() if IS_WINDOWS else _load_posix(now_ms)


def parent_of(procs: dict, pid: int):
    """The live parent, or None when it died (PID reuse: a 'parent' younger than its child)."""
    proc, parent = procs.get(pid), procs.get(procs.get(pid, {}).get("ppid"))
    if not proc or not parent or parent["pid"] == pid or parent["created"] > proc["created"]:
        return None
    return parent["pid"]


def ancestors(procs: dict, pid: int) -> list:
    chain, seen = [pid], {pid}
    while (pid := parent_of(procs, pid)) is not None and pid not in seen:
        chain.append(pid)
        seen.add(pid)
    return chain


def descendants(procs: dict, root: int) -> set:
    children = {}
    for pid in procs:
        children.setdefault(parent_of(procs, pid), []).append(pid)
    found, stack = set(), [root]
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in found:
                found.add(child)
                stack.append(child)
    return found


def session_files(sessions_dir: Path) -> dict:
    sessions = {}
    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sessions[int(data["pid"])] = data
        except (ValueError, KeyError, OSError):
            continue
    return sessions


def find_session(procs: dict, start_pid: int, sessions: dict):
    """Nearest ancestor with ~/.claude/sessions/<pid>.json; else one that looks like the claude CLI."""
    chain = ancestors(procs, start_pid)[1:]
    for pid in chain:
        if pid in sessions:
            return pid
    return next((p for p in chain if base(procs[p]) == "claude" or CLAUDE_CMD.search(procs[p]["cmd"])), None)


def _orphaned(procs: dict, pid: int) -> bool:
    parent = parent_of(procs, pid)
    return parent is None or parent == 1 or base(procs[parent]) in INIT_NAMES


def _is_orphan(proc: dict, procs: dict, started_ms: int) -> bool:
    name = base(proc)
    if name not in ORPHAN_NAMES or proc["created"] < started_ms or not _orphaned(procs, proc["pid"]):
        return False
    if "chrom" in name:
        return any(mark in proc["cmd"] for mark in HEADLESS_MARKS)
    return True


def _protected(procs: dict, self_chain: list, other_sessions: set) -> set:
    protected = set(self_chain) | other_sessions | descendants(procs, self_chain[0])
    for other in other_sessions:
        protected |= descendants(procs, other)
    return protected


def find_leftovers(procs: dict, session_pid: int, started_ms: int, self_chain: list,
                   other_sessions: set, now_ms: int) -> dict:
    mcp_tree = set()
    for pid in descendants(procs, session_pid):
        if parent_of(procs, pid) == session_pid and MCP_MARK in procs[pid]["cmd"].lower():
            mcp_tree |= {pid} | descendants(procs, pid)
    pool = descendants(procs, session_pid)
    for pid, proc in procs.items():
        if _is_orphan(proc, procs, started_ms):
            pool |= {pid} | descendants(procs, pid)
    pool -= _protected(procs, self_chain, other_sessions)
    pool = {p for p in pool if base(procs[p]) not in IGNORED_NAMES}
    return _report(procs, pool, session_pid, mcp_tree, now_ms)


def _inner_cmd(procs: dict, root: int, pool: set) -> str:
    """What actually runs under a wrapper shell (bash -c / cmd /c)."""
    for pid in sorted(descendants(procs, root) & pool, key=lambda p: procs[p]["created"]):
        if base(procs[pid]) not in SHELL_NAMES | IGNORED_NAMES:
            return procs[pid]["cmd"][:CMD_PREVIEW]
    return ""


def _item(procs: dict, pid: int, pool: set, session_pid: int, mcp_tree: set, now_ms: int) -> dict:
    kind = "mcp" if pid in mcp_tree else "child" if session_pid in ancestors(procs, pid) else "orphan"
    return {"pid": pid, "name": procs[pid]["name"], "kind": kind,
            "minutes": round((now_ms - procs[pid]["created"]) / 60000, 1),
            "children": len(descendants(procs, pid) & pool),
            "cmd": procs[pid]["cmd"][:CMD_PREVIEW], "inner": _inner_cmd(procs, pid, pool)}


def _report(procs: dict, pool: set, session_pid: int, mcp_tree: set, now_ms: int) -> dict:
    roots = [p for p in sorted(pool) if parent_of(procs, p) not in pool]
    items = [_item(procs, p, pool, session_pid, mcp_tree, now_ms) for p in roots]
    leftovers = [i for i in items if i["kind"] != "mcp"]
    return {"status": "leftovers" if leftovers else "clean", "session_pid": session_pid,
            "leftovers": leftovers, "mcp_servers": [i for i in items if i["kind"] == "mcp"],
            "killable": sorted(p for p in pool if p not in mcp_tree)}


def _kill_tree(pid: int) -> dict:
    if IS_WINDOWS:
        done = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
        return {"pid": pid, "ok": done.returncode == 0, "reason": done.stdout.strip()[:CMD_PREVIEW]}
    tree = [pid, *descendants(load_processes(int(time.time() * 1000)), pid)]
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for target in reversed(tree):
            try:
                os.kill(target, sig)
            except (ProcessLookupError, PermissionError):
                continue
        time.sleep(KILL_GRACE_SECONDS)
    return {"pid": pid, "ok": True, "reason": f"signalled {len(tree)} process(es)"}


def kill(pids: list, killable: list) -> list:
    return [_kill_tree(pid) if pid in killable else
            {"pid": pid, "ok": False, "reason": "not a leftover of this session - refused"} for pid in pids]


def scan(session_pid_arg) -> dict:
    now_ms = int(time.time() * 1000)
    procs, sessions = load_processes(now_ms), session_files(SESSIONS_DIR)
    session_pid = session_pid_arg or find_session(procs, os.getpid(), sessions)
    if session_pid is None or session_pid not in procs:
        return {"status": "error", "reason": "could not find this Claude session's process; pass --session-pid"}
    others = {p for p in sessions if p in procs and p != session_pid}
    started = int(sessions.get(session_pid, {}).get("startedAt") or procs[session_pid]["created"])
    return find_leftovers(procs, session_pid, started, ancestors(procs, os.getpid()), others, now_ms)


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--session-pid", type=int, default=None)
    p.add_argument("--kill", type=int, nargs="+", default=[])
    args = p.parse_args(argv)
    report = scan(args.session_pid)
    if args.kill and report["status"] != "error":
        killed = kill(args.kill, report["killable"])
        time.sleep(KILL_GRACE_SECONDS)
        report = {**scan(args.session_pid), "killed": killed}
    print(json.dumps({k: v for k, v in report.items() if k != "killable"}, ensure_ascii=False, indent=2))
    refused = any(not k["ok"] for k in report.get("killed", []))
    return 0 if report["status"] == "clean" and not refused else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
