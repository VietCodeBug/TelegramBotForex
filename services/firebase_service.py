"""
Firebase Service Module - Tích hợp Firebase Realtime Database
Sử dụng REST API (không cần service account)
"""
import requests
from datetime import datetime
from typing import Optional, List, Dict
import json
import os


class FirebaseService:
    """
    Firebase Realtime Database via REST API
    Không cần service account, chỉ cần API key và Database URL
    """
    
    def __init__(self, database_url: str, api_key: str = None):
        """
        Khởi tạo Firebase connection
        
        Args:
            database_url: URL của Realtime Database
            api_key: Firebase API Key (optional for public access)
        """
        # Clean URL (remove trailing slash)
        self.database_url = database_url.rstrip('/')
        self.api_key = api_key or os.getenv('FIREBASE_API_KEY', '')
        self.initialized = False
        
        # Test connection
        try:
            test_url = f"{self.database_url}/.json"
            if self.api_key:
                test_url += f"?auth={self.api_key}"
            
            response = requests.get(test_url, timeout=10)
            if response.status_code == 200:
                self.initialized = True
                print(f"✅ Firebase connected!")
            else:
                print(f"⚠️ Firebase responded with status {response.status_code}")
                self._init_local_storage()
        except Exception as e:
            print(f"⚠️ Firebase connection failed: {e}")
            self._init_local_storage()
    
    def _init_local_storage(self):
        """Initialize local storage fallback"""
        self._local_storage = {'trades': [], 'config': {'capital': 100}}
        self.initialized = False
    
    def _make_request(self, method: str, path: str, data: dict = None) -> Optional[dict]:
        """Make REST API request to Firebase"""
        url = f"{self.database_url}/{path}.json"
        if self.api_key:
            url += f"?auth={self.api_key}"
        
        try:
            if method == 'GET':
                response = requests.get(url, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, timeout=10)
            else:
                return None
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"⚠️ Firebase {method} failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Firebase request error: {e}")
            return None
    
    def save_signal(self, signal: dict, executed: bool = False) -> str:
        """
        Lưu tín hiệu giao dịch
        
        Args:
            signal: Dict chứa action, entry, sl, tp, etc.
            executed: True nếu đã thực hiện lệnh
            
        Returns:
            ID của record
        """
        record = {
            'timestamp': datetime.now().isoformat(),
            'action': signal.get('action', 'WAIT'),
            'entry': signal.get('entry'),
            'stoploss': signal.get('stoploss'),
            'takeprofit': signal.get('takeprofit'),
            'confidence': signal.get('confidence', 0),
            'wyckoff_phase': signal.get('wyckoff_phase', ''),
            'event_detected': signal.get('event_detected', ''),
            'reason': signal.get('reason', ''),
            'executed': executed,
            'status': 'OPEN' if executed else 'SIGNAL_ONLY'
        }
        
        if self.initialized:
            result = self._make_request('POST', 'trades', record)
            if result and 'name' in result:
                return result['name']
        
        # Local fallback
        if not hasattr(self, '_local_storage'):
            self._init_local_storage()
        self._local_storage['trades'].append(record)
        return f"local_{len(self._local_storage['trades'])}"
    
    def update_trade_result(self, trade_id: str, pnl: float, status: str = 'CLOSED'):
        """Cập nhật kết quả lệnh sau khi đóng"""
        if not self.initialized or trade_id.startswith('local_'):
            return
        
        self._make_request('PATCH', f'trades/{trade_id}', {
            'pnl': pnl,
            'status': status,
            'closed_at': datetime.now().isoformat()
        })
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Lấy lịch sử giao dịch"""
        if self.initialized:
            result = self._make_request('GET', 'trades')
            if result and isinstance(result, dict):
                trades = list(result.values())
                # Sort by timestamp descending
                trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                return trades[:limit]
        
        # Local fallback
        if hasattr(self, '_local_storage'):
            return self._local_storage['trades'][-limit:]
        return []
    
    def get_capital(self) -> float:
        """Lấy số vốn hiện tại"""
        if self.initialized:
            result = self._make_request('GET', 'config/capital')
            if result is not None:
                return float(result)
        
        if hasattr(self, '_local_storage'):
            return self._local_storage.get('config', {}).get('capital', 100.0)
        return 100.0
    
    def update_capital(self, new_capital: float):
        """Cập nhật số vốn"""
        if self.initialized:
            self._make_request('PUT', 'config/capital', new_capital)
        
        if hasattr(self, '_local_storage'):
            self._local_storage['config']['capital'] = new_capital
    
    def update_risk(self, risk_percent: float):
        """Cập nhật % rủi ro"""
        if self.initialized:
            self._make_request('PUT', 'config/risk_percent', risk_percent)
    
    def get_daily_stats(self) -> Dict:
        """Lấy thống kê trong ngày"""
        today = datetime.now().strftime("%Y-%m-%d")
        trades = self.get_trade_history(100)
        
        daily_trades = [t for t in trades if t.get('timestamp', '').startswith(today)]
        
        wins = len([t for t in daily_trades if t.get('pnl', 0) > 0])
        losses = len([t for t in daily_trades if t.get('pnl', 0) < 0])
        total_pnl = sum(t.get('pnl', 0) for t in daily_trades)
        
        return {
            'date': today,
            'total_trades': len(daily_trades),
            'wins': wins,
            'losses': losses,
            'winrate': (wins / len(daily_trades) * 100) if daily_trades else 0,
            'pnl': round(total_pnl, 2)
        }
    
    def log_event(self, event_type: str, message: str):
        """Log sự kiện hệ thống"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'message': message
        }
        
        if self.initialized:
            self._make_request('POST', 'logs', log_entry)
    
    def save_external_signal(self, signal: dict, ai_analysis: dict = None) -> str:
        """
        Lưu tín hiệu từ kênh Telegram bên ngoài
        
        Args:
            signal: Dict với source, action, entry, sl, tp
            ai_analysis: Kết quả phân tích AI
            
        Returns:
            ID của signal
        """
        signal_data = {
            'timestamp': datetime.now().isoformat(),
            'source': signal.get('source', 'unknown'),
            'symbol': signal.get('symbol', 'XAUUSD'),
            'action': signal.get('action', 'N/A'),
            'entry': signal.get('entry', 0),
            'stoploss': signal.get('stoploss', 0),
            'takeprofit': signal.get('takeprofit', 0),
            'status': 'PENDING',
            'raw_text': signal.get('raw_text', '')[:200],
        }
        
        if ai_analysis:
            signal_data['ai_recommendation'] = ai_analysis.get('recommendation', 'N/A')
            signal_data['ai_confidence'] = ai_analysis.get('confidence', 0)
            signal_data['ai_reason'] = ai_analysis.get('reason', '')
        
        if self.initialized:
            result = self._make_request('POST', 'external_signals', signal_data)
            if result and 'name' in result:
                return result['name']
        
        return None
    
    def get_external_signals(self, source: str = None, limit: int = 20) -> List[Dict]:
        """
        Lấy lịch sử tín hiệu từ kênh ngoài
        
        Args:
            source: Lọc theo nguồn (optional)
            limit: Số lượng tối đa
        """
        if not self.initialized:
            return []
        
        try:
            result = self._make_request('GET', 'external_signals')
            if not result:
                return []
            
            signals = []
            for key, value in result.items():
                if isinstance(value, dict):
                    value['id'] = key
                    
                    # Filter by source if specified
                    if source and value.get('source') != source:
                        continue
                    
                    signals.append(value)
            
            # Sort by timestamp desc
            signals.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return signals[:limit]
            
        except Exception as e:
            return []
    
    def update_signal_result(self, signal_id: str, result: str, pips: float = 0):
        """
        Cập nhật kết quả của tín hiệu (WIN/LOSS)
        
        Args:
            signal_id: ID của signal
            result: 'WIN' hoặc 'LOSS'
            pips: Số pip lời/lỗ
        """
        if not self.initialized or not signal_id:
            return
        
        update_data = {
            'status': result,
            'pips_result': pips,
            'closed_at': datetime.now().isoformat()
        }
        
        self._make_request('PATCH', f'external_signals/{signal_id}', update_data)
    
    def get_signal_stats(self, source: str = None) -> Dict:
        """
        Thống kê WIN/LOSS của tín hiệu
        
        Args:
            source: Lọc theo nguồn (optional)
        """
        signals = self.get_external_signals(source=source, limit=100)
        
        wins = sum(1 for s in signals if s.get('status') == 'WIN')
        losses = sum(1 for s in signals if s.get('status') == 'LOSS')
        pending = sum(1 for s in signals if s.get('status') == 'PENDING')
        total_pips = sum(s.get('pips_result', 0) for s in signals)
        
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        return {
            'total': len(signals),
            'wins': wins,
            'losses': losses,
            'pending': pending,
            'win_rate': round(win_rate, 1),
            'total_pips': round(total_pips, 1)
        }


# Quick test
if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv()
    
    db_url = os.getenv("FIREBASE_DATABASE_URL")
    api_key = os.getenv("FIREBASE_API_KEY")
    
    if db_url:
        print("🔥 Testing Firebase REST API...")
        fb = FirebaseService(db_url, api_key)
        
        if fb.initialized:
            # Test save signal
            test_signal = {
                'action': 'BUY',
                'entry': 2620.50,
                'stoploss': 2612.00,
                'takeprofit': 2638.00,
                'confidence': 75,
                'wyckoff_phase': 'ACCUMULATION',
                'event_detected': 'SPRING'
            }
            
            signal_id = fb.save_signal(test_signal)
            print(f"✅ Saved signal with ID: {signal_id}")
            
            # Test get history
            history = fb.get_trade_history(5)
            print(f"📊 Recent trades: {len(history)}")
            
            # Test capital
            capital = fb.get_capital()
            print(f"💰 Capital: ${capital}")
            
            # Test stats
            stats = fb.get_daily_stats()
            print(f"📈 Daily stats: {stats}")
        else:
            print("⚠️ Using local storage fallback")
    else:
        print("⚠️ FIREBASE_DATABASE_URL not set")
