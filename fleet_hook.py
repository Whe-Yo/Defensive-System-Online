#!/usr/bin/env python3
"""Inundation_Agent — universal hook handler.

Registered on multiple Claude Code hook events. Reads the event JSON from
stdin, updates a per-session state file at ~/.claude/inundation_agent/<id>.json,
then exits 0 with no stdout so it never blocks a tool call.

The renderer (fleet.py) tails that directory to render every live session as
a descending hostile contact engaged by the orbital defense turret.
"""
import json
import os
import sys
import time

FLEET_DIR = os.path.join(os.path.expanduser("~"), ".claude", "inundation_agent")


def short(s, n=40):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 2] + ".."   # ASCII (no ambiguous-width …)


def describe(tool, ti):
    """Human-readable target for a tool call."""
    ti = ti or {}
    if tool in ("Edit", "Write", "Read", "NotebookEdit"):
        return os.path.basename(ti.get("file_path", "") or "")
    if tool == "Bash":
        return short(ti.get("command", ""), 38)
    if tool in ("Grep", "Glob"):
        return short(ti.get("pattern", ti.get("glob", "")), 30)
    if tool == "Task":
        return short(ti.get("subagent_type") or ti.get("description", ""), 30)
    if tool in ("WebFetch", "WebSearch"):
        u = ti.get("url") or ti.get("query") or ""
        return short(u.replace("https://", "").replace("http://", ""), 34)
    return ""


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return
    sid = ev.get("session_id")
    if not sid:
        return
    os.makedirs(FLEET_DIR, exist_ok=True)
    path = os.path.join(FLEET_DIR, f"{sid}.json")
    st = load(path)

    now = time.time()
    name = ev.get("hook_event_name", "")
    st["session_id"] = sid
    st["cwd"] = ev.get("cwd", st.get("cwd", ""))
    st["last_event_at"] = now
    st.setdefault("started_at", now)
    st.setdefault("tool_count", 0)

    if name == "SessionStart":
        st["status"] = "idle"
        st["action"] = ""
        if ev.get("source") in ("startup", "clear"):
            st["started_at"] = now
            st["tool_count"] = 0
    elif name == "UserPromptSubmit":
        st["status"] = "thinking"
        st["action"] = short(ev.get("prompt", ""), 38)
    elif name == "PreToolUse":
        tool = ev.get("tool_name", "")
        st["status"] = "working"
        st["tool"] = tool
        tgt = describe(tool, ev.get("tool_input"))
        st["action"] = f"{tool} {tgt}".strip()
        if tool == "TodoWrite":                          # capture the task list (one enemy per todo)
            items = (ev.get("tool_input") or {}).get("todos") or []
            st["todos"] = [{"c": short(it.get("content", ""), 38),
                            "s": it.get("status", "pending")}
                           for it in items if it.get("content")]
    elif name == "PostToolUse":
        st["tool_count"] = int(st.get("tool_count", 0)) + 1
        st["status"] = "thinking"
        st["last_tool_at"] = now
    elif name == "Notification":
        # any notification = the session is blocked pending the user (permission OR
        # waiting for input to finish a task) -> HOLD, so it shows as "needs you"
        st["status"] = "waiting"
        st["action"] = short(ev.get("message", "needs input"), 38)
    elif name in ("Stop", "SubagentStop"):
        st["status"] = "idle"
        st["action"] = ""

    save(path, st)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never break a tool call
