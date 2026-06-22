    import requests
    import pandas as pd
    import numpy as np
    import time
    from datetime import datetime

    # 1. 업비트 데이터 수집 ( 10만 개 + 변수 33개 ) 
    def fetch_massive_upbit_data(market="KRW-BTC", count=100000):
        url = "https://api.upbit.com/v1/candles/minutes/5"
        all_candles = []
        to = None
        
        iterations = count // 200
        print(f"[{market}] 데이터 수집 시작 (총 {iterations}회 호출)...")
        
        for i in range(iterations):
            try:
                params = {"market": market, "count": 200, "to": to}
                response = requests.get(url, params=params)
                data = response.json()
                if not data: break
                all_candles.extend(data)
                to = data[-1]['candle_date_time_utc'] + "Z"
                if (i + 1) % 50 == 0:
                    print(f"진행도: {len(all_candles)}/{count} 완료...")
                time.sleep(0.1)
            except Exception as e:
                print(f"오류 발생: {e}"); time.sleep(2); continue

        df = pd.DataFrame(all_candles)
        df = df[['candle_date_time_kst', 'opening_price', 'high_price', 'low_price', 'trade_price', 'candle_acc_trade_volume']]
        df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
        df['time'] = pd.to_datetime(df['time'])
        return df.sort_values('time').reset_index(drop=True)

    # 2. 지표 직접 계산 (Pure Pandas/Numpy)
    def add_all_indicators_pure(df):
        # --- [추세 지표] ---
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['EMA_120'] = df['close'].ewm(span=120, adjust=False).mean()
        
        # MACD
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # 일목균형표 전환선 (9일 최고/최저의 평균)
        df['Ichimoku_TS'] = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2

        # --- [모멘텀 지표] ---
      
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        # Stochastic %K, %D
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['Stoch_K'] = (df['close'] - low_14) / (high_14 - low_14) * 100
        df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
        
        # Williams %R
        df['WillR'] = (high_14 - df['close']) / (high_14 - low_14) * -100
        # ROC
        df['ROC'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100

        # --- [변동성 지표] ---
        # 볼린저 밴드
        df['BB_Mid'] = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Mid'] + (std * 2)
        df['BB_Lower'] = df['BB_Mid'] - (std * 2)
        
        # ATR
        tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift()), abs(df['low']-df['close'].shift())], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean()
        
        # Keltner Channel (간략화 버전)
        df['KC_Upper'] = df['EMA_20'] + (df['ATR'] * 2)
        df['KC_Lower'] = df['EMA_20'] - (df['ATR'] * 2)

        # --- [거래량/에너지 지표] ---
        # OBV
        df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        # MFI (Money Flow Index)
        tp = (df['high'] + df['low'] + df['close']) / 3
        mf = tp * df['volume']
        pos_mf = mf.where(tp > tp.shift(1), 0).rolling(14).sum()
        neg_mf = mf.where(tp < tp.shift(1), 0).rolling(14).sum()
        df['MFI'] = 100 - (100 / (1 + (pos_mf / neg_mf)))

        # --- [파생/시간 변수] ---
        df['Price_EMA_Diff'] = (df['close'] - df['EMA_20']) / df['EMA_20']
        
        # 연속 양봉/음봉 카운트
        sig = np.sign(df['close'].diff().fillna(0))
        df['consecutive'] = sig.groupby((sig != sig.shift()).cumsum()).cumsum()

        # 시간 변환
        h, m, wd = df['time'].dt.hour, df['time'].dt.minute, df['time'].dt.weekday
        df['hr_sin'], df['hr_cos'] = np.sin(2*np.pi*h/24), np.cos(2*np.pi*h/24)
        df['day_sin'], df['day_cos'] = np.sin(2*np.pi*wd/7), np.cos(2*np.pi*wd/7)
        df['is_weekend'] = (wd >= 5).astype(int)
        
        # 나스닥 (서머타임 고려)
        def nasdaq(dt):
            is_s = 3 < dt.month < 11
            curr = dt.hour + dt.minute/60
            return 1 if (curr >= (22.5 if is_s else 23.5) or curr < (5.0 if is_s else 6.0)) else 0
        df['is_nasdaq'] = df['time'].apply(nasdaq)

        return df

    # 실행
    if __name__ == "__main__":
        raw_df = fetch_massive_upbit_data(count=100000)
        final_df = add_all_indicators_pure(raw_df)
        final_df.dropna(inplace=True)
      
        # high를 target으로 설정하고 열의 마지막으로 넘김
        cols = list(final_df.columns)
        cols.remove('high')
        cols.append('high')
        final_df = final_df[cols]
        
        path = f"btc_100k_back_high.csv"
        final_df.to_csv(path, index=False)
        print(f"완료! 데이터 크기: {final_df.shape}")
        # 99980개 데이터 
