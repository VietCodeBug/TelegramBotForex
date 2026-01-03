"""
Telegram Bot v2.0 - Command Handler
Hỗ trợ các lệnh tương tác: /start, /check, /von, /risk, /mode, /history, /status, /stop
"""
import telebot
from telebot import types
from typing import Dict, Optional, Callable
from datetime import datetime
import threading


class TelegramCommandBot:
    """
    Telegram Bot với các commands tương tác
    """
    
    COMMANDS = {
        'start': '🚀 Khởi động và xem hướng dẫn',
        'check': '🔍 Phân tích thị trường NGAY LẬP TỨC',
        'von': '💰 Cập nhật vốn (VD: /von 1000)',
        'risk': '⚠️ Chỉnh % rủi ro (VD: /risk 2)',
        'mode': '⚙️ Chỉnh chế độ (Scalping/Swing)',
        'history': '📜 Xem 5 tín hiệu gần nhất',
        'status': '📊 Kiểm tra trạng thái Bot & Cấu hình',
        'stop': '🛑 Tạm dừng Bot (Khi có tin mạnh)',
        'news': '📰 Tin tức kinh tế hôm nay',
        'tintuc': '📃 Lấy tin tức + dịch sang tiếng Việt',
        'signals': '📡 Xem tín hiệu từ các kênh Telegram',
        'stats': '📊 Thống kê WIN/LOSS của các kênh',
        'crawlnews': '📰 Crawl tin tức mới từ kênh Telegram'
    }
    
    def __init__(self, token: str, chat_id: str, firebase_service=None):
        """
        Args:
            token: Telegram Bot Token
            chat_id: Default chat ID để gửi tin
            firebase_service: FirebaseService instance để lưu config
        """
        self.token = token
        self.chat_id = chat_id
        self.firebase = firebase_service
        self.bot = telebot.TeleBot(token)
        self.is_paused = False
        
        # Callbacks cho các actions
        self.on_check_market: Optional[Callable] = None
        self.on_get_status: Optional[Callable] = None
        self.on_get_history: Optional[Callable] = None
        self.on_get_tintuc: Optional[Callable] = None  # Tin tức tiếng Việt
        self.on_get_news: Optional[Callable] = None
        self.on_get_signals: Optional[Callable] = None  # Tín hiệu từ kênh
        self.on_get_stats: Optional[Callable] = None  # Thống kê tín hiệu
        self.on_crawl_news: Optional[Callable] = None  # Crawl tin tức từ kênh
        
        # User configs (từ Firebase hoặc local)
        self.user_config = {
            'capital': 100,
            'risk_percent': 2,
            'mode': 'scalping',
        }
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Đăng ký các command handlers"""
        
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self._cmd_start(message)
        
        @self.bot.message_handler(commands=['check'])
        def handle_check(message):
            self._cmd_check(message)
        
        @self.bot.message_handler(commands=['von'])
        def handle_von(message):
            self._cmd_von(message)
        
        @self.bot.message_handler(commands=['risk'])
        def handle_risk(message):
            self._cmd_risk(message)
        
        @self.bot.message_handler(commands=['mode'])
        def handle_mode(message):
            self._cmd_mode(message)
        
        @self.bot.message_handler(commands=['history'])
        def handle_history(message):
            self._cmd_history(message)
        
        @self.bot.message_handler(commands=['status'])
        def handle_status(message):
            self._cmd_status(message)
        
        @self.bot.message_handler(commands=['stop'])
        def handle_stop(message):
            self._cmd_stop(message)
        
        @self.bot.message_handler(commands=['news'])
        def handle_news(message):
            self._cmd_news(message)
        
        @self.bot.message_handler(commands=['help'])
        def handle_help(message):
            self._cmd_start(message)  # Same as start
        
        @self.bot.message_handler(commands=['tintuc'])
        def handle_tintuc(message):
            self._cmd_tintuc(message)
        
        @self.bot.message_handler(commands=['signals'])
        def handle_signals(message):
            self._cmd_signals(message)
        
        @self.bot.message_handler(commands=['stats'])
        def handle_stats(message):
            self._cmd_stats(message)
        
        @self.bot.message_handler(commands=['crawlnews'])
        def handle_crawlnews(message):
            self._cmd_crawlnews(message)
    
    def _cmd_crawlnews(self, message):
        """Handler cho /crawlnews - Crawl tin tức từ kênh Telegram"""
        self._send_message("📰 Đang crawl tin tức từ các kênh Telegram...", message.chat.id)
        
        if self.on_crawl_news:
            try:
                result = self.on_crawl_news()
                self._send_message(result, message.chat.id)
            except Exception as e:
                self._send_message(f"❌ Lỗi: {str(e)[:100]}", message.chat.id)
        else:
            self._send_message("⚠️ Chức năng chưa được kết nối.", message.chat.id)
    
    def _cmd_start(self, message):
        """Handler cho /start"""
        welcome = f"""
