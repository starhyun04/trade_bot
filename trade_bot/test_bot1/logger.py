import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    """봇의 모든 활동을 터미널과 파일에 동시에 기록하는 로거 설정"""
    
    # data 폴더가 없으면 생성 (에러 방지)
    if not os.path.exists('data'):
        os.makedirs('data')

    # 최상위 로거 객체 가져오기
    logger = logging.getLogger()
    
    # 기록할 최소 레벨 설정 (INFO 이상만 기록, DEBUG는 무시)
    logger.setLevel(logging.INFO)

    # 로거가 여러 번 호출되어 로그가 중복 출력되는 것을 방지
    if not logger.handlers:
        
        # ----------------------------------------------------
        # 1. 파일 핸들러 (system.log 파일에 텍스트 저장)
        # ----------------------------------------------------
        # maxBytes=5*1024*1024 (5MB) -> 파일이 5MB가 넘어가면 
        # backupCount=1 -> 기존 파일을 system.log.1로 백업하고 새 파일을 만듦
        file_handler = RotatingFileHandler(
            'data/system.log', 
            maxBytes=5*1024*1024, 
            backupCount=1, 
            encoding='utf-8'
        )
        
        # ----------------------------------------------------
        # 2. 콘솔 핸들러 (터미널 검은 창에 실시간 출력)
        # ----------------------------------------------------
        console_handler = logging.StreamHandler()

        # ----------------------------------------------------
        # 3. 로그 포맷(형식) 지정
        # ----------------------------------------------------
        # 출력 예시: 2026-04-19 22:31:41,123 [INFO] 5분 주기 사이클 시작!
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 로거에 핸들러 부착
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger