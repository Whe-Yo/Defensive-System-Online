#!/usr/bin/env python3
"""Inundation_Agent — ORBITAL DEFENSE (pixel renderer).

A real-time, half-block PIXEL framebuffer dashboard for multiple Claude Code
sessions, themed as a planetary defense turret.

  * One defense TURRET sits at 6 o'clock (bottom-centre) on the ground.
  * Every live Claude session is an unidentified hostile CONTACT descending
    from the sky.
  * When a session is ENGAGED (running a tool), the turret fires a neon beam
    up at that contact. One turret, many targets — beams fan out to each
    active session.

Lineage: a sibling of the *범람 (Inundation)* project. Where 범람 is a fleet
returning to Earth, Inundation_Agent is the turret that defends it. This is a
MONITOR, not the game; 범람 is developed separately.

Why half-block: one terminal cell = two vertically-stacked pixels (the `▀`
char with independent fg/bg colours), giving a colour framebuffer that survives
tmux/SSH (it is coloured text, not a bitmap protocol).

    python3 fleet.py             # run the live scene  (q / Ctrl-C to quit)
    python3 fleet.py --once      # print one frame and exit (snapshot)
    python3 fleet.py --fps 15    # frame rate (default 12)
    python3 fleet.py --truecolor # 24-bit colour (needs RGB-capable tmux/term)
    python3 fleet.py --cards     # simple card view (fleet_cards.py)
    python3 fleet.py --bench 60  # render-only benchmark

Honest note: Claude exposes no true task "% complete". The SIG gauge shows
*activity output* (full while acting, decaying while idle); the turret fires
only for genuinely active sessions. Status, current action, HITS (tool count)
and T+ (elapsed) are real.
"""
import json
import os
import sys
import time
import glob
import math
import unicodedata

FLEET_DIR = os.path.join(os.path.expanduser("~"), ".claude", "inundation_agent")
IDLE_AFTER = 20
OFFLINE_AFTER = 1800
PRUNE_AFTER = 7200

MAX_W, MAX_H = 220, 64
BG = (4, 8, 16)

# ---- CRT-neon palette (RGB) -------------------------------------------------
STAR_DIM = (95, 105, 125)
STAR_BRT = (215, 225, 245)
GROUND = (10, 30, 28)
GROUND_RIM = (40, 120, 110)
CITY = (120, 200, 180)
TURRET_HULL = (60, 150, 170)
TURRET_HI = (130, 220, 235)
TURRET_SH = (28, 70, 86)
TURRET_BARREL = (170, 235, 245)
HOSTILE_DARK = (24, 14, 30)
WHITE = (245, 255, 250)

STATUS = {
    "working":  ((80, 255, 150), "ENGAGED",  "교전"),     # turret fires
    "thinking": ((255, 200, 80), "TRACKING", "추적"),
    "waiting":  ((255, 84, 162), "HOLD",     "대기명령"),
    "idle":     ((90, 190, 230), "DORMANT",  "휴면"),
    "offline":  ((90, 100, 116), "LOST",     "소실"),
}

# descending hostile contact, 11 x 6  (k=shell, m=membrane[accent], e=eye)
HOSTILE = [
    "..k.....k..",
    ".kkmmkmmkk.",
    "kmmm e mmmk",
    "kmmmeeemmmk",
    ".kmm e mmk.",
    "..kk.k.kk..",
]
HOST_W, HOST_H = 11, 6

CLASSES = [("Drifter", "UX"), ("Stinger", "UX"), ("Lurker", "UX"), ("Maw", "UX")]