🏅 *WYCKOFF SMART BOT v2.0*
━━━━━━━━━━━━━━━━━━━━━

Chào mừng bạn đến với hệ thống giao dịch XAU/USD thông minh!

📊 *Phương pháp:* Wyckoff + Smart Money
🤖 *AI:* Gemini 2.5 Pro
💰 *Vốn hiện tại:* ${self.user_config['capital']}
⚠️ *Rủi ro:* {self.user_config['risk_percent']}%

━━━━━━━━━━━━━━━━━━━━━
📋 *DANH SÁCH LỆNH*
━━━━━━━━━━━━━━━━━━━━━

/check - 🔍 Phân tích thị trường NGAY
/von <số> - 💰 Cập nhật vốn (VD: /von 1000)
/risk <số> - ⚠️ % rủi ro (VD: /risk 2)
/mode - ⚙️ Đổi chế độ Scalping/Swing
/history - 📜 5 tín hiệu gần nhất
/status - 📊 Trạng thái Bot
/news - 📰 Tin tức kinh tế
/tintuc - 📃 Tin tức + Dịch tiếng Việt
/signals - 📡 Tín hiệu từ kênh Telegram
/crawlnews - 📰 Crawl tin tức mới
/stats - 📊 Thống kê tín hiệu
/stop - 🛑 Tạm dừng Bot

━━━━━━━━━━━━━━━━━━━━━
📡 *KÊNH TÍN HIỆU:*
@ducforex6789 | @vnscalping | @XAUUSDINSIDER_FX

📰 *KÊNH TIN TỨC:*
@lichkinhte

💡 Bot sẽ tự động gửi tín hiệu và tin tức quan trọng!
"""
        self._send_message(welcome, message.chat.id)
    
    def _cmd_check(self, message):
        """Handler cho /check - Phân tích ngay"""
        self._send_message("🔍 *Đang phân tích thị trường...*\n⏳ Vui lòng chờ...", message.chat.id)
        
        if self.on_check_market:
            try:
                result = self.on_check_market()
                if result:
                    self.send_wyckoff_signal(result)
                else:
                    self._send_message("❌ Không thể phân tích. Thử lại sau.", message.chat.id)
            except Exception as e:
                self._send_message(f"❌ Lỗi: {str(e)[:100]}", message.chat.id)
        else:
            self._send_message("⚠️ Chức năng phân tích chưa được kết nối.", message.chat.id)
    
    def _cmd_von(self, message):
        """Handler cho /von - Cập nhật vốn"""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                self._send_message("❌ Sử dụng: /von <số tiền>\nVD: /von 1000", message.chat.id)
                return
            
            amount = float(parts[1])
            if amount <= 0:
                self._send_message("❌ Số tiền phải lớn hơn 0!", message.chat.id)
                return
            
            old_capital = self.user_config['capital']
            self.user_config['capital'] = amount
            
            # Save to Firebase
            if self.firebase:
                self.firebase.update_capital(amount)
            
            self._send_message(f"""
💰 *CẬP NHẬT VỐN THÀNH CÔNG*
━━━━━━━━━━━━━━━━━━━━━
💵 Vốn cũ: ${old_capital}
💵 Vốn mới: ${amount}
━━━━━━━━━━━━━━━━━━━━━
""", message.chat.id)
            
        except ValueError:
            self._send_message("❌ Số tiền không hợp lệ!\nVD: /von 1000", message.chat.id)
    
    def _cmd_risk(self, message):
        """Handler cho /risk - Cập nhật % rủi ro"""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                self._send_message("❌ Sử dụng: /risk <phần trăm>\nVD: /risk 2", message.chat.id)
                return
            
            percent = float(parts[1])
            if percent <= 0 or percent > 10:
                self._send_message("❌ Rủi ro phải từ 0.1% đến 10%!", message.chat.id)
                return
            
            old_risk = self.user_config['risk_percent']
            self.user_config['risk_percent'] = percent
            
            # Save to Firebase
            if self.firebase:
                self.firebase.update_risk(percent)
            
            self._send_message(f"""
