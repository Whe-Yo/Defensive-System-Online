#!/usr/bin/env bash
# DSO launcher (Linux/macOS).
#   - typed in a terminal   -> runs the dashboard right here
#   - double-clicked in a file manager (no terminal) -> opens a new terminal and runs there
# Same file for both. `install.py` symlinks this to ~/.local/bin/dso so `dso` works anywhere.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
APP="$DIR/src/dso.py"
PY="$(command -v python3 || command -v python)"

if [ -t 0 ] || [ -t 1 ] || [ -t 2 ]; then
    exec "$PY" "$APP" "$@"          # attached to a terminal (incl. piped/redirected): run inline
fi

# no controlling terminal (launched from a GUI): reopen inside one
for term in x-terminal-emulator gnome-terminal konsole xfce4-terminal xterm; do
    if command -v "$term" >/dev/null 2>&1; then
        exec "$term" -e "$PY" "$APP" "$@"
    fi
done
exec "$PY" "$APP" "$@"              # nothing found: last resort
