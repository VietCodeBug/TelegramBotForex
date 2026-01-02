"""
News Crawler Module - Crawl và phân tích tin tức forex
Sử dụng Gemini để dịch và phân tích tầm quan trọng
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re
from dataclasses import dataclass

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


@dataclass
class NewsEvent:
    """Sự kiện tin tức kinh tế"""
    time: str
    currency: str
    impact: str  # HIGH, MEDIUM, LOW
    event: str
    forecast: str
    previous: str
    actual: str
    title_vi: str  # Tiêu đề tiếng Việt


class NewsCrawler:
    """
    Crawl tin tức kinh tế từ ForexFactory, Investing.com
    Dịch sang tiếng Việt bằng AI
    """
    
    # More realistic browser headers to bypass bot detection
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    # Tin tức ảnh hưởng mạnh đến Vàng
    GOLD_IMPACT_EVENTS = [
        'Non-Farm', 'NFP', 'CPI', 'PPI', 'GDP', 'FOMC', 'Fed', 'Interest Rate',
        'Unemployment', 'Retail Sales', 'PMI', 'ISM', 'Core', 'Inflation',
        'Powell', 'Yellen', 'Treasury', 'Jobs', 'Employment'
    ]
    
    def __init__(self, gemini_api_key: str = None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.gemini_key = gemini_api_key
        self.model = None
        
        if GENAI_AVAILABLE and gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def get_economic_calendar(self) -> List[NewsEvent]:
        """
        Lấy lịch kinh tế hôm nay
        Priority: Telegram @lichkinhte > NASDAQ API > CafeF
        """
        events = []
        
        # Try Telegram channel first (Vietnamese - most relevant)
        try:
            events = self._crawl_telegram_lichkinhte()
            if events:
                print(f"✅ Telegram @lichkinhte: {len(events)} events loaded")
                return events
        except Exception as e:
            pass  # Silent fail
        
        # Try NASDAQ (US Economic Calendar - reliable)
        try:
            events = self._crawl_nasdaq()
            if events:
                print(f"✅ NASDAQ: {len(events)} events loaded")
                return events
        except Exception as e:
            pass  # Silent fail
        
        # Fallback to CafeF 
        try:
            events = self._crawl_cafef()
            if events:
                print(f"✅ CafeF: {len(events)} events loaded")
                return events
        except Exception as e:
            pass  # Silent fail
        
        # Return empty if all fail
        return []
    
    def _crawl_telegram_lichkinhte(self) -> List[NewsEvent]:
        """
        Lấy tin tức từ Telegram channel @lichkinhte via web preview
        Channel này cập nhật lịch kinh tế tiếng Việt rất tốt
        """
        url = "https://t.me/s/lichkinhte"
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return []
            
            if not BS4_AVAILABLE:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            messages = soup.find_all('div', class_='tgme_widget_message_text')
            
            events = []
            today = datetime.now().strftime("%d/%m")
            
            for msg in messages[-20:]:  # Lấy 20 tin mới nhất
                text = msg.get_text(strip=True)
                
                # Parse tin tức có format: 🇺🇸 Hoa Kỳ : Event...
                if any(flag in text for flag in ['🇺🇸', '🇪🇺', '🇬🇧', '🇯🇵', '🇨🇳', '🇦🇺', '🇨🇦', '🇨🇭', '🇻🇳']):
                    # Xác định impact từ số sao
                    if '⭐⭐⭐⭐⭐' in text or '⭐⭐⭐⭐☆' in text:
                        impact = 'HIGH'
                    elif '⭐⭐⭐' in text:
                        impact = 'MEDIUM'
                    else:
                        impact = 'LOW'
                    
                    # Xác định tốt/xấu
                    is_positive = '🟢' in text
                    is_negative = '🔴' in text
                    
                    # Parse currency
                    currency = 'USD'
                    if '🇪🇺' in text:
                        currency = 'EUR'
                    elif '🇬🇧' in text:
                        currency = 'GBP'
                    elif '🇯🇵' in text:
                        currency = 'JPY'
                    elif '🇨🇳' in text:
                        currency = 'CNY'
                    elif '🇻🇳' in text:
                        currency = 'VND'
                    
                    # Extract event name (after country name)
                    event_match = re.search(r'[A-Z][a-z]+\s*:\s*(.+?)(?:🔴|🟢|Trước đó)', text)
                    event_name = event_match.group(1).strip() if event_match else text[:80]
                    
                    # Extract actual value
                    actual_match = re.search(r'Thực tế\s*:\s*([^\n]+)', text)
                    actual = actual_match.group(1).strip() if actual_match else ''
                    
                    # Extract forecast
                    forecast_match = re.search(r'Kì vọng\s*:\s*([^\n]+)', text)
                    forecast = forecast_match.group(1).strip() if forecast_match else '--'
                    
                    # Extract previous
                    prev_match = re.search(r'Trước đó\s*:\s*([^\n]+)', text)
                    previous = prev_match.group(1).strip() if prev_match else ''
                    
                    events.append(NewsEvent(
                        time=datetime.now().strftime("%H:%M"),
                        currency=currency,
                        impact=impact,
                        event=event_name,
                        forecast=forecast,
                        previous=previous,
                        actual=actual,
                        title_vi=event_name
                    ))
            
            return events
            
        except Exception as e:
            return []
    
    def _crawl_nasdaq(self) -> List[NewsEvent]:
        """
        Lấy lịch kinh tế từ NASDAQ API (Reliable, no rate limit)
        """
        url = "https://api.nasdaq.com/api/calendar/economicevents"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        params = {'date': today_str}
        
        response = self.session.get(url, headers=headers, params=params, timeout=10, verify=False)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        data = response.json()
        rows = data.get('data', {}).get('calendar', {}).get('rows', [])
        
        events = []
        
        # Dictionary to translate NASDAQ events to Vietnamese
        translate_dict = {
            "GDP": "GDP (Tổng sản phẩm quốc nội)",
            "CPI": "CPI (Lạm phát)",
            "PPI": "PPI (Chỉ số sản xuất)",
            "Nonfarm Payrolls": "Bảng lương Non-Farm",
            "Unemployment Rate": "Tỷ lệ Thất nghiệp",
            "Fed Interest Rate": "Lãi suất Fed",
            "FOMC": "Biên bản họp FOMC",
            "Initial Jobless Claims": "Đơn xin trợ cấp thất nghiệp",
            "Retail Sales": "Doanh số Bán lẻ",
            "Crude Oil": "Dự trữ Dầu thô",
            "Consumer Confidence": "Niềm tin Tiêu dùng"
        }
        
        for item in rows:
            # Only US events
            if item.get('country') != 'United States':
                continue
            
            name = item.get('eventTitle', '')
            time_str = item.get('time', '00:00')
            actual = item.get('actual', '')
            forecast = item.get('consensus', '')
            
            # Check if important
            is_important = any(key in name for key in translate_dict.keys())
            
            if is_important:
                # Translate to Vietnamese
                vn_name = name
                for en, vn in translate_dict.items():
                    if en in name:
                        vn_name = vn
                        break
                
                events.append(NewsEvent(
                    time=time_str,
                    currency='USD',
                    impact='HIGH',
                    event=name,
                    title_vi=vn_name,
                    forecast=forecast,
                    previous=actual
                ))
        
        return events
    
    def _crawl_cafef(self) -> List[NewsEvent]:
        """
        Lấy tin tức từ CafeF (Vietnamese financial news)
        Fallback khi NASDAQ không có data
        """
        from bs4 import BeautifulSoup
        
        url = "https://cafef.vn/tai-chinh-quoc-te.chn"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = self.session.get(url, headers=headers, timeout=10, verify=False)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = soup.find_all('h3', limit=15)
        
        events = []
        keywords = ["Vàng", "USD", "Fed", "Lãi suất", "Lạm phát", "Chứng khoán", "Gold"]
        
        current_time = datetime.now().strftime("%H:%M")
        
        for article in articles:
            text = article.text.strip()
            
            if any(k.lower() in text.lower() for k in keywords):
                events.append(NewsEvent(
                    time=current_time,
                    currency='USD',
                    impact='MEDIUM',
                    event=text[:100],  # Truncate to 100 chars
                    title_vi=text[:100],
                    forecast='',
                    previous=''
                ))
                
                if len(events) >= 5:  # Max 5 events
                    break
        
        return events
    
    def _crawl_forexfactory(self) -> List[NewsEvent]:
        """
        Lấy data từ ForexFactory JSON API (Hidden endpoint)
        URL thần thánh: https://nfs.faireconomy.media/ff_calendar_thisweek.json
        """
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            
            data = response.json()
            events = []
            
            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")
            
            for item in data:
                try:
                    # Parse date
                    event_date = item.get('date', '')[:10]  # YYYY-MM-DD
                    
                    # Only get today and tomorrow's events
                    if event_date < today:
                        continue
                    
                    # Map impact
                    impact_map = {
                        'Holiday': 'LOW',
                        'Low': 'LOW',
                        'Medium': 'MEDIUM',
                        'High': 'HIGH'
                    }
                    impact = impact_map.get(item.get('impact', 'Low'), 'LOW')
                    
                    # Parse time
                    time_str = item.get('date', '')[11:16]  # HH:MM
                    if not time_str:
                        time_str = 'All Day'
                    
                    events.append(NewsEvent(
                        time=time_str,
                        currency=item.get('country', 'USD'),
                        impact=impact,
                        event=item.get('title', ''),
                        forecast=str(item.get('forecast', '')),
                        previous=str(item.get('previous', '')),
                        actual=str(item.get('actual', '')),
                        title_vi=''  # Sẽ dịch sau nếu cần
                    ))
                except:
                    continue
            
            print(f"✅ ForexFactory JSON: {len(events)} events loaded")
            return events
            
        except Exception as e:
            print(f"⚠️ ForexFactory JSON failed: {e}")
            return []
    
    def _get_news_from_api(self) -> List[NewsEvent]:
        """Fallback API for economic calendar"""
        # Using mock data as fallback since most calendar APIs require auth
        return self._get_mock_calendar()
    
    def _crawl_investing_calendar(self) -> List[NewsEvent]:
        """Crawl từ Investing.com"""
        url = "https://www.investing.com/economic-calendar/"
        
        response = self.session.get(url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        if not BS4_AVAILABLE:
            raise Exception("BeautifulSoup not available")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        events = []
        
        # Parse calendar table (simplified)
        # Note: Actual parsing depends on current HTML structure
        rows = soup.find_all('tr', class_='js-event-item')[:20]
        
        for row in rows:
            try:
                time_el = row.find('td', class_='time')
                currency_el = row.find('td', class_='flagCur')
                event_el = row.find('td', class_='event')
                
                if time_el and event_el:
                    # Get impact (bulls icons)
                    impact_el = row.find('td', class_='sentiment')
                    impact = 'LOW'
                    if impact_el:
                        bulls = len(impact_el.find_all('i', class_='grayFullBullishIcon'))
                        if bulls >= 3:
                            impact = 'HIGH'
                        elif bulls == 2:
                            impact = 'MEDIUM'
                    
                    events.append(NewsEvent(
                        time=time_el.text.strip(),
                        currency=currency_el.text.strip() if currency_el else 'USD',
                        impact=impact,
                        event=event_el.text.strip(),
                        forecast='',
                        previous='',
                        actual='',
                        title_vi=''
                    ))
            except:
                continue
        
        return events
    
    def _get_mock_calendar(self) -> List[NewsEvent]:
        """Mock data khi không crawl được"""
        now = datetime.now()
        
        return [
            NewsEvent(
                time=now.strftime("%H:%M"),
                currency='USD',
                impact='HIGH',
                event='Core CPI m/m',
                forecast='0.3%',
                previous='0.2%',
                actual='',
                title_vi='Chỉ số CPI lõi tháng'
            ),
            NewsEvent(
                time=(now + timedelta(hours=2)).strftime("%H:%M"),
                currency='USD',
                impact='HIGH', 
                event='FOMC Statement',
                forecast='',
                previous='',
                actual='',
                title_vi='Tuyên bố của FOMC'
            )
        ]
    
    def get_high_impact_news(self, currency: str = 'USD') -> List[NewsEvent]:
        """
        Chỉ lấy tin QUAN TRỌNG (High Impact) cho một loại tiền
        """
        all_events = self.get_economic_calendar()
        
        high_impact = [
            e for e in all_events 
            if e.impact == 'HIGH' and currency.upper() in e.currency.upper()
        ]
        
        # Dịch sang tiếng Việt
        if self.model:
            for event in high_impact:
                event.title_vi = self._translate_event(event.event)
        
        return high_impact
    
    def _translate_event(self, event_name: str) -> str:
        """Dịch tên sự kiện sang tiếng Việt"""
        if not self.model:
            return event_name
        
        # Translation dictionary cho các sự kiện phổ biến
        translations = {
            'Non-Farm Payrolls': 'Bảng lương phi nông nghiệp',
            'CPI': 'Chỉ số giá tiêu dùng',
            'Core CPI': 'CPI lõi (không thực phẩm & năng lượng)',
            'PPI': 'Chỉ số giá sản xuất',
            'GDP': 'Tổng sản phẩm quốc nội',
            'FOMC': 'Cuộc họp Ủy ban Thị trường Mở',
            'Interest Rate Decision': 'Quyết định lãi suất',
            'Unemployment Rate': 'Tỷ lệ thất nghiệp',
            'Retail Sales': 'Doanh số bán lẻ',
            'PMI': 'Chỉ số quản lý thu mua',
        }
        
        for eng, vi in translations.items():
            if eng.lower() in event_name.lower():
                return vi
        
        # Use AI for unknown terms
        try:
            prompt = f"Dịch thuật ngữ tài chính sau sang tiếng Việt ngắn gọn (chỉ trả về bản dịch): {event_name}"
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except:
            return event_name
    
    def should_pause_trading(self, minutes_before: int = 30) -> Tuple[bool, Optional[NewsEvent]]:
        """
        Kiểm tra có nên tạm dừng trading không
        (Có tin High Impact trong X phút tới?)
        
        Returns:
            (should_pause, upcoming_event)
        """
        high_impact = self.get_high_impact_news('USD')
        
        now = datetime.now()
        
        for event in high_impact:
            try:
                # Parse event time
                event_time = datetime.strptime(event.time, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )
                
                # Check if within window
                time_diff = (event_time - now).total_seconds() / 60
                
                if 0 <= time_diff <= minutes_before:
                    return True, event
            except:
                continue
        
        return False, None
    
    def is_gold_impacting(self, event: NewsEvent) -> bool:
        """Kiểm tra tin có ảnh hưởng đến Vàng không"""
        for keyword in self.GOLD_IMPACT_EVENTS:
            if keyword.lower() in event.event.lower():
                return True
        return event.currency == 'USD' and event.impact == 'HIGH'
    
    def get_news_summary(self) -> str:
        """Tạo tóm tắt tin tức"""
        high_impact = self.get_high_impact_news('USD')
        should_pause, upcoming = self.should_pause_trading()
        
        lines = [
            "📰 TIN TỨC KINH TẾ",
            "=" * 30,
        ]
        
        if should_pause and upcoming:
            lines.append(f"⚠️ CẢNH BÁO: Sắp có tin quan trọng!")
            lines.append(f"   🕐 {upcoming.time} - {upcoming.event}")
            if upcoming.title_vi:
                lines.append(f"   🇻🇳 {upcoming.title_vi}")
            lines.append(f"   💡 Nên TẠM DỪNG giao dịch để tránh rủi ro!")
        else:
            lines.append("✅ Không có tin quan trọng sắp tới")
        
        if high_impact:
            lines.append(f"\n📋 Tin High Impact hôm nay ({len(high_impact)}):")
            for event in high_impact[:5]:
                icon = "🔴" if event.impact == 'HIGH' else "🟡"
                lines.append(f"   {icon} {event.time} - {event.event}")
        
        return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    crawler = NewsCrawler(api_key)
    
    print("Testing News Crawler...")
    print(crawler.get_news_summary())
    
    # Test pause check
    should_pause, event = crawler.should_pause_trading()
    print(f"\nShould pause: {should_pause}")
    if event:
        print(f"Upcoming: {event.event}")
