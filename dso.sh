#!/usr/bin/env bash
# DSO launcher (Linux/macOS).
#   - run from a terminal   -> runs the dashboard right here
#   - launched from a GUI (no terminal at all) -> opens a new terminal and runs there
# install.py symlinks this to ~/.local/bin/dso so `dso` works anywhere.

# resolve this script's real directory, following symlinks.
# portable: avoids `readlink -f` (a GNU extension missing on stock macOS).
SOURCE="$0"
while [ -h "$SOURCE" ]; do
    D="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    case "$SOURCE" in /*) ;; *) SOURCE="$D/$SOURCE";; esac
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
APP="$DIR/src/dso.py"
PY="$(command -v python3 || command -v python)"

# any std stream attached to a terminal? -> run inline (covers `dso` typed in a shell)
if [ -t 0 ] || [ -t 1 ] || [ -t 2 ]; then
    exec "$PY" "$APP" "$@"
fi

# no terminal at all (launched from a file manager): reopen inside one.
# gnome-terminal / xfce4-terminal take the command after `--`; others use `-e`.
for term in x-terminal-emulator gnome-terminal konsole xfce4-terminal xterm; do
    command -v "$term" >/dev/null 2>&1 || continue
    case "$term" in
        gnome-terminal|xfce4-terminal) exec "$term" -- "$PY" "$APP" "$@" ;;
        *)                             exec "$term" -e "$PY" "$APP" "$@" ;;
    esac
done
exec "$PY" "$APP" "$@"   # no terminal emulator found: last resort
