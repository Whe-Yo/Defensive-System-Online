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

### 구조 (패키징 제거 — 소스 전용, 260701 리팩터)
```
├── src/
│   ├── dso.py         # 메인 픽셀 렌더러 (하프블록 컬러 프레임버퍼, 차분 렌더)
│   ├── dso_cards.py   # 정적 카드 뷰 (dso.py --cards 가 __file__ 옆에서 exec)
│   └── dso_hook.py    # Claude 이벤트 훅 (stdin→세션 상태파일, stdout 없음·exit 0)
├── install.py         # src/dso_hook.py를 ~/.claude/dso_hook.py로 복사·등록 + dso 명령 연결
├── dso.sh             # 리눅스 런처: tty면 인라인, tty 없으면(클릭) 새 터미널
├── dso.bat            # 윈도우 런처: cmd 인라인 / 더블클릭 시 콘솔
└── README.md
```
- `dso.py` 튜닝 상수: `IDLE_AFTER=90`, `FIRE_LINGER=6`, `OFFLINE_AFTER=1800`, `PRUNE_AFTER=7200`, `MAX_W/MAX_H`, `TIERS`, 팔레트.
- 상태 폴더: `~/.claude/inundation_agent/<id>.json` (리네이밍 후에도 폴더명 유지).
- PyInstaller 패키징(build/·dist/·.github CI·requirements-build.txt·dso.spec·dso.desktop) **전부 삭제**.

### 상태 모델 (세션 → 적대체 contact)
ENGAGED(교전/도구실행) · TRACKING(추론) · HOLD(입력·권한 대기) · DORMANT(휴면) · LOST(30분+ 무이벤트).
- 크기 = 누적 도구 호출 수 proxy (작은 십자 → 다이아 → 큰 다이아 → 보스).
- 보스 = 최고 점수 단일 contact, 자동 승계.

### 최근 완료
- **동기화 버그 수정 (260701)**: settings.json이 옛 경로 `/workspace/00/Inundation_Agent/fleet_hook.py`(삭제됨)를 가리켜 훅이 조용히 실패 → dso 빈 화면이던 것을, install.py 재실행으로 복구. 훅이 다시 세션 상태를 기록함(검증됨).
- **패키징 제거 + 구조 단순화 (260701)**: PyInstaller/CI 삭제, src/ 폴더 + install.py + dso.sh/dso.bat 런처로 정리.
- fleet → dso 리네이밍 (32aa4c7).
- 알림 처리: 입력 대기 세션은 HOLD로 (b12b0f4 / 2aa0d59).
- contact 소실/미발화 버그 수정, 폴링 스로틀 등 성능 (885b16a).

### 작업 트리
- 깨끗함 (uncommitted 없음). 브랜치: main.

## AntiPatterns / 주의
- **네이밍 레이어 불일치**: README·docstring은 "Inundation_Agent", 디렉토리·바이너리는 "dso", 상태 폴더는 `inundation_agent`. 코드 참조 시 어느 이름인지 확인.
- SIG 게이지는 완료율이 아니라 **활동 신호** (Claude가 진행%를 노출 안 함). "완료%"로 오해 금지.
- 훅은 절대 도구 호출을 막으면 안 됨 (stdout 없음·exit 0 유지).

## 안티테제 (260701, 리팩터 검토)
- **채택** #2 read_settings: 파싱 실패 시 `{}` 반환 → settings.json 전체 덮어써 사용자 훅/권한 소실 위험 → 중단하도록 수정(검증됨).
- **채택** #1 Windows PATH: `setx PATH "%PATH%;.."`는 병합 PATH 오염+1024자 잘림 → PowerShell `SetEnvironmentVariable(...,'User')`로 교체 (**Windows 미검증** — 리눅스 환경).
- **채택** #4 dso.sh: `gnome/xfce4-terminal -e` 다중인자 미지원 → `--` 분기.
- **채택** #5 dso.sh: macOS `readlink -f` 부재 → 이식성 있는 symlink 해석(검증됨).
- **기각** #3 sys.executable→python3: 훅 exec 환경 PATH에 python3 부재 위험 신규 발생, 절대경로가 일반 설치에서 더 안전.
- **주석수정** #6 tty OR 판정 과장 주석 정정.

## 다음 할 일
- (미정 — 사용자 지시 대기)
- Windows에서 install.py PATH 등록 실제 검증 (현재 미검증).
