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
    self.driver.get('https://dhlottery.co.kr')
    time.sleep(2)
    
    # 잔고 정보를 찾는 여러 방법 시도
    try:
      # 방법 1: 기존 방식
      money = WebDriverWait(self.driver, 5).until(
        EC.presence_of_element_located((By.XPATH, '//li[@class="money"]/a/strong'))
      )
      balance_text = money.text.strip()
      # "원"으로 끝나는 텍스트만 반환 (잔고 형식)
      if '원' in balance_text and len(balance_text) < 50:
        return balance_text
    except:
      pass
    
    try:
      # 방법 2: 다른 선택자 시도
      money = self.driver.find_element(By.XPATH, '//*[contains(@class, "money")]//strong')
      balance_text = money.text.strip()
      if '원' in balance_text and len(balance_text) < 50:
        return balance_text
    except:
      pass
    
    try:
      # 방법 3: 마이페이지로 이동해서 확인
      self.driver.get('https://dhlottery.co.kr/mypage/home')
      time.sleep(3)
      
      # 예치금 또는 잔고 정보 찾기
      try:
        # 예치금 정보 찾기
        balance_elements = self.driver.find_elements(By.XPATH, '//*[contains(text(), "원") and (contains(text(), "예치금") or contains(text(), "잔액") or contains(text(), "잔고"))]')
        for elem in balance_elements:
          text = elem.text.strip()
          if '원' in text and ('예치금' in text or '잔액' in text or '잔고' in text):
            # 숫자와 원만 추출
            match = re.search(r'[\d,]+원', text)
            if match:
              return match.group()
      except:
        pass
      
      # 일반적인 잔고 표시 찾기
      try:
        money = self.driver.find_element(By.XPATH, '//*[contains(@class, "balance") or contains(@class, "money")]//*[contains(text(), "원")]')
        balance_text = money.text.strip()
        if '원' in balance_text:
          match = re.search(r'[\d,]+원', balance_text)
          if match:
            return match.group()
      except:
        pass
      
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

      if not dryrun:
        # 구매 버튼 누름
        buy_button = self.driver.find_element(By.NAME, 'btnBuy')
        buy_button.click()

        # 구매 확인 누름
        self.driver.execute_script('closepopupLayerConfirm(true)')

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
      # 구매/당첨 내역 페이지로 이동
      self.driver.get('https://dhlottery.co.kr/mypage/mylotteryledger')
      time.sleep(3)
      
      # 페이지가 로드되었는지 확인 (404가 아닌지)
      if 'error' in self.driver.current_url.lower() or '404' in self.driver.page_source[:1000]:
        return f'당첨 확인 실패: 구매/당첨 내역 페이지를 찾을 수 없습니다. 페이지 구조가 변경되었을 수 있습니다.'
      
      # 복권 선택 드롭다운 찾기
      try:
        lottoid_dropdown = WebDriverWait(self.driver, 10).until(
          EC.presence_of_element_located((By.ID, 'lottoId'))
        )
        lottoid_dropdown = Select(lottoid_dropdown)
      except:
        try:
          lottoid_dropdown = Select(self.driver.find_element(By.NAME, 'lottoId'))
        except:
          return f'당첨 확인 실패: 복권 선택 드롭다운을 찾을 수 없습니다.'
      
      lottoid_dropdown.select_by_value(code)

      # 당첨여부 선택
      try:
        wingrade_dropdown = Select(self.driver.find_element(By.ID, 'winGrade'))
      except:
        wingrade_dropdown = Select(self.driver.find_element(By.NAME, 'winGrade'))
      
      wingrade_dropdown.select_by_value('1') # 당첨내역

      # 기간은 1주일 선택
      try:
        self.driver.execute_script('changeTerm(7, "1주일")')
      except:
        # 스크립트가 없으면 직접 선택 시도
        pass

      # 조회
      try:
        search_button = self.driver.find_element(By.ID, 'submit_btn')
      except:
        search_button = self.driver.find_element(By.XPATH, '//button[contains(text(), "조회")]')
      
      search_button.click()
      time.sleep(2)

      # 조회 결과는 iframe 안에 있다.
      try:
        iframe = WebDriverWait(self.driver, 10).until(
          EC.presence_of_element_located((By.ID, 'lottoBuyList'))
        )
        self.driver.switch_to.frame(iframe)
      except:
        # iframe이 없으면 현재 페이지에서 찾기
        pass

      try:
        page_box = WebDriverWait(self.driver, 10).until(
          EC.presence_of_element_located((By.ID, 'page_box'))
        )
        pages = page_box.find_elements(By.TAG_NAME, 'a')
        if len(pages) == 0:
          return f'{self._code_to_name(code)} 당첨 없음'
      except:
        # 페이지 박스가 없으면 테이블에서 직접 확인
        try:
          trs = self.driver.find_elements(By.XPATH, '//table/tbody/tr')
          if len(trs) == 0:
            return f'{self._code_to_name(code)} 당첨 없음'
        except:
          return f'{self._code_to_name(code)} 당첨 없음'

      bar = '---------------------------------------'
      messages = ['당첨된 게 있다!!!', bar]
      
      try:
        for page in pages:
          page.click()
          time.sleep(1)
          trs = self.driver.find_elements(By.XPATH, '//table/tbody/tr')
          for tr in trs:
            buy_date = tr.find_element(By.XPATH, 'td[1]').text
            lottery_name = tr.find_element(By.XPATH, 'td[2]').text
            money = tr.find_element(By.XPATH, 'td[7]').text
            messages.append(f'{buy_date} {lottery_name} {money}')
      except:
        # 페이지네이션 없이 직접 테이블 읽기
        trs = self.driver.find_elements(By.XPATH, '//table/tbody/tr')
        for tr in trs:
          buy_date = tr.find_element(By.XPATH, 'td[1]').text
          lottery_name = tr.find_element(By.XPATH, 'td[2]').text
          money = tr.find_element(By.XPATH, 'td[7]').text
          messages.append(f'{buy_date} {lottery_name} {money}')
      
      messages.append(bar)
      return '\n'.join(messages)

    except Exception as e:
      print('당첨 확인 실패:', e)
      traceback.print_exc()
      return f'당첨 확인 실패: {e}'
