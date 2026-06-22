class ExitBot:
    def __init__(self, hard_stop_loss=-3.0, trailing_threshold=2.0):
        self.hard_stop_loss = hard_stop_loss
        self.trailing_threshold = trailing_threshold

    def evaluate_exit(self, position, df, ai_probability):
        """
        position: 현재 보유 중인 포지션 정보 (entry_price, strategy_type, breakout_price, max_price 등)
        """
        if len(df) < 2:
            return False, None, "HOLD" # 데이터 부족
        
        curr = df.iloc[-1]
        profit_pct = (curr['close'] / position['entry_price'] - 1) * 100
        
        # [1] 공통 방어 레이어 (최우선 순위)
        if profit_pct <= self.hard_stop_loss:
            return True, "HARD_STOP_LOSS", f"손절선 도달 ({profit_pct:.1f}%)"

        # [2] Trailing Stop (수익 보존 - 먼저 체크하여 수익 최대화)
        if 'max_price' in position and position['max_price'] > 0:
            max_profit_pct = (position['max_price'] / position['entry_price'] - 1) * 100
            if max_profit_pct >= self.trailing_threshold:
                trail_stop_price = position['max_price'] * (1 - self.trailing_threshold / 100)
                if curr['close'] <= trail_stop_price:
                    return True, "TRAILING_STOP", f"트레일링 스탑 ({curr['close']:.0f} <= {trail_stop_price:.0f})"

        # [3] 수익 실현 레이어 (트레일링 후 체크 - 분할 매도 개념)
        if profit_pct >= 5.0:
            return True, "PROFIT_TAKING", f"수익 5% 달성 ({profit_pct:.1f}%)"

        # [4] 전략별 맞춤 레이어
        tag = position['strategy_type']
        
        # A. AI 전용 매도 로직
        if tag == "AI_PRIORITY":
            ai_raw = (ai_probability - 0.5) * 2
            ai_scaled = pow(ai_raw, 3)
            if ai_scaled < -0.2: # AI가 하락으로 전환 (임계값 완화)
                return True, "AI_REVERSAL", f"AI 예측 방향 전환 ({ai_probability:.3f})"

        # B. 돌파 전용 매도 로직
        elif tag == "BREAKOUT_PRIORITY":
            if curr['close'] < position['breakout_price']: # 돌파했던 저항선 재침범
                return True, "FALSE_BREAKOUT", f"저항선 재이탈 ({curr['close']:.0f} < {position['breakout_price']:.0f})"
            if curr['rsi'] > 80: # 과매수 기준 상향 (강한 추세 유지)
                return True, "BREAKOUT_OVERBOUGHT", f"돌파 후 과매수 ({curr['rsi']:.1f})"

        # C. 일반 점수 매도 로직
        elif tag == "GENERAL_SCORE":
            # MACD 데드크로스
            if curr['macd_hist'] < 0 and df['macd_hist'].iloc[-2] > 0:
                return True, "INDICATOR_EXIT", "MACD 데드크로스"
            # RSI 과매수
            if curr['rsi'] > 70:
                return True, "OVERBOUGHT_RSI", f"RSI 과매수 ({curr['rsi']:.1f})"
            # 볼린저 상단 이탈 (추세 약화 - 최근 2봉 모두 밴드 아래 + RSI < 70)
            if (curr['close'] < curr['bb_upper'] and df['close'].iloc[-2] < df['bb_upper'].iloc[-2] and curr['rsi'] < 70):
                return True, "BB_UPPER_EXIT", "볼린저 상단 지속 이탈 + RSI 하락"

        return False, None, "HOLD"