⚠️ *CẬP NHẬT RỦI RO THÀNH CÔNG*
━━━━━━━━━━━━━━━━━━━━━
📉 Rủi ro cũ: {old_risk}%
📈 Rủi ro mới: {percent}%
━━━━━━━━━━━━━━━━━━━━━
💡 Với vốn ${self.user_config['capital']}, mỗi lệnh rủi ro ${self.user_config['capital'] * percent / 100:.2f}
""", message.chat.id)
            
        except ValueError:
            self._send_message("❌ Số không hợp lệ!\nVD: /risk 2", message.chat.id)
    
    def _cmd_mode(self, message):
        """Handler cho /mode - Đổi chế độ trading"""
        current = self.user_config['mode']
        
        # Toggle mode
        new_mode = 'swing' if current == 'scalping' else 'scalping'
        self.user_config['mode'] = new_mode
        
        mode_info = {
            'scalping': ('⚡ SCALPING', 'M5-M15', 'Ngắn hạn, nhiều lệnh'),
            'swing': ('🌊 SWING', 'H1-H4', 'Dài hạn, ít lệnh hơn')
        }
        
        info = mode_info[new_mode]
        
        self._send_message(f"""
⚙️ *ĐỔI CHẾ ĐỘ TRADING*
━━━━━━━━━━━━━━━━━━━━━
📊 Chế độ: {info[0]}
⏰ Timeframe: {info[1]}
📝 Mô tả: {info[2]}
━━━━━━━━━━━━━━━━━━━━━
""", message.chat.id)
    
    def _cmd_history(self, message):
        """Handler cho /history - Xem lịch sử"""
        if self.on_get_history:
            try:
                history = self.on_get_history()
                if history:
                    self._send_message(history, message.chat.id)
                else:
                    self._send_message("📜 Chưa có tín hiệu nào.", message.chat.id)
            except Exception as e:
                self._send_message(f"❌ Lỗi: {str(e)[:100]}", message.chat.id)
        else:
            self._send_message("📜 Chưa có lịch sử giao dịch.", message.chat.id)
    
    def _cmd_status(self, message):
        """Handler cho /status - Trạng thái bot"""
        status_icon = "🟢" if not self.is_paused else "🔴"
        status_text = "ĐANG CHẠY" if not self.is_paused else "TẠM DỪNG"
        
        mode_icon = "⚡" if self.user_config['mode'] == 'scalping' else "🌊"
        
        status_msg = f"""
📊 *TRẠNG THÁI BOT*
━━━━━━━━━━━━━━━━━━━━━

{status_icon} Status: *{status_text}*
🤖 AI: Gemini 2.5 Pro
📈 Symbol: XAU/USD

━━━━━━━━━━━━━━━━━━━━━
💰 *CẤU HÌNH*
━━━━━━━━━━━━━━━━━━━━━
💵 Vốn: ${self.user_config['capital']}
⚠️ Rủi ro: {self.user_config['risk_percent']}%
{mode_icon} Mode: {self.user_config['mode'].upper()}

━━━━━━━━━━━━━━━━━━━━━
⏰ Thời gian: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
        
        if self.on_get_status:
            try:
                extra = self.on_get_status()
                if extra:
                    status_msg += f"\n{extra}"
            except:
                pass
        
        self._send_message(status_msg, message.chat.id)
    
    def _cmd_stop(self, message):
        """Handler cho /stop - Toggle pause"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            msg = """
🛑 *BOT ĐÃ TẠM DỪNG*
━━━━━━━━━━━━━━━━━━━━━
Bot sẽ KHÔNG gửi tín hiệu tự động.
Sử dụng /stop để tiếp tục.
"""
        else:
            msg = """
