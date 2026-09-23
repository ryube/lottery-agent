#!/usr/bin/env python3
"""
전체 함수 테스트 (실제 사이트 접속, 구매는 dryrun)

  uv run python test_all_functions.py
"""
import sys
import traceback

from dotenv import load_dotenv

from accounts import resolve_accounts
from dhlottery import DhLottery

load_dotenv(override=True)


def run(name, fn):
  print(f'\n--- {name} ---')
  try:
    result = fn()
    print(result)
    print(f'✅ {name} 성공')
    return True
  except Exception:
    traceback.print_exc()
    print(f'❌ {name} 실패')
    return False


results = []
for account in resolve_accounts():
  print(f'\n=========== {account.userid} ===========')
  dhlottery = DhLottery()
  if not run('login', lambda: dhlottery.login(account.userid, account.password)):
    results.append(False)
    continue
  results.append(run('get_balance_info', dhlottery.get_balance_info))
  results.append(run('buyLo40 (dryrun)', lambda: dhlottery.buyLo40(1, dryrun=True)))
  results.append(run('check', lambda: dhlottery.check('LO40', days=35)))

print(f'\n결과: {sum(results)}/{len(results)} 성공')
sys.exit(0 if all(results) else 1)
