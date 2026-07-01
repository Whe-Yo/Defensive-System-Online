#!/usr/bin/env python3
"""DSO installer (cross-platform) — the only file you run to set things up.

  python3 install.py               # install: register the Claude hook + `dso` command
  python3 install.py --uninstall   # remove both

What it does:
  1. Writes the event hook to ~/.claude/dso_hook.py and registers it on every
     relevant Claude Code event in ~/.claude/settings.json. The hook is plain
     Python (fast to start ~30ms) — a frozen binary would add ~250ms to every
     tool call, so the hook is intentionally NOT the dso binary.
  2. Installs the `dso` dashboard command: on Linux/macOS a launcher in
     ~/.local/bin + a desktop entry (double-click opens a terminal); on Windows
     copies dso.exe into %LOCALAPPDATA%\\Programs\\DSO and adds it to PATH.

Distribute just two files: this install.py and the dso binary (dso / dso.exe).
Run from a source checkout (no binary) and it wires up `python dso.py` instead.
"""
import json
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
CLAUDE = os.path.join(HOME, ".claude")
SETTINGS = os.path.join(CLAUDE, "settings.json")
HOOK_PATH = os.path.join(CLAUDE, "dso_hook.py")
EVENTS = ["PreToolUse", "PostToolUse", "UserPromptSubmit",
          "Notification", "SessionStart", "Stop", "SubagentStop"]
HERE = os.path.dirname(os.path.realpath(__file__))
WINDOWS = os.name == "nt"

# The event hook, written to disk verbatim. Single source of truth for hook
# behaviour lives here (there is no separate hook file to ship).
HOOK_SRC = r'''#!/usr/bin/env python3
"""DSO event hook. Reads a Claude Code hook event from stdin and updates a
per-session state file the dso dashboard renders. Never writes stdout; always
exits 0 so it can't block a tool call."""
import json
import os
import sys
import time

STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "inundation_agent")


def short(s, n=40):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 2] + ".."


def describe(tool, ti):
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
    os.makedirs(STATE_DIR, exist_ok=True)
    path = os.path.join(STATE_DIR, f"{sid}.json")
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
        if tool == "TodoWrite":
            items = (ev.get("tool_input") or {}).get("todos") or []
            st["todos"] = [{"c": short(it.get("content", ""), 38),
                            "s": it.get("status", "pending")}
                           for it in items if it.get("content")]
    elif name == "PostToolUse":
        st["tool_count"] = int(st.get("tool_count", 0)) + 1
        st["status"] = "thinking"
        st["last_tool_at"] = now
    elif name == "Notification":
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
        pass
'''


def read_settings():
    if not os.path.exists(SETTINGS):
        return {}
    try:
        with open(SETTINGS, encoding="utf-8-sig") as f:   # tolerate a pre-existing BOM
            return json.load(f)
    except Exception:
        return {}


def write_settings(data):
    os.makedirs(CLAUDE, exist_ok=True)
    if os.path.exists(SETTINGS):
        shutil.copy2(SETTINGS, SETTINGS + ".dso-bak")
    with open(SETTINGS, "w", encoding="utf-8") as f:      # no BOM: strict JSON parsers reject it
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_dso_hook(cmd):
    return "dso_hook.py" in cmd or "fleet_hook.py" in cmd   # also matches the old name for migration


def register_hook():
    with open(HOOK_PATH, "w", encoding="utf-8") as f:
        f.write(HOOK_SRC)
    cmd = f'"{sys.executable}" "{HOOK_PATH}"'
    data = read_settings()
    hooks = data.setdefault("hooks", {})
    added = []
    for ev in EVENTS:
        blocks = hooks.setdefault(ev, [])
        # drop any stale dso/fleet registration first, then add the current one
        for b in blocks:
            b["hooks"] = [h for h in b.get("hooks", []) if not is_dso_hook(h.get("command", ""))]
        blocks[:] = [b for b in blocks if b.get("hooks")]
        blocks.append({"hooks": [{"type": "command", "command": cmd}]})
        added.append(ev)
    write_settings(data)
    print(f"hook -> {HOOK_PATH}")
    print(f"registered on: {', '.join(added)}")


