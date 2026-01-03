"""
Gemini Forex Bot - Configuration
Tập trung tất cả cấu hình và API keys
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============== API KEYS ==============
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============== FIREBASE CONFIG ==============
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": "gen-lang-client-0378738005.firebaseapp.com",
    "databaseURL": os.getenv("FIREBASE_DATABASE_URL"),
    "projectId": "gen-lang-client-0378738005",
    "storageBucket": "gen-lang-client-0378738005.firebasestorage.app",
    "messagingSenderId": "368275384827",
    "appId": "1:368275384827:web:fe2e4edbc812156b69435e"
}

# ============== TRADING CONFIG ==============
SYMBOL = "XAUUSD"
TIMEFRAME = "M15"  # M5, M15, H1
EXCHANGE = "OANDA"  # Sàn: OANDA, FXCM, FOREXCOM
N_CANDLES = 30  # Số nến lấy về

# ============== RISK MANAGEMENT ==============
USER_CAPITAL = 100  # Số vốn (USD)
RISK_PERCENT = 0.02  # 2% rủi ro mỗi lệnh
MIN_LOT = 0.01  # Lot tối thiểu
MAX_DAILY_LOSS = 0.06  # Dừng giao dịch nếu lỗ 6%/ngày

# ============== TIME FILTERS (GMT) ==============
ASIAN_SESSION_START = "00:00"
ASIAN_SESSION_END = "06:00"
LONDON_OPEN = "07:00"
NY_OPEN = "12:00"
KILL_ZONE_START = "12:00"  # London-NY overlap
KILL_ZONE_END = "16:00"

# ============== TECHNICAL INDICATORS ==============
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14

# ============== BOT SETTINGS ==============
# Check interval - 2 minutes for fast signal detection
LOOP_INTERVAL = 120  # 2 minutes - Fast signal & news checking

# Real-time thresholds (kept for future use)
SIGNAL_CHECK_INTERVAL = 120  # 2 minutes
NEWS_CHECK_INTERVAL = 300     # 5 minutes

ERROR_RETRY_INTERVAL = 60  # Thử lại sau 60s nếu lỗi
