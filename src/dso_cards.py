#!/usr/bin/env python3
"""Claude Fleet — INUNDATION // FLEET COMMAND console.

A terminal dashboard that renders every live Claude Code session as a military
frigate in a retro CRT-neon fleet command display. Aesthetic inspired by the
*범람 (Inundation)* project (CRT neon vector, rectilinear hard-SF warships) —
this is a monitor, not the game; 범람 is developed separately.

    python3 dso_cards.py            # run the console
    python3 dso_cards.py --once     # print one frame and exit (no TUI)

Honest note: Claude exposes no true task "% complete". The REACTOR gauge shows
*activity output* (full while acting, decaying while idle); SECTOR is a cosmetic
function of elapsed time. Status, current action, SCRAP (tool count) and
operation time are real.
"""
import json
import os
import sys
import time
import glob

FLEET_DIR = os.path.join(os.path.expanduser("~"), ".claude", "inundation_agent")
IDLE_AFTER = 20
OFFLINE_AFTER = 1800
PRUNE_AFTER = 7200
BAR_W = 18

# CRT-neon palette (truecolor)
NEON = {
    "green": "#39ff9e", "cyan": "#27e6ff", "amber": "#ffcc44",
    "magenta": "#ff4fa3", "grey": "#46606e", "dark": "#1b3a3a",
    "scan": "#0fae8a",
}

# hull classes assigned deterministically by session id
HULLS = [
    ("Frigate", "FF"),
    ("Destroyer", "DD"),
    ("Cruiser", "CG"),
    ("Flagship", "ARK"),
]

# rectilinear / stepped military frigate, facing right (block art, width-1 cells)
SHIP = [
    "   ▟██▙   ",
    " ▐███████▶",
    "   ▜██▛   ",
]

STATUS = {
    "working":  ("green",   "◤ ENGAGED",   "교전중"),
    "thinking": ("amber",   "◈ PROCESS",   "연산중"),
    "waiting":  ("magenta", "⚠ AWAITING",  "명령대기"),
    "idle":     ("cyan",    "○ STANDBY",   "대기"),
    "offline":  ("grey",    "✕ NO SIGNAL", "통신두절"),
}


def hull_for(sid):
    h = sum(bytearray(sid.encode()))
    cls, tag = HULLS[h % len(HULLS)]
    return cls, f"{tag}-{h % 90 + 10:02d}"


def fmt_dur(sec):
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m"
    return f"{sec // 3600}h{(sec % 3600) // 60}m"


def pad(s, w):
    return s + " " * max(0, w - len(s))


def read_sessions():
    out, now = [], time.time()
    for p in glob.glob(os.path.join(FLEET_DIR, "*.json")):
        try:
            with open(p) as f:
                st = json.load(f)
        except Exception:
            continue
        age = now - st.get("last_event_at", 0)
        if age > PRUNE_AFTER:
            try:
                os.remove(p)
            except OSError:
                pass
            continue
        st["_age"] = age
        eff = st.get("status", "idle")
        if age > OFFLINE_AFTER:
            eff = "offline"
        elif eff in ("working", "thinking") and age > IDLE_AFTER:
            eff = "idle"
        st["_eff"] = eff
        out.append(st)
    out.sort(key=lambda s: (s["_eff"] == "offline", s["_age"]))
    return out


def reactor_bar(st, frame):
    age, eff = st["_age"], st["_eff"]
    if eff in ("working", "thinking", "waiting"):
        level = max(0.35, 1.0 - age / IDLE_AFTER)
    elif eff == "idle":
        level = max(0.0, 0.35 - age / OFFLINE_AFTER)
    else:
        level = 0.0
    filled = int(round(level * BAR_W))
    color = NEON[STATUS.get(eff, ("grey",))[0]]
    cells = []
    for i in range(BAR_W):
        if i < filled:
            shimmer = eff == "working" and i == filled - 1 and (frame % 2)
            cells.append(f"[{color}]{'▒' if shimmer else '█'}[/]")
        else:
            cells.append(f"[{NEON['dark']}]░[/]")
    return "".join(cells)


