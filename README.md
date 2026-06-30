# Inundation_Agent — ORBITAL DEFENSE 🛰

여러 Claude Code 세션의 작업 상황을 **터미널에서 실시간 픽셀 그래픽**으로 보여주는
지구방위 터렛 콘솔. [SKILL-HERO](https://github.com/Ign0reLee/SKILL-HERO)의 "작업=게임"
발상과 **범람(Inundation)** 프로젝트의 레트로 CRT 네온 미감에서 영감을 받았다.

> **세계관**: 범람이 *지구로 귀환하는 함대*였다면, Inundation_Agent는 *그 지구를 지키는
> 터렛*이다. 화면 6시(하단 중앙)에 방어 터렛 하나가 있고, 하늘에서 미확인 적대체(=각 세션)가
> 강하한다. 세션이 **교전중(ENGAGED)**이면 터렛이 그 적대체로 네온 빔을 발사한다 — 터렛
> 하나가 다수 표적을 상대하며 빔이 부채꼴로 뻗는다.

이건 **모니터**이지 게임이 아니며, 범람은 별개로 개발된다.

**하프블록 픽셀 렌더링**: 터미널 한 칸(`▀`)의 위/아래 색을 따로 줘서 칸당 픽셀 2개의
컬러 프레임버퍼를 만든다. 비트맵 프로토콜(sixel)이 아니라 "색 입힌 글자"라서 **tmux·SSH를
그대로 통과**한다. 별 배경, 강하 적대체, 교전 빔, 지면·도시 불빛이 매 프레임 그려진다.

하이브리드 레이아웃 — **상단에 작은 전투 배너**(터렛 + 적대체 블립 + 교전 빔, 연출용),
**하단에 가독성 리스트**(세션당 한 줄: 상태·프로젝트명 전체·활동바·현재 동작·도구수·경과).
세션이 많아도 한 줄씩이라 다 보이고, 긴 프로젝트명도 안 잘린다.

```
INUNDATION_AGENT // ORBITAL DEFENSE          3 ENGAGING  5 CONTACTS  0 LOST   q quit
   ◦   ·    ◦         ◦   ·       blips(적대체)        ·    ◦
        ╲       ╲      beams      ╱
                   ▁▆█▆▁   ← 작은 터렛(6시)      · 지상 조명 ·
────────────────────────────────────────────────────────────────────────────────────
 ● ENGAGED   ml-pipeline        ▮▮▮▮▮▮▮▯ ▸ Read config.yaml              22t  1m
 ● ENGAGED   BeatSenseVid_VJ    ▮▮▮▮▮▮▮▯ ▸ Bash pytest -q tests/unit      4t  2m
 ▲ HOLD      api-gateway        ▮▮▮▮▮▮▮▯ ▸ permission: Bash(rm -rf …)     7t 25m
 ● ENGAGED   Inundation_Agent   ▮▮▮▮▮▮▮▯ ▸ Edit fleet.py                 45t 12m
 ○ DORMANT   2dtomesh           ▮▮▮▯▯▯▯▯ ▸ idle 40s                      12t  3m
```
(실제 화면은 트루컬러 네온 + 애니메이션 배너. 위는 흑백 개념도)

## 동작 구조

```
각 Claude 세션 ──(hook)──> ~/.claude/inundation_agent/<id>.json ──(읽기)──> fleet.py 렌더러
```

- `fleet_hook.py` — 모든 세션의 훅 이벤트(도구 사용·프롬프트·정지 등)를 받아 세션별 상태 파일에 기록. **stdout 출력 없음 · 항상 exit 0** → 도구 호출을 절대 막지 않는다.
- `fleet.py` — 상태 폴더를 매 프레임 읽어 **상단 배너(블립·터렛·빔)** + **하단 리스트(세션당 한 줄)**로 렌더. 리스트는 프로젝트명·동작을 전부 보여주고 세션 수만큼 줄이 늘어난다(활동순 정렬). **교전중(working)인 세션만 터렛이 빔으로 조준**한다. 차분 렌더(바뀐 칸만 전송)로 SSH에서도 가볍다.
- `fleet_cards.py` — 픽셀 대신 정적 카드를 원할 때의 경량 폴백 뷰 (`fleet.py --cards`로 실행).

## 설치

```bash
bash install.sh          # textual 설치 + ~/.claude/settings.json에 훅 등록(멱등·백업)
```

설치 후 **새로 시작하는 세션부터** 추적된다(기존 세션은 다음 도구 사용 시 등장).
경로를 옮긴 뒤에는 `bash install.sh --uninstall && bash install.sh`로 훅을 재연결한다.

## 실행

```bash
python3 fleet.py              # 라이브 픽셀 씬 (q 또는 Ctrl-C 종료)
python3 fleet.py --fps 15     # 프레임레이트 (기본 12, 2~30). SSH가 느리면 낮춰라
python3 fleet.py --truecolor  # 24비트 네온 (tmux/터미널이 RGB 지원 시 더 선명)
python3 fleet.py --once        # 한 프레임만 출력하고 종료 (스냅샷)
python3 fleet.py --cards       # 픽셀 대신 카드 뷰 (fleet_cards.py)
python3 fleet.py --bench 60    # 60프레임 렌더 벤치 (fps·프레임당 바이트)
```

별도 터미널/탭에서 띄워두고 작업하면 된다. 큰 화면일수록 적대체가 더 많이 보인다.

- **색**: 기본은 256색이라 `tmux-256color`에서 무조건 동작. 트루컬러 네온을 원하면
  `--truecolor` + tmux RGB 설정(`tmux set -as terminal-features ',*:RGB'`).
- **터미널 그래픽 한계**: 진짜 비트맵 이미지(sixel/kitty)는 tmux가 막는다. 이 렌더러는
  하프블록(색 입힌 글자)이라 tmux를 통과한다 — 도트 게임 룩이 한계이자 목표.

## 적대체 상태와 계기

| 상태 | 표기 | 의미 | 연출 |
|---|---|---|---|
| ENGAGED | 교전 | 도구 실행 중 (Edit/Bash/Grep…) | **터렛이 빔으로 조준·발사** |
| TRACKING | 추적 | 도구 사이 추론 중 | 막 점멸 |
| HOLD | 대기명령 | 입력/권한 대기 (Notification) | 마젠타 경고색 |
| DORMANT | 휴면 | 턴 종료 후 사용자 대기 | 약한 발광 |
| LOST | 소실 | 30분+ 무이벤트 | 적체 명멸(소멸) |

- **SIG 게이지 = 활동 신호, 작업 완료율이 아니다.** Claude는 작업의 정확한 완료 %를
  노출하지 않으므로, 게이지는 활동 중 가득 차고 유휴 시간에 따라 감쇠한다.
- **터렛은 ENGAGED(working) 세션에만 발사**한다 — 가짜 진행률이 아니라 실제 활동에 반응.
- **실값**: 상태 · 현재 동작(`▸`) · HITS(누적 도구 수) · T+(경과시간) · 분류(UX-##).

## 제거

```bash
bash install.sh --uninstall   # 훅 제거 (settings.json 백업됨)
```

## 튜닝

`fleet.py` 상단 상수: `IDLE_AFTER`(유휴 판정 초), `OFFLINE_AFTER`, `PRUNE_AFTER`(상태파일 삭제),
`HOSTILE`(적대체 도트), `STATUS`·팔레트(네온 색), `draw_turret`(터렛 모양), `MAX_W/MAX_H`(렌더 상한).
