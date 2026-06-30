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
IDLE_AFTER = 90       # no events this long -> treat as idle (fallback; Stop sets idle instantly)
FIRE_LINGER = 6       # a 'thinking' session that ran a tool within this many seconds keeps firing
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
TURRET_HULL = (120, 120, 120)
TURRET_HI = (195, 195, 195)
TURRET_SH = (70, 70, 70)
TURRET_BARREL = (170, 235, 245)
HOSTILE_DARK = (24, 14, 30)
WHITE = (245, 255, 250)
ENEMY = (255, 78, 78)          # incoming alien fire
GREY = (170, 170, 170)         # neutral grey (r=g=b -> stays grey, not blue, in 256c)
ENERGY = (90, 220, 230)        # underground energy flow converging into the base
RADAR = (40, 240, 90)          # saturated radar-scope green (stays green when dimmed/256c)

STATUS = {
    "working":  ((80, 255, 150), "ENGAGED",  "교전"),     # turret fires
    "thinking": ((255, 200, 80), "TRACKING", "추적"),
    "waiting":  ((255, 84, 162), "HOLD",     "대기명령"),
    "idle":     ((90, 190, 230), "DORMANT",  "휴면"),
    "offline":  ((90, 100, 116), "LOST",     "소실"),
    "pending":  ((120, 150, 185), "PENDING",  "대기과제"),  # queued todo (incoming, no fire)
    "done":     ((70, 130, 95),   "CLEARED",  "완료"),       # completed todo (log only)
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
        elif eff == "thinking" and (now - st.get("last_tool_at", 0)) < FIRE_LINGER:
            eff = "working"          # mid tool-burst (just ran a tool) -> keep firing
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
DOT = {"working": "*", "thinking": "+", "waiting": "!", "idle": "o", "offline": "x",
       "pending": ".", "done": "v"}


def draw_turret(fb, cx, bottom, frame):
    """Small rectangular base, 5 px wide x 3 px tall, planted with its base on
    `bottom`. Returns the muzzle point just above the top."""
    half, h = 2, 3
    top = bottom - (h - 1)
    for j in range(h):
        y = top + j
        for dx in range(-half, half + 1):
            edge = abs(dx) == half or j == 0
            col = TURRET_HI if edge else (TURRET_HULL if j < h - 1 else TURRET_SH)
            fb.set(cx + dx, y, col)
    fb.add(cx, top, (210, 210, 215), 0.9)             # grey core glow at the top
    return cx, top - 1


TIERS = (10, 80, 400)          # (tool_count x elapsed-min) thresholds: cross|diamond|large|BOSS


def task_score(st):
    """Task-scale proxy: cumulative tool calls x elapsed minutes (Claude exposes no
    true size). Heavier + longer-running work scores higher."""
    t = st.get("tool_count", 0)
    m = max(0.0, (time.time() - st.get("started_at", time.time())) / 60.0)
    return t * m


def tier_of(s):
    return 0 if s < TIERS[0] else 1 if s < TIERS[1] else 2 if s < TIERS[2] else 3


def tier(st):
    return tier_of(task_score(st))


def has_work(s):
    """True if the session is worth showing: actively engaged, or still has queued
    tasks. Idle-with-nothing-to-do and offline sessions are hidden."""
    if s["_eff"] == "offline":
        return False
    if s["_eff"] in ("working", "thinking", "waiting"):
        return True
    return any(t.get("s") in ("pending", "in_progress")     # idle, but tasks remain
               for t in (s.get("todos") or []) if t.get("c"))


def build_contacts(sessions):
    """Expand sessions into contacts. A session running a TodoWrite task list yields
    one contact per todo (pending / in_progress shown, completed -> 'done'); a
    session with no todos yields a single session-level contact (fallback).
    Sessions with nothing to do are skipped."""
    out = []
    for s in sessions:
        if not has_work(s):                                 # hide idle / done / offline sessions
            continue
        base = {"sid": s.get("session_id", ""),
                "project": os.path.basename(s.get("cwd", "")) or "~",
                "hits": s.get("tool_count", 0),
                "started_at": s.get("started_at", time.time()),
                "age": s.get("_age", 0)}
        todos = [t for t in (s.get("todos") or []) if t.get("c")]
        if todos and s["_eff"] != "offline":
            ssc = task_score(s)                             # compute the score once
            stier = tier_of(ssc)
            for t in todos:
                stt = t.get("s", "pending")
                if stt == "completed":
                    eff, ct, sc = "done", 0, 0
                elif stt == "in_progress":
                    eff = s["_eff"] if s["_eff"] in ("working", "thinking", "waiting") else "idle"
                    ct, sc = stier, ssc
                else:
                    eff, ct, sc = "pending", 0, 0
                out.append({**base, "eff": eff, "label": t.get("c", ""), "tier": ct, "score": sc, "todo": stt})
        else:
            fsc = task_score(s)
            out.append({**base, "eff": s["_eff"], "label": s.get("action", "") or "-",
                        "tier": tier_of(fsc), "score": fsc, "todo": None})
    return out


def draw_enemy(fb, cx, cy, t, eff, accent, frame):
    """Contact sized by task scale: 0 small cross, 1 diamond, 2 large diamond."""
    pulse = 0.55 + 0.45 * math.sin(frame * 0.3 + cx)
    body = accent if eff != "offline" else dim(accent, 0.4)
    eye = lerp(body, WHITE, 0.4 + 0.3 * pulse)
    if t == 0:                                             # small cross
        fb.set(cx, cy, eye)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            fb.set(cx + dx, cy + dy, body)
    elif t == 1:                                           # diamond + spike legs
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            fb.set(cx + dx, cy + dy, lerp(dim(body, 0.5), body, pulse))
        for dx, dy in ((-2, -1), (2, -1), (-2, 1), (2, 1)):
            fb.set(cx + dx, cy + dy, dim(body, 0.7))
        fb.set(cx, cy, eye)
    else:                                                  # large diamond
        for dy in range(-2, 3):
            w = 2 - abs(dy)
            for dx in range(-w, w + 1):
                fb.set(cx + dx, cy + dy, lerp(dim(body, 0.5), body, pulse))
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
            fb.set(cx + dx, cy + dy, dim(body, 0.7))
        for dx in (-1, 0, 1):
            fb.set(cx + dx, cy, eye)


def draw_boss(fb, p0, frame, accent, firing):
    """Colossal contact covering the top band of the sky. Returns the beam target."""
    x0, x1 = 3, fb.w - 3
    base = p0 + 6
    body = lerp(HOSTILE_DARK, accent, 0.30)
    for x in range(x0, x1):
        jag = base - (1 + noise(x, 2, frame // 6) % 3)     # jagged underside
        for y in range(p0, jag + 1):
            fb.set(x, y, body)
        fb.add(x, jag, accent, 0.45)                       # glowing rim
    pulse = 0.5 + 0.5 * math.sin(frame * 0.2)
    for k in range(5):                                     # glowing eyes
        ex = x0 + (x1 - x0) * (2 * k + 1) // 10
        fb.add(ex, p0 + 2, lerp(accent, WHITE, 0.5 + 0.3 * pulse), 1.0)
        if firing:
            fb.add(ex, p0 + 3, ENEMY, 0.5)
    return fb.w // 2, p0 + 2          # aim at the boss core (centre eye row)


TRACER = (255, 225, 90)           # yellow allied flak tracer (ground -> up)
LASER = (130, 220, 255)           # allied laser bolt (ground -> up)
COMET = (255, 80, 70)             # red comet falling from the sky (enemy attack)


def draw_tracers(fb, frame, p0, surf_y, cols):
    """Faint yellow flak climbing from the ground into the sky at varied angles —
    a few at a time, short fading tails. Pure, subdued background ambiance."""
    if surf_y - 1 <= p0:
        return
    n = max(3, cols // 18)
    travel = 24
    for k in range(n):
        L = travel + 6 + noise(k, 1, 0) % 16               # in flight `travel`, then a short gap
        ph = (frame + k * 11) % L
        if ph >= travel:
            continue
        cyc = (frame + k * 11) // L                        # re-randomise each volley
        x0 = noise(k, 2, cyc) % cols                       # launch column along the ground
        x1 = x0 + (noise(k, 4, cyc) % 27 - 13)             # wider, more varied slant
        y0 = surf_y - 1 - noise(k, 5, cyc) % 3             # launch near the ground
        y1 = p0 - 4                                        # climb past the top of the sky
        f = ph / travel
        for t in range(7):                                 # head + fading trail (toward ground)
            ft = f - t * 0.045
            if ft < 0:
                continue
            x = int(x0 + (x1 - x0) * ft)
            y = int(y0 + (y1 - y0) * ft)
            fb.add(x, y, TRACER, max(0.0, 0.30 - t * 0.06))  # subdued, dimmer


def draw_lasers(fb, frame, p0, surf_y, cols):
    """Allied laser bolts fired straight up from the ground into the sky — brief,
    dim flashes with a bright tip. Background ambiance."""
    if surf_y - 1 <= p0:
        return
    for k in range(max(1, cols // 40)):
        L = 56 + noise(k, 8, 0) % 50
        ph = (frame + k * 29) % L
        if ph >= 4:                                        # brief flash (~4 frames)
            continue
        cyc = (frame + k * 29) // L
        a = 0.22 * (1 - abs(ph - 1.5) / 2.5)               # fade in then out
        x0 = noise(k, 10, cyc) % cols                      # ground launch column
        y0 = surf_y - 1
        x1 = x0 + (noise(k, 11, cyc) % 17 - 8)             # mild slant up
        y1 = p0 - 1
        steps = max(abs(y1 - y0), 1)
        for i in range(steps + 1):
            fr = i / steps
            x = int(x0 + (x1 - x0) * fr)
            y = int(y0 + (y1 - y0) * fr)
            fb.add(x, y, LASER, a)
        fb.add(x1, y1, WHITE, a + 0.18)                    # bright bolt tip


def draw_comets(fb, frame, p0, surf_y, cols):
    """Red comets falling from the sky on a steep diagonal, with a trailing tail."""
    if surf_y - 1 <= p0:
        return
    n = max(1, cols // 32)
    travel = 22
    for k in range(n):
        L = travel + 16 + noise(k, 14, 0) % 30             # rarer than tracers
        ph = (frame + k * 23) % L
        if ph >= travel + 8:                               # keep going so the tail drains in
            continue
        cyc = (frame + k * 23) // L
        x0 = noise(k, 15, cyc) % cols                      # enters near the top
        y0 = p0 - 2
        x1 = x0 + (12 + noise(k, 16, cyc) % 12) * (1 if noise(k, 17, cyc) & 1 else -1)
        y1 = surf_y - 1
        f = ph / travel
        for t in range(7):                                 # head + red tail (toward the sky)
            ft = f - t * 0.045
            if not 0.0 <= ft <= 1.0:                       # above launch / below ground -> skip
                continue                                   #   head vanishes at the ground, tail keeps falling
            x = int(x0 + (x1 - x0) * ft)
            y = int(y0 + (y1 - y0) * ft)
            fb.add(x, y, lerp(COMET, WHITE, 0.4) if t == 0 else COMET, max(0.0, 0.40 - t * 0.07))
        for sp in range(3):                                # flickering embers/sparks (flame-like)
            fs = f - (0.03 + sp * 0.07)
            if not 0.0 <= fs <= 1.0:
                continue
            bx = int(x0 + (x1 - x0) * fs)
            by = int(y0 + (y1 - y0) * fs)
            nz = noise(bx, by, frame)
            if nz < 90:                                    # twinkle on/off
                ember = (255, 220, 120) if nz % 2 else (255, 160, 70)
                fb.add(bx + (nz % 3 - 1), by, ember, 0.30 + 0.0015 * nz)


def draw_searchlight(fb, ox, oy, top_y, angle):
    """Dim grey beam sweeping the sky (searching for contacts). Background only."""
    length = max(1, oy - top_y)
    for d in range(length):
        y = oy - d
        x = ox + int(round(math.tan(angle) * d))
        spread = 2 + d // 7                                # a bit thicker cone
        a = 0.42 - 0.16 * (d / length)                     # a bit brighter, visible to the top
        for w in range(-spread, spread + 1):
            fb.add(x + w, y, GREY, a * (1 - abs(w) / (spread + 1)))


def draw_underground(fb, cx, surf, frame, powered):
    """A single half-pixel line below the ground: energy pulses march inward from
    both edges and converge into the base (symmetric; brighter/faster while firing)."""
    y = surf + 1                                           # one pixel row = half a cell
    step = (frame * (2 if powered else 1)) // 3            # slower inward march
    for x in range(fb.w):
        dist = abs(x - cx)                                 # symmetric about the base
        if (dist + step) % 6 < 2:                          # pulses converge toward centre
            near = 1.0 - dist / max(1, cx)                 # brighter as it nears the base
            a = (0.35 + 0.5 * near) * (1.2 if powered else 0.8)
            fb.add(x, y, ENERGY, min(1.0, a))
    fb.add(cx, surf, lerp(ENERGY, WHITE, 0.4), 0.9 if powered else 0.6)  # convergence point


# ---- overlay text (width-aware: CJK/emoji render as 2 terminal cells) -------
def cw(ch):
    """Display width of a character: 2 for wide/fullwidth (한글·CJK·emoji), else 1."""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def dw(s):
    return sum(cw(c) for c in s)


def fit(s, width):
    """Truncate to <= `width` display columns, marking a cut with '..'."""
    if dw(s) <= width:
        return s
    out, w = [], 0
    for ch in s:
        if w + cw(ch) > width - 2:
            break
        out.append(ch)
        w += cw(ch)
    return "".join(out) + ".."


def put_text(overlay, row, col, s, rgb, maxcol, mincol=0):
    """Place text; a width-2 glyph occupies cell c plus a `None` continuation
    cell c+1 so the column model stays aligned with what the terminal renders."""
    c = col
    for ch in s:
        w = cw(ch)
        if c + w > maxcol:
            break
        if c >= mincol and ch != " ":
            overlay[(row, c)] = (ch, rgb)
            if w == 2:
                overlay[(row, c + 1)] = (None, rgb)
        c += w
    return c


def put_center(overlay, row, cx, s, rgb, maxcol):
    return put_text(overlay, row, cx - dw(s) // 2, s, rgb, maxcol)


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


# ---- allied comms chatter (retro-SF military radio, reacts to the scene) ----
COMMS_COL = (165, 245, 115)        # light-green (연두) comms phosphor
COMMS_CYCLE = 150                  # frames between transmissions (~12s at 12fps)
COMMS_ON = 34                      # transmission visible window (~3s)
COMMS = {                          # short grimdark vox-lines that fit the corner panel
    "boss":  ["ABOMINATION RISES", "IT BLOTS THE SKY", "WE CANNOT HOLD"],
    "hold":  ["STAY YOUR GUNS", "AWAIT THE WORD", "HOLD... HOLD..."],
    "lost":  ["VOX GONE DARK", "ANOTHER SOUL LOST", "THEY ARE GONE"],
    "many":  ["THEY COME ENDLESS", "NO END TO THEM", "A TIDE OF THEM"],
    "one":   ["TARGET MARKED", "BURN IT DOWN", "ONE LESS"],
    "watch": ["THEY CIRCLE US", "EYES TO THE DARK", "SOMETHING STIRS"],
    "clear": ["THE CALM WON'T LAST", "THEY WILL COME", "SOMETHING APPROACHES",
              "TOO QUIET...", "THE VOID STIRS", "NOT IF, BUT WHEN", "STAND READY"],
}
INVADER_COMMS = ["WE ARE LEGION", "YOU ARE PREY", "YOUR WALLS FALL",
                 "I SEE YOU", "WE HUNGER", "NO ESCAPE", "FLESH AND ASH",
                 "SILENCE YOUR GODS"]
# crew calling for the commander (= the user) while input is awaited; escalates
# by how long the wait has run (calm -> insistent -> desperate)
HOLD_CALLS = [
    ["ORDERS, COMMANDER?", "AWAITING ORDERS", "COMMAND, ADVISE"],
    ["COMMANDER, YOUR ORDERS", "WE NEED A DECISION", "COMMAND, RESPOND"],
    ["COMMANDER, RESPOND!!", "WHERE IS COMMAND?!", "WE STAND BLIND!!"],
]
STATIC = ".:'`~*"                  # radio-static flecks on the panel border


def pick_comms(sky, seq):
    """Choose a radio line for the displayed contacts (priority + per-volley pick).
    HOLD/waiting is handled separately in draw_comms."""
    eng = sum(1 for c in sky if c["eff"] == "working")
    if any(c["tier"] >= 3 for c in sky):
        key = "boss"
    elif eng >= 2:
        key = "many"
    elif eng == 1:
        key = "one"
    elif sky:
        key = "watch"
    else:
        key = "clear"                                      # nothing out there (yet)
    pool = COMMS[key]
    return pool[seq % len(pool)]


def draw_comms(overlay, cx, surf_char, cols, frame, sessions, sky):
    """An allied comms panel at the turret's upper-right. It appears ONLY while
    transmitting (intermittent); the line sits inside a thin box drawn with real
    box-drawing glyphs (a true 1-px line, not half-blocks)."""
    wait_ages = [s.get("_age", 0) for s in sessions if s["_eff"] == "waiting"]
    waiting = bool(wait_ages)
    if not waiting and (frame % COMMS_CYCLE) >= COMMS_ON:  # idle gap (input-needed stays up)
        return
    r_bot = surf_char - 2
    r_top = r_bot - 2
    if r_top < 1:
        return
    seq = frame // COMMS_CYCLE
    hijack = (not waiting) and noise(seq, 99, 7) < 10      # really rare: invaders seize the channel
    if hijack:                                             # corrupted red transmission
        col = ENEMY
        msg = INVADER_COMMS[seq % len(INVADER_COMMS)]
        fleck, jit0, jit1 = 46, 0.40, 0.60                 # heavy static, harsh jitter
        sig = 0.45 + 0.5 * (noise(frame, 1, 1) / 255.0)    # weak, unstable signal
    elif waiting:                                          # input needed -> call for the commander
        age = max(wait_ages)
        lvl = 0 if age < 12 else 1 if age < 40 else 2      # longer wait -> more desperate
        col = COMMS_COL
        msg = HOLD_CALLS[lvl][seq % len(HOLD_CALLS[lvl])]
        fleck, jit0, jit1 = 4, 0.82, 0.18
        if lvl >= 2:                                       # desperate: urgent alarm blink
            sig = 0.5 + 0.5 * ((frame // 3) % 2)
        else:
            sig = 0.86 + 0.14 * (noise(frame, 1, 1) / 255.0)
    else:                                                  # steady allied green vox
        col = COMMS_COL
        msg = pick_comms(sky, seq)
        fleck, jit0, jit1 = 4, 0.82, 0.18                  # subtle flecks, gentle jitter
        sig = 0.86 + 0.14 * (noise(frame, 1, 1) / 255.0)

    inner = dw(msg)
    left = cx + 3
    if left + inner + 1 > cols - 2:                        # keep the box on screen
        left = max(1, cols - 2 - inner - 1)
        if left + inner + 1 > cols - 2:                    # still too wide -> truncate
            msg = fit(msg, max(4, cols - 2 - left - 1))
            inner = dw(msg)
    right = left + inner + 1

    def cell(r, c, ch, glitchable):
        nz = noise(c, r, frame // 2)
        if glitchable and nz < fleck:                      # static fleck
            ch, base = STATIC[nz % len(STATIC)], 0.45
        else:                                              # gentle per-cell brightness jitter
            base = jit0 + jit1 * (noise(c, r, frame // 2) / 255.0)
        put_text(overlay, r, c, ch, dim(col, base * sig), cols)

    cell(r_top, left, "┌", True)                           # top edge
    for i in range(inner):
        cell(r_top, left + 1 + i, "─", True)
    cell(r_top, right, "┐", True)
    cell(r_top + 1, left, "│", True)                       # sides + text (text glitches only on hijack)
    for i, ch in enumerate(msg):
        cell(r_top + 1, left + 1 + i, ch, hijack)
    cell(r_top + 1, right, "│", True)
    cell(r_bot, left, "└", True)                           # bottom edge
    for i in range(inner):
        cell(r_bot, left + 1 + i, "─", True)
    cell(r_bot, right, "┘", True)


def fire_bullets(fb, mx, my, tx, ty, frame, seed):
    """Turret main gun: a stream of tracer rounds (matches the background flak)
    travelling from the muzzle up to the contact, with a muzzle flash."""
    for k in range(3):                                     # a few rounds in flight
        f = ((frame * 3 + seed * 7 + k * 9) % 18) / 18.0
        for t in range(3):                                 # round + short trail
            ft = f - t * 0.06
            if ft < 0:
                continue
            x = int(mx + (tx - mx) * ft)
            y = int(my + (ty - my) * ft)
            fb.add(x, y, WHITE if t == 0 else TRACER, max(0.0, 0.9 - t * 0.3))
    if (frame + seed) % 4 < 2:                             # muzzle flash
        fb.add(mx, my, WHITE, 0.9)


def scan_contact(fb, mx, my, cx, cy, frame, seed):
    """TRACKING: a solid radar-green sweep line from the base, running through the
    contact and on past it to the screen edge; the line pivots so the sweep
    crosses the target back and forth."""
    ex = cx + int(round(5 * math.sin(frame * 0.25 + seed)))  # sweep crosses the target L<->R
    ey = cy
    dx, dy = ex - mx, ey - my
    dist = max(abs(dx), abs(dy), 1)
    for i in range(dist * 3):                              # extend beyond the target to the edge
        fr = i / dist
        x = int(mx + dx * fr)
        y = int(my + dy * fr)
        if not (0 <= x < fb.w and 0 <= y < fb.h):
            break
        fb.add(x, y, RADAR, 0.5)
    fb.add(ex, ey, WHITE, 0.65)                            # bright read at the contact


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
    contacts = build_contacts(sessions)                 # one contact per todo (task), or per session
    sky = [c for c in contacts if c["eff"] != "done"]
    hud = f"{active} ENGAGING  {len(sky)} CONTACTS  {lost} LOST   q quit"
    put_text(overlay, 0, max(19, cols - len(hud) - 1), hud, cyan, cols)

    # ---- scene: sky (top) | ground at terminal centre | 3-row underground ----
    cx = cols // 2
    p0 = 2                                              # top of sky (below header)
    surf_char = rows // 2                               # ground line at terminal centre
    ground_px = surf_char * 2 + 1
    powered = active > 0

    draw_comets(fb, frame, p0, ground_px, cols)         # red comets falling from the sky
    draw_lasers(fb, frame, p0, ground_px, cols)         # allied laser bolts (ground -> up)
    draw_tracers(fb, frame, p0, ground_px, cols)        # yellow flak climbing into the sky
    for j, ph in enumerate((0.0, math.pi)):             # grey searchlights, up to screen top
        ox = cx + (cols // 4) * (1 if j else -1)
        draw_searchlight(fb, ox, ground_px - 1, 0, 0.4 * math.sin(frame * 0.045 + ph))
    for x in range(cols):                               # single ground line (grey)
        fb.add(x, ground_px, GREY, 0.4)
    for d in range(8, cx, 8):                           # white perimeter lights ABOVE the line
        fb.set(cx + d, ground_px - 1, WHITE)
        fb.set(cx - d, ground_px - 1, WHITE)
    muzzle = draw_turret(fb, cx, ground_px, frame)      # 3-cell tower planted on the line
    draw_underground(fb, cx, ground_px, frame, powered)  # supply feed into base while firing
    draw_comms(overlay, cx, surf_char, cols, frame, sessions, sky)

    ns = len(sky)
    if ns:
        boss_i = None                                    # one colossal boss = highest-score tier-3
        cand = [(c["score"], i) for i, c in enumerate(sky) if c["tier"] >= 3]
        if cand:                                         # only the top scorer evolves; others stay large
            boss_i = max(cand)[1]
            beff = sky[boss_i]["eff"]
            bacc = STATUS.get(beff, ((200, 200, 200),))[0]
            btx, bty = draw_boss(fb, p0, frame, bacc, beff == "working")
            if beff == "working":
                fire_bullets(fb, muzzle[0], muzzle[1], btx, bty, frame, 99)
            elif beff == "thinking":
                scan_contact(fb, muzzle[0], muzzle[1], btx, bty, frame, 99)
        sky_top = p0 + 8 if boss_i is not None else p0 + 1
        others = [i for i in range(ns) if i != boss_i]
        m = max(1, len(others))
        margin, span = 6, max(1, cols - 12)
        span_y = max(2, ground_px - 3 - sky_top)         # scatter contacts below the boss
        for j, i in enumerate(others):
            c = sky[i]
            eff = c["eff"]
            accent = STATUS.get(eff, ((200, 200, 200),))[0]
            bx = margin + (span * (2 * j + 1)) // (2 * m)
            by = sky_top + (noise(i, 4, 0) % span_y) + int(round(math.sin(frame * 0.1 + i)))
            draw_enemy(fb, bx, by, min(2, c["tier"]), eff, accent, frame)
            seed = i + 1
            if eff == "working":                         # main gun: tracer bullets at the contact
                fire_bullets(fb, muzzle[0], muzzle[1], bx, by, frame, seed)
            elif eff == "thinking":                      # green scan over the contact
                scan_contact(fb, muzzle[0], muzzle[1], bx, by, frame, seed)
            elif eff == "waiting":                       # minimal amber hold tick
                if (frame // 4) % 2:
                    fb.add(bx, by - 2, (255, 200, 90), 0.6)
            # pending / idle / offline: just the descending sprite (no turret fire)

    # ---- divider (below the single underground row) ----
    drow = surf_char + 2
    for x in range(cols):
        fb.set(x, drow * 2, dim(cyan, 0.35))
        fb.set(x, drow * 2 + 1, dim(cyan, 0.35))

    # ---- readable list: one line per task (todo), grouped by session ----
    list_top = drow + 1
    capacity = max(0, rows - list_top)
    nc = len(contacts)
    shown = contacts if nc <= capacity else contacts[:max(0, capacity - 1)]
    prev_sid = None
    for i, c in enumerate(shown):
        eff = c["eff"]
        accent, label, kor = STATUS.get(eff, ((200, 200, 200), eff, ""))
        proj = fit(c["project"], 20) if c["sid"] != prev_sid else ""   # project once per session
        prev_sid = c["sid"]
        op = fmt_dur(time.time() - c["started_at"])
        action = c["label"] or "-"
        if eff == "idle" and c["age"] > 2:
            action = f"idle {fmt_dur(c['age'])}"
        elif eff == "offline":
            action = f"lost {fmt_dur(c['age'])} ago"
        tail = f"{c['hits']}t {op}"          # {tools}t  {elapsed: s/m/h}
        row = list_top + i
        put_text(overlay, row, 1, DOT.get(eff, "?"), accent, cols)
        put_text(overlay, row, 3, label, accent, 12)
        put_text(overlay, row, 13, proj, cyan, 34)            # width-aware (한글 OK)
        put_text(overlay, row, 34, sig_blocks({"_age": c["age"], "_eff": eff}, 8), accent, cols)
        avail = max(0, cols - len(tail) - 2 - 45)             # 45 = 43 + len("> ")
        body = green if eff == "working" else (dim(green, 0.5) if eff == "done" else dim(cyan, 0.85))
        put_text(overlay, row, 43, "> " + fit(action, avail), body, cols - len(tail) - 2)
        put_text(overlay, row, cols - len(tail) - 1, tail, dimc, cols)

    if nc > len(shown):
        put_text(overlay, list_top + len(shown), 1,
                 f"+{nc - len(shown)} more (enlarge terminal)", dimc, cols)
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
        if len(_sgr_cache) > 4096:        # bound growth over long runs
            _sgr_cache.clear()
        _sgr_cache[k] = s
    return s


def emit_full(grid, truecolor):
    out = ["\x1b[H"]
    last = None
    for r, line in enumerate(grid):
        for ch, fg, bg in line:
            if ch is None:        # continuation of a wide glyph -> emit nothing
                continue
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
                if ch is None:    # wide-glyph continuation; head already advanced cursor
                    c += 1
                    continue
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


POLL_INTERVAL = 0.3                                    # seconds between disk re-reads of session state


def render_grid(cols, rows, frame, truecolor, sessions=None):
    fb = FB(cols, rows * 2)
    overlay = {}
    if sessions is None:
        sessions = read_sessions()
    build_scene(fb, overlay, sessions, frame, rows, cols)
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
        sessions, last_poll = read_sessions(), time.time()
        while not stop["v"]:
            cols, rows = term_size()
            if (cols, rows) != psize:
                sys.stdout.write("\x1b[2J")
                prev, psize = None, (cols, rows)
            now = time.time()                              # poll session state a few times/sec, not every frame
            if now - last_poll >= POLL_INTERVAL:
                sessions, last_poll = read_sessions(), now
            grid = render_grid(cols, rows - 1, frame, truecolor, sessions)
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
