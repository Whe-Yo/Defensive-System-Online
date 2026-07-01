#!/usr/bin/env python3
"""DSO installer (cross-platform) — the only file you run to set things up.

  python3 install.py               # install: register the Claude hook + `dso` command
  python3 install.py --uninstall   # remove both

What it does:
  1. Copies the event hook (src/dso_hook.py) to ~/.claude/dso_hook.py and
     registers it on every relevant Claude Code event in ~/.claude/settings.json.
     The hook is plain Python (fast to start) and never writes stdout, so it
     can't block a tool call.
  2. Wires up the `dso` dashboard command so you can run it from anywhere:
       Linux/macOS -> symlink ~/.local/bin/dso to dso.sh + a desktop entry
                      (double-click opens a terminal).
       Windows     -> adds this folder to the user PATH so `dso` finds dso.bat.

No packaging, no binary: it just runs the scripts in this folder with your
system Python. Keep this folder where it is (re-run install.py if you move it).
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
HOOK_SRC_FILE = os.path.join(HERE, "src", "dso_hook.py")
WINDOWS = os.name == "nt"


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
    os.makedirs(CLAUDE, exist_ok=True)
    shutil.copy2(HOOK_SRC_FILE, HOOK_PATH)
    cmd = f'"{sys.executable}" "{HOOK_PATH}"'
    data = read_settings()
    hooks = data.setdefault("hooks", {})
    for ev in EVENTS:
        blocks = hooks.setdefault(ev, [])
        # drop any stale dso/fleet registration first, then add the current one
        for b in blocks:
            b["hooks"] = [h for h in b.get("hooks", []) if not is_dso_hook(h.get("command", ""))]
        blocks[:] = [b for b in blocks if b.get("hooks")]
        blocks.append({"hooks": [{"type": "command", "command": cmd}]})
    write_settings(data)
    print(f"hook -> {HOOK_PATH}")
    print(f"registered on: {', '.join(EVENTS)}")


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
    if os.path.exists(HOOK_PATH):
        os.remove(HOOK_PATH)
    print("hook unregistered")


def install_command_unix():
    launcher = os.path.join(HERE, "dso.sh")
    os.chmod(launcher, 0o755)
    bindir = os.path.join(HOME, ".local", "bin")
    os.makedirs(bindir, exist_ok=True)
    dest = os.path.join(bindir, "dso")
    if os.path.lexists(dest):
        os.remove(dest)
    os.symlink(launcher, dest)
    # desktop entry (double-click opens a terminal and runs)
    apps = os.path.join(HOME, ".local", "share", "applications")
    os.makedirs(apps, exist_ok=True)
    with open(os.path.join(apps, "dso.desktop"), "w") as f:
        f.write("[Desktop Entry]\nType=Application\nName=DSO — Orbital Defense\n"
                f"Comment=Claude Code sessions dashboard\nExec={launcher}\n"
                "Terminal=true\nCategories=Utility;\n")
    print(f"command -> {dest} -> {launcher}")
    if bindir not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"note: add {bindir} to PATH to run `dso` from anywhere")


def install_command_windows():
    launcher = os.path.join(HERE, "dso.bat")   # `dso` on PATH resolves to dso.bat
    cur = os.environ.get("PATH", "")
    if HERE.lower() not in cur.lower():
        subprocess.run(["setx", "PATH", f"{cur};{HERE}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"added to PATH: {HERE}  (open a NEW terminal for `dso`)")
    print(f"command -> {launcher}")


def uninstall_command():
    if WINDOWS:
        print("note: remove this folder from PATH manually if desired")
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
    if not os.path.exists(HOOK_SRC_FILE):
        sys.exit(f"error: {HOOK_SRC_FILE} not found; run install.py from the repo root.")
    register_hook()
    if WINDOWS:
        install_command_windows()
    else:
        install_command_unix()
    print("\ndone. new Claude sessions are tracked. run the dashboard:  dso")


if __name__ == "__main__":
    main()
