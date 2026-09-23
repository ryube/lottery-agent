"""
동행복권 비공식 API 클라이언트 (requests 기반)

https://github.com/roeniss/dhlottery-api 의 LotteryClient 를 참고해서 재작성했다.
브라우저(Selenium) 없이 HTTP 요청만으로 로그인/잔고조회/로또 구매/당첨확인을 한다.
"""
import datetime
import json
import re
import time
from typing import Dict, List, Optional

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

KST = datetime.timezone(datetime.timedelta(hours=9))
MAX_LO40_PER_BUY = 5


class LotteryError(Exception):
  """로또 구매/확인 중 발생하는 에러"""


def to_int(value) -> int:
  """API 금액 필드를 정수로 (None, '5,000' 같은 값도 처리)"""
  try:
    return int(str(value).replace(',', '').strip() or 0) if value is not None else 0
  except ValueError:
    return 0


class DhLottery:
  BASE_URL = 'https://www.dhlottery.co.kr'
  OL_URL = 'https://ol.dhlottery.co.kr'

  LOGIN_PAGE = f'{BASE_URL}/login'
  RSA_KEY_URL = f'{BASE_URL}/login/selectRsaModulus.do'
  LOGIN_URL = f'{BASE_URL}/login/securityLoginCheck.do'
  MYPAGE_URL = f'{BASE_URL}/mypage/home'
  BALANCE_URL = f'{BASE_URL}/mypage/selectUserMndp.do'
  LEDGER_PAGE = f'{BASE_URL}/mypage/mylotteryledger'
  LEDGER_URL = f'{BASE_URL}/mypage/selectMyLotteryledger.do'
  TICKET_DETAIL_URL = f'{BASE_URL}/mypage/lotto645TicketDetail.do'

  GAME645_PAGE = f'{OL_URL}/olotto/game/game645.do'
  READY_SOCKET_URL = f'{OL_URL}/olotto/game/egovUserReadySocket.json'
  BUY_LO40_URL = f'{OL_URL}/olotto/game/execBuy.do'

  TIMEOUT = 15
  BUY_TIMEOUT = (10, 60)  # 구매 요청은 응답이 늦어도 기다린다 (connect, read)
  READY_MAX_WAIT = 120  # 접속 대기열 최대 대기 시간(초)

  def __init__(self, session: Optional[requests.Session] = None):
    self.session = session or requests.Session()
    # 사이트가 Linux/모바일 환경을 차단하므로 Windows Chrome 으로 위장한다.
    self.session.headers.update({
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
      'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
      'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
      'sec-ch-ua-mobile': '?0',
      'sec-ch-ua-platform': '"Windows"',
    })
    self.userid = None

  # ------------------------------------------------------------------ 공통
  def _get(self, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault('timeout', self.TIMEOUT)
    return self.session.get(url, **kwargs)

  def _post(self, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault('timeout', self.TIMEOUT)
    return self.session.post(url, **kwargs)

  def _json_headers(self, referer: str) -> Dict[str, str]:
    return {
      'Accept': 'application/json, text/javascript, */*; q=0.01',
      'X-Requested-With': 'XMLHttpRequest',
      'Referer': referer,
    }

  @staticmethod
  def _rsa_encrypt(plain_text: str, modulus_hex: str, exponent_hex: str) -> str:
    key = RSA.construct((int(modulus_hex, 16), int(exponent_hex, 16)))
    return PKCS1_v1_5.new(key).encrypt(plain_text.encode('utf-8')).hex()

  # ------------------------------------------------------------------ 로그인
  def login(self, userid: str, password: str):
    print(f'[로그인] {userid} 로그인 시도...')
    try:
      resp = self._get(f'{self.BASE_URL}/')
      if 'index_check.html' in resp.url:
        raise LotteryError('동행복권 사이트가 현재 시스템 점검중입니다.')
      self._get(self.LOGIN_PAGE)

      rsa = self._get(self.RSA_KEY_URL, headers=self._json_headers(self.LOGIN_PAGE)).json().get('data')
      if not rsa:
        raise LotteryError('로그인용 RSA 키를 가져올 수 없습니다.')
      modulus, exponent = rsa['rsaModulus'], rsa['publicExponent']

      resp = self._post(
        self.LOGIN_URL,
        headers={'Origin': self.BASE_URL, 'Referer': self.LOGIN_PAGE},
        data={
          'userId': self._rsa_encrypt(userid, modulus, exponent),
          'userPswdEncn': self._rsa_encrypt(password, modulus, exponent),
          'inpUserId': userid,
        },
      )
      if resp.status_code != 200 or 'loginSuccess' not in resp.url:
        raise LotteryError('로그인에 실패했습니다. 아이디 또는 비밀번호를 확인해주세요.')

      # 구매 도메인(ol.dhlottery.co.kr)의 JSESSIONID 를 받아둔다.
      self._get(f'{self.BASE_URL}/main')
      self._get(self.GAME645_PAGE)
      self.userid = userid
      print('[로그인] ✅ 로그인 성공')
    except LotteryError:
      raise
    except Exception as e:
      raise LotteryError(f'로그인 실패: {e}') from e

  # ------------------------------------------------------------------ 잔고
  def get_balance_info(self) -> Dict[str, int]:
    resp = self._get(self.BALANCE_URL, headers=self._json_headers(self.MYPAGE_URL))
    if resp.status_code != 200 or 'json' not in resp.headers.get('Content-Type', '').lower():
      raise LotteryError('예치금 조회 API 응답 오류 (세션 만료 가능성)')
    mndp = resp.json().get('data', {}).get('userMndp', {}) or {}

    def amt(key):
      return to_int(mndp.get(key))

    total = (
      (amt('pntDpstAmt') - amt('pntTkmnyAmt'))
      + (amt('ncsblDpstAmt') - amt('ncsblTkmnyAmt'))
      + (amt('csblDpstAmt') - amt('csblTkmnyAmt'))
    )
    return {
      'total': total,  # 총예치금
      'available': amt('crntEntrsAmt'),  # 구매가능금액
      'reserved': amt('rsvtOrdrAmt'),  # 예약구매금액
      'withdrawing': amt('dawAplyAmt'),  # 출금신청중금액
    }

  def getBalance(self) -> str:
    try:
      info = self.get_balance_info()
      return f'{info["available"]:,}원'
    except Exception as e:
      return f'잔고 확인 실패: {e}'

  # ------------------------------------------------------------------ 로또 6/45 구매
  def _get_lo40_round_info(self, allow_fallback: bool) -> Dict[str, str]:
    """구매 페이지에서 현재 회차/추첨일/지급기한을 읽는다. (dryrun 이면 실패 시 날짜로 계산)"""
    html = self._get(self.GAME645_PAGE).text
    round_match = re.search(r'id="curRound"[^>]*>\s*(\d+)\s*<', html)
    draw_match = re.search(r'id="ROUND_DRAW_DATE"[^>]*value="([\d/]+)"', html)
    limit_match = re.search(r'id="WAMT_PAY_TLMT_END_DT"[^>]*value="([\d/]+)"', html)
    if round_match and draw_match and limit_match:
      return {'round': round_match.group(1), 'draw_date': draw_match.group(1), 'pay_limit_date': limit_match.group(1)}

    if not allow_fallback:
      raise LotteryError('구매 페이지에서 회차 정보를 찾지 못했습니다. (세션 만료 또는 사이트 구조 변경)')
    print('[로또 구매] ⚠️ 구매 페이지에서 회차 정보를 못 찾아 날짜로 계산합니다.')
    return self.calculate_lo40_round_info(datetime.datetime.now(KST).date())

  @staticmethod
  def calculate_lo40_round_info(today: datetime.date) -> Dict[str, str]:
    """로또 6/45 는 2002-12-07(토) 1회부터 매주 토요일 추첨."""
    draw_date = today + datetime.timedelta(days=(5 - today.weekday()) % 7)
    round_number = 1 + (draw_date - datetime.date(2002, 12, 7)).days // 7
    pay_limit_date = draw_date + datetime.timedelta(days=366)
    return {
      'round': str(round_number),
      'draw_date': draw_date.strftime('%Y/%m/%d'),
      'pay_limit_date': pay_limit_date.strftime('%Y/%m/%d'),
    }

  def _wait_ready_socket(self) -> str:
    """접속 대기열을 통과하고 구매 서버 주소(direct)를 받는다."""
    deadline = time.time() + self.READY_MAX_WAIT
    while True:
      resp = self._post(self.READY_SOCKET_URL, headers={'Referer': self.GAME645_PAGE, 'Origin': self.OL_URL})
      data = json.loads(resp.text)
      ready_cnt = int(data.get('ready_cnt') or 0)
      if ready_cnt <= 0:
        return data.get('ready_ip', '')
      if time.time() > deadline:
        raise LotteryError(f'접속 대기열이 너무 깁니다 (대기 인원 {ready_cnt}명)')
      wait = min(max(int(data.get('ready_time') or 3), 1), 10)
      print(f'[로또 구매] 접속 대기중... (대기 인원 {ready_cnt}명, {wait}초 후 재시도)')
      time.sleep(wait)

  @staticmethod
  def make_lo40_param(count: int) -> str:
    """자동 번호 count 게임 구매 파라미터. (alpabet 은 사이트 쪽 오타 그대로)"""
    return json.dumps([
      {'genType': '0', 'arrGameChoiceNum': None, 'alpabet': 'ABCDE'[i]}
      for i in range(count)
    ])

  @staticmethod
  def format_lo40_numbers(lines: List[str]) -> List[str]:
    """
    예: ["A|01|02|04|27|39|443"] -> ["A 자동: 01 02 04 27 39 44"]
    마지막 글자는 선택구분 (1: 수동, 2: 반자동, 3: 자동)
    """
    mode = {'1': '수동', '2': '반자동', '3': '자동'}
    result = []
    for line in lines:
      if not line:
        continue
      body, gbn = line[:-1], line[-1]
      parts = body.split('|')
      result.append(f'{parts[0]} {mode.get(gbn, "?")}: {" ".join(parts[1:])}')
    return result

  def buyLo40(self, count: int, dryrun: bool) -> str:
    try:
      if count > MAX_LO40_PER_BUY:
        print(f'[로또 구매] ⚠️ 1회 최대 {MAX_LO40_PER_BUY}매까지 구매 가능하여 {MAX_LO40_PER_BUY}매로 조정합니다.')
        count = MAX_LO40_PER_BUY
      print(f'[로또 구매] {count}매 구매 시작 (dryrun={dryrun})...')

      info = self._get_lo40_round_info(allow_fallback=dryrun)
      print(f'[로또 구매] 회차: {info["round"]}, 추첨일: {info["draw_date"]}')

      # 재실행 등으로 같은 회차를 중복 구매하지 않도록 이미 산 수량만큼 뺀다. (회차당 최대 5매)
      bought = self.get_bought_count(info['round'])
      if bought:
        print(f'[로또 구매] 이번 회차 이미 구매한 수량: {bought}매')
      remain = min(count, MAX_LO40_PER_BUY - bought)
      if remain <= 0:
        return f'로또 {info["round"]}회는 이미 {bought}매 구매해서 추가 구매하지 않습니다.'
      if remain < count:
        print(f'[로또 구매] ⚠️ 이미 {bought}매 구매해서 {remain}매만 구매합니다.')
        count = remain

      available = self.get_balance_info()['available']
      if available < 1000 * count:
        raise LotteryError(f'예치금 부족 (구매가능금액 {available:,}원, 필요금액 {1000 * count:,}원)')

      data = {
        'round': info['round'],
        'direct': '',
        'nBuyAmount': str(1000 * count),
        'param': self.make_lo40_param(count),
        'ROUND_DRAW_DATE': info['draw_date'],
        'WAMT_PAY_TLMT_END_DT': info['pay_limit_date'],
        'gameCnt': str(count),
        'saleMdaDcd': '10',
      }

      if dryrun:
        print(f'[로또 구매] dryrun: 구매 요청 생략 {data}')
        return f'[dryrun] 로또 {info["round"]}회 {count}매 구매 직전까지 확인 완료'

      data['direct'] = self._wait_ready_socket()
    except LotteryError:
      raise
    except Exception as e:
      raise LotteryError(f'로또 구매 실패: {e}') from e

    # 여기부터는 서버에 구매 요청이 갔을 수 있으므로, 알 수 없는 에러는 '실패'가 아니라 '확인 필요'로 알린다.
    try:
      resp = self._post(self.BUY_LO40_URL, headers={'Referer': self.GAME645_PAGE, 'Origin': self.OL_URL}, data=data, timeout=self.BUY_TIMEOUT)
      print(f'[로또 구매] 응답: {resp.text[:500]}')
      return self._parse_buy_response(json.loads(resp.text), info['round'], count)
    except LotteryError:
      raise
    except Exception as e:
      raise LotteryError(f'⚠️ 로또 구매 결과 확인 불가 ({e}). 구매되었을 수 있으니 재실행 전에 구매내역을 확인하세요.') from e

  def get_bought_count(self, round_number: str) -> int:
    """이번 회차에 이미 구매한 로또 수량"""
    today = datetime.datetime.now(KST).date()
    items = self.get_buy_list(today - datetime.timedelta(days=7), today)
    return sum(
      to_int(i.get('prchsQty')) for i in items
      if i.get('ltGdsCd') == 'LO40' and str(i.get('ltEpsd') or i.get('ltEpsdView')) == str(round_number)
    )

  def _parse_buy_response(self, response: dict, round_number: str, count: int) -> str:
    if response.get('loginYn') == 'N':
      raise LotteryError('로또 구매 실패: 로그인 세션이 만료되었습니다.')
    if response.get('isAllowed') == 'N':
      raise LotteryError('로또 구매 실패: 비정상적인 접속 환경으로 차단되었습니다.')
    if response.get('isGameManaged') == 'Y':
      raise LotteryError(f'로또 구매 실패: {response.get("errorMsg")}')
    if response.get('checkOltSaleTime') is False:
      raise LotteryError('로또 구매 실패: 판매 시간이 아니거나 잘못된 요청입니다.')

    result = response.get('result') or {}
    if result.get('resultCode') != '100':
      raise LotteryError(f'로또 구매 실패: {result.get("resultMsg") or "알 수 없는 오류"}')

    lines = self.format_lo40_numbers(result.get('arrGameChoiceNum') or [])
    print(f'[로또 구매] ✅ 구매 성공: {len(lines)}매')
    return '\n'.join([f'로또 구매완료: {round_number}회 {len(lines) or count}매', *lines])

  # ------------------------------------------------------------------ 당첨 확인
  def get_buy_list(self, start: datetime.date, end: datetime.date) -> List[dict]:
    self._get(self.LEDGER_PAGE)
    resp = self._get(
      self.LEDGER_URL,
      headers=self._json_headers(self.LEDGER_PAGE),
      params={
        'srchStrDt': start.strftime('%Y%m%d'),
        'srchEndDt': end.strftime('%Y%m%d'),
        'pageNum': 1,
        'recordCountPerPage': 100,
        '_': int(time.time() * 1000),
      },
    )
    if resp.status_code != 200 or 'json' not in resp.headers.get('Content-Type', '').lower():
      raise LotteryError('구매 내역 조회 API 응답 오류 (세션 만료 가능성)')
    return (resp.json().get('data') or {}).get('list') or []

  def _get_lo40_ticket_numbers(self, item: dict) -> List[str]:
    """구매 건의 상세 번호 (실패하면 빈 목록)"""
    try:
      buy_date = datetime.datetime.strptime(item['eltOrdrDt'], '%Y-%m-%d').date()
      resp = self._get(self.TICKET_DETAIL_URL, headers=self._json_headers(self.LEDGER_PAGE), params={
        'ntslOrdrNo': item['ntslOrdrNo'],
        'srchStrDt': (buy_date - datetime.timedelta(days=7)).strftime('%Y%m%d'),
        'srchEndDt': (buy_date + datetime.timedelta(days=7)).strftime('%Y%m%d'),
        'barcd': item['gmInfo'],
      })
      data = resp.json().get('data') or {}
      if not data.get('success'):
        return []
      mode = {1: '수동', 2: '반자동', 3: '자동'}
      return [
        f'  {g.get("idx", "")} {mode.get(g.get("type"), "자동")}: {" ".join(f"{n:02d}" for n in g.get("num", []))}'
        for g in data['ticket'].get('game_dtl', [])
      ]
    except Exception as e:
      print(f'[당첨 확인] ⚠️ 번호 상세 조회 실패: {e}')
      return []

  @staticmethod
  def is_winning(item: dict) -> bool:
    return to_int(item.get('ltWnAmt')) > 0 or item.get('ltWnResult') not in ('낙첨', '미추첨', None, '')

  def check(self, code: str = 'LO40', days: int = 7) -> str:
    try:
      print(f'[당첨 확인] 로또 6/45 최근 {days}일 구매내역 확인...')
      today = datetime.datetime.now(KST).date()
      items = [i for i in self.get_buy_list(today - datetime.timedelta(days=days), today) if i.get('ltGdsCd') == code]
      print(f'[당첨 확인] 로또 구매 건수: {len(items)}')

      if not items:
        return '로또 6/45 당첨 없음 (최근 구매 내역 없음)'

      winnings = [i for i in items if self.is_winning(i)]
      summary = [
        f'{i.get("eltOrdrDt")} {i.get("ltEpsdView")}회 {i.get("prchsQty")}매: {i.get("ltWnResult")}'
        for i in items
      ]

      if not winnings:
        return '\n'.join(['로또 6/45 당첨 없음', *summary])

      bar = '---------------------------------------'
      lines = ['당첨된 게 있다!!!', bar]
      for i in winnings:
        lines.append(f'{i.get("eltOrdrDt")} 로또6/45 {i.get("ltEpsdView")}회 {to_int(i.get("ltWnAmt")):,}원 ({i.get("ltWnResult")})')
        lines.extend(self._get_lo40_ticket_numbers(i))
      lines.append(bar)
      return '\n'.join(lines)
    except LotteryError:
      raise
    except Exception as e:
      raise LotteryError(f'당첨 확인 실패: {e}') from e
