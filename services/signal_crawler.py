"""
Signal Crawler Module - Crawl tín hiệu từ các kênh Telegram
Lấy tín hiệu BUY/SELL với Entry, SL, TP từ:
- @ducforex6789
- @vnscalping
- @lichkinhte
"""
import requests
import re
from datetime import datetime
from typing import List, Dict, Optional
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
    
    def to_dict(self) -> Dict:
        return asdict(self)


class SignalCrawler:
    """
    Crawl tín hiệu trading từ các kênh Telegram
    Sử dụng web preview t.me/s/channel_name
    """
    
    CHANNELS = [
        'ducforex6789',
        'vnscalping',
        'lichkinhte'
    ]
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
    }
    
    def __init__(self, firebase_service=None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.firebase = firebase_service
        self.signals_cache = []
    
    def crawl_all_channels(self) -> List[TradingSignal]:
        """Crawl tất cả các kênh và trả về tín hiệu"""
        all_signals = []
        
        for channel in self.CHANNELS:
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
        """Crawl một kênh Telegram cụ thể"""
        url = f"https://t.me/s/{channel}"
        
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return []
            
            if not BS4_AVAILABLE:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # Lấy cả widget message để có thể lấy ảnh
            message_widgets = soup.find_all('div', class_='tgme_widget_message')
            
            signals = []
            
            for widget in message_widgets[-30:]:  # 30 tin mới nhất
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
                    img_match = re.search(r"url\(['"]?([^'"\)]+)['"]?\)", style)
                    if img_match:
                        image_url = img_match.group(1)
                
                signal = self._parse_signal(text, channel, image_url)
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            return []
    
    def _parse_signal(self, text: str, source: str, image_url: str = '') -> Optional[TradingSignal]:
        """Parse tin nhắn để tìm tín hiệu trading"""
        text_lower = text.lower()
        
        # Xác định action (BUY/SELL)
        action = None
        if any(word in text_lower for word in ['buy', 'mua', 'long', 'bú', 'húp']):
            action = 'BUY'
        elif any(word in text_lower for word in ['sell', 'bán', 'short']):
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
        entry = self._extract_price(text, ['entry', 'giá', 'quanh', 'vào', 'hiện tại'])
        
        # Parse SL
        sl = self._extract_price(text, ['sl', 'stop', 'stoploss', 'cắt lỗ'])
        
        # Parse TP  
        tp = self._extract_price(text, ['tp', 'take', 'takeprofit', 'chốt lời', 'target'])
        
        # Nếu không có đủ thông tin, bỏ qua
        if not entry:
            # Thử parse giá từ số có 4 chữ số (giá vàng)
            prices = re.findall(r'\b(4[0-5]\d{2})\b', text)
            if prices:
                entry = float(prices[0])
        
        if not entry:
            return None
        
        # Ước tính SL/TP nếu không có
        if not sl:
            sl = entry - 20 if action == 'BUY' else entry + 20
        if not tp:
            tp = entry + 30 if action == 'BUY' else entry - 30
        
        return TradingSignal(
            source=source,
            timestamp=datetime.now().isoformat(),
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
            # Pattern: keyword + số (có thể có dấu :, =, khoảng trắng)
            pattern = rf'{keyword}\s*[:=]?\s*(\d+\.?\d*)'
            match = re.search(pattern, text_lower)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        
        return None
    
    def _save_to_firebase(self, signals: List[TradingSignal]):
        """Lưu tín hiệu vào Firebase"""
        try:
            for signal in signals[-10]:  # Chỉ lưu 10 tín hiệu mới nhất
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
    
    def format_for_telegram(self, signals: List[TradingSignal] = None) -> str:
        """Format tín hiệu để gửi lên Telegram"""
        if signals is None:
            signals = self.signals_cache[-5:]
        
        if not signals:
            return "📊 Chưa có tín hiệu mới từ các kênh."
        
        lines = ["📡 *TÍN HIỆU TỪ KÊNH TELEGRAM*", "━━━━━━━━━━━━━━━━━"]
        
        for sig in signals:
            emoji = '🟢' if sig.action == 'BUY' else '🔴'
            lines.append(f"""
{emoji} *{sig.action} {sig.symbol}*
📍 Entry: {sig.entry}
🛡️ SL: {sig.stoploss}
🎯 TP: {sig.takeprofit}
📢 Source: @{sig.source}
⏰ {sig.timestamp[:16]}
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
