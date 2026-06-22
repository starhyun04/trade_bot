# MyQuantBot/config.py

import os
from dotenv import load_dotenv

# .env 파일에 있는 비밀 정보들을 불러와서 메모리에 올림
load_dotenv()

class Config:
    # ----------------------------------------------------
    # 🔐 1. 보안/API 설정 (금고에서 꺼내오기)
    # ----------------------------------------------------
    UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
    UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")
    
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # ----------------------------------------------------
    # 📊 2. 트레이딩 기본 설정 (여기서 봇의 성향을 튜닝)
    # ----------------------------------------------------
    SYMBOL = "KRW-BTC"       # 거래할 코인 종목
    INTERVAL = "minute5"     # 캔들 주기 (5분봉)
    MAX_SLOTS = 3            # 최대 분할 매수 슬롯 개수
    
    # ----------------------------------------------------
    # ⚔️ 3. 전략 파라미터 (공격수 & 수비수 세팅)
    # ----------------------------------------------------
    BUY_THRESHOLD = 80       # 매수 진입 커트라인 점수
    TARGET_PROFIT_PCT = 3.0  # 기본 익절 목표 (3%)
    STOP_LOSS_PCT = 2.0      # 기본 손절 방어선 (2%)
    ORDER_AMOUNT = 10000     # 1슬롯당 매수 금액 (원)
    
    @classmethod
    def validate(cls):
        """봇을 켜기 전에 필수 키들이 잘 세팅되었는지 검사하는 안전장치"""
        missing_keys = []
        if not cls.UPBIT_ACCESS_KEY: missing_keys.append("UPBIT_ACCESS_KEY")
        if not cls.UPBIT_SECRET_KEY: missing_keys.append("UPBIT_SECRET_KEY")
        if not cls.TELEGRAM_TOKEN: missing_keys.append("TELEGRAM_TOKEN")
        if not cls.TELEGRAM_CHAT_ID: missing_keys.append("TELEGRAM_CHAT_ID")
        
        if missing_keys:
            raise ValueError(f"🚨 환경 변수 누락! .env 파일을 확인하세요: {', '.join(missing_keys)}")