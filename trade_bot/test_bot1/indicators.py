import pandas as pd
import numpy as np

def calculate_macd(df, fast=12, slow=26, signal=9):
    """MACD 계산"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist

def calculate_bollinger_bands(df, window=20, num_std=2):
    """볼린저 밴드 계산"""
    rolling_mean = df['close'].rolling(window=window).mean()
    rolling_std = df['close'].rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return upper_band, rolling_mean, lower_band
    # 20개가 들어오지 않았을 경우 NaN이 나올 수도 있음

def calculate_rsi(df, periods=14):
    """RSI 계산"""
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=periods-1, adjust=False).mean()
    ema_down = down.ewm(com=periods-1, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-10)
    return 100 - (100 / (1 + rs))

def get_prepared_df(df):
    """
    모든 봇이 공통으로 사용할 지표를 한 번에 계산
    """
    # 1. RSI 추가
    df['rsi'] = calculate_rsi(df)
    
    # 2. 이동평균선 (역배열 필터용)
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    
    # 3. 가격 변화율 (급락 필터용)
    df['change'] = df['close'].pct_change()
    
    # 4. 돌파 매매 기준선 (최근 20봉 고가)
    df['resistance'] = df['high'].rolling(window=20).max().shift(1)
    
    # 5. 거래량 평균 (거래량 폭발 확인용)
    df['vol_sma'] = df['volume'].rolling(window=20).mean().shift(1)

    # 6. MACD 추가
    df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(df)

    # 7. 볼린저 밴드 추가
    df['bb_upper'], df['bb_mid'], df['bb_lower'] = calculate_bollinger_bands(df)
    
    # 8. 볼린저 밴드 폭 (Bandwidth) - 변동성이 응축됐는지 확인용
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
    
    return df

def is_safe_zone(df):
    """
    매수 전 철벽 방어 필터 (Global Filter)
    리턴: (True/False, "이유")
    """
    curr = df.iloc[-1]
    
    # A. 역배열 필터: 5 < 20 < 60 순서로 정렬된 하락 추세인가?
    if curr['ma5'] < curr['ma20'] < curr['ma60']:
        return False, "역배열 하락 추세 구간"
    
    # B. 급락 필터: 최근 3개 봉 이내에 -2% 이상의 급락이 있었는가?
    recent_drops = df['change'].tail(3)
    if (recent_drops <= -0.02).any():
        return False, "최근 급락 발생 구간"
        
    return True, "안전 구역"