def make_card(st, frame):
    from rich.panel import Panel
    from rich.text import Text
    from rich.console import Group
    from rich import box

    sid = st.get("session_id", "?")
    cls, desig = hull_for(sid)
    proj = os.path.basename(st.get("cwd", "")) or "~"
    eff = st["_eff"]
    skey, label, kor = STATUS.get(eff, ("grey", eff, ""))
    color = NEON[skey]

    # weapon muzzle / engine trail animation
    trail = ""
    if eff == "working":
        trail = ["  ·", "  ─", " ─✦", "─✦ "][frame % 4]
    elif eff in ("thinking", "waiting"):
        trail = ["  ·", "   ", "  ·", "   "][frame % 4]

    op = fmt_dur(time.time() - st.get("started_at", time.time()))
    sector = min(6, 1 + int((time.time() - st.get("started_at", time.time())) // 300))
    scrap = st.get("tool_count", 0)

    # 3 ship-art lines, each with side text
    side = [
        f"[bold {color}]{label}[/]",
        f"[{NEON['cyan']}]{desig}[/] [dim]{cls}[/]",
        f"[dim {color}]{kor}[/]",
    ]
    ship_lines = []
    for i, art in enumerate(SHIP):
        art_disp = art + (trail if i == 1 else "")
        ln = f"[{color}]{pad(art_disp, 11)}[/]  {side[i]}"
        ship_lines.append(Text.from_markup(ln))

    bar = Text.from_markup(f"[{NEON['scan']}]REACTOR[/] " + reactor_bar(st, frame))

    action = st.get("action", "") or "—"
    if eff == "idle" and st.get("_age", 0) > 2:
        extra = f"  ({action})" if action and action != "—" else ""
        action = f"standby {fmt_dur(st['_age'])}{extra}"
    elif eff == "offline":
        action = f"signal lost {fmt_dur(st['_age'])} ago"
    act = Text("▶ " + action, style=color if eff == "working" else NEON["cyan"],
               overflow="ellipsis")

    meta = Text.from_markup(
        f"[dim]SECTOR {sector}/6 · SCRAP {scrap} · OP {op}[/]")

    title = f"[bold {color}]◢ {desig}[/] [dim]·[/] [{NEON['cyan']}]{proj}[/]"
    body = Group(*ship_lines, bar, act, meta)
    return Panel(body, title=title, title_align="left", box=box.DOUBLE,
                 border_style=color, width=40, padding=(0, 1))


def render(frame):
    from rich.columns import Columns
    from rich.text import Text
    from rich.console import Group

    sessions = read_sessions()
    title = Text.from_markup(
        f"[{NEON['scan']}]▞▚[/] [bold {NEON['green']}]INUNDATION[/] "
        f"[{NEON['cyan']}]// FLEET COMMAND[/] [{NEON['scan']}]▚▞[/]")
    if not sessions:
        return Group(title, Text(""),
                     Text("  편대 대기 — 활성 함선이 없습니다.", style=NEON["grey"]),
                     Text("  세션에서 도구를 쓰면 함선이 출격합니다.", style=NEON["grey"]))
    active = sum(1 for s in sessions if s["_eff"] in ("working", "thinking", "waiting"))
    lost = sum(1 for s in sessions if s["_eff"] == "offline")
    status = Text.from_markup(
        f"  [{NEON['green']}]⚔ {active} engaged[/]  "
        f"[dim]· {len(sessions)} hulls · {lost} lost ·[/]  "
        f"[{NEON['scan']}]q 종료[/]")
    scan = Text("  " + "▔" * 56, style=NEON["dark"])
    cards = [make_card(s, frame) for s in sessions]
    return Group(title, status, scan, Columns(cards, expand=False, equal=False))


def run_once():
    from rich.console import Console
    Console().print(render(0))


def run_tui():
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    class Fleet(App):
        CSS = "Screen { background: #061212; } Static { padding: 1; }"
        BINDINGS = [("q", "quit", "Quit"), ("ctrl+c", "quit", "Quit")]

        def compose(self) -> ComposeResult:
            yield Static(id="grid")

        def on_mount(self):
            self.frame = 0
            self.tick()
            self.set_interval(0.5, self.tick)

        def tick(self):
            self.frame += 1
            self.query_one("#grid", Static).update(render(self.frame))

    Fleet().run()


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        try:
            run_tui()
        except ImportError:
            print("textual 미설치 — pip install textual\n폴백: --once 1프레임 출력\n")
            run_once()
