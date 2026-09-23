"""
다중 계정 로딩

1. 프로필 파일 (dhlottery-api 호환, toml)
   기본 경로 ~/.dhapi/credentials (DHL_CREDENTIALS 로 변경 가능)

     [default]
     username = "id1"
     password = "pw1"
     [wife]
     username = "id2"
     password = "pw2"

   --profile NAME (여러 번 지정 가능) 또는 --all-profiles 로 선택한다.
   LTA_PROFILES=default,wife 로도 지정 가능 ('all' 이면 전체).

2. 환경변수 (프로필을 지정하지 않았을 때)
     DHL_USERID / DHL_PASSWORD         첫 번째 계정
     DHL_USERID_2 / DHL_PASSWORD_2     두 번째 계정
     DHL_USERID_3 / DHL_PASSWORD_3     ...
"""
import os
import re
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

DEFAULT_CREDENTIALS_PATH = '~/.dhapi/credentials'


@dataclass
class Account:
  name: str
  userid: str
  password: str = field(default='', repr=False)  # 비밀번호가 로그에 찍히지 않도록


def credentials_path(env: Mapping[str, str] = os.environ) -> str:
  return os.path.expanduser(env.get('DHL_CREDENTIALS') or DEFAULT_CREDENTIALS_PATH)


def load_profiles(path: str) -> Dict[str, Account]:
  if not os.path.exists(path):
    raise FileNotFoundError(f'프로필 파일을 찾을 수 없습니다: {path}')
  with open(path, 'rb') as f:
    config = tomllib.load(f)

  profiles = {}
  for name, value in config.items():
    if not isinstance(value, dict) or not value.get('username') or not value.get('password'):
      print(f'⚠️ 프로필 [{name}] 에 username/password 가 없어 건너뜁니다.')
      continue
    profiles[name] = Account(name=name, userid=str(value['username']), password=str(value['password']))
  return profiles


def dedupe(accounts: List[Account]) -> List[Account]:
  """같은 아이디가 두 번 들어가서 중복 구매하지 않도록 제거"""
  result, seen = [], set()
  for a in accounts:
    if a.userid in seen:
      print(f'⚠️ 계정 {a.userid} 가 중복 지정되어 한 번만 실행합니다.')
      continue
    seen.add(a.userid)
    result.append(a)
  return result


def load_env_accounts(env: Mapping[str, str] = os.environ) -> List[Account]:
  accounts = []
  if env.get('DHL_USERID'):
    if not env.get('DHL_PASSWORD'):
      raise ValueError('DHL_PASSWORD 가 설정되지 않았습니다.')
    accounts.append(Account(name='1', userid=env['DHL_USERID'], password=env['DHL_PASSWORD']))

  suffixes = sorted(
    int(m.group(1)) for key in env
    if (m := re.fullmatch(r'DHL_USERID_(\d+)', key)) and env[key]
  )
  for n in suffixes:
    password = env.get(f'DHL_PASSWORD_{n}')
    if not password:
      raise ValueError(f'DHL_PASSWORD_{n} 가 설정되지 않았습니다.')
    accounts.append(Account(name=str(n), userid=env[f'DHL_USERID_{n}'], password=password))
  return accounts


def resolve_accounts(profiles: Optional[List[str]] = None, all_profiles: bool = False,
                     env: Mapping[str, str] = os.environ) -> List[Account]:
  if not profiles and not all_profiles and env.get('LTA_PROFILES'):
    names = [p.strip() for p in env['LTA_PROFILES'].split(',') if p.strip()]
    if names == ['all']:
      all_profiles = True
    else:
      profiles = names

  if profiles or all_profiles:
    available = load_profiles(credentials_path(env))
    if all_profiles:
      return dedupe(list(available.values()))
    missing = [p for p in profiles if p not in available]
    if missing:
      raise ValueError(f'프로필을 찾지 못했습니다: {", ".join(missing)} (등록된 프로필: {", ".join(available)})')
    return dedupe([available[p] for p in profiles])

  accounts = load_env_accounts(env)
  if not accounts:
    raise ValueError('계정이 없습니다. DHL_USERID/DHL_PASSWORD 환경변수나 --profile 옵션을 설정하세요.')
  return dedupe(accounts)
