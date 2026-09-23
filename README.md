# 간단설명

동행복권 로또 6/45 를 커맨드라인으로 구매하고 당첨을 확인한다.

브라우저(Selenium) 없이 HTTP 요청만으로 동작한다. ([roeniss/dhlottery-api](https://github.com/roeniss/dhlottery-api) 참고)
연금복권 720+ 는 지원하지 않는다.

# PC에서 개발/실행하기

## 준비

```bash
uv venv
uv pip install -r requirements.txt
```

.env.sample 파일을 .env 로 복사하고 본인 계정을 세팅한다.

* DHL_USERID / DHL_PASSWORD : 동행복권 계정
* DHL_USERID_2 / DHL_PASSWORD_2, DHL_USERID_3 / ... : 추가 계정 (다중 계정)
* TLG_BOTTOKEN : 텔레그램 봇 토큰
* TLG_CHATID : 텔레그램 메시지 수신 아이디

텔레그램 세팅은 안해도 된다. 세팅하고 싶다면 [여기](https://www.keywordontop.com/%EA%B5%AC%EA%B8%80seo/%ED%85%94%EB%A0%88%EA%B7%B8%EB%9E%A8-%EB%B4%87/)를 참고.

## 다중 계정

계정마다 따로 실행되고 텔레그램 메시지도 계정별로 따로 간다. 한 계정이 실패해도 나머지 계정은 계속 진행한다.

### 방법 1: 환경변수

```
DHL_USERID=first_id
DHL_PASSWORD=first_pw
DHL_USERID_2=second_id
DHL_PASSWORD_2=second_pw
```

### 방법 2: 프로필 파일 (dhlottery-api 호환)

`~/.dhapi/credentials` (경로는 `DHL_CREDENTIALS` 로 변경 가능)

```toml
[default]
username = "first_id"
password = "first_pw"
[wife]
username = "second_id"
password = "second_pw"
```

```bash
uv run python main.py buy -p default -p wife   # 지정한 프로필만
uv run python main.py buy --all-profiles       # 전체 프로필
LTA_PROFILES=all uv run python main.py buy     # 환경변수로 지정
```

프로필을 지정하면 DHL_USERID 환경변수는 무시한다.

## 실행

### 구매
```bash
uv run python main.py buy [--lo40 n] [--dryrun/--no-dryrun] [-p NAME] [--all-profiles]
```

* --lo40 : 로또 구매 수량 (자동, 최대 5매)
* --dryrun : 구매 직전까지만 실행하고 멈춘다

### 당첨 확인
```bash
uv run python main.py check [lo40]
```

최근 1주일 구매내역에서 당첨 여부를 확인한다.

### 잔고 확인
```bash
uv run python main.py balance
```

`--headless`, `--lp72` 옵션은 예전 버전 호환용으로 받기만 하고 무시한다.

같은 회차에 이미 산 수량이 있으면 그만큼 빼고 산다 (회차당 최대 5매). 재실행해도 중복 구매되지 않는다.

# GitHub Actions

* `Lottery purchase` : 매주 월요일 19시(KST) 구매. 수동 실행 시 수량/dryrun 선택 가능
* `Lotto 6/45 result checker` : 매주 일요일 21시(KST) 당첨 확인

Settings > Secrets and variables > Actions 에 등록한다.

* secrets : `DHL_USERID`, `DHL_PASSWORD`, `DHL_USERID_2`, `DHL_PASSWORD_2` (두 번째 계정, 선택), `TLG_BOTTOKEN`, `TLG_CHATID`
* variables : `LO40_COUNT` (스케줄 구매 수량, 기본 5)

계정을 더 늘리려면 `DHL_USERID_3` / `DHL_PASSWORD_3` secret 을 만들고 워크플로 env 에 추가한다.

## 테스트

```bash
# 네트워크 없이 도는 단위 테스트
uv run python -m unittest test_unit

# 로그인 + 잔고 (실제 사이트)
uv run python test_login.py

# 전체 함수 (실제 사이트, 구매는 dryrun)
uv run python test_all_functions.py
```

회사망처럼 SSL 인증서를 가로채는 환경에서 `CERTIFICATE_VERIFY_FAILED` 가 나면
`REQUESTS_CA_BUNDLE` 에 시스템 인증서 번들을 지정한다.

```bash
security find-certificate -a -p /Library/Keychains/System.keychain /System/Library/Keychains/SystemRootCertificates.keychain > /tmp/ca.pem
REQUESTS_CA_BUNDLE=/tmp/ca.pem uv run python test_login.py
```
