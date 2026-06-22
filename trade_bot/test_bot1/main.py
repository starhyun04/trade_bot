import time
import logging
import traceback
from datetime import datetime

from logger import setup_logger
from config import Config
from telegram_bot import TelegramBot
from control_manager import ControlManager

def run_bot():
    # 1. 시스템 블랙박스(로거) 세팅 및 가동
    setup_logger()
    logging.info("========================================")
    logging.info("🚀 5분봉 퀀트 자동매매 봇 가동 준비 중...")
    
    try:
        # 2. 필수 환경변수(API 키, 토큰 등) 누락 검사
        Config.validate()
        logging.info("✅ 환경변수 및 키 검증 완료")
        
        # 3. 텔레그램 봇 및 사령관 초기화
        tele_bot = TelegramBot()
        manager = ControlManager(tele_bot=tele_bot)
        
        # 시작 알림 전송
        start_msg = f"🚀 5분봉 퀀트 자동매매 봇이 정상적으로 시작되었습니다.\n시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        tele_bot.send_message(start_msg)
        logging.info("✅ 시스템 초기화 완료. 메인 루프 진입.")
        
    except Exception as e:
        # 키본 세팅부터 꼬였다면 봇을 아예 켜지 않음
        logging.error(f"🚨 봇 초기화 실패: {e}")
        return 

    # 4. 무한 루프
    while True:
        try:
            now = datetime.now()
            
            # 5분 단위 정각 (예: 00분, 05분, 10분...)의 0~2초 사이에만 실행
            if now.minute % 5 == 0 and now.second <= 2:
                logging.info("========================================")
                logging.info(f"⏰ [{now.strftime('%H:%M:%S')}] 5분 주기 사이클 시작!")
                
                # 사령관에게 5분 주기 업무 지시
                manager.run_5min_cycle()
                
                # 중복 실행을 막기 위해 60초(1분) 동안 수면
                # (이 코드가 없으면 2초 동안 루프가 수백 번 돌아서 업비트 API가 차단됨)
                time.sleep(60)
            else:
                # 정각이 아닐 때는 1초마다 시간 체크
                time.sleep(1)
                
        except KeyboardInterrupt:
            # 사용자가 터미널에서 Ctrl+C를 눌러 봇을 강제로 끌 때의 처리
            stop_msg = "🛑 사용자에 의해 봇이 안전하게 종료되었습니다."
            logging.info(stop_msg)
            try:
                tele_bot.send_message(stop_msg)
            except:
                pass
            break # while 루프 탈출 및 프로그램 종료
            
        except Exception as e:
            # 메인 루프 안에서 발생하는 예상치 못한 치명적 에러 처리
            error_trace = traceback.format_exc() # 에러가 발생한 코드 위치를 정확히 추적
            error_msg = f"🚨 [치명적 오류 발생] 메인 루프가 중단되었습니다.\n{e}"
            
            logging.error(error_msg)
            logging.error(error_trace) # 터미널/로그 파일에 상세 에러 추적 기록
            tele_bot.send_message(error_msg)
            
            # 에러 발생 시 봇이 패닉에 빠져 알람을 무한정 보내지 않도록 1분 대기 후 재시도
            time.sleep(60)

if __name__ == "__main__":
    run_bot()