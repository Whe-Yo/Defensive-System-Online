# Inundation_Agent — ORBITAL DEFENSE 🛰

A real-time, terminal-native **pixel-art monitor** for multiple concurrent Claude
Code sessions, themed as a planetary defense turret. Inspired by
[SKILL-HERO](https://github.com/Ign0reLee/SKILL-HERO)'s "work = game" idea and the
retro CRT-neon look of the separate **범람 (Inundation)** project.

> **Lore**: where 범람 is a *fleet returning to Earth*, Inundation_Agent is the
> *turret that defends it*. One defense turret sits at 6 o'clock (bottom-centre);
> every live Claude session is an unidentified hostile **contact** descending from
> the sky. When a session is **ENGAGED** (running a tool) the turret fires a neon
> beam at it — one turret, many targets, beams fanning out to each active session.

This is a **monitor, not a game**, and 범람 is developed separately.

**Half-block pixel rendering**: one terminal cell (`▀`) gets independent top/bottom
colours, giving a 2-pixels-per-cell colour framebuffer. It is *coloured text*, not
a bitmap protocol (sixel/kitty), so it **passes straight through tmux and SSH**.

Layout — **battle scene on top** (descending contacts, turret, engagement beams,
plus subdued background FX) and a **readable list below** (one line per session:
status, full project name, activity gauge, current action, tool count, elapsed).
Every session gets its own line, so nothing is hidden and long names are not cut.

```
INUNDATION_AGENT // ORBITAL DEFENSE       3 ENGAGING  5 CONTACTS  0 LOST   q quit
   .  *      contacts descend (sized by task scale)        '  comet \
      \        \   beams    /                              .         \
        searchlights  ▮▮ turret (6 o'clock)  · perimeter lights ·   flak ↑ laser ↑
────────────────────────────────────────────────────────────────────────────────
 * ENGAGED   ml-pipeline        ▮▮▮▮▮▮▮▯ > Read config.yaml              22t  1m
 * ENGAGED   BeatSenseVid_VJ    ▮▮▮▮▮▮▮▯ > Bash pytest -q tests/unit      4t  2m
 ! HOLD      api-gateway        ▮▮▮▮▮▮▮▯ > permission: Bash(rm -rf ..)     7t 25m
 * ENGAGED   Inundation_Agent   ▮▮▮▮▮▮▮▯ > Edit dso.py                 45t 12m
 o DORMANT   2dtomesh           ▮▮▮▯▯▯▯▯ > idle 40s                      12t  3m
```
(Real output is animated truecolor/256-colour neon; the above is a mono sketch.)

## How it works

```
each Claude session ─(hook)─> ~/.claude/inundation_agent/<id>.json ─(read)─> src/dso.py
```

- `install.py` — the only setup file. Copies the event hook (`src/dso_hook.py`) to
  `~/.claude/dso_hook.py`, registers it in `settings.json`, and wires up the `dso`
  command. The hook receives every session's event and writes a per-session state
  file. **No stdout, always exits 0**, so it can never block a tool call.
- `src/dso.py` — reads that folder every frame and renders the **scene** (contacts,
  turret, beams, background FX) plus the **per-session list**. Diff rendering (only
  changed cells are emitted) keeps it light over SSH.
- `src/dso_cards.py` — a lightweight static card view (`python3 src/dso_cards.py`).
- `dso.sh` / `dso.bat` — launchers. Type the name in a terminal to run inline, or
  double-click to open a new terminal. `install.py` puts `dso` on your PATH.

## Scene elements

- **Contacts = sessions**, sized by **task scale** (a proxy from cumulative tool
  calls — Claude exposes no true task size): small cross → diamond → large diamond →
  a colossal **boss** covering the top band.
- **Turret** at 6 o'clock: grey rectangular base on the central ground line, white
  perimeter lights, grey searchlights sweeping the sky, an underground energy line
  feeding into the base.
- **Engagement beams** fire only at **ENGAGED** (working) sessions and aim at the
  contact's core; one turret hits many targets at once.
- **Background FX** (dim, additive, never occluding): yellow flak tracers and allied
  cyan laser bolts rising from the ground, red comets falling from the sky.

## Status & instruments

| Status | Label | Meaning | Cue |
|---|---|---|---|
| ENGAGED  | working  | running a tool (Edit/Bash/Grep…) | **turret fires a beam** |
| TRACKING | thinking | reasoning between tools | pulsing |
| HOLD     | waiting  | awaiting input / permission | magenta warning |
| DORMANT  | idle     | turn ended, awaiting the user | faint glow |
| LOST     | offline  | 30 min+ with no events | fading |

- The **SIG gauge is an activity signal, not a completion %.** Claude does not expose
  exact progress, so it fills while active and decays while idle.
- Real values shown: status · current action (`>`) · HITS (tool count) · elapsed time.

## Install

```bash
python3 install.py          # register hooks in ~/.claude/settings.json (idempotent, backed up)
```

Tracking begins **from newly started sessions** (existing ones appear on their next
tool use). After moving the folder: `python3 install.py --uninstall && python3 install.py`.

## Run

```bash
dso              # live pixel scene (q or Ctrl-C to quit)
dso --fps 15     # frame rate (default 12, range 2–30); lower it on slow SSH
dso --truecolor  # 24-bit neon (needs an RGB-capable terminal/tmux)
dso --once        # print one frame and exit (snapshot)
dso --bench 60    # render-only benchmark (fps, bytes/frame)
python3 src/dso_cards.py   # card view instead of pixels (source only)
```

- **Colour**: 256-colour by default (works on `tmux-256color`). For truecolor neon use
  `--truecolor` plus `tmux set -as terminal-features ',*:RGB'`.
- **Terminal-graphics limit**: true bitmap images (sixel/kitty) are blocked by tmux.
  This renderer uses half-blocks (coloured text), so it survives tmux — a dot-art look
  is both the constraint and the goal.

## Uninstall

```bash
python3 install.py --uninstall   # remove hooks (settings.json is backed up)
```

## Tuning

`src/dso.py` top-of-file constants: `IDLE_AFTER`, `OFFLINE_AFTER`, `PRUNE_AFTER`,
`TIERS` (task-scale thresholds), `STATUS` / palette, `draw_turret` (base shape),
the background-FX functions (`draw_tracers` / `draw_lasers` / `draw_comets`),
`MAX_W` / `MAX_H` (render caps).

---

# Inundation_Agent — 지구방위 터렛 🛰 (한글)

여러 Claude Code 세션의 작업 상황을 **터미널에서 실시간 픽셀아트**로 보여주는
지구방위 터렛 모니터. [SKILL-HERO](https://github.com/Ign0reLee/SKILL-HERO)의
"작업=게임" 발상과, 별도로 개발 중인 **범람(Inundation)** 프로젝트의 레트로 CRT
네온 미감에서 영감을 받았다.

> **세계관**: 범람이 *지구로 귀환하는 함대*였다면, Inundation_Agent는 *그 지구를
> 지키는 터렛*이다. 화면 6시(하단 중앙)에 방어 터렛 하나가 있고, 하늘에서 미확인
> 적대체(=각 세션)가 강하한다. 세션이 **교전중(ENGAGED)**이면 터렛이 그 적대체로
> 네온 빔을 발사한다 — 터렛 하나가 다수 표적을 상대하며 빔이 부채꼴로 뻗는다.

이건 **모니터**이지 게임이 아니며, 범람은 별개로 개발된다.

**하프블록 픽셀 렌더링**: 터미널 한 칸(`▀`)의 위/아래 색을 따로 줘서 칸당 픽셀
2개의 컬러 프레임버퍼를 만든다. 비트맵 프로토콜(sixel)이 아니라 "색 입힌 글자"라서
**tmux·SSH를 그대로 통과**한다.

레이아웃 — **상단에 전투 씬**(강하 적대체 + 터렛 + 교전 빔 + 은은한 배경 효과),
**하단에 가독 리스트**(세션당 한 줄: 상태·프로젝트명 전체·활동바·현재 동작·도구수·경과).
세션이 많아도 한 줄씩이라 다 보이고, 긴 프로젝트명도 안 잘린다.

## 동작 구조

```
각 Claude 세션 ─(hook)─> ~/.claude/inundation_agent/<id>.json ─(읽기)─> src/dso.py 렌더러
```

- `install.py` — 유일한 설치 파일. 훅(`src/dso_hook.py`)을 `~/.claude/dso_hook.py`로 복사·
  `settings.json`에 등록하고 `dso` 명령을 연결한다. 훅은 모든 세션 이벤트를 받아 세션별
  상태 파일에 기록한다. **stdout 없음 · 항상 exit 0** → 도구 호출을 절대 막지 않는다.
- `src/dso.py` — 상태 폴더를 매 프레임 읽어 **씬**(적대체·터렛·빔·배경 효과)과
  **세션 리스트**를 렌더. 차분 렌더(바뀐 칸만 전송)로 SSH에서도 가볍다.
- `src/dso_cards.py` — 픽셀 대신 정적 카드 뷰 (`python3 src/dso_cards.py`).
- `dso.sh` / `dso.bat` — 런처. 터미널에서 이름을 치면 그 자리에서 실행, 더블클릭하면 새
  터미널이 열린다. `install.py`가 `dso`를 PATH에 올린다.

## 씬 구성

- **적대체 = 세션**, **작업 규모**(누적 도구 호출 수 proxy — Claude는 실제 작업
  크기를 노출하지 않음)에 비례한 크기: 작은 십자 → 다이아몬드 → 큰 다이아몬드 →
  상단을 덮는 초대형 **보스**.
- **터렛**(6시): 중앙 지상선 위 회색 직사각형 기지, 흰색 지상 조명, 하늘을 훑는 회색
  탐조등, 기지로 모여드는 지하 에너지 흐름.
- **교전 빔**은 **교전중(working)** 세션에만, 적대체의 **핵**을 조준해 발사. 터렛
  하나가 동시에 여러 표적을 친다.
- **배경 효과**(어둡게·가산·가림 없음): 지상에서 솟는 노란 예광탄과 인류측 시안
  레이저, 하늘에서 떨어지는 붉은 혜성.

## 상태와 계기

| 상태 | 의미 | 연출 |
|---|---|---|
| ENGAGED(교전) | 도구 실행 중 | **터렛이 빔으로 조준·발사** |
| TRACKING(추적) | 도구 사이 추론 중 | 점멸 |
| HOLD(대기명령) | 입력/권한 대기 | 마젠타 경고 |
| DORMANT(휴면) | 턴 종료 후 사용자 대기 | 약한 발광 |
| LOST(소실) | 30분+ 무이벤트 | 명멸·소멸 |

- **SIG 게이지는 활동 신호이지 완료율이 아니다.** Claude는 정확한 진행 %를 노출하지
  않으므로, 활동 중 가득 차고 유휴 시간에 따라 감쇠한다.
- 실값: 상태 · 현재 동작(`>`) · HITS(누적 도구 수) · 경과시간.

## 설치

```bash
python3 install.py          # ~/.claude/settings.json에 훅 등록(멱등·백업)
```

**새로 시작하는 세션부터** 추적된다(기존 세션은 다음 도구 사용 시 등장). 경로를 옮긴
뒤에는 `python3 install.py --uninstall && python3 install.py`로 훅을 재연결한다.

## 실행

```bash
dso              # 라이브 픽셀 씬 (q 또는 Ctrl-C 종료)
dso --fps 15     # 프레임레이트(기본 12, 2~30). SSH 느리면 낮춰라
dso --truecolor  # 24비트 네온 (RGB 지원 터미널/tmux)
dso --once        # 한 프레임만 출력하고 종료 (스냅샷)
dso --bench 60    # 렌더 벤치 (fps·프레임당 바이트)
python3 src/dso_cards.py   # 픽셀 대신 카드 뷰 (소스 전용)
```

- **색**: 기본 256색(`tmux-256color`에서 동작). 트루컬러 네온은 `--truecolor` +
  `tmux set -as terminal-features ',*:RGB'`.
- **터미널 그래픽 한계**: 진짜 비트맵(sixel/kitty)은 tmux가 막는다. 이 렌더러는
  하프블록(색 입힌 글자)이라 tmux를 통과한다 — 도트아트 룩이 한계이자 목표.

## 제거

```bash
python3 install.py --uninstall   # 훅 제거 (settings.json 백업됨)
```

## 튜닝

`src/dso.py` 상단 상수: `IDLE_AFTER`·`OFFLINE_AFTER`·`PRUNE_AFTER`, `TIERS`(작업 규모
임계값), `STATUS`·팔레트, `draw_turret`(기지 모양), 배경 효과 함수(`draw_tracers`·
`draw_lasers`·`draw_comets`), `MAX_W`·`MAX_H`(렌더 상한).
