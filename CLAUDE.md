# lottery-agent

## 프로젝트 개요
동행복권(dhlottery.co.kr)에서 로또 6/45, 연금복권 720+를 자동 구매/당첨확인하는 Selenium 기반 자동화 도구.

## 구조
- `main.py` - 엔트리포인트. Chrome 드라이버 생성, CLI 파싱, 구매/확인 실행
- `dhlottery.py` - 핵심 로직. 로그인, 잔고확인, 로또/연금복권 구매, 당첨확인
- `message.py` - 텔레그램 메시지 전송
- `test_login.py` - 로그인 테스트 (로컬 macOS용, headless=False)
- `test_all_functions.py` - 전체 함수 테스트 (로컬 macOS용, dryrun)
- `Dockerfile` - Docker 빌드 (Chromium + Python 3.11)

## 실행 환경
- **Docker (프로덕션)**: `/usr/bin/chromium` 사용, headless 모드
- **로컬 macOS (개발/테스트)**: 시스템 Chrome 사용, `test_*.py` 파일로 테스트
- **GitHub Actions**: `.github/workflows/` 참조

## 환경변수
- `DHL_USERID` / `DHL_PASSWORD` - 동행복권 계정
- `TLG_BOTTOKEN` / `TLG_CHATID` - 텔레그램 알림 (선택)
- `.env` 파일에 설정

## 테스트
```bash
# 로그인 테스트
uv run python test_login.py

# 전체 함수 테스트 (dryrun)
uv run python test_all_functions.py
```

## 동행복권 사이트 구조 (2025~)
- 구매 페이지: `https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40`
- 로또 iframe: `https://ol.dhlottery.co.kr/olotto/game/game645.do`
- iframe 내에 **대기열 시스템** 존재 (showRealPage/hideWaitUI 함수로 제어)
- 대기열 완료 후 게임 인터페이스 로드
- navigator.platform이 Win64여야 접속 가능 (Linux 차단)

## 작업 이력

### 2025-02-10: 자동 번호 선택 실패 문제 수정
**문제**: `buyLo40()`에서 자동 번호 선택 3가지 방법 모두 실패
- 방법 1 (selectWayTab JS 함수): 함수 미존재
- 방법 2 (onclick 버튼 클릭): 요소 미발견
- 방법 3 (ID/class 탭 찾기): 요소 미발견

**원인 분석**: 동행복권 사이트 iframe이 `ol.dhlottery.co.kr/olotto/game/game645.do`로 변경되면서 대기열 시스템이 추가됨. 기존 코드는 iframe 전환 후 5초 대기만 하고 바로 요소를 찾으려 했으나, 대기열이 완료되지 않은 상태에서는 게임 요소가 DOM에 없음.

**수정 내용**:
1. `_wait_for_game_ready()` 추가 - 대기열 완료 후 게임 요소(amoundApply, btnSelectNum, selectWayTab) 출현까지 최대 60초 대기
2. `_select_auto_number()` 리팩토링 - 5가지 방법으로 분리하여 시도
   - JS 함수 호출 (selectWayTab)
   - onclick 속성 버튼 클릭
   - ID/class 기반 탭 찾기 (여러 XPath)
   - 텍스트 기반 "자동" 버튼 찾기
   - JS querySelector로 auto 관련 요소 탐색
3. `_dump_page_state()` 추가 - 실패 시 페이지 소스, 요소 존재 여부, JS 함수 존재 여부 덤프

**상태**: 테스트 필요 - 실제 사이트 접속하여 대기열 통과 후 게임 요소 셀렉터 확인 필요
