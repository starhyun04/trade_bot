import numpy as np
import pandas as pd
from indicators import get_prepared_df, is_safe_zone

class EntryBot:
    def __init__(self, buy_threshold=75):
        """
        buy_threshold: 매수 진입을 위한 최소 점수 (기본 75점)
        """
        self.buy_threshold = buy_threshold
        self.min_data_count = 100  # 지표 안정성을 위한 최소 데이터 개수
        
        # 각 부문별 최종 점수 기여 비중 (합이 1.0)
        self.WEIGHTS = {
            'ai': 0.50,        # AI 예측 비중 (가장 높음)
            'breakout': 0.35,  # 돌파 강도 및 가격 액션 비중
            'indicators': 0.15 # 보조지표(RSI, MACD 등) 비중
        }

    def calculate_score(self, df, ai_probability):
        """
        전체 매수 로직 실행: 필터 -> 우선순위 -> 가중치 점수 합산
        """
        # [1] 데이터 가드: 데이터가 너무 적으면 에러 방지를 위해 패스
        if len(df) < self.min_data_count:
            return self._create_report(False, 0, "DATA_LACK", None, f"데이터 부족({len(df)})")

        # [2] 지표 준비: indicators.py의 공통 함수 사용
        df = get_prepared_df(df)
        
        # [3] NaN 방어: 지표 계산 후 NaN이 있는 행은 제외하고 마지막 데이터 추출
        clean_df = df.dropna()
        if clean_df.empty:
            return self._create_report(False, 0, "NAN_ERROR", None, "유효 데이터 없음")
            
        curr = clean_df.iloc[-1]

        # [4] 글로벌 철벽 필터: 역배열 및 급락장 체크
        # is_safe, filter_reason = is_safe_zone(clean_df)
        # if not is_safe:
        #     return self._create_report(False, 0, "FILTERED", curr, filter_reason)

        # --- [Step A: AI 점수 계산 (지수 함수 비선형 처리)] ---
        # 0.5(중립)를 0으로 맞추고 -1.0 ~ 1.0 범위로 변환
        ai_raw = (ai_probability - 0.5) * 2
        # 지수 함수(3제곱) 적용: 애매한 점수는 죽이고 확실한 점수(0.7 이상)는 부각함
        ai_scaled = pow(ai_raw, 3) 
        ai_score_final = ai_scaled * 100  # -100 ~ 100점 스케일

        # --- [Step B: 돌파 강도 점수 계산 (0 ~ 100)] ---
        # 저항선 대비 현재가 위치 (0.5% 돌파 시 만점) + 볼밴 상단 터치 여부 (최근 3봉 중 2봉 이상 터치로 추세 지속 확인)
        price_diff = (curr['close'] / curr['resistance']) - 1
        breakout_raw = min(100, max(0, (price_diff / 0.005) * 100))
        
        # 볼린저 밴드 상단 터치 (추세 지속 확인)
        recent_bb_touches = df['close'].tail(3).ge(df['bb_upper'].tail(3)).sum()
        bb_upper_touch = 1.0 if recent_bb_touches >= 2 else 0.0
        
        # 거래량 폭발 정도 (평균 대비 2.0배부터 시작, 3.0배면 만점)
        vol_ratio = curr['volume'] / (curr['vol_sma'] + 1e-10)
        vol_score = min(100, max(0, (vol_ratio - 2.0) / 1.0 * 100))
        
        # 돌파 부문 통합 (가격 돌파 강도 50% + 볼린저 추세 확인 25% + 거래량 폭발도 25%)
        breakout_score_final = (breakout_raw * 0.5) + (bb_upper_touch * 25) + (vol_score * 0.25)

        # --- [Step C: 모멘텀/보조지표 점수 계산 (0 ~ 100)] ---
        # RSI 점수화: 40~80 긍정, 80 이상 과매수 페널티, 40 이하 과매도 중립
        if curr['rsi'] > 80:
            rsi_score = 0  # 과매수 페널티
        elif curr['rsi'] < 40:
            rsi_score = 50  # 과매도 중립
        else:
            rsi_score = (curr['rsi'] - 40) * 2.5
        
        # MACD 히스토그램 방향성 (양수이고 증가 중이면 가점)
        macd_positive = curr['macd_hist'] > 0
        macd_increasing = curr['macd_hist'] > df['macd_hist'].iloc[-2] if len(df) > 1 else False
        macd_score = 100 if (macd_positive and macd_increasing) else 0
        
        ind_score_final = (rsi_score * 0.6) + (macd_score * 0.4)

        # --- [Step D: 우선순위 매수 판단 (Hard Trigger)] ---
        
        # 1. AI 우선순위: AI가 지수함수를 뚫고 압도적 확신을 보일 때
        if ai_scaled > 0.85: # 원본 확률 약 94% 이상
            return self._create_report(True, 100, "AI_PRIORITY", curr, "AI 압도적 확신")

        # 2. 돌파 우선순위: 거래량이 2.5배 이상 터지며 저항선을 뚫을 때 (더 유연하게, 최소 거래량 필터 추가)
        min_volume_threshold = 1000  # 비트코인 기준 최소 거래량 (시장에 따라 조정)
        if curr['close'] > curr['resistance'] and vol_ratio > 2.5 and curr['volume'] > min_volume_threshold:
            return self._create_report(True, 100, "BREAKOUT_PRIORITY", curr, "거래량 폭발 돌파")

        # --- [Step E: 일반 가중치 합산 점수 계산] ---
        total_score = (
            (ai_score_final * self.WEIGHTS['ai']) +
            (breakout_score_final * self.WEIGHTS['breakout']) +
            (ind_score_final * self.WEIGHTS['indicators'])
        )

        # 최종 판단
        is_buy = total_score >= self.buy_threshold

        return self._create_report(
            is_buy, 
            total_score, 
            "GENERAL_SCORE", 
            curr, 
            "지표 합산 조건 충족" if is_buy else "점수 미달"
        )

    def _create_report(self, is_buy, score, tag, curr, reason):
        """결과 리포트 포맷팅"""
        return {
            "is_buy": is_buy,
            "score": round(score, 2),
            "strategy_type": tag,
            "current_price": curr['close'] if curr is not None else 0,
            "breakout_price": curr['resistance'] if curr is not None else 0,
            "reason": reason
        }