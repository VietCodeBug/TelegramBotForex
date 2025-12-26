"""
═══════════════════════════════════════════════════════════════════
    WYCKOFF SMART BOT v2.0 - Main Entry Point
    Trading Bot for XAU/USD with Wyckoff + SMC Analysis
═══════════════════════════════════════════════════════════════════
"""
import time
import sys
import os
from datetime import datetime, timedelta
import threading

# Load environment first
from dotenv import load_dotenv
load_dotenv()

# Flask for health check (Render Web Service)
from flask import Flask
app = Flask(__name__)

@app.route('/')
def health():
    return "🏅 Wyckoff Bot is running!"

@app.route('/health')
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

def run_flask():
    """Run Flask in background thread"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, threaded=True)

# Import config
from config import (
    GEMINI_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
    FIREBASE_CONFIG, SYMBOL, TIMEFRAME, N_CANDLES,
    USER_CAPITAL, RISK_PERCENT, LOOP_INTERVAL, ERROR_RETRY_INTERVAL
)

# Import services
from services.scraper import RealtimeGoldScraper
from services.indicators import calculate_indicators, get_indicator_summary
from services.patterns import detect_patterns, get_pattern_summary
from services.wyckoff import WyckoffAnalyzer
from services.smc import SMCAnalyzer
from services.ai_engine import WyckoffAIEngine
from services.telegram_bot import TelegramCommandBot
from services.risk_manager import RiskManager
from services.firebase_service import FirebaseService
from services.news_crawler import NewsCrawler


def display_banner():
    """Hiển thị banner khởi động"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  ██╗    ██╗██╗   ██╗ ██████╗██╗  ██╗ ██████╗ ███████╗███████╗║
║  ██║    ██║╚██╗ ██╔╝██╔════╝██║ ██╔╝██╔═══██╗██╔════╝██╔════╝║
║  ██║ █╗ ██║ ╚████╔╝ ██║     █████╔╝ ██║   ██║█████╗  █████╗  ║
║  ██║███╗██║  ╚██╔╝  ██║     ██╔═██╗ ██║   ██║██╔══╝  ██╔══╝  ║
║  ╚███╔███╔╝   ██║   ╚██████╗██║  ██╗╚██████╔╝██║     ██║     ║
║   ╚══╝╚══╝    ╚═╝    ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝     ║
║                                                              ║
║      🏅 SMART TRADING BOT v2.0 - Wyckoff + SMC 🏅            ║
║                                                              ║
║  Symbol: XAU/USD    AI: Gemini 2.5 Pro    Method: Wyckoff    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