def dim(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


def lerp(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def noise(x, y, t):
    h = (x * 374761393 + y * 668265263 + t * 982451653) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h >> 8) & 0xFF


# ---- data -------------------------------------------------------------------
def fmt_dur(sec):
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m"
    return f"{sec // 3600}h{(sec % 3600) // 60}m"


def contact_id(sid):
    h = sum(bytearray(sid.encode()))
    cls, tag = CLASSES[h % 4]
    return cls, f"{tag}-{h % 90 + 10:02d}"


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


# ---- framebuffer ------------------------------------------------------------
class FB:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[BG] * w for _ in range(h)]

    def clear(self):
        for row in self.px:
            for i in range(self.w):
                row[i] = BG

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def add(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = self.px[y][x]
            self.px[y][x] = (min(255, o[0] + int(c[0] * a)),
                             min(255, o[1] + int(c[1] * a)),
                             min(255, o[2] + int(c[2] * a)))

    def line(self, x0, y0, x1, y1, color, frame=0, dashed=False):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        i = 0
        while True:
            if not dashed or ((i + frame * 2) % 5 < 3):
                core = (i % 7 < 2)
                self.add(x0, y0, WHITE if core else color, 1.0 if core else 0.75)
            i += 1
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy


# ---- scene elements ---------------------------------------------------------
# ASCII-only glyphs — avoid East-Asian "ambiguous width" chars that render as
# 2 cells in CJK terminals/tmux and break the 1-cell-per-char column model.
DOT = {"working": "*", "thinking": "+", "waiting": "!", "idle": "o", "offline": "x"}


def draw_turret(fb, cx, top, frame):
    """Small flat square defense base (sits on the ground lights). top = base top px."""
    for j in range(2):                                # 5-wide x 2-tall flat block
        for dx in range(-2, 3):
            col = (TURRET_HI if abs(dx) == 2 else TURRET_HULL) if j == 0 else TURRET_SH
            fb.set(cx + dx, top + j, col)
    return cx, top - 1                                # beams emanate from top centre


def draw_blip(fb, cx, cy, eff, accent, frame):
    """Small contact blip (3x3 diamond) for the banner radar."""
    pulse = 0.55 + 0.45 * math.sin(frame * 0.3 + cx)
    body = accent if eff != "offline" else dim(accent, 0.4)
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        fb.set(cx + dx, cy + dy, lerp(dim(body, 0.5), body, pulse))
    fb.set(cx, cy, lerp(body, WHITE, 0.4 + 0.3 * pulse))   # bright core


# ---- overlay text -----------------------------------------------------------
_BLOCK = set("█░▀▒▓")


def _safe(ch):
    """Force width-1: arbitrary CJK/emoji in actions/paths would render 2 cells
    and desync the column model, so map any wide/ambiguous glyph to '?'."""
    if 32 <= ord(ch) < 127 or ch in _BLOCK:
        return ch
    return "?" if unicodedata.east_asian_width(ch) in ("W", "F", "A") else ch


def put_text(overlay, row, col, s, rgb, maxcol, mincol=0):
    for i, ch in enumerate(s):
        c = col + i
        if c >= maxcol:
            break
        if c >= mincol and ch != " ":
            overlay[(row, c)] = (_safe(ch), rgb)
    return col + len(s)


def put_center(overlay, row, cx, s, rgb, maxcol):
    return put_text(overlay, row, cx - len(s) // 2, s, rgb, maxcol)


def sig_blocks(st, n=8):
    age, eff = st["_age"], st["_eff"]
    if eff in ("working", "thinking", "waiting"):
        lvl = max(0.35, 1.0 - age / IDLE_AFTER)
    elif eff == "idle":
        lvl = max(0.0, 0.35 - age / OFFLINE_AFTER)
    else:
        lvl = 0.0
    f = int(round(lvl * n))
    return "█" * f + "░" * (n - f)   # block elements = fixed width 1


def build_scene(fb, overlay, sessions, frame, rows, cols):
    fb.clear()
    cyan = (90, 200, 230)
    green = (80, 255, 150)
    dimc = dim(cyan, 0.65)
    active = sum(1 for s in sessions if s["_eff"] in ("working", "thinking", "waiting"))
    lost = sum(1 for s in sessions if s["_eff"] == "offline")

    # ---- header (row 0) ----
    put_text(overlay, 0, 1, "INUNDATION_AGENT", green, cols)
    put_text(overlay, 0, 18, "// ORBITAL DEFENSE", cyan, cols)
    hud = f"{active} ENGAGING  {len(sessions)} CONTACTS  {lost} LOST   q quit"
    put_text(overlay, 0, max(19, cols - len(hud) - 1), hud, cyan, cols)

    # ---- compact battle banner (pixels, char rows 1..ban_h) ----
    ban_top, ban_h = 1, 6
    p0, p1 = ban_top * 2, (ban_top + ban_h) * 2 - 1
    cx = cols // 2
    for d in range(0, cx, 4):                           # symmetric base lights (about centre)
        fb.set(cx + d, p1, CITY)
        fb.set(cx - d, p1, CITY)
    muzzle = draw_turret(fb, cx, p1 - 1, frame)         # base sits on the light row
    n = len(sessions)
    if n:
        margin, span = 6, max(1, cols - 12)
        for i, st in enumerate(sessions):
            eff = st["_eff"]
            accent = STATUS.get(eff, ((200, 200, 200),))[0]
            bx = margin + (span * (2 * i + 1)) // (2 * n)
            by = p0 + 2 + (noise(i, 4, 0) % 3) + int(round(math.sin(frame * 0.1 + i)))
            draw_blip(fb, bx, by, eff, accent, frame)
            if eff == "working":
                fb.line(muzzle[0], muzzle[1], bx, by + 1, accent, frame=frame, dashed=True)
                fb.add(muzzle[0], muzzle[1], WHITE, 1.0)

    # ---- divider (drawn as pixels, not box-drawing chars) ----
    drow = ban_top + ban_h
    for x in range(cols):
        fb.set(x, drow * 2, dim(cyan, 0.35))
        fb.set(x, drow * 2 + 1, dim(cyan, 0.35))

    # ---- readable list: one line per session ----
    list_top = drow + 1
    capacity = max(0, rows - list_top)
    shown = sessions if n <= capacity else sessions[:max(0, capacity - 1)]
    for i, st in enumerate(shown):
        eff = st["_eff"]
        accent, label, kor = STATUS.get(eff, ((200, 200, 200), eff, ""))
        proj = os.path.basename(st.get("cwd", "")) or "~"
        if len(proj) > 20:
            proj = proj[:18] + ".."
        op = fmt_dur(time.time() - st.get("started_at", time.time()))
        hits = st.get("tool_count", 0)
        action = st.get("action", "") or "—"
        if eff == "idle" and st.get("_age", 0) > 2:
            action = f"idle {fmt_dur(st['_age'])}"
        elif eff == "offline":
            action = f"lost {fmt_dur(st['_age'])} ago"
        tail = f"{hits}t {op}"
        row = list_top + i
        put_text(overlay, row, 1, DOT.get(eff, "·"), accent, cols)
        put_text(overlay, row, 3, label.ljust(9), accent, cols)
        put_text(overlay, row, 13, proj.ljust(21), cyan, cols)
        put_text(overlay, row, 34, sig_blocks(st, 8), accent, cols)
        put_text(overlay, row, 43, "> " + action,
                 green if eff == "working" else dim(cyan, 0.85),
                 cols - len(tail) - 2)
        put_text(overlay, row, cols - len(tail) - 1, tail, dimc, cols)

    if n > len(shown):
        put_text(overlay, list_top + len(shown), 1,
                 f"+{n - len(shown)} more (enlarge terminal)", dimc, cols)
    if not sessions:
        put_center(overlay, list_top + 1, cols // 2,
                   "SKIES CLEAR - no contacts. Use a tool in any session.",
                   dimc, cols)


# ---- cells / emit -----------------------------------------------------------
def make_cells(fb, overlay, rows, cols):
    grid = []
    for r in range(rows):
        line = []
        for c in range(cols):
            o = overlay.get((r, c))
            if o:
                line.append((o[0], o[1], BG))
            else:
                top = fb.px[2 * r][c] if 2 * r < fb.h else BG
                bot = fb.px[2 * r + 1][c] if 2 * r + 1 < fb.h else BG
                line.append(("▀", top, bot))
        grid.append(line)
    return grid


def rgb_to_256(c):
    r, g, b = c
    if abs(r - g) < 11 and abs(g - b) < 11:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + (r - 8) * 24 // 247

    def q(v):
        return 0 if v < 48 else (1 if v < 115 else (v - 35) // 40)
    return 16 + 36 * q(r) + 6 * q(g) + q(b)


_sgr_cache = {}


def sgr(fg, bg, truecolor):
    k = (fg, bg, truecolor)
    s = _sgr_cache.get(k)
    if s is None:
        if truecolor:
            s = f"\x1b[38;2;{fg[0]};{fg[1]};{fg[2]};48;2;{bg[0]};{bg[1]};{bg[2]}m"
        else:
            s = f"\x1b[38;5;{rgb_to_256(fg)};48;5;{rgb_to_256(bg)}m"
        _sgr_cache[k] = s
    return s


def emit_full(grid, truecolor):
    out = ["\x1b[H"]
    last = None
    for r, line in enumerate(grid):
        for ch, fg, bg in line:
            s = sgr(fg, bg, truecolor)
            if s != last:
                out.append(s)
                last = s
            out.append(ch)
        out.append("\x1b[0m")
        last = None
        if r < len(grid) - 1:
            out.append("\r\n")
    return "".join(out)


def emit_diff(prev, grid, truecolor):
    out = []
    last = None
    for r, line in enumerate(grid):
        pline = prev[r] if prev and r < len(prev) else None
        c, n = 0, len(line)
        while c < n:
            if pline and c < len(pline) and pline[c] == line[c]:
                c += 1
                continue
            out.append(f"\x1b[{r + 1};{c + 1}H")
            last = None
            while c < n and not (pline and c < len(pline) and pline[c] == line[c]):
                ch, fg, bg = line[c]
                s = sgr(fg, bg, truecolor)
                if s != last:
                    out.append(s)
                    last = s
                out.append(ch)
                c += 1
            out.append("\x1b[0m")
            last = None
    return "".join(out)


# ---- run --------------------------------------------------------------------
def term_size():
    sz = os.get_terminal_size() if sys.stdout.isatty() else os.terminal_size((100, 30))
    return min(sz.columns, MAX_W), min(sz.lines, MAX_H)


def render_grid(cols, rows, frame, truecolor):
    fb = FB(cols, rows * 2)
    overlay = {}
    build_scene(fb, overlay, read_sessions(), frame, rows, cols)
    return make_cells(fb, overlay, rows, cols)


def run_once(truecolor):
    cols, rows = term_size()
    sys.stdout.write(emit_full(render_grid(cols, rows - 1, 0, truecolor), truecolor))
    sys.stdout.write("\x1b[0m\n")


def run_bench(n, truecolor):
    cols, rows = term_size()
    prev, t0, total = None, time.time(), 0
    for f in range(n):
        grid = render_grid(cols, rows - 1, f, truecolor)
        out = emit_diff(prev, grid, truecolor) if prev else emit_full(grid, truecolor)
        total += len(out)
        prev = grid
    dt = time.time() - t0
    print(f"bench: {n} frames @ {cols}x{rows}  {dt:.2f}s  "
          f"{n / dt:.1f} fps-compute  ~{total // n} B/frame")


def run_loop(fps, truecolor):
    import termios
    import tty
    import select
    import signal

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sys.stdout.write("\x1b[?1049h\x1b[?25l")
    sys.stdout.flush()
    stop = {"v": False}
    signal.signal(signal.SIGINT, lambda *a: stop.__setitem__("v", True))
    try:
        tty.setcbreak(fd)
        prev, psize, frame = None, None, 0
        dt = 1.0 / fps
        while not stop["v"]:
            cols, rows = term_size()
            if (cols, rows) != psize:
                sys.stdout.write("\x1b[2J")
                prev, psize = None, (cols, rows)
            grid = render_grid(cols, rows - 1, frame, truecolor)
            out = emit_diff(prev, grid, truecolor) if prev else emit_full(grid, truecolor)
            sys.stdout.write(out)
            sys.stdout.flush()
            prev = grid
            frame += 1
            if select.select([sys.stdin], [], [], dt)[0]:
                if sys.stdin.read(1).lower() == "q":
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


def main():
    args = sys.argv[1:]
    if "--cards" in args:
        here = os.path.dirname(os.path.abspath(__file__))
        os.execv(sys.executable, [sys.executable, os.path.join(here, "fleet_cards.py")]
                 + [a for a in args if a != "--cards"])
    truecolor = "--truecolor" in args
    fps = 12
    if "--fps" in args:
        try:
            fps = max(2, min(30, int(args[args.index("--fps") + 1])))
        except (ValueError, IndexError):
            pass
    if "--bench" in args:
        try:
            n = int(args[args.index("--bench") + 1])
        except (ValueError, IndexError):
            n = 60
        run_bench(n, truecolor)
    elif "--once" in args or not sys.stdout.isatty():
        run_once(truecolor)
    else:
        run_loop(fps, truecolor)


if __name__ == "__main__":
    main()
