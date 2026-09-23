#!/usr/bin/env python3
"""
네트워크 없이 돌아가는 단위 테스트

  uv run python -m unittest test_unit
"""
import datetime
import json
import os
import tempfile
import unittest

from accounts import load_env_accounts, resolve_accounts
from dhlottery import DhLottery, LotteryError


class RoundInfoTest(unittest.TestCase):
  def test_round_on_draw_day(self):
    info = DhLottery.calculate_lo40_round_info(datetime.date(2026, 9, 26))
    self.assertEqual(info, {'round': '1243', 'draw_date': '2026/09/26', 'pay_limit_date': '2027/09/27'})

  def test_round_midweek(self):
    info = DhLottery.calculate_lo40_round_info(datetime.date(2026, 9, 21))  # 월요일
    self.assertEqual(info['round'], '1243')
    self.assertEqual(info['draw_date'], '2026/09/26')

  def test_round_sunday_moves_to_next(self):
    info = DhLottery.calculate_lo40_round_info(datetime.date(2026, 9, 27))
    self.assertEqual(info['round'], '1244')


class BuyTest(unittest.TestCase):
  def test_make_param(self):
    param = json.loads(DhLottery.make_lo40_param(3))
    self.assertEqual([p['alpabet'] for p in param], ['A', 'B', 'C'])
    self.assertTrue(all(p['genType'] == '0' and p['arrGameChoiceNum'] is None for p in param))

  def test_format_numbers(self):
    self.assertEqual(
      DhLottery.format_lo40_numbers(['A|01|02|04|27|39|443', 'B|11|23|25|27|28|451']),
      ['A 자동: 01 02 04 27 39 44', 'B 수동: 11 23 25 27 28 45'],
    )

  def test_parse_success(self):
    msg = DhLottery()._parse_buy_response(
      {'result': {'resultCode': '100', 'arrGameChoiceNum': ['A|01|02|03|04|05|063']}}, '1243', 1)
    self.assertIn('로또 구매완료: 1243회 1매', msg)
    self.assertIn('A 자동: 01 02 03 04 05 06', msg)

  def test_parse_failure(self):
    with self.assertRaisesRegex(LotteryError, '구매한도'):
      DhLottery()._parse_buy_response({'result': {'resultCode': '-1', 'resultMsg': '구매한도 초과'}}, '1243', 1)
    with self.assertRaisesRegex(LotteryError, '세션'):
      DhLottery()._parse_buy_response({'loginYn': 'N'}, '1243', 1)


class WinningTest(unittest.TestCase):
  def test_is_winning_string_amount(self):
    self.assertTrue(DhLottery.is_winning({'ltWnResult': '', 'ltWnAmt': '5,000'}))

  def test_is_winning(self):
    self.assertFalse(DhLottery.is_winning({'ltWnResult': '낙첨', 'ltWnAmt': 0}))
    self.assertFalse(DhLottery.is_winning({'ltWnResult': '미추첨', 'ltWnAmt': None}))
    self.assertTrue(DhLottery.is_winning({'ltWnResult': '당첨', 'ltWnAmt': 5000}))


class AccountsTest(unittest.TestCase):
  def test_env_accounts(self):
    env = {'DHL_USERID': 'a', 'DHL_PASSWORD': 'pa', 'DHL_USERID_3': 'c', 'DHL_PASSWORD_3': 'pc',
           'DHL_USERID_2': 'b', 'DHL_PASSWORD_2': 'pb'}
    self.assertEqual([a.userid for a in load_env_accounts(env)], ['a', 'b', 'c'])

  def test_env_missing_password(self):
    with self.assertRaises(ValueError):
      load_env_accounts({'DHL_USERID': 'a', 'DHL_USERID_2': 'b', 'DHL_PASSWORD': 'x'})

  def test_no_accounts(self):
    with self.assertRaises(ValueError):
      resolve_accounts(env={})

  def test_profiles(self):
    with tempfile.NamedTemporaryFile('w', suffix='.toml', delete=False) as f:
      f.write('[default]\nusername = "id1"\npassword = "p=w,1"\n[wife]\nusername = "id2"\npassword = "pw2"\n')
    try:
      env = {'DHL_CREDENTIALS': f.name, 'DHL_USERID': 'ignored', 'DHL_PASSWORD': 'x'}
      self.assertEqual([a.userid for a in resolve_accounts(['wife'], env=env)], ['id2'])
      self.assertEqual([a.password for a in resolve_accounts(all_profiles=True, env=env)], ['p=w,1', 'pw2'])
      self.assertEqual([a.userid for a in resolve_accounts(env={**env, 'LTA_PROFILES': 'default, wife'})], ['id1', 'id2'])
      self.assertEqual([a.userid for a in resolve_accounts(env={**env, 'LTA_PROFILES': 'all'})], ['id1', 'id2'])
      with self.assertRaisesRegex(ValueError, 'nope'):
        resolve_accounts(['nope'], env=env)
    finally:
      os.unlink(f.name)

  def test_dedupe(self):
    env = {'DHL_USERID': 'a', 'DHL_PASSWORD': 'pa', 'DHL_USERID_2': 'a', 'DHL_PASSWORD_2': 'pa'}
    self.assertEqual([a.userid for a in resolve_accounts(env=env)], ['a'])

  def test_empty_numbered_env_skipped(self):
    env = {'DHL_USERID': 'a', 'DHL_PASSWORD': 'pa', 'DHL_USERID_2': '', 'DHL_PASSWORD_2': ''}
    self.assertEqual([a.userid for a in resolve_accounts(env=env)], ['a'])

  def test_repr_hides_password(self):
    self.assertNotIn('secret', repr(load_env_accounts({'DHL_USERID': 'a', 'DHL_PASSWORD': 'secret'})[0]))


if __name__ == '__main__':
  unittest.main()
