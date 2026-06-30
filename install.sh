#!/usr/bin/env bash
# Claude Fleet installer — registers the fleet hook on every relevant Claude
# Code event by merging into ~/.claude/settings.json (idempotent, backed up).
#
#   bash install.sh            # install / re-run safely
#   bash install.sh --uninstall  # remove the fleet hooks
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="${HOME}/.claude/settings.json"
PY="$(command -v python3)"
CMD="${PY} ${DIR}/fleet_hook.py >/dev/null 2>&1 || true"
EVENTS="PreToolUse PostToolUse UserPromptSubmit Notification SessionStart Stop SubagentStop"

[ -f "$SETTINGS" ] || { echo '{}' > "$SETTINGS"; }
cp "$SETTINGS" "${SETTINGS}.fleet-bak.$(date +%s)"

if [ "${1:-}" = "--uninstall" ]; then
  "$PY" - "$SETTINGS" "$DIR" <<'PY'
import json, sys
settings, d = sys.argv[1], sys.argv[2]
data = json.load(open(settings))
hooks = data.get("hooks", {})
for ev, blocks in list(hooks.items()):
    nb = []
    for b in blocks:
        b["hooks"] = [h for h in b.get("hooks", []) if "fleet_hook.py" not in h.get("command", "")]
        if b["hooks"]:
            nb.append(b)
    if nb:
        hooks[ev] = nb
    else:
        del hooks[ev]
json.dump(data, open(settings, "w"), indent=2, ensure_ascii=False)
print("uninstalled fleet hooks")
PY
  echo "done. 백업: ${SETTINGS}.fleet-bak.*"
  exit 0
fi

# install textual if missing
"$PY" -c "import textual" 2>/dev/null || { echo "installing textual..."; "$PY" -m pip install -q textual; }

"$PY" - "$SETTINGS" "$CMD" "$EVENTS" <<'PY'
import json, sys
settings, cmd, events = sys.argv[1], sys.argv[2], sys.argv[3].split()
data = json.load(open(settings))
hooks = data.setdefault("hooks", {})
added = []
for ev in events:
    blocks = hooks.setdefault(ev, [])
    present = any(cmd in h.get("command", "")
                 or "fleet_hook.py" in h.get("command", "")
                 for b in blocks for h in b.get("hooks", []))
    if not present:
        blocks.append({"hooks": [{"type": "command", "command": cmd}]})
        added.append(ev)
json.dump(data, open(settings, "w"), indent=2, ensure_ascii=False)
print("added fleet hook to:", ", ".join(added) if added else "(already installed)")
PY

echo
echo "설치 완료. 새 Claude 세션부터 추적됩니다."
echo "대시보드 실행:  python3 ${DIR}/fleet.py"
