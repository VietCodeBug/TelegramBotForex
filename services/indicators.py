"""
Technical Indicators Module - Tính toán các chỉ báo kỹ thuật
RSI, MACD, EMA, ATR sử dụng pandas_ta hoặc ta library
"""
import pandas as pd
import numpy as np

# Try pandas-ta first (Python 3.12+), then ta library (Python 3.11 compatible)
TA_AVAILABLE = False
TA_LIB_TYPE = None  # "pandas_ta" or "ta"

try:
    import pandas_ta as ta
    TA_AVAILABLE = True
    TA_LIB_TYPE = "pandas_ta"
except ImportError:
    try:
        import ta as ta_lib
        TA_AVAILABLE = True
        TA_LIB_TYPE = "ta"
        print("✅ Using 'ta' library (Python 3.11 compatible)")
    except ImportError:
        TA_AVAILABLE = False
        print("⚠️ No TA library installed. Using basic calculations.")


def calculate_indicators(df: pd.DataFrame, 
                         rsi_period: int = 14,
                         ema_fast: int = 50,
                         ema_slow: int = 200,
                         atr_period: int = 14) -> pd.DataFrame:
    """
    Tính toán các chỉ báo kỹ thuật chính
    
    Args:
        df: DataFrame với columns [open, high, low, close, volume]
        rsi_period: Chu kỳ RSI (default 14)
        ema_fast: EMA nhanh (default 50)
        ema_slow: EMA chậm (default 200)
        atr_period: Chu kỳ ATR (default 14)
    
    Returns:
        DataFrame với các cột chỉ báo đã thêm
    """
    df = df.copy()
    
    if TA_AVAILABLE and TA_LIB_TYPE == "pandas_ta":
        # Use pandas_ta (Python 3.12+)
        # RSI
        df['RSI'] = ta.rsi(df['close'], length=rsi_period)
        
        # EMA
        df['EMA_50'] = ta.ema(df['close'], length=ema_fast)
        df['EMA_200'] = ta.ema(df['close'], length=ema_slow)
        
        # ATR
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=atr_period)
        
        # MACD
        macd = ta.macd(df['close'])
        if macd is not None:
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_Signal'] = macd['MACDs_12_26_9']
            df['MACD_Hist'] = macd['MACDh_12_26_9']
        
        # Bollinger Bands (bonus)
        try:
            bb = ta.bbands(df['close'], length=20)
            if bb is not None and not bb.empty:
                for col in bb.columns:
                    if 'BBU' in col:
                        df['BB_Upper'] = bb[col]
                    elif 'BBL' in col:
                        df['BB_Lower'] = bb[col]
                    elif 'BBM' in col:
                        df['BB_Middle'] = bb[col]
        except Exception:
            pass
            
    elif TA_AVAILABLE and TA_LIB_TYPE == "ta":
        # Use ta library (Python 3.11 compatible)
        # RSI
        df['RSI'] = ta_lib.momentum.RSIIndicator(df['close'], window=rsi_period).rsi()
        
        # EMA
        df['EMA_50'] = ta_lib.trend.EMAIndicator(df['close'], window=ema_fast).ema_indicator()
        df['EMA_200'] = ta_lib.trend.EMAIndicator(df['close'], window=ema_slow).ema_indicator()
        
        # ATR
        df['ATR'] = ta_lib.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=atr_period).average_true_range()
        
        # MACD
        macd_indicator = ta_lib.trend.MACD(df['close'])
        df['MACD'] = macd_indicator.macd()
        df['MACD_Signal'] = macd_indicator.macd_signal()
        df['MACD_Hist'] = macd_indicator.macd_diff()
        
        # Bollinger Bands
        try:
            bb = ta_lib.volatility.BollingerBands(df['close'], window=20)
            df['BB_Upper'] = bb.bollinger_hband()
            df['BB_Lower'] = bb.bollinger_lband()
            df['BB_Middle'] = bb.bollinger_mavg()
        except Exception:
            pass
    else:
        # Fallback: Basic calculations
        df = _calculate_rsi_basic(df, rsi_period)
        df = _calculate_ema_basic(df, ema_fast, ema_slow)
        df = _calculate_atr_basic(df, atr_period)
    
    return df


