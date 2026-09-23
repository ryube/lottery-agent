#!/usr/bin/env python3
"""
로그인 + 잔고 조회 테스트 (실제 사이트 접속, 구매 없음)

  uv run python test_login.py
"""
import sys

from dotenv import load_dotenv

from accounts import resolve_accounts
from dhlottery import DhLottery

load_dotenv(override=True)

failed = 0
for account in resolve_accounts():
  print(f'\n=== {account.userid} ===')
  try:
    dhlottery = DhLottery()
    dhlottery.login(account.userid, account.password)
    print(f'잔고: {dhlottery.getBalance()}')
  except Exception as e:
    failed += 1
    print(f'❌ 실패: {e}')

sys.exit(1 if failed else 0)
