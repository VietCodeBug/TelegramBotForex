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
    port = int(os.environ.get('PORT', 7860))  # HF Spaces uses 7860
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
from services.signal_crawler import SignalCrawler


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
        
        # 9. Signal Crawler (Telegram channels) - Truyền AI engine để phân tích
        print("📡 Initializing Signal Crawler...", end=" ")
        self.signal_crawler = SignalCrawler(self.firebase, self.ai)
        print("✅")
        
        # Track last signal check
        self.last_signal_check = None
        self.known_signals = set()  # Track đã xử lý signals nào
        self.known_news = set()  # Track tin tức đã thông báo
        self.last_news_check = None  # Thời gian check tin tức cuối
        
        print("-" * 50)
        print("✅ TẤT CẢ COMPONENTS ĐÃ SẴN SÀNG!\n")
    
    def _setup_telegram_callbacks(self):
        """Thiết lập callbacks cho Telegram commands"""
        self.telegram.on_check_market = self.analyze_market
        self.telegram.on_get_status = self.get_status_text
        self.telegram.on_get_history = self.get_history_text
        self.telegram.on_get_news = self.get_news_text
        self.telegram.on_get_tintuc = self.get_tintuc_text  # Tin tức tiếng Việt
        self.telegram.on_get_signals = self.get_signals_text  # Tín hiệu từ kênh
        self.telegram.on_get_stats = self.get_signal_stats_text  # Thống kê
        self.telegram.on_crawl_news = self.crawl_news_text  # Crawl tin tức từ kênh
    
    def crawl_news_text(self) -> str:
        """Crawl tin tức mới từ các kênh Telegram và trả về text"""
        try:
            # Crawl tin tức
            news_count = self.check_news_updates()
            
            # Format kết quả
            news_text = self.signal_crawler.format_news_for_telegram()
            
            return f"""
📰 *KẾT QUẢ CRAWL TIN TỨC*
━━━━━━━━━━━━━━━━━━

✅ Đã tìm thấy {news_count} tin tức mới quan trọng!

{news_text}

━━━━━━━━━━━━━━━━━━
💡 Tin tức HIGH impact sẽ được tự động thông báo!
"""
        except Exception as e:
            return f"❌ Lỗi crawl tin tức: {str(e)[:100]}"
    
    def check_external_signals(self):
        """
        Kiểm tra tín hiệu mới từ các kênh Telegram
        Nếu có tín hiệu mới → AI phân tích (text + ảnh chart) → Gửi thông báo
        """
        try:
            signals = self.signal_crawler.crawl_all_channels()
            
            new_signals = []
            for sig in signals:
                # Tạo unique key để track
                sig_key = f"{sig.source}_{sig.action}_{sig.entry}"
                
                if sig_key not in self.known_signals:
                    self.known_signals.add(sig_key)
                    new_signals.append(sig)
            
            # Xử lý tín hiệu mới
            for sig in new_signals[:3]:  # Xử lý tối đa 3 tín hiệu cùng lúc
                print(f"📡 New signal: {sig.action} {sig.symbol} @ {sig.entry} from @{sig.source}")
                
                # Lấy giá hiện tại
                rt = self.fetcher.get_realtime_price()
                current_price = rt.get('price') if rt else None
                
                # 1️⃣ AI phân tích TEXT tín hiệu
                sig = self.signal_crawler.analyze_signal_with_ai(sig, current_price)
                
                ai_result = {
                    'recommendation': sig.ai_recommendation,
                    'confidence': sig.ai_confidence,
                    'reason': sig.ai_analysis
                }
                
                # 2️⃣ Nếu có ảnh chart → AI phân tích ẢNH
                chart_analysis = None
                if sig.image_url:
                    print(f"📸 Analyzing chart image from @{sig.source}...")
                    try:
                        chart_analysis = self.ai.analyze_chart_image(
                            image_url=sig.image_url,
                            signal_data={
                                'action': sig.action,
                                'entry': sig.entry,
                                'stoploss': sig.stoploss,
                                'takeprofit': sig.takeprofit
                            }
                        )
                        
                        # Merge chart analysis vào kết quả
                        if chart_analysis.get('recommendation'):
                            # Ưu tiên chart analysis nếu có
                            chart_rec = chart_analysis['recommendation']
                            chart_conf = chart_analysis.get('confidence', 0)
                            
                            # Trung bình confidence từ 2 nguồn
                            combined_conf = (sig.ai_confidence + chart_conf) // 2
                            
                            # Nếu chart nói SKIP thì ưu tiên SKIP
                            if chart_rec == 'SKIP':
                                ai_result['recommendation'] = 'SKIP'
                                ai_result['confidence'] = chart_conf
                            # Nếu chart nói CAUTION và text nói FOLLOW -> CAUTION
                            elif chart_rec == 'CAUTION' and sig.ai_recommendation == 'FOLLOW':
                                ai_result['recommendation'] = 'CAUTION'
                                ai_result['confidence'] = combined_conf
                            # Nếu cả 2 đều FOLLOW -> tăng confidence
                            elif chart_rec == 'FOLLOW' and sig.ai_recommendation == 'FOLLOW':
                                ai_result['confidence'] = min(95, combined_conf + 10)
                            
                            # Merge reason
                            chart_reason = chart_analysis.get('reason', '')
                            if chart_reason:
                                ai_result['reason'] = f"{sig.ai_analysis} | Chart: {chart_reason}"
                            
                            print(f"✅ Chart analysis: {chart_rec} ({chart_conf}%)")
                            
                    except Exception as img_err:
                        print(f"⚠️ Chart analysis failed: {img_err}")
                        chart_analysis = None
                
                # Gửi thông báo (kèm chart analysis nếu có)
                self._send_signal_notification(sig, ai_result, current_price, chart_analysis)
                
                # Lưu vào Firebase
                if self.firebase:
                    signal_dict = sig.to_dict()
                    if chart_analysis:
                        signal_dict['chart_analysis'] = chart_analysis
                    self.firebase.save_external_signal(signal_dict, ai_result)
            
            return len(new_signals)
            
        except Exception as e:
            print(f"❌ Signal check error: {e}")
            return 0
    
    def check_news_updates(self):
        """
        Kiểm tra tin tức mới từ các kênh Telegram tin tức
        Nếu có tin quan trọng → AI phân tích → Tự động thông báo
        """
        try:
            print("📰 Checking news from Telegram channels...")
            
            # Crawl tin tức mới
            news_list = self.signal_crawler.get_new_important_news()
            
            new_news_count = 0
            for news in news_list:
                # Tạo unique key
                news_key = f"{news.source}_{news.message_id}"
                
                if news_key not in self.known_news:
                    self.known_news.add(news_key)
                    
                    # Chỉ xử lý tin HIGH impact
                    if news.impact == 'HIGH':
                        print(f"🔴 HIGH IMPACT NEWS: {news.title[:50]}...")
                        
                        # AI phân tích tin tức
                        news = self.signal_crawler.analyze_news_with_ai(news)
                        
                        # Gửi thông báo
                        self._send_news_notification(news)
                        new_news_count += 1
                    
                    elif news.impact == 'MEDIUM':
                        print(f"🟡 MEDIUM NEWS: {news.title[:50]}...")
                        new_news_count += 1
            
            self.last_news_check = datetime.now()
            return new_news_count
            
        except Exception as e:
            print(f"❌ News check error: {e}")
            return 0
    
    def _send_news_notification(self, news):
        """Gửi thông báo tin tức quan trọng qua Telegram"""
        impact_emoji = '🔴' if news.impact == 'HIGH' else '🟡'
        gold_emoji = '📈' if news.ai_impact_on_gold == 'BULLISH' else '📉' if news.ai_impact_on_gold == 'BEARISH' else '➖'
        
        message = f"""
{impact_emoji} *TIN TỨC QUAN TRỌNG*
━━━━━━━━━━━━━━━━━━

📰 *{news.title[:150]}*

🌍 Tiền tệ: {news.currency}
⏰ {news.timestamp}
📢 Nguồn: @{news.source}

{gold_emoji} *ẢNH HƯỞNG VÀNG:* {news.ai_impact_on_gold if news.ai_impact_on_gold else 'Đang phân tích...'}

📝 *PHÂN TÍCH AI:*
{news.ai_summary if news.ai_summary else 'Không có phân tích'}

━━━━━━━━━━━━━━━━━━
⚠️ *Lưu ý:* Cân nhắc kỹ trước khi vào lệnh!
"""
        
        try:
            # Gửi ảnh nếu có
            if news.image_url:
                try:
                    self.telegram.bot.send_photo(
                        self.telegram.chat_id,
                        news.image_url,
                        caption=message,
                        parse_mode='Markdown'
                    )
                    print(f"📸 Đã gửi tin tức kèm ảnh từ @{news.source}")
                    return
                except Exception as img_err:
                    print(f"⚠️ Không gửi được ảnh tin tức: {img_err}")
            
            # Gửi text
            self.telegram.send_message(message)
            print(f"📰 Đã gửi thông báo tin tức từ @{news.source}")
            
        except Exception as e:
            print(f"❌ Send news notification error: {e}")
    
    def _send_signal_notification(self, signal, ai_result, current_price=None, chart_analysis=None):
        """Gửi thông báo tín hiệu mới qua Telegram (kèm ảnh và phân tích chart)"""
        emoji = '🟢' if signal.action == 'BUY' else '🔴'
        rec_emoji = '✅' if ai_result.get('recommendation') == 'FOLLOW' else '⚠️' if ai_result.get('recommendation') == 'CAUTION' else '❌'
        
        # Build chart insights section
        chart_section = ""
        if chart_analysis:
            trend_emoji = "📈" if "UP" in chart_analysis.get('trend', '') else "📉" if "DOWN" in chart_analysis.get('trend', '') else "➖"
            pattern_text = f"\n🎯 Pattern: {chart_analysis.get('pattern')}" if chart_analysis.get('pattern') else ""
            
            # Format support/resistance levels
            support_text = ""
            if chart_analysis.get('support_levels'):
                supports = chart_analysis['support_levels'][:3]  # Max 3
                support_text = f"\n🛡️ Support: {', '.join(map(str, supports))}"
            
            resistance_text = ""
            if chart_analysis.get('resistance_levels'):
                resistances = chart_analysis['resistance_levels'][:3]  # Max 3
                resistance_text = f"\n🎯 Resistance: {', '.join(map(str, resistances))}"
            
            chart_section = f"""
📊 *PHÂN TÍCH CHART:*
{trend_emoji} Trend: {chart_analysis.get('trend', 'N/A')}{pattern_text}{support_text}{resistance_text}
"""
        
        message = f"""
📡 *TÍN HIỆU MỚI TỪ KÊNH*
━━━━━━━━━━━━━━━━━━

{emoji} *{signal.action} {signal.symbol}*
📍 Entry: {signal.entry}
🛡️ SL: {signal.stoploss}
🎯 TP: {signal.takeprofit}
📢 Source: @{signal.source}
{chart_section}
{rec_emoji} *AI NHẬN ĐỊNH:*
📊 Recommendation: {ai_result.get('recommendation', 'N/A')}
💯 Confidence: {ai_result.get('confidence', 0)}%
📝 {ai_result.get('reason', 'N/A')}

{"💰 Giá hiện tại: $" + str(current_price) if current_price else ""}
⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
        
        try:
            # Gửi ảnh chart nếu có
            if hasattr(signal, 'image_url') and signal.image_url:
                try:
                    self.telegram.bot.send_photo(
                        self.telegram.chat_id,
                        signal.image_url,
                        caption=message,
                        parse_mode='Markdown'
                    )
                    print(f"📸 Đã gửi ảnh chart từ @{signal.source}")
                except Exception as img_err:
                    # Fallback: gửi text nếu không gửi được ảnh
                    print(f"⚠️ Không gửi được ảnh: {img_err}")
                    self.telegram.send_message(message)
            else:
                self.telegram.send_message(message)
        except Exception as e:
            print(f"❌ Send notification error: {e}")
    
    def get_signals_text(self) -> str:
        """Lấy tín hiệu mới nhất từ các kênh"""
        return self.signal_crawler.format_for_telegram()
    
    def get_signal_stats_text(self) -> str:
        """Lấy thống kê WIN/LOSS của các kênh"""
        if not self.firebase:
            return "⚠️ Firebase chưa được kết nối."
        
        stats = self.firebase.get_signal_stats()
        
        return f"""