def _calculate_rsi_basic(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Tính RSI thủ công"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df


def _calculate_ema_basic(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Tính EMA thủ công"""
    df['EMA_50'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['EMA_200'] = df['close'].ewm(span=slow, adjust=False).mean()
    return df


def _calculate_atr_basic(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Tính ATR thủ công"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = true_range.rolling(window=period).mean()
    return df


def get_trend(df: pd.DataFrame) -> str:
    """
    Xác định xu hướng dựa trên EMA
    
    Returns:
        "UPTREND", "DOWNTREND", hoặc "SIDEWAYS"
    """
    if 'EMA_50' not in df.columns:
        return "UNKNOWN"
    
    try:
        current_price = df['close'].iloc[-1]
        ema_50 = df['EMA_50'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1] if 'EMA_200' in df.columns else ema_50
        
        # Handle NaN values
        if pd.isna(current_price) or pd.isna(ema_50):
            return "UNKNOWN"
        if pd.isna(ema_200):
            ema_200 = ema_50
        
        # Giá trên cả 2 EMA -> Uptrend mạnh
        if current_price > ema_50 and current_price > ema_200:
            if ema_50 > ema_200:
                return "STRONG_UPTREND"
            return "UPTREND"
        
        # Giá dưới cả 2 EMA -> Downtrend mạnh
        elif current_price < ema_50 and current_price < ema_200:
            if ema_50 < ema_200:
                return "STRONG_DOWNTREND"
            return "DOWNTREND"
        
        else:
            return "SIDEWAYS"
    except Exception:
        return "UNKNOWN"


def get_rsi_signal(df: pd.DataFrame, overbought: float = 70, oversold: float = 30) -> str:
    """
    Đánh giá RSI
    
    Returns:
        "OVERBOUGHT", "OVERSOLD", "NEUTRAL", hoặc "BULLISH"/"BEARISH"
    """
    if 'RSI' not in df.columns:
        return "UNKNOWN"
    
    rsi = df['RSI'].iloc[-1]
    rsi_prev = df['RSI'].iloc[-2] if len(df) > 1 else rsi
    
    if pd.isna(rsi):
        return "UNKNOWN"
    
    if rsi > overbought:
        return "OVERBOUGHT"
    elif rsi < oversold:
        return "OVERSOLD"
    elif rsi > 50 and rsi > rsi_prev:
        return "BULLISH_MOMENTUM"
    elif rsi < 50 and rsi < rsi_prev:
        return "BEARISH_MOMENTUM"
    else:
        return "NEUTRAL"


def get_macd_signal(df: pd.DataFrame) -> str:
    """
    Đánh giá MACD
    
    Returns:
        "BULLISH_CROSS", "BEARISH_CROSS", "BULLISH", "BEARISH"
    """
    if 'MACD' not in df.columns or 'MACD_Signal' not in df.columns:
        return "UNKNOWN"
    
    macd = df['MACD'].iloc[-1]
    signal = df['MACD_Signal'].iloc[-1]
    macd_prev = df['MACD'].iloc[-2] if len(df) > 1 else macd
    signal_prev = df['MACD_Signal'].iloc[-2] if len(df) > 1 else signal
    
    if pd.isna(macd) or pd.isna(signal):
        return "UNKNOWN"
    
    # Check for crossover
    if macd > signal and macd_prev <= signal_prev:
        return "BULLISH_CROSS"
    elif macd < signal and macd_prev >= signal_prev:
        return "BEARISH_CROSS"
    elif macd > signal:
        return "BULLISH"
    else:
        return "BEARISH"


def get_indicator_summary(df: pd.DataFrame) -> dict:
    """
    Tổng hợp tất cả chỉ báo thành dict để gửi cho AI
    
    Returns:
        Dict chứa tất cả thông tin chỉ báo
    """
    def safe_round(val, decimals=2):
        """Safely round a value, handling None and NaN"""
        try:
            if val is None or pd.isna(val):
                return None
            return round(float(val), decimals)
        except (TypeError, ValueError):
            return None
    
    summary = {}
    
    try:
        # Price info
        if len(df) > 0:
            price = safe_round(df['close'].iloc[-1])
            if price:
                summary['Current_Price'] = price
            if len(df) > 1:
                change = safe_round(df['close'].iloc[-1] - df['close'].iloc[-2])
                if change is not None:
                    summary['Change'] = change
        
        # RSI
        if 'RSI' in df.columns:
            rsi_val = safe_round(df['RSI'].iloc[-1])
            if rsi_val is not None:
                summary['RSI'] = rsi_val
                summary['RSI_Signal'] = get_rsi_signal(df)
        
        # Trend
        summary['Trend'] = get_trend(df)
        
        # EMA
        if 'EMA_50' in df.columns:
            ema50 = safe_round(df['EMA_50'].iloc[-1])
            if ema50:
                summary['EMA_50'] = ema50
        if 'EMA_200' in df.columns:
            ema200 = safe_round(df['EMA_200'].iloc[-1])
            if ema200:
                summary['EMA_200'] = ema200
        
        # MACD
        summary['MACD_Signal'] = get_macd_signal(df)
        
        # ATR (for SL calculation)
        if 'ATR' in df.columns:
            atr_val = safe_round(df['ATR'].iloc[-1])
            if atr_val is not None:
                summary['ATR'] = atr_val
                summary['Suggested_SL_Distance'] = safe_round(atr_val * 1.5)
    except Exception as e:
        summary['error'] = str(e)
    
    return summary


# Quick test
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range(end='2024-01-01', periods=50, freq='15min')
    np.random.seed(42)
    
    base = 2030
    changes = np.random.randn(50) * 2
    closes = base + np.cumsum(changes)
    
    df = pd.DataFrame({
        'open': closes - np.random.rand(50),
        'high': closes + np.random.rand(50) * 2,
        'low': closes - np.random.rand(50) * 2,
        'close': closes,
        'volume': np.random.randint(100, 1000, 50)
    }, index=dates)
    
    # Calculate indicators
    df = calculate_indicators(df)
    
    # Get summary
    summary = get_indicator_summary(df)
    print("📊 Indicator Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