🟢 *BOT ĐÃ TIẾP TỤC*
━━━━━━━━━━━━━━━━━━━━━
Bot sẽ tiếp tục gửi tín hiệu.
"""
        
        self._send_message(msg, message.chat.id)
    
    def _cmd_news(self, message):
        """Handler cho /news - Tin tức"""
        if self.on_get_news:
            try:
                news = self.on_get_news()
                self._send_message(news, message.chat.id)
            except Exception as e:
                self._send_message(f"❌ Lỗi lấy tin tức: {str(e)[:100]}", message.chat.id)
        else:
            self._send_message("📰 Chức năng tin tức chưa được kết nối.", message.chat.id)
    
    def _cmd_tintuc(self, message):
        """Handler cho /tintuc - Tin tức tiếng Việt"""
        self._send_message("📃 *Đang lấy và dịch tin tức...*\n⏳ Vui lòng chờ...", message.chat.id)
        
        if self.on_get_tintuc:
            try:
                tintuc = self.on_get_tintuc()
                self._send_message(tintuc, message.chat.id)
            except Exception as e:
                self._send_message(f"❌ Lỗi: {str(e)[:100]}", message.chat.id)
        else:
            self._send_message("📃 Chức năng tin tức tiếng Việt chưa được kết nối.", message.chat.id)
    
    def _cmd_signals(self, message):
        """Handler cho /signals - Tín hiệu từ các kênh Telegram"""
        self._send_message("📡 *Đang lấy tín hiệu từ các kênh...*\n⏳ Vui lòng chờ...", message.chat.id)
        
        if self.on_get_signals:
            try:
                signals = self.on_get_signals()
                self._send_message(signals, message.chat.id)
            except Exception as e:
                self._send_message(f"❌ Lỗi: {str(e)[:100]}", message.chat.id)
        else:
            self._send_message("📡 Chức năng tín hiệu chưa được kết nối.", message.chat.id)
    
    def _cmd_stats(self, message):
        """Handler cho /stats - Thống kê WIN/LOSS"""
        self._send_message("📊 *Đang lấy thống kê...*\n⏳ Vui lòng chờ...", message.chat.id)
        
        if self.on_get_stats:
            try:
                stats = self.on_get_stats()
                self._send_message(stats, message.chat.id)
            except Exception as e:
                self._send_message(f"❌ Lỗi: {str(e)[:100]}", message.chat.id)
        else:
            self._send_message("📊 Chức năng thống kê chưa được kết nối.", message.chat.id)
    
    def send_news_alert(self, news_event, minutes_until: int):
        """
        Gửi cảnh báo tin tức quan trọng (Báo Thức)
        
        Args:
            news_event: NewsEvent object
            minutes_until: Số phút còn lại đến khi tin ra
        """
        alert_msg = f"""
🚨🚨🚨 *CẢNH BÁO TIN QUAN TRỌNG* 🚨🚨🚨
━━━━━━━━━━━━━━━━━━━━━

⏰ *Còn {minutes_until} phút nữa có tin!*

📰 *{news_event.event}*
💱 Currency: {news_event.currency}
🔴 Impact: {news_event.impact}

━━━━━━━━━━━━━━━━━━━━━
⚠️ *KHUYẾN CÁO:*
• Không vào lệnh mới
• Cân nhắc đóng lệnh đang có
• Chờ tin ra rồi hãy trade
━━━━━━━━━━━━━━━━━━━━━

💡 Bot đã TỰ ĐỘNG TẠM DỪNG!
Sử dụng /stop để tiếp tục sau khi tin qua.
"""
        self._send_message(alert_msg)
        
        # Auto pause
        self.is_paused = True
    
    def send_analysis_result(self, signal: Dict, price: float = None):
        """
        Gửi kết quả phân tích (kể cả WAIT) về Telegram
        """
        action = signal.get('action', 'WAIT')
        confidence = signal.get('confidence', 0)
        phase = signal.get('wyckoff_phase', 'N/A')
        event = signal.get('event_detected', 'NONE')
        reason = signal.get('reason', 'N/A')
        
        # Icons by action
        if action == 'BUY':
            icon = "🟢"
            action_text = "LONG BUY"
        elif action == 'SELL':
            icon = "🔴" 
            action_text = "SHORT SELL"
        else:
            icon = "⏳"
            action_text = "WAIT"
        
        price_text = f"${price:.2f}" if price else "N/A"
        
        msg = f"""
{icon} *KẾT QUẢ PHÂN TÍCH* {icon}
━━━━━━━━━━━━━━━━━━━━━

💰 *Giá XAU/USD:* {price_text}
🎯 *Hành động:* {action_text}
📊 *Độ tin cậy:* {confidence}%

━━━━━━━━━━━━━━━━━━━━━
🔮 *WYCKOFF*
━━━━━━━━━━━━━━━━━━━━━
📈 Phase: {phase}
⚡ Event: {event}

━━━━━━━━━━━━━━━━━━━━━
💡 *LÝ DO:*
{reason}

