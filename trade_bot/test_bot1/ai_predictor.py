import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import logging
import os

# 코랩에서 만들었던 것과 100% 동일한 모델 구조(껍데기)를 만들어야 가중치를 입힐 수 있음
class QuantLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers):
        super(QuantLSTM, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        out = self.fc(out)
        return self.sigmoid(out)

class AIPredictor:
    def __init__(self, model_path='data/quant_brain.pth'):
        # 내 PC에 그래픽카드가 없어도 CPU로 충분히 빠르게 돌아감
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model_path = model_path
        self.model = None
        
        self._load_model()

    def _load_model(self):
        """저장된 뇌(가중치)를 불러와서 모델에 씌우는 작업"""
        if not os.path.exists(self.model_path):
            logging.warning(f"[WARNING] AI 모델 파일({self.model_path})을 찾을 수 없습니다! 기본 확률(0.5)을 반환합니다.")
            return
            
        try:
            # 파라미터 세팅 (코랩과 동일하게)
            features_len = 8 # open, high, low, close, volume, rsi, vol_sma, close_sma
            self.model = QuantLSTM(input_size=features_len, hidden_size=64, num_layers=2).to(self.device)
            
            # 가중치 덮어씌우기
            self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
            self.model.eval() # 실전(평가) 모드로 전환 (Dropout 등 비활성화)
            logging.info("[OK] AI 퀀트 뇌(LSTM) 이식 완료!")
            
        except Exception as e:
            logging.error(f"[ERROR] AI 모델 로딩 실패: {e}")
            self.model = None

    def _calculate_rsi(self, df, periods=14):
        """RSI 계산 (코랩과 동일)"""
        delta = df['close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        ema_up = up.ewm(com=periods-1, adjust=False).mean()
        ema_down = down.ewm(com=periods-1, adjust=False).mean()
        rs = ema_up / (ema_down + 1e-10)
        return 100 - (100 / (1 + rs))

    def predict(self, df):
        """최신 12개의 캔들을 보고 다음 봉 상승 확률(0~1) 반환"""
        if self.model is None:
            return 0.5 # 모델이 없으면 중립(50%) 반환

        try:
            # 1. 데이터 복사 및 피처 엔지니어링 (원본 훼손 방지)
            data = df.copy()
            data['rsi'] = self._calculate_rsi(data)
            data['vol_sma_20'] = data['volume'].rolling(window=20).mean()
            data['close_sma_12'] = data['close'].rolling(window=12).mean()
            
            # 결측치 제거 (최근 데이터만 필요하므로 dropna 후 뒤에서 12개 자름)
            data.dropna(inplace=True)
            
            # 과거 12개(1시간) 캔들이 안 모였으면 예측 불가
            if len(data) < 12:
                logging.warning("[WARNING] AI 예측을 위한 캔들 데이터(12개)가 부족합니다.")
                return 0.5

            # 최근 12개 캔들만 추출
            recent_12 = data.iloc[-12:]
            features = ['open', 'high', 'low', 'close', 'volume', 'rsi', 'vol_sma_20', 'close_sma_12']
            
            # 2. 스케일링 (0~1 압축)
            scaler = MinMaxScaler()
            scaled_data = scaler.fit_transform(recent_12[features])
            
            # 3. 텐서 변환 (Batch=1, Seq=12, Features=8)
            tensor_data = torch.FloatTensor(scaled_data).unsqueeze(0).to(self.device)
            
            # 4. 딥러닝 예측 (기울기 계산 끄기 = 속도 향상)
            with torch.no_grad():
                probability = self.model(tensor_data).item()
                
            return round(probability, 4) # 소수점 4자리까지 반환 (예: 0.8521)
            
        except Exception as e:
            logging.error(f"[ERROR] AI 예측 중 에러 발생: {e}")
            return 0.5