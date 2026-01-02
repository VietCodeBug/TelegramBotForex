"""
Signal Crawler Module - Crawl tín hiệu từ các kênh Telegram
Lấy tín hiệu BUY/SELL với Entry, SL, TP từ:
- @ducforex6789
- @vnscalping
- @XAUUSDINSIDER_FX
- @lichkinhte (tin tức)

Tính năng:
- Auto crawl tín hiệu từ nhiều kênh
- AI phân tích tín hiệu trước khi gửi
- Lọc tin theo ngày và mức độ quan trọng
- Tự động thông báo tin tức mới quan trọng
"""
import requests
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


@dataclass
class TradingSignal:
    """Tín hiệu giao dịch từ kênh Telegram"""
    source: str           # Kênh nguồn
    timestamp: str        # Thời gian
    symbol: str           # XAU/USD, BTC, etc
    action: str           # BUY / SELL
    entry: float          # Giá vào lệnh
    stoploss: float       # Stop loss
    takeprofit: float     # Take profit
    status: str           # PENDING / WIN / LOSS
    raw_text: str         # Text gốc
    image_url: str = ''   # URL ảnh chart (nếu có)
    ai_analysis: str = '' # Phân tích của AI
    ai_recommendation: str = ''  # FOLLOW / CAUTION / SKIP
    ai_confidence: int = 0  # 0-100
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass 
class NewsItem:
    """Tin tức từ kênh Telegram"""
    source: str           # Kênh nguồn
    timestamp: str        # Thời gian đăng
    message_id: str       # ID tin nhắn (để track)
    title: str            # Tiêu đề/Nội dung chính
    content: str          # Nội dung đầy đủ
    impact: str           # HIGH / MEDIUM / LOW
    currency: str         # USD, EUR, etc
    is_analyzed: bool = False  # Đã phân tích AI chưa
    ai_summary: str = ''  # Tóm tắt của AI
    ai_impact_on_gold: str = ''  # Ảnh hưởng đến vàng
    image_url: str = ''   # URL ảnh (nếu có)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class SignalCrawler:
    """
    Crawl tín hiệu trading từ các kênh Telegram
    Sử dụng web preview t.me/s/channel_name
    """
    
    # Kênh tín hiệu giao dịch
    SIGNAL_CHANNELS = [
        'ducforex6789',
        'vnscalping',
        'XAUUSDINSIDER_FX'  # Kênh mới - XAU/USD Insider
    ]
    
    # Kênh tin tức kinh tế
    NEWS_CHANNELS = [
        'lichkinhte'
    ]
    
    # Tất cả kênh
    CHANNELS = SIGNAL_CHANNELS + NEWS_CHANNELS
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
    }
    
    def __init__(self, firebase_service=None, ai_engine=None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.firebase = firebase_service
        self.ai_engine = ai_engine  # AI để phân tích tín hiệu
        self.signals_cache = []
        self.news_cache = []  # Cache tin tức
        self.last_crawl_time = None
        self.known_message_ids = set()  # Track tin đã xử lý
    
    def crawl_all_channels(self) -> List[TradingSignal]:
        """Crawl tất cả các kênh tín hiệu (không bao gồm kênh tin tức)"""
        all_signals = []
        
        for channel in self.SIGNAL_CHANNELS:
            try:
                signals = self._crawl_channel(channel)
                all_signals.extend(signals)
                print(f"✅ @{channel}: {len(signals)} signals")
            except Exception as e:
                print(f"❌ @{channel}: Error - {str(e)[:50]}")
        
        # Lưu vào cache
        self.signals_cache = all_signals
        
        # Lưu vào Firebase nếu có
        if self.firebase and all_signals:
            self._save_to_firebase(all_signals)
        
        return all_signals
    
    def _crawl_channel(self, channel: str) -> List[TradingSignal]:
        """Crawl một kênh Telegram cụ thể - CHỈ LẤY TIN TRONG 24H GẦN NHẤT"""
        url = f"https://t.me/s/{channel}"
        
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return []
            
            if not BS4_AVAILABLE:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # Lấy cả widget message để có thể lấy ảnh và datetime
            message_widgets = soup.find_all('div', class_='tgme_widget_message')
            
            signals = []
            skipped_old = 0
            now = datetime.now()
            
            # Lấy 30 tin mới nhất để filter
            for widget in message_widgets[-30:]:
                # Lấy thời gian tin nhắn (CHỈ LẤY HÔM NAY)
                time_elem = widget.find('time', class_='time')
                msg_datetime = None
                msg_time_str = now.strftime("%H:%M %d/%m/%Y")
                
                if time_elem and time_elem.get('datetime'):
                    try:
                        dt_str = time_elem.get('datetime')
                        # Parse ISO datetime from Telegram
                        # Example: "2024-01-02T10:30:00+07:00"
                        dt_clean = dt_str.split('+')[0].split('Z')[0]
                        msg_datetime = datetime.fromisoformat(dt_clean)
                        msg_time_str = msg_datetime.strftime("%H:%M %d/%m/%Y")
                        
                        # ⚠️ FILTER: Chỉ lấy tin trong 24h gần nhất
                        time_diff = (now - msg_datetime).total_seconds()
                        if time_diff > 86400:  # 24 hours = 86400 seconds
                            skipped_old += 1
                            continue  # Skip tin cũ
                        elif time_diff < 0:
                            # Tin trong tương lai? (lỗi timezone) - vẫn lấy
                            pass
                            
                    except Exception as e:
                        # Không parse được datetime -> Skip để an toàn
                        print(f"⚠️ Cannot parse datetime for @{channel}: {e}")
                        continue
                
                # Lấy text
                text_div = widget.find('div', class_='tgme_widget_message_text')
                if not text_div:
                    continue
                text = text_div.get_text(strip=True)
                
                # Lấy ảnh (nếu có)
                image_url = ''
                photo_wrap = widget.find('a', class_='tgme_widget_message_photo_wrap')
                if photo_wrap:
                    style = photo_wrap.get('style', '')
                    # Extract URL from style="background-image:url('...')"
                    img_match = re.search(r"url\(([^)]+)\)", style)
                    if img_match:
                        image_url = img_match.group(1).strip("'\"")
                
                signal = self._parse_signal(text, channel, image_url, msg_time_str)
                if signal:
                    signals.append(signal)
            
            # Log filtering results
            if skipped_old > 0:
                print(f"📅 @{channel}: Filtered out {skipped_old} old signals (>24h)")
            
            return signals
            
        except Exception as e:
            return []
    
    
    def _parse_signal_with_ai(self, text: str, source: str) -> Optional[TradingSignal]:
        """
        Dùng AI để parse tín hiệu - Linh hoạt với mọi format
        AI có thể hiểu được cách viết tự nhiên của con người
        """
        if not self.ai_engine or not hasattr(self.ai_engine, 'model') or not self.ai_engine.model:
            return None
        
        try:
            prompt = f"""
Phân tích tin nhắn trading sau và trích xuất thông tin:

TEXT: "{text}"

Trả lời theo JSON format:
{{
    "action": "BUY" hoặc "SELL" hoặc null (nếu không phải tín hiệu),
    "symbol": "XAUUSD" hoặc "BTCUSD" (mặc định XAUUSD),
    "entry": giá vào lệnh (số),
    "stoploss": giá cắt lỗ (số),
    "takeprofit": giá chốt lời (số)
}}

LƯU Ý:
- Nếu không phải tín hiệu trading → action: null
- Nếu thiếu thông tin nào thì để null
- Giá XAUUSD thường 4 chữ số (2500-5000)
- Keywords: buy/mua/long = BUY, sell/bán/short = SELL
- SL = stoploss, TP = takeprofit
"""
            
            response = self.ai_engine.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Parse JSON
            import json
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                if not data.get('action'):
                    return None
                
                # Get values with fallbacks
                entry = data.get('entry')
                sl = data.get('stoploss')
                tp = data.get('takeprofit')
                action = data.get('action', 'BUY')
                
                # Validate entry
                if not entry or entry == 0:
                    return None
                
                # Estimate SL/TP if AI didn't provide
                if not sl or sl == 0:
                    sl = entry - 20 if action == 'BUY' else entry + 20
                if not tp or tp == 0:
                    tp = entry + 30 if action == 'BUY' else entry - 30
                
                # Build signal
                return TradingSignal(
                    source=source,
                    timestamp=datetime.now().strftime("%H:%M %d/%m/%Y"),
                    symbol=data.get('symbol', 'XAUUSD'),
                    action=action,
                    entry=float(entry),
                    stoploss=float(sl),
                    takeprofit=float(tp),
                    status='PENDING',
                    raw_text=text[:200]
                )
        except Exception as e:
            print(f"⚠️ AI parsing error: {e}")
        
        return None
    
    def _parse_signal(self, text: str, source: str, image_url: str = '', msg_time_str: str = '') -> Optional[TradingSignal]:
        """Parse tin nhắn để tìm tín hiệu trading"""
        text_lower = text.lower()
        
        # Xác định action (BUY/SELL)
        action = None
        if any(word in text_lower for word in ['buy', 'mua', 'long', 'bú', 'húp', 'vào lệnh mua']):
            action = 'BUY'
        elif any(word in text_lower for word in ['sell', 'bán', 'short', 'vào lệnh bán']):
            action = 'SELL'
        
        if not action:
            return None
        
        # Xác định symbol
        symbol = 'XAUUSD'  # Default là vàng
        if any(word in text_lower for word in ['btc', 'bitcoin']):
            symbol = 'BTCUSD'
        elif any(word in text_lower for word in ['eth', 'ethereum']):
            symbol = 'ETHUSD'
        
        # Parse giá entry
        entry = self._extract_price(text, ['entry', 'giá', 'quanh', 'vào', 'hiện tại', 'now', 'limit'])
        
        # Parse SL
        sl = self._extract_price(text, ['sl', 'stop', 'stoploss', 'cắt lỗ'])
        
        # Parse TP  
        tp = self._extract_price(text, ['tp', 'take', 'takeprofit', 'chốt lời', 'target'])
        
        # Nếu không có đủ thông tin, thử nhiều pattern khác
        if not entry:
            # Pattern 1: Số 4 chữ số đầy đủ (2650, 2700, 4350, 4480...)
            # Hỗ trợ cả giá vàng mới (26xx, 27xx) và cũ (43xx, 44xx)
            prices = re.findall(r'\b(2[5-9]\d{2}|[34][0-5]\d{2})\b', text)
            if prices:
                entry = float(prices[0])
        
        if not entry:
            # Pattern 2: Format range "4337-4333" hoặc "2650-2645"
            range_match = re.search(r'(\d{4})\s*[-–]\s*(\d{4})', text)
            if range_match:
                entry = float(range_match.group(1))  # Lấy giá đầu tiên
        
        if not entry:
            # Pattern 3: Format 432x, 435x (Vietnamese slang, x=wildcard 0-9)
            # "432x" có nghĩa là khoảng 4320-4329
            slang_prices = re.findall(r'(4[0-5]\d)[xX*]', text)
            if slang_prices:
                entry = float(slang_prices[0] + '0')  # 432x -> 4320
        
        if not entry:
            # Pattern 4: Số 3 chữ số có thể là giá vàng rút gọn (265, 270, 435...)
            short_prices = re.findall(r'\b(2[5-9]\d|[34][0-5]\d)\b', text)
            if short_prices and 'sl' in text_lower:  # Có SL thì chắc là tin trading
                entry = float(short_prices[0] + '0')  # Expand to 4 digits
        
        if not entry:
            # Nhưng chỉ khi context là vàng
            short_prices = re.findall(r'\b(4[0-5]\d)\b', text)
            if short_prices and 'sl' in text_lower:  # Có SL thì chắc là tin trading
                entry = float(short_prices[0] + '0')  # Expand to 4 digits
        
        # ⚠️ FALLBACK: Nếu regex không parse được → Dùng AI
        if not entry or not sl:
            print(f"   🤖 Regex failed, trying AI parser for @{source}...")
            ai_signal = self._parse_signal_with_ai(text, source)
            if ai_signal:
                ai_signal.image_url = image_url
                ai_signal.timestamp = msg_time_str if msg_time_str else datetime.now().strftime("%H:%M %d/%m/%Y")
                print(f"   ✅ AI parsed: {ai_signal.action} @ {ai_signal.entry}")
                return ai_signal
        
        # Validation: Entry phải trong khoảng giá vàng hợp lệ (2500-5000)
        if entry and (entry < 2500 or entry > 5000):
            # Có thể đây là lot size hoặc số khác, không phải giá
            entry = None
        
        if not entry:
            return None
        
        # Ước tính SL/TP nếu không có
        if not sl:
            sl = entry - 20 if action == 'BUY' else entry + 20
        if not tp:
            tp = entry + 30 if action == 'BUY' else entry - 30
        
        # Sử dụng thời gian từ message, nếu không có thì dùng now
        timestamp = msg_time_str if msg_time_str else datetime.now().strftime("%H:%M %d/%m/%Y")
        
        return TradingSignal(
            source=source,
            timestamp=timestamp,
            symbol=symbol,
            action=action,
            entry=entry,
            stoploss=sl,
            takeprofit=tp,
            status='PENDING',
            raw_text=text[:200],
            image_url=image_url
        )
    
    def _extract_price(self, text: str, keywords: List[str]) -> Optional[float]:
        """Trích xuất giá từ text dựa trên keywords"""
        text_lower = text.lower()
        
        for keyword in keywords:
            # Pattern 1: keyword + số (có thể có dấu :, =, ., khoảng trắng)
            # Hỗ trợ cả "sl: 4416", "sL. 4416", "sl 4416", "sl=4416"
            pattern = rf'{keyword}\s*[:=.]?\s*(\d+\.?\d*)'
            match = re.search(pattern, text_lower)
            if match:
                try:
                    price = float(match.group(1))
                    # Nếu giá 4 chữ số trong khoảng hợp lệ của vàng
                    if 2500 <= price <= 5000:
                        return price
                    # Nếu giá 3 chữ số -> expand (441 -> 4410)
                    elif 250 <= price <= 500:
                        return price * 10
                except:
                    pass
        
        return None
    
    def _save_to_firebase(self, signals: List[TradingSignal]):
        """Lưu tín hiệu vào Firebase"""
        try:
            for signal in signals[-10:]:  # Chỉ lưu 10 tín hiệu mới nhất
                signal_data = signal.to_dict()
                signal_data['saved_at'] = datetime.now().isoformat()
                
                # Gọi Firebase service
                if hasattr(self.firebase, 'save_signal'):
                    self.firebase.save_signal(signal_data)
        except Exception as e:
            print(f"⚠️ Firebase save error: {e}")
    
    def get_latest_signals(self, limit: int = 5) -> List[TradingSignal]:
        """Lấy tín hiệu mới nhất từ cache"""
        return self.signals_cache[-limit:]
    
    # ═══════════════════════════════════════════════════════════════
    # NEWS CRAWLING - Crawl tin tức từ kênh Telegram
    # ═══════════════════════════════════════════════════════════════
    
    def crawl_news_channels(self) -> List[NewsItem]:
        """
        Crawl tin tức từ các kênh tin tức Telegram
        Chỉ lấy tin hôm nay và lọc theo mức độ quan trọng
        """
        all_news = []
        today = datetime.now().strftime("%d/%m")
        
        for channel in self.NEWS_CHANNELS:
            try:
                news = self._crawl_news_from_channel(channel)
                all_news.extend(news)
                print(f"📰 @{channel}: {len(news)} tin tức")
            except Exception as e:
                print(f"❌ @{channel}: Error - {str(e)[:50]}")
        
        # Lọc chỉ tin hôm nay
        today_news = [n for n in all_news if today in n.timestamp]
        
        # Sắp xếp theo: 1. Currency USD first, 2. Impact HIGH > MEDIUM > LOW
        def sort_key(news):
            currency_order = 0 if news.currency == 'USD' else 1
            impact_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
            return (currency_order, impact_order.get(news.impact, 2))
        
        today_news.sort(key=sort_key)
        
        # Cập nhật cache
        self.news_cache = today_news
        self.last_crawl_time = datetime.now()
        
        return today_news
    
    def _crawl_news_from_channel(self, channel: str) -> List[NewsItem]:
        """Crawl tin tức từ một kênh cụ thể"""
        url = f"https://t.me/s/{channel}"
        
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return []
            
            if not BS4_AVAILABLE:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            message_widgets = soup.find_all('div', class_='tgme_widget_message')
            
            news_items = []
            
            for widget in message_widgets[-30:]:  # 30 tin mới nhất
                # Lấy message ID
                msg_id = widget.get('data-post', '').split('/')[-1]
                
                # Skip nếu đã xử lý
                full_msg_id = f"{channel}_{msg_id}"
                if full_msg_id in self.known_message_ids:
                    continue
                
                # Lấy thời gian
                time_elem = widget.find('time', class_='time')
                msg_time_str = datetime.now().strftime("%H:%M %d/%m/%Y")
                
                if time_elem and time_elem.get('datetime'):
                    try:
                        dt_str = time_elem.get('datetime')
                        dt_clean = dt_str.split('+')[0].split('Z')[0]
                        msg_datetime = datetime.fromisoformat(dt_clean)
                        msg_time_str = msg_datetime.strftime("%H:%M %d/%m/%Y")
                    except:
                        pass
                
                # Lấy text
                text_div = widget.find('div', class_='tgme_widget_message_text')
                if not text_div:
                    continue
                text = text_div.get_text(strip=True)
                
                # Lấy ảnh (nếu có)
                image_url = ''
                photo_wrap = widget.find('a', class_='tgme_widget_message_photo_wrap')
                if photo_wrap:
                    style = photo_wrap.get('style', '')
                    img_match = re.search(r"url\(([^)]+)\)", style)
                    if img_match:
                        image_url = img_match.group(1).strip("'\"")
                
                # Parse tin tức
                news_item = self._parse_news(text, channel, msg_id, msg_time_str, image_url)
                if news_item:
                    news_items.append(news_item)
                    self.known_message_ids.add(full_msg_id)
            
            return news_items
            
        except Exception as e:
            print(f"❌ News crawl error @{channel}: {e}")
            return []
    
    def _parse_news(self, text: str, source: str, msg_id: str, 
                    timestamp: str, image_url: str = '') -> Optional[NewsItem]:
        """Parse tin nhắn thành tin tức"""
        # Xác định mức độ quan trọng từ emoji/text
        impact = 'LOW'
        
        # Đếm số sao để xác định impact
        star_count = text.count('⭐')
        if star_count >= 4:
            impact = 'HIGH'
        elif star_count >= 3:
            impact = 'MEDIUM'
        elif star_count >= 2:
            impact = 'MEDIUM'  # 2 sao cũng là MEDIUM
        
        # Tin quan trọng từ emoji
        if '🔴🔴🔴' in text or '🔴🔴' in text:
            impact = 'HIGH'
        
        # Các từ khóa quan trọng ảnh hưởng vàng (tiếng Anh + tiếng Việt)
        high_impact_keywords = [
            # Tin Mỹ quan trọng
            'Non-Farm', 'NFP', 'CPI', 'PPI', 'GDP', 'FOMC', 'Fed', 
            'Interest Rate', 'Powell', 'Inflation', 'Core PCE',
            'Unemployment', 'Jobless', 'Retail Sales', 'ISM', 'PMI',
            # Tiếng Việt
            'Lãi suất', 'Lạm phát', 'Thất nghiệp', 'Bảng lương', 
            'Phi nông nghiệp', 'NÓNG', 'BREAKING', 'QUAN TRỌNG'
        ]
        
        if any(kw.lower() in text.lower() for kw in high_impact_keywords):
            impact = 'HIGH'
        
        # Nếu là tin USD thì nâng cao mức độ quan trọng
        if '🇺🇸' in text:  # Cờ Mỹ
            if impact == 'LOW':
                impact = 'MEDIUM'
        
        # Xác định currency
        currency = 'USD'
        if '🇪🇺' in text:
            currency = 'EUR'
        elif '🇬🇧' in text:
            currency = 'GBP'
        elif '🇯🇵' in text:
            currency = 'JPY'
        elif '🇨🇳' in text:
            currency = 'CNY'
        elif '🇺🇸' in text:
            currency = 'USD'
        elif '🇦🇺' in text:
            currency = 'AUD'
        elif '🇨🇦' in text:
            currency = 'CAD'
        elif '🇨🇭' in text:
            currency = 'CHF'
        elif '🇻🇳' in text:
            currency = 'VND'
        
        # Chỉ lấy tin có nội dung đáng kể
        if len(text) < 20:
            return None
        
        # Tạo title từ 100 ký tự đầu
        title = text[:100] + ('...' if len(text) > 100 else '')
        
        return NewsItem(
            source=source,
            timestamp=timestamp,
            message_id=msg_id,
            title=title,
            content=text,
            impact=impact,
            currency=currency,
            image_url=image_url
        )
    
    def get_new_important_news(self) -> List[NewsItem]:
        """
        Lấy tin tức quan trọng MỚI (chưa được thông báo)
        Chỉ trả về tin HIGH/MEDIUM impact
        """
        # Crawl tin mới
        all_news = self.crawl_news_channels()
        
        # Lọc tin quan trọng
        important_news = [n for n in all_news if n.impact in ['HIGH', 'MEDIUM']]
        
        return important_news
    
    def analyze_news_with_ai(self, news: NewsItem) -> NewsItem:
        """
        Dùng AI phân tích tin tức và đánh giá ảnh hưởng đến vàng
        """
        if not self.ai_engine or not hasattr(self.ai_engine, 'model') or not self.ai_engine.model:
            return news
        
        try:
            prompt = f"""
Phân tích tin tức kinh tế sau và đánh giá ảnh hưởng đến giá VÀNG (XAU/USD):

TIN TỨC:
{news.content[:500]}

Trả lời ngắn gọn bằng TIẾNG VIỆT theo format:
1. TÓM TẮT: (1-2 câu tóm tắt tin)
2. ẢNH HƯỞNG VÀNG: (TĂNG GIÁ / GIẢM GIÁ / TRUNG LẬP)
3. MỨC ĐỘ: (MẠNH / TRUNG BÌNH / YẾU)
4. LÝ DO: (1 câu giải thích ngắn gọn)
"""
            response = self.ai_engine.model.generate_content(prompt)
            ai_result = response.text.strip()
            
            # Parse kết quả
            news.ai_summary = ai_result
            news.is_analyzed = True
            
            # Xác định ảnh hưởng đến vàng
            if 'TĂNG GIÁ' in ai_result.upper():
                news.ai_impact_on_gold = 'BULLISH'
            elif 'GIẢM GIÁ' in ai_result.upper():
                news.ai_impact_on_gold = 'BEARISH'
            else:
                news.ai_impact_on_gold = 'NEUTRAL'
            
        except Exception as e:
            print(f"⚠️ AI news analysis error: {e}")
        
        return news
    
    def analyze_signal_with_ai(self, signal: TradingSignal, current_price: float = None) -> TradingSignal:
        """
        Dùng AI phân tích tín hiệu từ kênh và đưa ra khuyến nghị
        """
        if not self.ai_engine or not hasattr(self.ai_engine, 'model') or not self.ai_engine.model:
            return signal
        
        try:
            price_info = f"\nGiá hiện tại: ${current_price}" if current_price else ""
            
            prompt = f"""
Phân tích tín hiệu trading từ kênh Telegram và đưa ra khuyến nghị:

TÍN HIỆU:
- Action: {signal.action} {signal.symbol}
- Entry: {signal.entry}
- Stop Loss: {signal.stoploss}
- Take Profit: {signal.takeprofit}
- Nguồn: @{signal.source}{price_info}

NỘI DUNG GỐC:
{signal.raw_text[:300]}

Đánh giá và trả lời theo format JSON:
{{
    "recommendation": "FOLLOW" | "CAUTION" | "SKIP",
    "confidence": 0-100,
    "reason": "lý do ngắn gọn bằng tiếng Việt"
}}

Lưu ý:
- FOLLOW: Tín hiệu tốt, có thể theo
- CAUTION: Có rủi ro, cân nhắc kỹ
- SKIP: Không nên theo
"""
            response = self.ai_engine.model.generate_content(prompt)
            ai_result = response.text.strip()
            
            # Parse JSON từ response
            import json
            json_match = re.search(r'\{[^}]+\}', ai_result, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                signal.ai_recommendation = result.get('recommendation', 'CAUTION')
                signal.ai_confidence = result.get('confidence', 50)
                signal.ai_analysis = result.get('reason', '')
            
        except Exception as e:
            print(f"⚠️ AI signal analysis error: {e}")
            signal.ai_recommendation = 'CAUTION'
            signal.ai_analysis = 'Không thể phân tích AI'
        
        return signal
    
    def format_news_for_telegram(self, news_list: List[NewsItem] = None) -> str:
        """Format tin tức để gửi lên Telegram"""
        if news_list is None:
            news_list = [n for n in self.news_cache if n.impact in ['HIGH', 'MEDIUM']][:5]
        
        if not news_list:
            return "📰 Không có tin tức quan trọng mới."
        
        lines = ["📰 *TIN TỨC QUAN TRỌNG*", "━━━━━━━━━━━━━━━━━"]
        
        for news in news_list:
            impact_emoji = '🔴' if news.impact == 'HIGH' else '🟡'
            gold_emoji = '📈' if news.ai_impact_on_gold == 'BULLISH' else '📉' if news.ai_impact_on_gold == 'BEARISH' else '➖'
            
            lines.append(f"""
{impact_emoji} *{news.impact}* | {news.currency}
📍 {news.title}
⏰ {news.timestamp}
{f'{gold_emoji} AI: {news.ai_impact_on_gold}' if news.ai_impact_on_gold else ''}
📢 @{news.source}
""")
        
        return "\n".join(lines)
    
    def format_for_telegram(self, signals: List[TradingSignal] = None) -> str:
        """Format tín hiệu để gửi lên Telegram"""
        if signals is None:
            signals = self.signals_cache[-5:]
        
        if not signals:
            return "📊 Chưa có tín hiệu mới từ các kênh."
        
        lines = ["📡 *TÍN HIỆU TỪ KÊNH TELEGRAM*", "━━━━━━━━━━━━━━━━━"]
        
        for sig in signals:
            emoji = '🟢' if sig.action == 'BUY' else '🔴'
            rec_emoji = '✅' if sig.ai_recommendation == 'FOLLOW' else '⚠️' if sig.ai_recommendation == 'CAUTION' else '❌'
            
            ai_info = ''
            if sig.ai_recommendation:
                ai_info = f"\n{rec_emoji} AI: {sig.ai_recommendation} ({sig.ai_confidence}%)"
                if sig.ai_analysis:
                    ai_info += f"\n💡 {sig.ai_analysis[:100]}"
            
            lines.append(f"""
{emoji} *{sig.action} {sig.symbol}*
📍 Entry: {sig.entry}
🛡️ SL: {sig.stoploss}
🎯 TP: {sig.takeprofit}
📢 Source: @{sig.source}
⏰ {sig.timestamp[:16]}{ai_info}
""")
        
        return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    crawler = SignalCrawler()
    signals = crawler.crawl_all_channels()
    
    print(f"\n📊 Total signals found: {len(signals)}")
    for sig in signals[:5]:
        print(f"  {sig.action} {sig.symbol} @ {sig.entry} | SL: {sig.stoploss} | TP: {sig.takeprofit}")
    
    print("\n" + crawler.format_for_telegram())
