#!/usr/bin/env python3
"""
모든 함수를 테스트하는 스크립트
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from dhlottery import DhLottery
from os import getenv
from dotenv import load_dotenv
import time
import traceback

load_dotenv(override=True)

def create_driver(headless=False):
  chrome_options = Options()
  if headless:
    chrome_options.add_argument('headless')
    chrome_options.add_argument('no-sandbox')
    chrome_options.add_argument('disable-dev-shm-usage')
    chrome_options.add_argument('window-size=1920x1080')
    chrome_options.add_argument('disable-gpu')
  chrome_options.add_experimental_option('excludeSwitches', ['disable-popup-blocking'])
  chrome_options.set_capability('unhandledPromptBehavior', 'accept')

  driver = webdriver.Chrome(options=chrome_options)
  driver.implicitly_wait(10)
  driver.execute_cdp_cmd(
    'Page.addScriptToEvaluateOnNewDocument',
    {'source': "Object.defineProperty(navigator, 'platform', {get: () => 'Win64'})"}
  )

  return driver

def test_login(dhlottery, userid, password):
  print('\n=== 1. login() 테스트 ===')
  try:
    dhlottery.login(userid, password)
    print('✅ login() 성공')
    return True
  except Exception as e:
    print(f'❌ login() 실패: {e}')
    traceback.print_exc()
    return False

def test_getBalance(dhlottery):
  print('\n=== 2. getBalance() 테스트 ===')
  try:
    balance = dhlottery.getBalance()
    print(f'잔고: {balance}')
    if balance and balance != '잔고 확인 실패':
      print('✅ getBalance() 성공')
      return True
    else:
      print('⚠️ getBalance() 잔고를 찾지 못함')
      return False
  except Exception as e:
    print(f'❌ getBalance() 실패: {e}')
    traceback.print_exc()
    return False

def test_buyLo40(dhlottery, dryrun=True):
  print('\n=== 3. buyLo40() 테스트 (dryrun) ===')
  try:
    result = dhlottery.buyLo40(1, dryrun)
    print(f'결과: {result}')
    if '구매완료' in result or '구매실패' in result:
      print('✅ buyLo40() 실행 완료')
      return True
    else:
      print('⚠️ buyLo40() 예상치 못한 결과')
      return False
  except Exception as e:
    print(f'❌ buyLo40() 실패: {e}')
    traceback.print_exc()
    return False

def test_buyLp72(dhlottery, dryrun=True):
  print('\n=== 4. buyLp72() 테스트 (dryrun) ===')
  try:
    result = dhlottery.buyLp72(1, dryrun)
    print(f'결과: {result}')
    if '구매완료' in result or '구매실패' in result:
      print('✅ buyLp72() 실행 완료')
      return True
    else:
      print('⚠️ buyLp72() 예상치 못한 결과')
      return False
  except Exception as e:
    print(f'❌ buyLp72() 실패: {e}')
    traceback.print_exc()
    return False

def test_check(dhlottery, code='LO40'):
  print(f'\n=== 5. check() 테스트 ({code}) ===')
  try:
    result = dhlottery.check(code)
    print(f'결과: {result[:200]}...' if len(result) > 200 else f'결과: {result}')
    if '당첨' in result or '실패' in result:
      print('✅ check() 실행 완료')
      return True
    else:
      print('⚠️ check() 예상치 못한 결과')
      return False
  except Exception as e:
    print(f'❌ check() 실패: {e}')
    traceback.print_exc()
    return False

def main():
  userid = getenv('DHL_USERID')
  password = getenv('DHL_PASSWORD')
  
  if not userid or not password:
    print('환경변수 DHL_USERID와 DHL_PASSWORD를 설정해주세요.')
    return
  
  print('=' * 50)
  print('모든 함수 테스트 시작')
  print('=' * 50)
  print(f'사용자 ID: {userid}')
  
  driver = None
  results = {}
  
  try:
    driver = create_driver(headless=False)
    dhlottery = DhLottery(driver)
    
    # 1. 로그인 테스트
    results['login'] = test_login(dhlottery, userid, password)
    if not results['login']:
      print('\n❌ 로그인 실패로 인해 다른 테스트를 건너뜁니다.')
      return
    
    time.sleep(2)
    
    # 2. 잔고 확인 테스트
    results['getBalance'] = test_getBalance(dhlottery)
    time.sleep(2)
    
    # 3. 로또 구매 테스트 (dryrun)
    results['buyLo40'] = test_buyLo40(dhlottery, dryrun=True)
    time.sleep(2)
    
    # 4. 연금복권 구매 테스트 (dryrun)
    results['buyLp72'] = test_buyLp72(dhlottery, dryrun=True)
    time.sleep(2)
    
    # 5. 당첨 확인 테스트
    results['check_LO40'] = test_check(dhlottery, 'LO40')
    time.sleep(2)
    
    results['check_LP72'] = test_check(dhlottery, 'LP72')
    
    # 결과 요약
    print('\n' + '=' * 50)
    print('테스트 결과 요약')
    print('=' * 50)
    for func_name, success in results.items():
      status = '✅ 성공' if success else '❌ 실패'
      print(f'{func_name}: {status}')
    
    print('\n브라우저를 10초간 열어둡니다...')
    time.sleep(10)
    
  except Exception as e:
    print(f'\n❌ 전체 테스트 중 오류 발생: {e}')
    traceback.print_exc()
    
    if driver:
      print('\n스크린샷을 저장합니다...')
      try:
        driver.save_screenshot('error_screenshot.png')
        print('error_screenshot.png 파일을 확인하세요.')
      except:
        pass
      
      print('\n브라우저를 30초간 열어둡니다...')
      time.sleep(30)
  finally:
    if driver:
      driver.quit()

if __name__ == '__main__':
  main()

