import requests
import pandas as pd
import time

def get_upbit_ohlcv(ticker="KRW-BTC", interval=5, count=1000):
    url = f"https://api.upbit.com/v1/candles/minutes/{interval}"
    to = None
    all_candles = []
    
    # 1000개를 가져오기 위해 호출 (최대 200개씩 끊어서) -> 업비트에서 호출되는 수가 제한되어있어 200개씩 불러오는거임 
    # 데이터가 현재 1000개를 불러왔으나 밑에 보조지표 계산때문에 앞에 60개 날라가고 941개씩 모든 배열에 저장되어있음
    # 데이터를 이어 붙인다고 하면 하루씩 나눠서 해야할듯 
    for _ in range(count // 200):
        params = {"market": ticker, "count": 200}
        if to: params["to"] = to
        
        response = requests.get(url, params=params)
        data = response.json()
        all_candles.extend(data)
        to = data[-1]['candle_date_time_utc'] + "Z"
        time.sleep(0.1)

    df = pd.DataFrame(all_candles)
    df = df[['candle_date_time_kst', 'opening_price', 'high_price', 'low_price', 'trade_price']]
    df.columns = ['time', 'open', 'high', 'low', 'close']
    df = df.sort_values(by='time').reset_index(drop=True)
    
    # 시간 분리
    df['time'] = pd.to_datetime(df['time'])
    df['day'], df['hour'], df['min'] = df['time'].dt.day, df['time'].dt.hour, df['time'].dt.minute

    # --- 보조지표 직접 계산 (Pandas 사용) ---
    
    # 1. 이동평균선 (MA)
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    
    # 2. RSI (상대강도지수)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 3. MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2

    # 데이터 정리 (NaN 제거) 지표계산 때문에 없는 값들이 있음
    df = df.dropna().reset_index(drop=True)
    return df

# 데이터 가져오기
df = get_upbit_ohlcv()

# --- 개별 배열로 담기 --- 
day = df['day'].tolist()
hour = df['hour'].tolist()
minute = df['min'].tolist()
open_p = df['open'].tolist()
high_p = df['high'].tolist()
low_p = df['low'].tolist()
close_p = df['close'].tolist()
ma5 = df['ma5'].tolist()
ma20 = df['ma20'].tolist()
ma60 = df['ma60'].tolist()
rsi = df['rsi'].tolist()
macd = df['macd'].tolist()
