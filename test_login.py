#!/usr/bin/env python3
"""
로컬에서 로그인 테스트를 위한 스크립트
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from dhlottery import DhLottery
from os import getenv
from dotenv import load_dotenv
import time

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

def main():
  userid = getenv('DHL_USERID')
  password = getenv('DHL_PASSWORD')
  
  if not userid or not password:
    print('환경변수 DHL_USERID와 DHL_PASSWORD를 설정해주세요.')
    return
  
  print('로그인 테스트를 시작합니다...')
  print(f'사용자 ID: {userid}')
  
  driver = None
  try:
    # headless=False로 설정하여 브라우저를 볼 수 있게 함
    driver = create_driver(headless=False)
    dhlottery = DhLottery(driver)
    
    print('로그인 시도 중...')
    dhlottery.login(userid, password)
    print('✅ 로그인 성공!')
    
    print('잔고 확인 중...')
    balance = dhlottery.getBalance()
    print(f'현재 잔고: {balance}')
    
    print('\n테스트 완료. 브라우저를 10초간 열어둡니다...')
    time.sleep(10)
    
  except Exception as e:
    print(f'❌ 오류 발생: {e}')
    import traceback
    traceback.print_exc()
    
    if driver:
      print('\n스크린샷을 저장합니다...')
      driver.save_screenshot('error_screenshot.png')
      print('error_screenshot.png 파일을 확인하세요.')
      
      print('\n브라우저를 30초간 열어둡니다...')
      time.sleep(30)
  finally:
    if driver:
      driver.quit()

if __name__ == '__main__':
  main()