class WyckoffBot:
    """
    Main Bot Class - Tích hợp tất cả components
    """
    
    def __init__(self):
        """Khởi tạo tất cả components"""
        print("\n🔧 KHỞI TẠO HỆ THỐNG...")
        print("-" * 50)
        
        # 1. Data Fetcher
        print("📊 Initializing Data Fetcher...", end=" ")
        self.fetcher = RealtimeGoldScraper()
        print("✅")
        
        # 2. Wyckoff Analyzer
        print("🔮 Initializing Wyckoff Analyzer...", end=" ")
        self.wyckoff = WyckoffAnalyzer()
        print("✅")
        
        # 3. SMC Analyzer
        print("🎯 Initializing SMC Analyzer...", end=" ")
        self.smc = SMCAnalyzer()
        print("✅")
        
        # 4. AI Engine
        print("🧠 Initializing Wyckoff AI Engine...", end=" ")
        self.ai = WyckoffAIEngine(GEMINI_API_KEY)
        print("✅")
        
        # 5. News Crawler
        print("📰 Initializing News Crawler...", end=" ")
        self.news = NewsCrawler(GEMINI_API_KEY)
        print("✅")
        
        # 6. Risk Manager
        print("💰 Initializing Risk Manager...", end=" ")
        self.risk_mgr = RiskManager(capital=USER_CAPITAL, risk_percent=RISK_PERCENT)
        print(f"✅ (Capital: ${USER_CAPITAL})")
        
        # 7. Firebase
        print("🔥 Initializing Firebase...", end=" ")
        self.firebase = None
        if FIREBASE_CONFIG.get('databaseURL'):
            self.firebase = FirebaseService(FIREBASE_CONFIG['databaseURL'])
            print("✅")
        else:
            print("⏭️ Skipped")
        
        # 8. Telegram Bot
        print("📱 Initializing Telegram Bot...", end=" ")
        self.telegram = TelegramCommandBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, self.firebase)
        self._setup_telegram_callbacks()
        print("✅")
        
        print("-" * 50)
        print("✅ TẤT CẢ COMPONENTS ĐÃ SẴN SÀNG!\n")
    
    def _setup_telegram_callbacks(self):
        """Thiết lập callbacks cho Telegram commands"""
        self.telegram.on_check_market = self.analyze_market
        self.telegram.on_get_status = self.get_status_text
        self.telegram.on_get_history = self.get_history_text
        self.telegram.on_get_news = self.get_news_text
        self.telegram.on_get_tintuc = self.get_tintuc_text  # Tin tức tiếng Việt
    
    def analyze_market(self) -> dict:
        """
        Phân tích thị trường đầy đủ với Wyckoff + SMC
        
        Returns:
            Signal dict
        """
        try:
            # 1. Fetch data
            print("   [2/4] 📥 Đang lấy dữ liệu thị trường...")
            df = self.fetcher.get_candles(n_bars=N_CANDLES, interval='15m')
            
            if df is None or df.empty:
                print("   ❌ Không lấy được dữ liệu!")
                return None
            
            # 2. Get realtime price
            rt = self.fetcher.get_realtime_price()
            print(f"   💰 Giá hiện tại: ${rt.get('price', 'N/A')}")
            
            # 3. Technical indicators
            print("   [3/4] 📈 Đang tính toán indicators...")
            df = calculate_indicators(df)
            indicators = get_indicator_summary(df)
            
            # 4. Wyckoff Analysis
            print("   🔮 Phân tích Wyckoff...")
            wyckoff_result = self.wyckoff.analyze(df)
            
            # 5. SMC Analysis
            print("   🎯 Phân tích SMC...")
            smc_result = self.smc.analyze(df)
            
            # 6. Pattern Detection
            print("🕯️ Pattern Detection...")
            patterns = detect_patterns(df)
            pattern_text = get_pattern_summary(df)
            
            # 7. News Context
            print("📰 Checking news...")
            should_pause, upcoming_news = self.news.should_pause_trading()
            news_context = None
            
            if should_pause and upcoming_news:
                news_context = f"⚠️ CẢNH BÁO: Tin quan trọng sắp ra - {upcoming_news.event}"
            
            # 8. Prepare market data for AI
            market_data = self.fetcher.format_for_ai(df)
            full_context = f"{market_data}\n\n{pattern_text}"
            
            # 9. AI Analysis
            print("🤖 AI analyzing...")
            signal = self.ai.analyze(
                market_data=full_context,
                indicators=indicators,
                wyckoff_analysis=wyckoff_result,
                smc_analysis=smc_result,
                news_context=news_context
            )
            
            # 10. Add lot size calculation
            if signal.get('action') != 'WAIT':
                entry = signal.get('entry', 0)
                sl = signal.get('stoploss', 0)
                
                if entry and sl:
                    trade_info = self.risk_mgr.calculate_lot_size(entry, sl)
                    signal['lot_size'] = trade_info.lot_size
                    signal['risk_amount'] = trade_info.risk_amount
            
            # Log
            print(f"✅ Analysis complete: {signal.get('action', 'WAIT')}")
            
            return signal
            
        except Exception as e:
            print(f"❌ Analysis error: {e}")
            return None
    
    def get_status_text(self) -> str:
        """Lấy thông tin status bổ sung"""
        try:
            rt = self.fetcher.get_realtime_price()
            price = rt.get('price', 'N/A')
            source = rt.get('source', 'N/A')
            
            return f"""
━━━━━━━━━━━━━━━━━━━━━
📊 *MARKET INFO*
━━━━━━━━━━━━━━━━━━━━━
💰 Price: ${price}
📡 Source: {source}
"""
        except:
            return ""
    
    def get_history_text(self) -> str:
        """Lấy lịch sử giao dịch"""
        if not self.firebase:
            return "📜 Firebase chưa được kết nối."
        
        try:
            history = self.firebase.get_trade_history(limit=5)
            if not history:
                return "📜 Chưa có tín hiệu nào."
            
            lines = ["📜 *5 TÍN HIỆU GẦN NHẤT*", "━━━━━━━━━━━━━━━━━━━━━"]
            
            for trade in history:
                action = trade.get('action', 'N/A')
                icon = "🟢" if action == 'BUY' else "🔴" if action == 'SELL' else "⚪"
                time_str = trade.get('timestamp', 'N/A')[:16]
                entry = trade.get('entry', 'N/A')
                conf = trade.get('confidence', 0)
                event = trade.get('event_detected', 'N/A')
                
                lines.append(f"{icon} {time_str}")
                lines.append(f"   {action} @ ${entry} ({conf}%)")
                lines.append(f"   Event: {event}")
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Lỗi: {str(e)[:50]}"
    
    def get_news_text(self) -> str:
        """Lấy tin tức"""
        return self.news.get_news_summary()
    
    def get_tintuc_text(self) -> str:
        """
        Lấy tin tức và dịch sang tiếng Việt
        """
        try:
            events = self.news.get_high_impact_news('USD')
            
            if not events:
                return "📃 *TIN TỨC KINH TẾ*\n\n✅ Không có tin quan trọng hôm nay."
            
            lines = [
                "📃 *TIN TỨC KINH TẾ (Tiếng Việt)*",
                "━━━━━━━━━━━━━━━━━━━━━",
                ""
            ]
            
            for event in events[:8]:
                impact_icon = "🔴" if event.impact == 'HIGH' else "🟡"
                name_vi = event.title_vi if event.title_vi else event.event
                
                lines.append(f"{impact_icon} *{event.time}* - {event.currency}")
                lines.append(f"   📰 {name_vi}")
                
                if event.forecast:
                    lines.append(f"   📊 Dự báo: {event.forecast} | Trước: {event.previous}")
                
                lines.append("")
            
            lines.append("━━━━━━━━━━━━━━━━━━━━━")
            lines.append("⚠️ *Lưu ý:* Không vào lệnh trước tin 🔴30 phút!")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Lỗi lấy tin tức: {str(e)[:50]}"
    
    def run_analysis_loop(self):
        """Vòng lặp phân tích chính"""
        loop_count = 0
        
        while True:
            loop_count += 1
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n{'='*60}")
            print(f"🔄 LOOP #{loop_count} | {current_time}")
            print(f"{'='*60}")
            
            # Check if paused
            if self.telegram.is_paused:
                print("⏸️ Bot is PAUSED. Use /stop to resume.")
                time.sleep(LOOP_INTERVAL)
                continue
            
            try:
                # Check daily limit
                can_trade, limit_msg = self.risk_mgr.check_daily_limit()
                if not can_trade:
                    print(limit_msg)
                    self.telegram.send_alert(limit_msg, "WARNING")
                    time.sleep(LOOP_INTERVAL)
                    continue
                
                # 🚨 NEWS ALERT - Báo Thức khi có tin quan trọng sắp ra
                should_pause, upcoming_news = self.news.should_pause_trading(minutes_before=15)
                if should_pause and upcoming_news:
                    # Tính số phút còn lại
                    try:
                        event_time = datetime.strptime(upcoming_news.time, "%H:%M").replace(
                            year=datetime.now().year,
                            month=datetime.now().month,
                            day=datetime.now().day
                        )
                        minutes_until = int((event_time - datetime.now()).total_seconds() / 60)
                        if minutes_until > 0:
                            print(f"\n🚨 CẢNH BÁO: Tin {upcoming_news.event} trong {minutes_until} phút!")
                            self.telegram.send_news_alert(upcoming_news, minutes_until)
                            time.sleep(LOOP_INTERVAL)
                            continue
                    except:
                        pass
                
                # Analyze market
                print("🔍 [1/4] Bắt đầu phân tích thị trường...")
                signal = self.analyze_market()
                
                if signal:
                    action = signal.get('action', 'WAIT')
                    confidence = signal.get('confidence', 0)
                    
                    print(f"\n✅ [4/4] PHÂN TÍCH XONG!")
                    print(f"━━━━━━━━━━━━━━━━━━━━━")
                    print(f"   🎯 Action: {action}")
                    print(f"   📊 Confidence: {confidence}%")
                    print(f"   ⚡ Event: {signal.get('event_detected', 'NONE')}")
                    print(f"   💡 Reason: {signal.get('reason', 'N/A')[:80]}...")
                    print(f"━━━━━━━━━━━━━━━━━━━━━")
                    
                    # Get current price for display
                    rt = self.fetcher.get_realtime_price()
                    current_price = rt.get('price') if rt else None
                    
                    # Always send analysis result to Telegram
                    print("\n📤 Đang gửi kết quả về Telegram...")
                    self.telegram.send_analysis_result(signal, current_price)
                    print("✅ Đã gửi về Telegram!")
                    
                    # If BUY/SELL with high confidence, also send full signal
                    if action in ['BUY', 'SELL'] and confidence >= 50:
                        print("🎯 Gửi TÍN HIỆU ĐẦY ĐỦ về Telegram...")
                        self.telegram.send_wyckoff_signal(signal)
                        print("✅ Đã gửi tín hiệu!")
                
                print(f"\n😴 Nghỉ {LOOP_INTERVAL//60} phút... (Loop tiếp theo lúc {(datetime.now() + timedelta(seconds=LOOP_INTERVAL)).strftime('%H:%M:%S')})")
                time.sleep(LOOP_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n\n⚠️ Bot stopped by user (Ctrl+C)")
                self.telegram.send_alert("Bot đã dừng bởi người dùng", "WARNING")
                break
                
            except Exception as e:
                error_msg = f"Error in loop #{loop_count}: {str(e)}"
                print(f"❌ {error_msg}")
                
                if self.firebase:
                    self.firebase.log_event("ERROR", error_msg)
                
                print(f"⏳ Retrying in {ERROR_RETRY_INTERVAL} seconds...")
                time.sleep(ERROR_RETRY_INTERVAL)
    
    def start(self):
        """Khởi động bot"""
        # Start Flask health server in background (for Render Web Service)
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("🌐 Health server started!")
        
        # Start Telegram polling in background
        self.telegram.start_polling(threaded=True)
        
        # Send startup message
        startup_msg = f"""
🚀 *WYCKOFF BOT STARTED!*
━━━━━━━━━━━━━━━━━━━━━
📊 Symbol: {SYMBOL}
🔮 Method: Wyckoff + SMC
🤖 AI: Gemini 2.5 Pro
💰 Capital: ${USER_CAPITAL}
⏰ Interval: {LOOP_INTERVAL//60} minutes
━━━━━━━━━━━━━━━━━━━━━
📋 Dùng /help để xem các lệnh
"""
        self.telegram.send_alert(startup_msg, "SUCCESS")
        
        # Start main loop
        self.run_analysis_loop()


def test_mode():
    """Chế độ test - chạy 1 lần"""
    print("\n🧪 RUNNING IN TEST MODE...\n")
    
    bot = WyckoffBot()
    
    print("\n" + "="*50)
    print("🔍 ANALYZING MARKET...")
    print("="*50)
    
    signal = bot.analyze_market()
    
    if signal:
        print("\n📊 ANALYSIS RESULT:")
        for k, v in signal.items():
            print(f"   {k}: {v}")
        
        # Ask to send
        print("\n" + "-"*50)
        response = input("📱 Send signal to Telegram? (y/n): ")
        if response.lower() == 'y':
            if signal.get('action') == 'WAIT':
                bot.telegram.send_alert("🧪 Test: Bot đang hoạt động!", "SUCCESS")
            else:
                bot.telegram.send_wyckoff_signal(signal)
            print("✅ Message sent!")
    else:
        print("❌ Analysis failed")
    
    # Show news
    print("\n📰 NEWS:")
    print(bot.get_news_text())


if __name__ == "__main__":
    display_banner()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_mode()
    else:
        bot = WyckoffBot()
        bot.start()