━━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
        self._send_message(msg)
    
    def send_message(self, text: str, chat_id: str = None):
        """Gửi tin nhắn - Public method"""
        self._send_message(text, chat_id)
    
    def _send_message(self, text: str, chat_id: str = None):
        """Gửi tin nhắn - Internal method (NO Markdown to avoid parse errors)"""
        try:
            self.bot.send_message(
                chat_id or self.chat_id,
                text
                # No parse_mode - plain text only to avoid errors
            )
        except Exception as e:
            print(f"❌ Telegram send error: {e}")
            # Fallback: try sending error message without formatting
            try:
                self.bot.send_message(
                    chat_id or self.chat_id,
                    f"Error: {str(e)[:100]}"
                )
            except:
                pass
    
    def send_wyckoff_signal(self, signal: Dict):
        """
        Gửi tín hiệu Wyckoff đẹp
        """
        if self.is_paused:
            print("⏸️ Bot paused, not sending signal")
            return
        
        action = signal.get('action', 'WAIT')
        
        if action == 'WAIT':
            return  # Không gửi tín hiệu WAIT
        
        # Icons
        if action == 'BUY':
            action_icon = "🟢🟢🟢"
            action_text = "LONG BUY"
        else:
            action_icon = "🔴🔴🔴"
            action_text = "SHORT SELL"
        
        # Calculate R:R
        entry = signal.get('entry', 0)
        sl = signal.get('stoploss', 0)
        tp = signal.get('takeprofit', 0)
        
        if entry and sl and tp:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr_ratio = reward / risk if risk > 0 else 0
        else:
            rr_ratio = 0
        
        # Wyckoff/SMC info
        phase = signal.get('wyckoff_phase', 'N/A')
        event = signal.get('event_detected', 'NONE')
        smc = signal.get('smc_trigger', 'NONE')
        
        # Calculate lot size
        capital = self.user_config['capital']
        risk_pct = self.user_config['risk_percent']
        risk_amount = capital * risk_pct / 100
        pip_value = 0.1  # For XAUUSD
        pips = abs(entry - sl) if entry and sl else 10
        lot_size = risk_amount / (pips * pip_value * 100) if pips > 0 else 0.01
        
        message = f"""
{action_icon} *WYCKOFF SIGNAL* {action_icon}
━━━━━━━━━━━━━━━━━━━━━

📈 *{action_text} XAU/USD*

💰 Entry: *${entry:.2f}* 
🛑 Stop Loss: *${sl:.2f}*
🎯 Take Profit: *${tp:.2f}*

━━━━━━━━━━━━━━━━━━━━━
📊 *WYCKOFF ANALYSIS*
━━━━━━━━━━━━━━━━━━━━━
🔮 Phase: {phase}
⚡ Event: {event}
🎯 SMC: {smc}

━━━━━━━━━━━━━━━━━━━━━
📊 Risk/Reward: *1:{rr_ratio:.1f}*
📈 Confidence: *{signal.get('confidence', 0)}%*
📦 Lot Size: *{lot_size:.2f}*
💵 Risk: *${risk_amount:.2f}* ({risk_pct}%)

━━━━━━━━━━━━━━━━━━━━━
💡 *{signal.get('reason', 'N/A')}*

⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
        
        self._send_message(message)
        
        # Log to Firebase
        if self.firebase:
            self.firebase.save_signal(signal, executed=False)
    
    def send_alert(self, message: str, alert_type: str = "INFO"):
        """Gửi cảnh báo"""
        icons = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }
        icon = icons.get(alert_type, "📢")
        self._send_message(f"{icon} {message}")
    
    def start_polling(self, threaded: bool = True):
        """
        Bắt đầu lắng nghe commands
        
        Args:
            threaded: Chạy trong thread riêng (không block main)
        """
        print("🤖 Telegram Bot started polling...")
        
        if threaded:
            thread = threading.Thread(target=self._poll_forever, daemon=True)
            thread.start()
        else:
            self._poll_forever()
    
    def _poll_forever(self):
        """Polling loop with error 409 handling"""
        import time as time_module
        retry_delay = 5
        max_delay = 60
        
        while True:
            try:
                self.bot.infinity_polling(timeout=60, long_polling_timeout=5)
            except Exception as e:
                error_msg = str(e)
                
                if "409" in error_msg or "Conflict" in error_msg:
                    # Error 409: Another bot instance running
                    print(f"⚠️ Bot conflict detected. Waiting {retry_delay}s...")
                    time_module.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, max_delay)
                else:
                    print(f"❌ Polling error: {error_msg[:100]}")
                    time_module.sleep(5)


# Quick test
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if token and chat_id:
        bot = TelegramCommandBot(token, chat_id)
        
        # Set up mock callbacks
        bot.on_check_market = lambda: {
            'action': 'BUY',
            'wyckoff_phase': 'ACCUMULATION',
            'event_detected': 'SPRING',
            'smc_trigger': 'LIQUIDITY_SWEEP',
            'entry': 2620.50,
            'stoploss': 2612.00,
            'takeprofit': 2638.00,
            'confidence': 78,
            'reason': 'Phát hiện Spring + Quét thanh khoản tại vùng hỗ trợ'
        }
        
        print("Starting bot...")
        bot.start_polling(threaded=False)
    else:
        print("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID in .env")
