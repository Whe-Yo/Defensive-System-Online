# RPW — Defensive-System-Online (DSO)

> 현재 상태 스냅샷 (히스토리 아님 — 결정 경위는 git 커밋에). 날짜: 260701

## Rule
- 이 프로젝트는 여러 Claude Code 세션을 **터미널 픽셀아트로 실시간 모니터링**하는 도구다 (게임 아님, 모니터).
- 최소 충격: 기존 파일 수정 우선, 범위 밖 리팩터링 금지.
- 커밋 메시지에 `Co-Authored-By` 금지.

## Plan (목표)
- 안정적인 다중 세션 모니터 + 배포 가능한 스탠드얼론 바이너리 유지.
- 현재 마일스톤(바이너리 패키징 + fleet→dso 통합)은 **완료 상태**. 다음 목표는 사용자 지시 대기 중.

## Work (현재 상태)

### 구조
- `dso.py` (1011줄) — 메인 픽셀 렌더러. 하프블록(`▀`) 컬러 프레임버퍼, 차분 렌더. 바이너리로 빌드됨.
  - 상단 튜닝 상수: `IDLE_AFTER=90`, `FIRE_LINGER=6`, `OFFLINE_AFTER=1800`, `PRUNE_AFTER=7200`, `MAX_W/MAX_H`, `TIERS`, 팔레트.
  - 상태 폴더: `FLEET_DIR = ~/.claude/inundation_agent/<id>.json` (주의: 리네이밍 후에도 폴더명은 `inundation_agent` 유지).
- `dso_cards.py` (242줄) — 정적 카드 뷰. 소스 전용, 바이너리 미포함.
- `install.py` (293줄) — 유일한 설치 파일. 훅을 `~/.claude/dso_hook.py`로 쓰고 `settings.json` 등록, `dso` 명령 설치. 멱등·백업. 훅은 stdout 없음·항상 exit 0.
- `build/`, `dist/` — PyInstaller 산출물. `requirements-build.txt`, `dso.desktop`.

### 상태 모델 (세션 → 적대체 contact)
ENGAGED(교전/도구실행) · TRACKING(추론) · HOLD(입력·권한 대기) · DORMANT(휴면) · LOST(30분+ 무이벤트).
- 크기 = 누적 도구 호출 수 proxy (작은 십자 → 다이아 → 큰 다이아 → 보스).
- 보스 = 최고 점수 단일 contact, 자동 승계.

### 최근 완료 (git 기준)
- fleet → dso 리네이밍, 설치 프로그램/바이너리 하나로 통합 (32aa4c7).
- PyInstaller로 Windows/Linux 스탠드얼론 바이너리 + CI (962a731).
- 알림 처리: 입력 대기 세션은 HOLD로 (b12b0f4 / 2aa0d59).
- contact 소실/미발화 버그 수정, 폴링 스로틀 등 성능 (885b16a).

### 작업 트리
- 깨끗함 (uncommitted 없음). 브랜치: main.

## AntiPatterns / 주의
- **네이밍 레이어 불일치**: README·docstring은 "Inundation_Agent", 디렉토리·바이너리는 "dso", 상태 폴더는 `inundation_agent`. 코드 참조 시 어느 이름인지 확인.
- SIG 게이지는 완료율이 아니라 **활동 신호** (Claude가 진행%를 노출 안 함). "완료%"로 오해 금지.
- 훅은 절대 도구 호출을 막으면 안 됨 (stdout 없음·exit 0 유지).

## 다음 할 일
- (미정 — 사용자 지시 대기)
