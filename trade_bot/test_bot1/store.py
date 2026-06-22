import json
import os
from datetime import datetime
import logging

class LedgerManager:
    def __init__(self, data_dir='data', max_slots=3):
        self.data_dir = data_dir
        self.active_file = os.path.join(data_dir, 'active_trades.json')
        self.history_file = os.path.join(data_dir, 'trade_history.json')
        self.max_slots = max_slots
        
        # 봇이 켜질 때 폴더와 파일이 없으면 자동으로 생성하는 초기화 작업
        self._initialize_storage()

    def _initialize_storage(self):
        """데이터 폴더 및 기초 JSON 파일 생성"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logging.info(f"📁 데이터 폴더({self.data_dir})가 생성되었습니다.")

        if not os.path.exists(self.active_file):
            self._save_json(self.active_file, {"max_slots": self.max_slots, "active_slots": []})
            
        if not os.path.exists(self.history_file):
            self._save_json(self.history_file, []) # 히스토리는 빈 리스트로 시작

    def _load_json(self, path):
        """JSON 파일 읽기 (에러 처리 포함)"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"🚨 장부 읽기 실패 ({path}): {e}")
            raise # 치명적 에러이므로 상위(Control)로 에러를 던짐

    def _save_json(self, path, data):
        """JSON 파일 쓰기"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"🚨 장부 쓰기 실패 ({path}): {e}")
            raise

    # ----------------------------------------------------
    # 🔍 조회(Read) 기능
    # ----------------------------------------------------
    def get_active_trades(self):
        """현재 보유 중인 모든 슬롯 리스트 반환"""
        data = self._load_json(self.active_file)
        return data.get('active_slots', [])

    def get_active_count(self):
        """현재 사용 중인 슬롯 개수 반환"""
        return len(self.get_active_trades())

    # ----------------------------------------------------
    # ✍️ 기록(Write) 기능
    # ----------------------------------------------------
    def add_trade(self, entry_price, quantity, reason, strategy_type=None, breakout_price=None, max_price=None, fee=0):
        """새로운 매수 건을 장부에 추가 (빈 슬롯 ID 자동 할당)"""
        active_data = self._load_json(self.active_file)
        slots = active_data['active_slots']
        
        if len(slots) >= self.max_slots:
            logging.warning("⚠️ 슬롯이 가득 차서 매수 기록을 추가할 수 없습니다.")
            return False

        # 비어있는 가장 빠른 슬롯 번호 찾기 (1, 2, 3 중)
        used_ids = [slot['slot_id'] for slot in slots]
        new_slot_id = next(i for i in range(1, self.max_slots + 1) if i not in used_ids)
        
        new_trade = {
            "trade_id": f"T-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "slot_id": new_slot_id,
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "entry_price": entry_price,
            "quantity": quantity,
            "reason": reason,
            "strategy_type": strategy_type or "GENERAL_SCORE",
            "breakout_price": breakout_price or entry_price,
            "max_price": max_price or entry_price,
            "entry_fee": fee  # 매수 수수료 기록
        }
        
        slots.append(new_trade)
        self._save_json(self.active_file, active_data)
        logging.info(f"✅ [장부 기록] {new_slot_id}번 슬롯 매수 완료 (가격: {entry_price}, 수수료: {fee:,.0f}원)")
        return True

    def update_trade_max_price(self, slot_id, new_max_price):
        """특정 슬롯의 max_price 업데이트 (Trailing Stop용)"""
        active_data = self._load_json(self.active_file)
        slots = active_data['active_slots']
        
        for slot in slots:
            if slot['slot_id'] == slot_id:
                slot['max_price'] = max(slot.get('max_price', slot['entry_price']), new_max_price)
                self._save_json(self.active_file, active_data)
                logging.info(f"🔄 [장부 업데이트] {slot_id}번 슬롯 max_price: {slot['max_price']}")
                return True
        
        logging.warning(f"⚠️ 슬롯 {slot_id}을 찾을 수 없습니다.")
        return False

    def remove_trade(self, slot_id, exit_price, exit_reason, exit_fee=0):
        """매도 완료된 건을 활성 장부에서 삭제하고 History로 이관"""
        active_data = self._load_json(self.active_file)
        history_data = self._load_json(self.history_file)
        
        slots = active_data['active_slots']
        # 매도할 타겟 찾기
        target_index = next((i for i, slot in enumerate(slots) if slot['slot_id'] == slot_id), None)
        
        if target_index is not None:
            target = slots.pop(target_index) # 리스트에서 빼내기 (삭제 효과)
            
            # 수익 계산 (수수료 차감)
            entry_price = target['entry_price']
            entry_fee = target.get('entry_fee', 0)
            gross_profit = (exit_price - entry_price) * target['quantity']
            net_profit = gross_profit - entry_fee - exit_fee  # 매수/매도 수수료 모두 차감
            profit_rate = (net_profit / (entry_price * target['quantity'])) * 100
            
            # 히스토리 기록용 데이터 가공
            history_record = {
                "trade_id": target['trade_id'],
                "entry_time": target['entry_time'],
                "exit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "quantity": target['quantity'],
                "strategy_type": target.get('strategy_type', 'UNKNOWN'),
                "gross_profit": round(gross_profit, 0),  # 수수료 전 수익
                "entry_fee": round(entry_fee, 0),  # 매수 수수료
                "exit_fee": round(exit_fee, 0),  # 매도 수수료
                "net_profit": round(net_profit, 0),  # 수수료 차감 후 순 수익
                "profit_rate": round(profit_rate, 2),  # 수익률 (%)
                "entry_reason": target['reason'],
                "exit_reason": exit_reason
            }
            
            # 히스토리에 추가 및 파일 저장
            history_data.append(history_record)
            
            self._save_json(self.active_file, active_data)
            self._save_json(self.history_file, history_data)
            
            logging.info(
                f"🔄 [장부 이관] {slot_id}번 슬롯 매도 완료 "
                f"(순수익률: {profit_rate:.2f}%, 순이익: {net_profit:,.0f}원) -> History 저장됨"
            )
            return True
        else:
            logging.error(f"⚠️ [장부 오류] 삭제하려는 {slot_id}번 슬롯을 찾을 수 없습니다.")
            return False