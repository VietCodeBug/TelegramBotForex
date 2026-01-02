"""
Debug Script - Test specific channel parsing
"""
import os
from dotenv import load_dotenv
from services.signal_crawler import SignalCrawler
from services.ai_engine import WyckoffAIEngine

load_dotenv()

print("🔍 DEBUGGING SIGNAL PARSER")
print("=" * 60)

# Initialize
api_key = os.getenv("GOOGLE_API_KEY")
ai = WyckoffAIEngine(api_key)
crawler = SignalCrawler(ai_engine=ai)

# Test crawl XAUUSD INSIDER specifically
channel = "XAUUSDINSIDER_FX"
print(f"\n📡 Crawling @{channel}...")

signals = crawler._crawl_channel(channel)

print(f"\n✅ Found {len(signals)} signals from @{channel}")
print("=" * 60)

for sig in signals:
    print(f"\n📊 Signal:")
    print(f"   Action: {sig.action}")
    print(f"   Symbol: {sig.symbol}")
    print(f"   Entry: {sig.entry}")
    print(f"   SL: {sig.stoploss}")
    print(f"   TP: {sig.takeprofit}")
    print(f"   Timestamp: {sig.timestamp}")
    print(f"   Has Image: {'Yes' if sig.image_url else 'No'}")
    print(f"   Raw: {sig.raw_text[:100]}...")
    print("-" * 60)

# Also test the text parsing
test_text = """Sell limit 4410-4414
sL. 4416"""

print(f"\n🧪 Testing parser with text:")
print(f'   "{test_text}"')

result = crawler._parse_signal(test_text, "XAUUSDINSIDER_FX", "", "15:00 02/01/2026")
if result:
    print(f"\n✅ Parsed successfully:")
    print(f"   Action: {result.action}")
    print(f"   Entry: {result.entry}")
    print(f"   SL: {result.stoploss}")
else:
    print("\n❌ Failed to parse!")