def unregister_hook():
    data = read_settings()
    hooks = data.get("hooks", {})
    for ev in list(hooks):
        for b in hooks[ev]:
            b["hooks"] = [h for h in b.get("hooks", []) if not is_dso_hook(h.get("command", ""))]
        hooks[ev] = [b for b in hooks[ev] if b.get("hooks")]
        if not hooks[ev]:
            del hooks[ev]
    write_settings(data)
    for p in (HOOK_PATH,):
        if os.path.exists(p):
            os.remove(p)
    print("hook unregistered")


def app_target():
    """The thing to launch: the shipped binary if present, else `python dso.py`."""
    binname = "dso.exe" if WINDOWS else "dso"
    binpath = os.path.join(HERE, binname)
    if os.path.exists(binpath):
        return ("binary", binpath)
    src = os.path.join(HERE, "dso.py")
    if os.path.exists(src):
        return ("source", src)
    return (None, None)


def install_command_unix(kind, path):
    bindir = os.path.join(HOME, ".local", "bin")
    os.makedirs(bindir, exist_ok=True)
    dest = os.path.join(bindir, "dso")
    if os.path.lexists(dest):
        os.remove(dest)
    if kind == "binary":
        shutil.copy2(path, dest)
    else:                                                  # source: tiny launcher -> python dso.py
        with open(dest, "w") as f:
            f.write(f'#!/usr/bin/env bash\nexec "{sys.executable}" "{path}" "$@"\n')
    os.chmod(dest, 0o755)
    # desktop entry (double-click opens a terminal and runs)
    apps = os.path.join(HOME, ".local", "share", "applications")
    os.makedirs(apps, exist_ok=True)
    with open(os.path.join(apps, "dso.desktop"), "w") as f:
        f.write("[Desktop Entry]\nType=Application\nName=DSO — Orbital Defense\n"
                "Comment=Claude Code sessions dashboard\nExec=dso\nTerminal=true\n"
                "Categories=Utility;\n")
    print(f"command -> {dest}")
    if bindir not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"note: add {bindir} to PATH to run `dso` from anywhere")


def install_command_windows(kind, path):
    progs = os.path.join(os.environ.get("LOCALAPPDATA", HOME), "Programs", "DSO")
    os.makedirs(progs, exist_ok=True)
    if kind == "binary":
        dest = os.path.join(progs, "dso.exe")
        shutil.copy2(path, dest)
    else:                                                  # source: dso.cmd -> python dso.py
        dest = os.path.join(progs, "dso.cmd")
        with open(dest, "w") as f:
            f.write(f'@echo off\r\n"{sys.executable}" "{path}" %*\r\n')
    # add install dir to the user PATH (persists; new terminals pick it up)
    cur = os.environ.get("PATH", "")
    if progs.lower() not in cur.lower():
        subprocess.run(["setx", "PATH", f"{cur};{progs}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"added to PATH: {progs}  (open a NEW terminal for `dso`)")
    print(f"command -> {dest}")


def uninstall_command():
    if WINDOWS:
        progs = os.path.join(os.environ.get("LOCALAPPDATA", HOME), "Programs", "DSO")
        for n in ("dso.exe", "dso.cmd"):
            p = os.path.join(progs, n)
            if os.path.exists(p):
                os.remove(p)
    else:
        for p in (os.path.join(HOME, ".local", "bin", "dso"),
                  os.path.join(HOME, ".local", "share", "applications", "dso.desktop")):
            if os.path.lexists(p):
                os.remove(p)
    print("command removed")


def main():
    if "--uninstall" in sys.argv[1:]:
        unregister_hook()
        uninstall_command()
        print("\ndone. new Claude sessions are no longer tracked.")
        return
    register_hook()
    kind, path = app_target()
    if kind is None:
        print("warning: neither dso binary nor dso.py found beside install.py; "
              "hook installed but `dso` command not set up.")
    elif WINDOWS:
        install_command_windows(kind, path)
    else:
        install_command_unix(kind, path)
    print("\ndone. new Claude sessions are tracked. run the dashboard:  dso")


if __name__ == "__main__":
    main()
