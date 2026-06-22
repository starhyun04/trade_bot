import requests
import logging
from config import Config

class TelegramBot:
    def __init__(self):
        # config.py를 통해 안전한 금고(.env)에서 키를 꺼내옴
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text):
        """
        내 텔레그램으로 텍스트 메시지를 전송하는 함수
        """
        # 토큰이나 채팅방 ID가 설정되지 않았다면 전송 시도조차 하지 않음
        if not self.token or not self.chat_id:
            logging.warning("⚠️ 텔레그램 토큰/채팅방 ID가 없어 알림을 보낼 수 없습니다.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown" # 굵은 글씨(**) 같은 마크다운 문법 지원
        }
        
        try:
            # timeout=10: 텔레그램 서버가 터져서 응답이 없을 때, 
            # 우리 봇이 무한정 기다리며 멈추는 것을 방지 (10초만 기다림)
            response = requests.post(url, json=payload, timeout=10)
            
            # 전송 성공 여부 확인
            if response.status_code == 200:
                return True
            else:
                logging.error(f"⚠️ 텔레그램 알림 전송 실패: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logging.error("⚠️ 텔레그램 서버 응답 지연 (Timeout)")
            return False
        except requests.exceptions.ConnectionError:
            logging.error("⚠️ 인터넷 연결 불안정으로 텔레그램 알림 전송 실패")
            return False
        except Exception as e:
            logging.error(f"⚠️ 텔레그램 전송 중 알 수 없는 에러 발생: {e}")
            return False

# ----------------------------------------------------
# 🧪 파일 단독 테스트 모드
# ----------------------------------------------------
# 메인 봇을 켜기 전에, 이 파일만 단독으로 실행해서 
# 내 폰으로 메시지가 잘 오는지 테스트해 볼 수 있는 코드
if __name__ == "__main__":
    from logger import setup_logger
    setup_logger() # 터미널 출력을 위해 로거 임시 세팅
    
    bot = TelegramBot()
    print("텔레그램 전송 테스트를 시작합니다...")
    
    # 테스트 전송
    success = bot.send_message("✅ **테스트 메시지**\n퀀트 봇의 텔레그램 알림 시스템이 정상적으로 연결되었습니다!")
    
    if success:
        print("전송 성공! 폰을 확인해보세요.")
    else:
        print("전송 실패. .env 파일의 토큰과 ID를 다시 확인해주세요.")