📊 *THỐNG KÊ TÍN HIỆU*
━━━━━━━━━━━━━━━━━━

📈 Tổng số: {stats.get('total', 0)}
✅ Win: {stats.get('wins', 0)}
❌ Loss: {stats.get('losses', 0)}
⏳ Pending: {stats.get('pending', 0)}

🎯 Win Rate: {stats.get('win_rate', 0)}%
💰 Total Pips: {stats.get('total_pips', 0)}
"""
    
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
            
            # 8. Get historical context from Firebase
            history_context = ""
            if self.firebase:
                try:
                    history = self.firebase.get_trade_history(limit=5)
                    if history:
                        history_lines = ["📊 LỊCH SỬ PHÂN TÍCH GẦN NHẤT:"]
                        for h in history:
                            history_lines.append(
                                f"- {h.get('timestamp', 'N/A')[:16]}: {h.get('action', 'N/A')} "
                                f"({h.get('confidence', 0)}%) - Phase: {h.get('wyckoff_phase', 'N/A')}, "
                                f"Event: {h.get('event_detected', 'NONE')}"
                            )
                        history_context = "\n".join(history_lines)
                except:
                    pass
            
            # 9. Prepare market data for AI
            market_data = self.fetcher.format_for_ai(df)
            full_context = f"{market_data}\n\n{pattern_text}"
            
            # Add history context if available
            if history_context:
                full_context = f"{full_context}\n\n{history_context}\n\n⚠️ LƯU Ý: Hãy xem xét lịch sử phân tích để đảm bảo tính nhất quán. Nếu xu hướng không thay đổi đáng kể, nên giữ nguyên nhận định trước đó."
            
            # 10. AI Analysis (trong thread riêng để không block khi CPU throttle)
            print("   🤖 AI đang phân tích...")
            
            # Wrapper để chạy AI trong thread riêng (fix Replit CPU throttle)
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
            import functools
            
            def run_ai_analysis():
                return self.ai.analyze(
                    market_data=full_context,
                    indicators=indicators,
                    wyckoff_analysis=wyckoff_result,
                    smc_analysis=smc_result,
                    news_context=news_context
                )
            
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_ai_analysis)
                    signal = future.result(timeout=120)  # 2 phút timeout
            except FuturesTimeoutError:
                print("⚠️ AI timeout - trả về WAIT")
                signal = {'action': 'WAIT', 'confidence': 0, 'reason': 'AI timeout'}
            
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
            # Lấy tất cả tin quan trọng (không chỉ USD)
            events = self.news.get_high_impact_news()
            
            if not events:
                return "📃 *TIN TỨC KINH TẾ*\n\n✅ Không có tin quan trọng hôm nay."
            
            lines = [
                "📃 *TIN TỨC KINH TẾ HÔM NAY*",
                "━━━━━━━━━━━━━━━━━━━━━",
                ""
            ]
            
            for event in events[:10]:  # Tăng lên 10 tin
                impact_icon = "🔴" if event.impact == 'HIGH' else "🟡" if event.impact == 'MEDIUM' else "⚪"
                name_vi = event.title_vi if event.title_vi else event.event
                
                lines.append(f"{impact_icon} *{event.time}* - {event.currency}")
                lines.append(f"   📰 {name_vi[:60]}")
                
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
                    
                    # Save to Firebase history
                    if self.firebase:
                        print("💾 Lưu vào Firebase...")
                        self.firebase.save_signal(signal)
                        print("✅ Đã lưu lịch sử!")
                    
                    # If BUY/SELL with high confidence, also send full signal
                    if action in ['BUY', 'SELL'] and confidence >= 50:
                        print("🎯 Gửi TÍN HIỆU ĐẦY ĐỦ về Telegram...")
                        self.telegram.send_wyckoff_signal(signal)
                        print("✅ Đã gửi tín hiệu!")
                
                # 📡 CHECK EXTERNAL SIGNALS - Auto check từ các kênh Telegram
                print("\n📡 Checking external signals from Telegram channels...")
                try:
                    new_signals_count = self.check_external_signals()
                    if new_signals_count > 0:
                        print(f"✅ Found {new_signals_count} new signals!")
                    else:
                        print("📭 No new signals from channels")
                except Exception as e:
                    print(f"⚠️ Signal check error: {str(e)[:50]}")
                
                # 📰 CHECK NEWS UPDATES - Auto check tin tức từ kênh Telegram
                print("\n📰 Checking news updates from Telegram channels...")
                try:
                    new_news_count = self.check_news_updates()
                    if new_news_count > 0:
                        print(f"✅ Found {new_news_count} new important news!")
                    else:
                        print("📭 No new important news")
                except Exception as e:
                    print(f"⚠️ News check error: {str(e)[:50]}")
                
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
