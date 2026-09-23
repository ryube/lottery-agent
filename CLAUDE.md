# lottery-agent

## 프로젝트 개요
동행복권(dhlottery.co.kr)에서 로또 6/45를 자동 구매/당첨확인하는 requests 기반 자동화 도구.
[roeniss/dhlottery-api](https://github.com/roeniss/dhlottery-api) 의 LotteryClient 를 참고해 재작성함. 연금복권 720+ 는 지원 중단.

## 구조
- `main.py` - 엔트리포인트. CLI 파싱(buy/check/balance), 계정별 실행 + 텔레그램 전송
- `dhlottery.py` - 핵심 로직. RSA 로그인, 잔고조회, 로또 구매(execBuy.do), 당첨확인(구매내역 JSON API)
- `accounts.py` - 다중 계정 로딩 (환경변수 `DHL_USERID[_N]` / 프로필 파일 `~/.dhapi/credentials`)
- `message.py` - 텔레그램 메시지 전송
- `test_unit.py` - 네트워크 없는 단위 테스트
- `test_login.py`, `test_all_functions.py` - 실사이트 테스트 (구매는 dryrun)
- `.github/workflows/` - GitHub Actions (구매: 월 19시 KST, 당첨확인: 일 21시 KST)

## 실행 환경
- **GitHub Actions (프로덕션)**: 저장소를 checkout 해서 `python main.py` 를 직접 실행 (Docker/외부 action 사용 안 함)
  - secrets: `DHL_USERID`, `DHL_PASSWORD`, `DHL_USERID_2`, `DHL_PASSWORD_2`, `TLG_BOTTOKEN`, `TLG_CHATID` / vars: `LO40_COUNT`
  - 스케줄/수동실행은 기본 브랜치(main)의 워크플로만 동작
- 예전 CLI 호환: `--headless`, `--lp72` 인자는 받기만 하고 무시

## 환경변수
- `DHL_USERID` / `DHL_PASSWORD` - 동행복권 계정, 추가 계정은 `DHL_USERID_2` / `DHL_PASSWORD_2` ...
- `LTA_PROFILES` - 프로필 파일에서 쓸 프로필 (`a,b` 또는 `all`), `DHL_CREDENTIALS` - 프로필 파일 경로
- `TLG_BOTTOKEN` / `TLG_CHATID` - 텔레그램 알림 (선택)
- `LTA_DRYRUN`, `LTA_LO40_COUNT`
- `.env` 파일에 설정

## 테스트
```bash
uv run python -m unittest test_unit
uv run python test_login.py
uv run python test_all_functions.py
```
로컬 회사망에서 SSL 에러 시 `REQUESTS_CA_BUNDLE` 에 시스템 인증서 번들 지정 (README 참고)

## 동행복권 API (2026-09 확인)
- 로그인: `GET /login/selectRsaModulus.do` 로 RSA 키 → `POST /login/securityLoginCheck.do` (userId, userPswdEncn 을 RSA PKCS1 암호화, 성공 시 URL 에 loginSuccess)
- 로그인 후 `ol.dhlottery.co.kr/olotto/game/game645.do` 접속해서 구매 도메인 JSESSIONID 획득
- 잔고: `GET /mypage/selectUserMndp.do` (crntEntrsAmt = 구매가능금액)
- 구매: game645.do 페이지에서 curRound / ROUND_DRAW_DATE / WAMT_PAY_TLMT_END_DT 파싱 → `POST egovUserReadySocket.json` (ready_cnt > 0 이면 대기, ready_ip = direct) → `POST execBuy.do` (resultCode 100 = 성공)
- 구매내역: `GET /mypage/selectMyLotteryledger.do` (JSON, ltGdsCd=LO40, ltWnResult, ltWnAmt)
- 번호 상세: `GET /mypage/lotto645TicketDetail.do`
- User-Agent 는 Windows Chrome 으로 위장 (Linux/모바일 차단)

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

**상태**: 로컬 테스트 통과 (headless/non-headless 모두)

### 2025-02-10: 페이지 로드 타임아웃 수정
**문제**: Docker 환경에서 `driver.get()` 호출 시 120초 타임아웃 발생
- "Timed out receiving message from renderer: 119.693"
- Chrome 144, Docker 컨테이너 내 Chromium

**원인**: Docker 환경에서 네트워크/리소스 제약으로 `el.dhlottery.co.kr` 페이지가 기본 타임아웃 내 로드 실패

**수정 내용**:
1. `_safe_get()` 메서드 추가 - page_load_timeout 설정 + 최대 3회 재시도
2. 부분 로드 상태에서도 진행 가능하면 계속 진행
3. `buyLo40()`, `buyLp72()` 모두 `_safe_get()` 사용으로 변경

**상태**: 로컬 헤드리스 테스트 통과, Docker 환경 테스트 필요

### 2026-09-23: Selenium 제거, requests 기반으로 재작성 + 다중 계정
**배경**: Selenium 방식은 대기열/iframe/페이지 로드 타임아웃 문제가 반복됨. dhlottery-api 처럼 HTTP API 직접 호출로 교체.

**변경 내용**:
1. `dhlottery.py` 전면 재작성 (requests + pycryptodome RSA 로그인)
2. 연금복권 720+ 지원 중단 (`--lp72` 는 무시)
3. `accounts.py` 추가 - 환경변수 `DHL_USERID_N` / dhapi 호환 프로필 파일로 다중 계정, 계정별 텔레그램 메시지
4. `balance` 명령 추가, Docker 빌드/외부 action 제거 → Actions 에서 python 직접 실행
5. 중복 구매 방지: 같은 회차 기구매 수량 차감, 구매 요청 후 에러는 '결과 확인 불가'로 알림, 계정 중복 제거

**상태**: 실계정으로 로그인/잔고/구매 dryrun/당첨확인/대기열 API 확인. 실제 구매(execBuy.do)는 미검증.

