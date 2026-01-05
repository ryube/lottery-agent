from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from random import randint
from os import getenv
import traceback
import time
import re

class DhLottery:
  driver: WebDriver
  dryrun: bool

  def __init__(self, driver: WebDriver):
    self.driver = driver
    self.dryrun = getenv('LTA_DRYRUN') == '1'

  def login(self, userid: str, password: str):
    # 로그인 화면
    self.driver.get('https://dhlottery.co.kr/login')

    # 아이디 입력
    userid_field = WebDriverWait(self.driver, 10).until(
      EC.presence_of_element_located((By.ID, 'inpUserId'))
    )
    userid_field.clear()
    userid_field.send_keys(userid)

    # 비밀번호 입력
    password_field = self.driver.find_element(By.ID, 'inpUserPswdEncn')
    password_field.clear()
    password_field.send_keys(password)

    # 로그인 버튼 클릭
    login_button = self.driver.find_element(By.ID, 'btnLogin')
    login_button.click()

    # 로그인 성공하면 메인 화면으로 이동됨
    # URL이 변경되거나 메인 페이지로 이동하는지 확인
    try:
      WebDriverWait(self.driver, 10).until(
        lambda driver: driver.current_url != 'https://dhlottery.co.kr/login'
      )
      
      # 로그인 실패 시 에러 메시지 확인
      try:
        error_msg = self.driver.find_element(By.CLASS_NAME, 'error-message')
        if error_msg.is_displayed():
          raise Exception(f'로그인 실패: {error_msg.text}')
      except:
        pass  # 에러 메시지가 없으면 로그인 성공으로 간주
      
      # 로그인 후 페이지 로딩 대기
      time.sleep(2)
    except Exception as e:
      # 로그인 실패 가능성 확인
      if 'login' in self.driver.current_url.lower():
        raise Exception(f'로그인 실패: 로그인 페이지에 머물러 있습니다. {e}')
      raise

  def getBalance(self) -> str:
    try:
      # 마이페이지로 이동해서 확인
      self.driver.get('https://dhlottery.co.kr/mypage/home')
      time.sleep(3)
      
      # 잔액 ID로 직접 찾기
      try:
        balance_element = WebDriverWait(self.driver, 10).until(
          EC.presence_of_element_located((By.ID, 'totalAmt'))
        )
        balance_text = balance_element.text.strip()
        # 숫자와 원이 포함된 텍스트 추출
        match = re.search(r'[\d,]+원', balance_text)
        if match:
          return match.group()
        # 원이 없으면 원 추가
        if balance_text and balance_text.replace(',', '').replace('원', '').isdigit():
          if '원' not in balance_text:
            return f'{balance_text}원'
          return balance_text
      except:
        pass
      
      # 대체 방법: 다양한 선택자 시도
      selectors = [
        (By.ID, 'totalAmt'),
        (By.XPATH, '//*[@id="totalAmt"]'),
        (By.CSS_SELECTOR, '#totalAmt'),
        (By.XPATH, '//*[contains(@id, "totalAmt")]'),
        (By.XPATH, '//*[contains(text(), "예치금")]'),
        (By.XPATH, '//*[contains(text(), "잔액")]'),
      ]
      
      for by, selector in selectors:
        try:
          element = self.driver.find_element(by, selector)
          text = element.text.strip()
          match = re.search(r'[\d,]+원', text)
          if match:
            return match.group()
          if text and text.replace(',', '').replace('원', '').isdigit():
            if '원' not in text:
              return f'{text}원'
            return text
        except:
          continue
      
      return '잔고 확인 실패 (페이지 구조 확인 필요)'
    except Exception as e:
      return f'잔고 확인 실패: {e}'

  def _get_popup_layer_message(self):
    try:
      layer_message = self.driver.find_element(By.XPATH, '//div[@id="popupLayerAlert"]/div/div/span[@class="layer-message"]')
      WebDriverWait(self.driver, 10).until(EC.visibility_of(layer_message))
      return layer_message.text
    except Exception as e:
      print('팝업 내용 못읽음:', e)
      traceback.print_exc()
      return ''

  def _check_purchase_limit_popup(self):
    """구매한도 팝업 확인"""
    try:
      # 구매한도 팝업 확인
      limit_popup = self.driver.find_element(By.ID, 'recommend720Plus')
      if limit_popup.is_displayed():
        try:
          # 팝업 내용 읽기
          cont1 = limit_popup.find_element(By.XPATH, './/p[@class="cont1"]')
          message = cont1.text.strip()
          print(f'[구매한도] 구매한도 팝업 발견: {message[:100]}...')
          return message
        except:
          return '구매한도에 도달했습니다.'
    except:
      pass
    return None

  # 로또 6/45
  def buyLo40(self, count: int, dryrun: bool) -> str:
    try:
      self.driver.get('https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40')

      iframe = self.driver.find_element(By.TAG_NAME, 'iframe')
      self.driver.switch_to.frame(iframe)

      # 자동 번호 선택
      try:
        self.driver.execute_script('selectWayTab(1)')
      except:
        # 로또는 판매시간이 아니면 팝업이 뜬다.
        message = self._get_popup_layer_message()
        if message:
          raise Exception(message)
        raise

      # 수량 선택
      count_dropdown = Select(self.driver.find_element(By.ID, 'amoundApply'))
      count_dropdown.select_by_value(str(count))

      # 수량 확인 버튼
      select_num_button = self.driver.find_element(By.ID, 'btnSelectNum')
      select_num_button.click()
      time.sleep(1)

      if not dryrun:
        # 구매 버튼 누름
        buy_button = self.driver.find_element(By.NAME, 'btnBuy')
        buy_button.click()
        time.sleep(1)

        # 구매한도 팝업 확인 (구매 버튼 클릭 후)
        limit_message = self._check_purchase_limit_popup()
        if limit_message:
          # 팝업 닫기
          try:
            close_button = self.driver.find_element(By.XPATH, '//div[@id="recommend720Plus"]//a[contains(@href, "closeRecomd720Popup")]')
            close_button.click()
            time.sleep(1)
          except:
            pass
          raise Exception(f'구매한도 초과: {limit_message}')

        # 구매 확인 누름
        self.driver.execute_script('closepopupLayerConfirm(true)')
        time.sleep(1)

        # 구매한도 팝업 다시 확인 (구매 확인 후)
        limit_message = self._check_purchase_limit_popup()
        if limit_message:
          # 팝업 닫기
          try:
            close_button = self.driver.find_element(By.XPATH, '//div[@id="recommend720Plus"]//a[contains(@href, "closeRecomd720Popup")]')
            close_button.click()
            time.sleep(1)
          except:
            pass
          raise Exception(f'구매한도 초과: {limit_message}')

        # 구매 결과 확인
        report_row = self.driver.find_element(By.ID, 'reportRow')
        WebDriverWait(self.driver, 10)\
          .until(lambda driver: len(report_row.find_elements(By.XPATH, './li')) > 0)

        report_count = len(report_row.find_elements(By.XPATH, './li'))
        if count != report_count:
          raise Exception(f'로또 구매 실패 {count - report_count}건 있음')

      return f'로또 구매완료: {count}매'
    except Exception as e:
      print('로또 구매실패:', e)
      traceback.print_exc()
      return f'로또 구매실패: {e}'

  # 연금복권 720+
  def buyLp72(self, count: int, dryrun: bool) -> str:
    try:
      self.driver.get('https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LP72')

      iframe = self.driver.find_element(By.TAG_NAME, 'iframe')
      self.driver.switch_to.frame(iframe)

      if count == 5:
        # # 같은조 5매 선택
        # jo_button = self.driver.find_element(By.XPATH, f'//span[@class="notranslate lotto720_box jogroup all"]')
        # jo_button.click()

        # 자동 번호 선택
        auto_button = self.driver.find_element(By.CLASS_NAME, 'lotto720_btn_auto_number')
        auto_button.click()

        # 구매 등록
        confirm_button = self.driver.find_element(By.CLASS_NAME, 'lotto720_btn_confirm_number')
        confirm_button.click()
      else:
        for i in range(count):
          # 랜덤으로 조 선택
          jo = randint(1, 5)
          jo_button = self.driver.find_element(By.XPATH, f'//span[@class="notranslate lotto720_box jogroup num{jo}"]')
          jo_button.click()

          # 자동 번호 선택
          auto_button = self.driver.find_element(By.CLASS_NAME, 'lotto720_btn_auto_number')
          auto_button.click()

          # 구매 등록
          confirm_button = self.driver.find_element(By.CLASS_NAME, 'lotto720_btn_confirm_number')
          confirm_button.click()

      # 구매 버튼
      buy1_button = self.driver.find_element(By.CLASS_NAME, 'lotto720_btn_pay')
      buy1_button.click()

      Alert(self.driver).accept()

      if not dryrun:
        # 구매 버튼이 하나 더 있음
        buy2_button = self.driver.find_element(By.XPATH, '//div[@id="lotto720_popup_confirm"]/div/div[@class="lotto720_popup_bottom_wrapper btn_area"]/a')
        WebDriverWait(self.driver, 10).until(EC.visibility_of(buy2_button))
        buy2_button.click()

        # 구매 결과

        sale_span = self.driver.find_element(By.CLASS_NAME, 'saleCnt')
        WebDriverWait(self.driver, 10).until(EC.visibility_of(sale_span))
        sale_count = int(sale_span.text)
        if sale_count != count:
          raise Exception(f'연금복권 구매 실패 {count - sale_count}건 있음')

      return f'연금복권 구매완료: {count}매'
    except Exception as e:
      print('연금복권 구매실패:', e)
      traceback.print_exc()
      return f'연금복권 구매실패: {e}'

  def _code_to_name(self, code: str):
    dict = {
      'LO40': '로또 6/45',
      'LP72': '연금복권 720+'
    }
    return dict.get(code, code)

  def check(self, code: str):
    try:
      print(f'[당첨 확인] {self._code_to_name(code)} 확인 시작...')
      
      # 구매/당첨 내역 페이지로 이동
      print('[당첨 확인] 구매/당첨 내역 페이지로 이동 중...')
      self.driver.get('https://dhlottery.co.kr/mypage/mylotteryledger')
      time.sleep(3)
      print(f'[당첨 확인] 현재 URL: {self.driver.current_url}')
      
      # 페이지가 로드되었는지 확인 (404가 아닌지)
      if 'error' in self.driver.current_url.lower() or '404' in self.driver.page_source[:1000]:
        print('[당첨 확인] ❌ 페이지 로드 실패 (404 또는 에러)')
        return f'당첨 확인 실패: 구매/당첨 내역 페이지를 찾을 수 없습니다. 페이지 구조가 변경되었을 수 있습니다.'
      
      # 1. 최근 1주일 버튼 클릭
      print('[당첨 확인] 최근 1주일 버튼 클릭 시도...')
      week_button_clicked = False
      try:
        week_button = WebDriverWait(self.driver, 10).until(
          EC.element_to_be_clickable((By.XPATH, '//button[contains(@onclick, "fn_chgDt") and contains(@onclick, "\'2\'")]'))
        )
        week_button.click()
        time.sleep(1)
        week_button_clicked = True
        print('[당첨 확인] ✅ 최근 1주일 버튼 클릭 성공')
      except:
        # 다른 방법으로 시도
        try:
          week_button = self.driver.find_element(By.XPATH, '//button[contains(text(), "최근 1주일")]')
          week_button.click()
          time.sleep(1)
          week_button_clicked = True
          print('[당첨 확인] ✅ 최근 1주일 버튼 클릭 성공 (대체 방법)')
        except:
          print('[당첨 확인] ⚠️ 최근 1주일 버튼을 찾을 수 없음 (계속 진행)')
      
      # 2. 검색 버튼 클릭
      print('[당첨 확인] 검색 버튼 클릭 시도...')
      try:
        search_button = WebDriverWait(self.driver, 10).until(
          EC.element_to_be_clickable((By.ID, 'btnSrch'))
        )
        search_button.click()
        time.sleep(3)  # 테이블 로딩 대기
        print('[당첨 확인] ✅ 검색 버튼 클릭 성공, 테이블 로딩 대기 중...')
      except:
        try:
          search_button = self.driver.find_element(By.XPATH, '//button[@id="btnSrch"]')
          search_button.click()
          time.sleep(3)
          print('[당첨 확인] ✅ 검색 버튼 클릭 성공 (대체 방법)')
        except:
          print('[당첨 확인] ❌ 검색 버튼을 찾을 수 없음')
          return f'당첨 확인 실패: 검색 버튼을 찾을 수 없습니다.'
      
      # 3. 결과 테이블 확인
      print('[당첨 확인] 결과 테이블 확인 중...')
      try:
        winning_list = WebDriverWait(self.driver, 10).until(
          EC.presence_of_element_located((By.ID, 'winning-history-list'))
        )
        print('[당첨 확인] ✅ 결과 테이블 찾음')
      except:
        print('[당첨 확인] ❌ 결과 테이블을 찾을 수 없음')
        return f'{self._code_to_name(code)} 당첨 없음 (결과 테이블을 찾을 수 없습니다)'
      
      # 당첨 결과가 있는지 확인
      print('[당첨 확인] 테이블 행 수 확인 중...')
      try:
        rows = winning_list.find_elements(By.XPATH, './/li[contains(@class, "whl-row")]')
        print(f'[당첨 확인] 총 {len(rows)}개의 행을 찾음')
        if len(rows) == 0:
          print('[당첨 확인] ⚠️ 행이 없음')
          return f'{self._code_to_name(code)} 당첨 없음'
      except Exception as e:
        print(f'[당첨 확인] ❌ 행 찾기 실패: {e}')
        return f'{self._code_to_name(code)} 당첨 없음'
      
      # 복권명 매핑
      lottery_name_map = {
        'LO40': '로또645',
        'LP72': '연금복권720+'
      }
      target_lottery_name = lottery_name_map.get(code, '')
      print(f'[당첨 확인] 대상 복권명: {target_lottery_name}')
      
      # 당첨된 항목만 필터링 (당첨금이 "-"가 아니고 "0 원"이 아닌 것)
      print('[당첨 확인] 당첨 항목 필터링 중...')
      winning_items = []
      checked_count = 0
      matched_count = 0
      
      for row in rows:
        try:
          checked_count += 1
          # 복권명 확인 (먼저 복권명으로 필터링)
          name_elem = row.find_element(By.XPATH, './/div[contains(@class, "col-name")]//span[contains(@class, "whl-txt")]')
          lottery_name = name_elem.text.strip()
          
          # 코드에 맞는 복권만 처리
          if lottery_name != target_lottery_name:
            continue
          
          matched_count += 1
          
          # 당첨금 확인
          prize_elem = row.find_element(By.XPATH, './/div[contains(@class, "col-am")]//span[contains(@class, "whl-txt")]')
          prize_text = prize_elem.text.strip()
          
          # 당첨결과 확인
          result_elem = row.find_element(By.XPATH, './/div[contains(@class, "col-result")]//span[contains(@class, "whl-txt")]')
          result_text = result_elem.text.strip()
          
          print(f'[당첨 확인] 행 {checked_count}: {lottery_name}, 당첨금={prize_text}, 결과={result_text}')
          
          # 당첨금이 "-"가 아니고 "0 원"이 아니며, 당첨결과가 "미추첨"이 아닌 경우
          if prize_text != '-' and prize_text != '0 원' and result_text != '미추첨':
            # 구입일자
            date_elem = row.find_element(By.XPATH, './/div[contains(@class, "col-date1")]//span[contains(@class, "whl-txt")]')
            buy_date = date_elem.text.strip()
            
            # 회차
            try:
              round_elem = row.find_element(By.XPATH, './/div[contains(@class, "col-th")]//span[contains(@class, "whl-txt")]')
              round_num = round_elem.text.strip()
            except:
              round_num = ''
            
            winning_items.append(f'{buy_date} {lottery_name} {round_num}회 {prize_text} ({result_text})')
            print(f'[당첨 확인] ✅ 당첨 항목 추가: {buy_date} {lottery_name} {round_num}회 {prize_text}')
        except Exception as e:
          print(f'[당첨 확인] ⚠️ 행 {checked_count} 처리 중 오류: {e}')
          continue
      
      print(f'[당첨 확인] 총 {checked_count}개 행 확인, {matched_count}개 {target_lottery_name} 매칭, {len(winning_items)}개 당첨')
      
      if len(winning_items) == 0:
        print(f'[당첨 확인] ⚠️ 당첨 항목 없음')
        return f'{self._code_to_name(code)} 당첨 없음'
      
      bar = '---------------------------------------'
      messages = ['당첨된 게 있다!!!', bar]
      messages.extend(winning_items)
      messages.append(bar)
      
      print(f'[당첨 확인] ✅ {len(winning_items)}개 당첨 항목 발견!')
      return '\n'.join(messages)

    except Exception as e:
      print(f'[당첨 확인] ❌ 오류 발생: {e}')
      traceback.print_exc()
      return f'당첨 확인 실패: {e}'
