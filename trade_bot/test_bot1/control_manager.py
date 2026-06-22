import pyupbit
import time
from entry_bot import EntryBot
from exit_bot import ExitBot
from store import LedgerManager
from telegram_bot import TelegramBot
from config import Config
import logging
from ai_predictor import AIPredictor
from indicators import get_prepared_df

class ControlManager:
    def __init__(self, tele_bot):
        # 1. 부하 직원들(모듈) 소환
        self.entry_bot = EntryBot(buy_threshold=80)
        self.exit_bot = ExitBot()
        self.ledger = LedgerManager() # Active_Trades.json 관리
        self.tele_bot = tele_bot

        # 👈 AI 모델 장착!
        self.ai = AIPredictor()
        
        # 2. 업비트 연결 (Config에서 API 키 로드)
        self.upbit = pyupbit.Upbit(Config.UPBIT_ACCESS_KEY, Config.UPBIT_SECRET_KEY)
        self.symbol = Config.SYMBOL
        self.order_amount = Config.ORDER_AMOUNT

    def run_5min_cycle(self):
        """5분마다 실행되는 사령관의 핵심 업무 프로세스"""
        try:
            # --- [STEP 1] 데이터 수집 (스냅샷) ---
            # 모든 봇이 동일한 데이터를 보게 함 (API 호출 최소화)
            df = pyupbit.get_ohlcv(self.symbol, interval="minute5", count=200)
            current_price = pyupbit.get_current_price(self.symbol)

            if df is None or len(df) < 20:
                logging.warning(f"⚠️ 데이터 부족 (현재 {len(df) if df is not None else 0}개). 다음 사이클을 대기합니다.")
                return  # 현재 함수를 종료하고 다음 5분 루프로 넘어감
            
            if df is None or current_price is None:
                raise Exception("업비트 데이터 수집 실패")

            # 데이터에 지표 추가 (RSI, MACD 등)
            df = get_prepared_df(df)
            
            # --- [STEP 2] 매도 검토 (Exit) ---
            # 장부에서 현재 들고 있는 물량 가져오기
            active_trades = self.ledger.get_active_trades()
            logging.info(f"활성 포지션 수: {len(active_trades)}")
            
            for trade in active_trades:
                # max_price 업데이트 (Trailing Stop용)
                if 'max_price' not in trade or trade['max_price'] < current_price:
                    trade['max_price'] = current_price
                    self.ledger.update_trade_max_price(trade['slot_id'], current_price)
                
                # 사령관이 수비수(ExitBot)에게 판단을 맡김
                should_sell, exit_tag, exit_reason = self.exit_bot.evaluate_exit(trade, df, self.ai.predict(df))
                
                if should_sell:
                    profit_pct = (current_price / trade['entry_price'] - 1) * 100
                    full_reason = f"{exit_reason} (수익률: {profit_pct:.1f}%)"
                    self._execute_sell(trade, current_price, full_reason)

            # --- [STEP 3] 매수 검토 (Entry) ---
            # 장부 확인: 빈 슬롯이 있는지 확인
            active_count = self.ledger.get_active_count()
            logging.info(f"활성 슬롯: {active_count}/{self.ledger.max_slots}")
            
            if active_count < self.ledger.max_slots:
                # 사령관이 공격수(EntryBot)에게 예측 확률과 데이터를 던져줌
                
                ai_probability = self.ai.predict(df) 
                logging.info(f"🤖 AI 상승 예측 확률: {ai_probability*100:.2f}%")
                entry_report = self.entry_bot.calculate_score(df, ai_probability)
                
                if entry_report['is_buy']:
                    self._execute_buy(entry_report)
            else:
                logging.info("슬롯이 가득 차서 매수 검토를 건너뜁니다.")

        except Exception as e:
            self._handle_error(e, "5분 주기 실행 중 오류")

    def _execute_buy(self, report):
        """실제 매수 주문 및 장부 기록 (강화된 에러 처리)"""
        try:
            # 1. 시드 머니 확인
            balance = self.upbit.get_balance("KRW")
            if balance < self.order_amount:
                raise RuntimeError(f"잔고 부족: 보유 {balance:,.0f}원 / 필요 {self.order_amount:,.0f}원")

            # 2. 실제 시장가 매수 주문 (재시도 로직)
            order = None
            for attempt in range(3):
                try:
                    order = self.upbit.buy_market_order(self.symbol, self.order_amount)
                    if order and 'uuid' in order:
                        break
                    elif attempt < 2:
                        time.sleep(1)
                except Exception as retry_err:
                    logging.warning(f"매수 재시도 {attempt + 1}/3 실패: {retry_err}")
                    if attempt < 2:
                        time.sleep(2)

            if not order or 'uuid' not in order:
                raise RuntimeError(f"매수 주문 최종 실패: {order}")

            # 3. 주문 체결 확인 (최대 5초 대기)
            order_detail = None
            for attempt in range(10):
                try:
                    time.sleep(0.5)
                    order_detail = self.upbit.get_order(order['uuid'])
                    if order_detail and order_detail.get('state') in ['done', 'cancel']:
                        break
                except Exception as query_err:
                    logging.warning(f"주문 조회 실패 {attempt + 1}/10: {query_err}")

            if not order_detail:
                raise RuntimeError(f"주문 조회 실패 (UUID: {order['uuid']})")

            # 4. 체결 가격/수량 추출 (수수료 포함)
            trades = order_detail.get('trades', [])
            if trades:
                total_price = sum(float(t['funds']) for t in trades)
                total_qty = sum(float(t['volume']) for t in trades)
                entry_price = total_price / total_qty if total_qty > 0 else report['current_price']
                quantity = total_qty
                paid_fee = sum(float(t.get('fee', 0)) for t in trades)
            else:
                # 체결 기록이 없을 경우 (매우 드문 케이스)
                entry_price = report['current_price']
                quantity = (self.order_amount * (1 - 0.0005)) / entry_price
                paid_fee = self.order_amount * 0.0005

            # 5. 장부 기록 (실제 데이터 기반)
            self.ledger.add_trade(
                entry_price=entry_price,
                quantity=quantity,
                reason=report['reason'],
                strategy_type=report['strategy_type'],
                breakout_price=report.get('breakout_price', entry_price),
                max_price=entry_price,
                fee=paid_fee  # 수수료 기록
            )

            # 6. 텔레그램 알림
            msg = (
                f"✅ **실거래 매수 완료**\n"
                f"단가: {entry_price:,.0f}원\n"
                f"수량: {quantity:.6f} BTC\n"
                f"수수료: {paid_fee:,.0f}원"
            )
            self.tele_bot.send_message(msg)
            logging.info(f"[매수 완료] {self.symbol} @ {entry_price:,.0f}원 x {quantity:.6f}")

        except RuntimeError as e:
            self._handle_error(e, "매수 주문 실패 (복구 불가)")
        except Exception as e:
            self._handle_error(e, "매수 주문 중 예상치 못한 오류")

    def _execute_sell(self, trade, price, reason):
        """실제 매도 주문 및 장부 기록 (강화된 에러 처리)"""
        try:
            # 1. 매도 주문 (재시도 로직)
            order = None
            for attempt in range(3):
                try:
                    order = self.upbit.sell_market_order(self.symbol, trade['quantity'])
                    if order and 'uuid' in order:
                        break
                    elif attempt < 2:
                        time.sleep(1)
                except Exception as retry_err:
                    logging.warning(f"매도 재시도 {attempt + 1}/3 실패: {retry_err}")
                    if attempt < 2:
                        time.sleep(2)

            if not order or 'uuid' not in order:
                raise RuntimeError(f"매도 주문 최종 실패: {order}")

            # 2. 주문 체결 확인 (최대 5초 대기)
            order_detail = None
            for attempt in range(10):
                try:
                    time.sleep(0.5)
                    order_detail = self.upbit.get_order(order['uuid'])
                    if order_detail and order_detail.get('state') in ['done', 'cancel']:
                        break
                except Exception as query_err:
                    logging.warning(f"매도 조회 실패 {attempt + 1}/10: {query_err}")

            if not order_detail:
                raise RuntimeError(f"매도 주문 조회 실패 (UUID: {order['uuid']})")

            # 3. 체결 가격/수수료 추출
            trades = order_detail.get('trades', [])
            if trades:
                total_price = sum(float(t['funds']) for t in trades)
                total_qty = sum(float(t['volume']) for t in trades)
                exit_price = total_price / total_qty if total_qty > 0 else price
                received_fee = sum(float(t.get('fee', 0)) for t in trades)
            else:
                exit_price = price
                received_fee = price * trade['quantity'] * 0.0005

            # 4. 장부에서 삭제 및 히스토리 이관
            self.ledger.remove_trade(
                trade['slot_id'],
                exit_price=exit_price,
                exit_reason=reason,
                exit_fee=received_fee
            )

            # 5. 알림 전송
            profit_pct = (exit_price / trade['entry_price'] - 1) * 100
            msg = (
                f"🚨 **실거래 매도 완료**\n"
                f"매도가: {exit_price:,.0f}원\n"
                f"수익: {profit_pct:+.2f}%\n"
                f"수수료: {received_fee:,.0f}원\n"
                f"사유: {reason}"
            )
            self.tele_bot.send_message(msg)
            logging.info(f"[매도 완료] {self.symbol} @ {exit_price:,.0f}원 수익 {profit_pct:+.2f}%")

        except RuntimeError as e:
            self._handle_error(e, "매도 주문 실패 (복구 불가)")
        except Exception as e:
            self._handle_error(e, "매도 주문 중 예상치 못한 오류")

    def _handle_error(self, e, context):
        """사령관의 에러 대응 매뉴얼"""
        error_msg = f"❌ [{context}] {str(e)}"
        logging.error(error_msg)
        self.tele_bot.send_message(error_msg)