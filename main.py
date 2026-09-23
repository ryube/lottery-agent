from argparse import ArgumentParser, Namespace, SUPPRESS
from os import getenv
import sys
import traceback

from dotenv import load_dotenv

from accounts import Account, resolve_accounts
from dhlottery import DhLottery, LotteryError
from message import Message

load_dotenv(override=True)

def show_welcome():
  try:
    with open('welcome.txt', 'r') as file:
      content = file.read()
      print('---------------------------------------------')
      print(content)
      print('---------------------------------------------')
  except FileNotFoundError:
    pass

def int_or_default(value, default=0):
  try:
    return int(value)
  except ValueError:
    return default

def get_args():
  dryrun = getenv('LTA_DRYRUN', '0') == '1'
  lo40_count = int(getenv('LTA_LO40_COUNT', '1'))

  # 모든 서브커맨드 공통 옵션 (계정 선택)
  common = ArgumentParser(add_help=False)
  common.add_argument('-p', '--profile', dest='profiles', action='append', metavar='NAME', help='프로필 파일(~/.dhapi/credentials)의 계정을 사용한다. 여러 번 지정 가능. [LTA_PROFILES=a,b]')
  common.add_argument('--all-profiles', dest='all_profiles', action='store_true', help='프로필 파일의 모든 계정을 사용한다. [LTA_PROFILES=all]')

  parser = ArgumentParser(description='Lottery Agent')
  # 예전 Selenium 버전과의 호환용 (무시됨)
  parser.add_argument('--headless', action='store_true', help=SUPPRESS)
  parser.add_argument('--no-headless', action='store_true', help=SUPPRESS)

  subparsers = parser.add_subparsers(dest='command', help='sub-command help')

  buy_parser = subparsers.add_parser('buy', help='buy lotto 6/45.', parents=[common])
  buy_parser.add_argument('--dryrun', dest='dryrun', action='store_true', default=dryrun, help='run only up to the point of purchase. [LTA_DRYRUN=1]')
  buy_parser.add_argument('--no-dryrun', dest='dryrun', action='store_false', default=dryrun, help='run to the end. [LTA_DRYRUN=0]')
  buy_parser.add_argument('--lo40', dest='lo40_count', metavar='n', type=lambda v: int_or_default(v, lo40_count), default=lo40_count, help='lotto 6/45 purchase quantity (max 5). [LTA_LO40_COUNT=n]')
  # 연금복권은 더 이상 지원하지 않는다. 기존 GitHub Action 호환을 위해 인자만 받는다.
  buy_parser.add_argument('--lp72', dest='lp72_count', type=lambda v: int_or_default(v, 0), default=0, help=SUPPRESS)

  check_parser = subparsers.add_parser('check', help='verify that the lotto 6/45 ticket has been won.', parents=[common])
  check_parser.add_argument('lottery', nargs='?', default='lo40', choices=['lo40', 'lp72'], help='select lottery. (lo40 only)')

  subparsers.add_parser('balance', help='show balance.', parents=[common])

  args = parser.parse_args()
  if not args.command:
    parser.print_help()
    sys.exit(1)

  print()
  print('Options')
  print('-------------------------------------')
  if args.command == 'buy':
    print(f'dryrun = {args.dryrun}')
    print(f'lo40 = {args.lo40_count}')
  if args.profiles or args.all_profiles:
    print(f'profiles = {"all" if args.all_profiles else ", ".join(args.profiles)}')
  print('-------------------------------------')
  print()

  return args

def run_account(args: Namespace, account: Account, message: Message) -> bool:
  """계정 하나에 대해 명령을 실행한다. 실패가 있으면 False."""
  dhlottery = DhLottery()
  dhlottery.login(account.userid, account.password)

  if args.command == 'buy':
    message.add('동행 복권 구매 결과입니다.\n')
    message.add(f'실행전 잔고: {dhlottery.getBalance()}')

    if args.lp72_count > 0:
      message.add('연금복권 720+ 는 더 이상 지원하지 않아 건너뜁니다.')

    ok = True
    if args.lo40_count > 0:
      try:
        message.add(dhlottery.buyLo40(args.lo40_count, args.dryrun))
      except LotteryError as e:
        ok = False
        message.add(str(e))

    message.add(f'실행후 잔고: {dhlottery.getBalance()}')
    return ok

  if args.command == 'check':
    if args.lottery == 'lp72':
      message.add('연금복권 720+ 는 더 이상 지원하지 않습니다.')
      return True
    message.add(dhlottery.check('LO40'))
    message.add(f'잔고: {dhlottery.getBalance()}')
    return True

  if args.command == 'balance':
    info = dhlottery.get_balance_info()
    message.add(f'구매가능금액: {info["available"]:,}원')
    message.add(f'총예치금: {info["total"]:,}원')
    if info['reserved']:
      message.add(f'예약구매금액: {info["reserved"]:,}원')
    if info['withdrawing']:
      message.add(f'출금신청중금액: {info["withdrawing"]:,}원')
    return True

  raise Exception(f'not implemented command: {args.command}')

def main() -> int:
  show_welcome()
  args = get_args()
  bottoken = getenv('TLG_BOTTOKEN')
  chatid = getenv('TLG_CHATID')

  try:
    accounts = resolve_accounts(args.profiles, args.all_profiles)
  except Exception as e:
    Message(bottoken=bottoken, chatid=chatid, message=f'에러 발생: {e}').send()
    raise

  print(f'대상 계정: {", ".join(a.userid for a in accounts)}')

  failed = 0
  for account in accounts:
    message = Message(bottoken=bottoken, chatid=chatid, message=f'🤑🤑🤑 유저ID: {account.userid} 🤑🤑🤑')
    try:
      if not run_account(args, account, message):
        failed += 1
    except Exception as e:
      failed += 1
      traceback.print_exc()
      message.add(f'\n에러 발생: {e}')
    try:
      message.send()
    except Exception as e:
      # 텔레그램 실패로 다음 계정 처리가 멈추면 안 된다. (에러 문구에 봇 토큰 URL 이 들어가므로 출력하지 않음)
      print(f'⚠️ 텔레그램 전송 실패 ({type(e).__name__})')

  if failed:
    print(f'{len(accounts)}개 계정 중 {failed}개 계정에서 실패가 있었습니다.')
    return 1
  return 0

if __name__ == '__main__':
  sys.exit(main())
