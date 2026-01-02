"""
AI Engine v2.0 - Tích hợp Wyckoff + SMC Analysis
Sử dụng Gemini 2.5 Pro cho phân tích chuyên sâu
"""
import json
import re
import asyncio
import functools
from typing import Optional, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Thread pool for running sync functions in background
_executor = ThreadPoolExecutor(max_workers=2)


# WYCKOFF EXPERT PROMPT
WYCKOFF_EXPERT_PROMPT = """
🎯 BẠN LÀ CHUYÊN GIA PHÂN TÍCH WYCKOFF + SMART MONEY 
Với 20 năm kinh nghiệm giao dịch Vàng (XAU/USD).

═══════════════════════════════════════
📊 PHƯƠNG PHÁP PHÂN TÍCH (Wyckoff Method)
═══════════════════════════════════════

1️⃣ XÁC ĐỊNH PHA HIỆN TẠI:
   • ACCUMULATION (Tích lũy): Composite Man đang mua - Chuẩn bị tăng giá
   • DISTRIBUTION (Phân phối): Composite Man đang bán - Chuẩn bị giảm giá  
   • MARKUP: Xu hướng tăng
   • MARKDOWN: Xu hướng giảm

2️⃣ PHÁT HIỆN SỰ KIỆN WYCKOFF:
   • SPRING: Phá vỡ support giả → BUY signal mạnh (Bẫy Gấu)
   • UPTHRUST (UTAD): Phá vỡ resistance giả → SELL signal mạnh (Bẫy Bò)
   • SOS (Sign of Strength): Nến tăng mạnh + volume cao → Phe mua kiểm soát
   • SOW (Sign of Weakness): Nến giảm mạnh + volume cao → Phe bán kiểm soát
   • LPS (Last Point of Support): Điểm vào lệnh BUY an toàn nhất
   • LPSY (Last Point of Supply): Điểm vào lệnh SELL an toàn nhất

3️⃣ VOLUME SPREAD ANALYSIS (VSA):
   • EFFORT (Volume cao) + RESULT nhỏ (Spread hẹp) = ABSORPTION (Hấp thụ) → Đảo chiều sắp tới
   • EFFORT thấp + RESULT lớn = Easy Movement → Xu hướng tiếp diễn

4️⃣ SMART MONEY CONCEPTS (SMC):
   • FVG (Fair Value Gap): Vùng mất cân bằng cung cầu
   • Order Block: Vùng lệnh của tổ chức lớn
   • Liquidity Sweep: Quét stop loss trước khi đảo chiều

═══════════════════════════════════════
⚠️ QUY TẮC VÀNG (QUAN TRỌNG!)
═══════════════════════════════════════

❌ KHÔNG bao giờ giao dịch ở lần phá vỡ ĐẦU TIÊN
✅ LUÔN chờ TEST hoặc LPS/LPSY để vào lệnh an toàn
❌ KHÔNG spam lệnh - Chỉ gửi tín hiệu khi Confidence >= 70%
✅ Nếu không chắc chắn → Trả về WAIT

═══════════════════════════════════════
📋 FORMAT TRẢ VỀ (JSON ONLY)
═══════════════════════════════════════

```json
{
    "action": "BUY" | "SELL" | "WAIT",
    "wyckoff_phase": "ACCUMULATION | DISTRIBUTION | MARKUP | MARKDOWN",
    "event_detected": "SPRING | UPTHRUST | SOS | SOW | LPS | LPSY | NONE",
    "smc_trigger": "FVG | ORDER_BLOCK | LIQUIDITY_SWEEP | NONE",
    "entry": <giá vào lệnh>,
    "stoploss": <giá cắt lỗ>,
    "takeprofit": <giá chốt lời>,
    "confidence": <0-100>,
    "reason": "<lý do ngắn gọn bằng TIẾNG VIỆT>"
}
```

⚠️ NHỚ: 
- Confidence < 70 → PHẢI trả về action: "WAIT"
- Nếu không phát hiện event → event_detected: "NONE"
- Reason phải bằng TIẾNG VIỆT, ngắn gọn, dễ hiểu
"""


class WyckoffAIEngine:
    """
    AI Engine v2.0 với Wyckoff + SMC expertise
    Sử dụng Gemini 2.5 Pro
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        """
        Args:
            api_key: Google API Key
            model_name: gemini-2.5-pro (mạnh nhất), gemini-2.5-flash (nhanh hơn)
        """
        self.api_key = api_key
        self.model_name = model_name
        self.model = None
        
        if GENAI_AVAILABLE and api_key:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(model_name)
                print(f"✅ Wyckoff AI Engine initialized with {model_name}")
            except Exception as e:
                print(f"❌ Failed to initialize AI: {e}")
    
    def analyze(self, 
                market_data: str, 
                indicators: Dict,
                wyckoff_analysis: Dict = None,
                smc_analysis: Dict = None,
                news_context: str = None) -> Dict:
        """
        Phân tích thị trường với Wyckoff + SMC
        
        Args:
            market_data: Dữ liệu giá đã format
            indicators: Dict chỉ báo kỹ thuật
            wyckoff_analysis: Kết quả từ WyckoffAnalyzer
            smc_analysis: Kết quả từ SMCAnalyzer
            news_context: Bối cảnh tin tức
            
        Returns:
            Dict với action, entry, sl, tp, confidence, reason
        """
        if not self.model:
            return self._get_demo_signal()
        
        # Build comprehensive prompt
        full_prompt = self._build_prompt(
            market_data, indicators, wyckoff_analysis, smc_analysis, news_context
        )
        
        try:
            response = self.model.generate_content(full_prompt)
            return self._parse_response(response.text)
        except Exception as e:
            print(f"❌ AI Analysis error: {e}")
            return self._get_wait_signal(f"Lỗi AI: {str(e)[:50]}")
    
    async def analyze_async(self, 
                market_data: str, 
                indicators: Dict,
                wyckoff_analysis: Dict = None,
                smc_analysis: Dict = None,
                news_context: str = None) -> Dict:
        """
        Async version - Chạy AI trong thread riêng để không block bot
        Dùng cho Replit FREE tier khi CPU bị throttle
        """
        loop = asyncio.get_running_loop()
        
        # Đẩy việc nặng sang thread khác
        result = await loop.run_in_executor(
            _executor,
            functools.partial(
                self.analyze,
                market_data=market_data,
                indicators=indicators,
                wyckoff_analysis=wyckoff_analysis,
                smc_analysis=smc_analysis,
                news_context=news_context
            )
        )
        return result
    
    def analyze_external_signal(self, signal_data: Dict, current_price: float = None) -> Dict:
        """
        Phân tích tín hiệu từ kênh Telegram bên ngoài
        
        Args:
            signal_data: Dict với source, action, entry, sl, tp
            current_price: Giá hiện tại (nếu có)
            
        Returns:
            Dict với recommendation, confidence, reason
        """
        if not self.model:
            return {
                'recommendation': 'UNKNOWN',
                'confidence': 0,
                'reason': 'AI không khả dụng'
            }
        
        prompt = f"""
🎯 PHÂN TÍCH TÍN HIỆU TRADING TỪ KÊNH TELEGRAM

📊 TÍN HIỆU:
- Nguồn: @{signal_data.get('source', 'unknown')}
- Lệnh: {signal_data.get('action', 'N/A')}
- Symbol: {signal_data.get('symbol', 'XAUUSD')}
- Entry: {signal_data.get('entry', 'N/A')}
- Stop Loss: {signal_data.get('stoploss', 'N/A')}
- Take Profit: {signal_data.get('takeprofit', 'N/A')}
{"- Giá hiện tại: " + str(current_price) if current_price else ""}

📋 YÊU CẦU:
1. Đánh giá tín hiệu này có HỢP LÝ không?
2. Risk/Reward ratio có tốt không?
3. Entry point có hợp lý không?
4. Nên THEO hay BỎ QUA tín hiệu này?

Trả lời theo format JSON:
```json
{{
    "recommendation": "FOLLOW" | "SKIP" | "CAUTION",
    "confidence": <0-100>,
    "risk_reward": "<X:X>",
    "reason": "<lý do ngắn gọn tiếng Việt>"
}}
```
"""
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_signal_analysis(response.text, signal_data)
        except Exception as e:
            return {
                'recommendation': 'SKIP',
                'confidence': 0,
                'reason': f'Lỗi AI: {str(e)[:50]}'
            }
    
    def _parse_signal_analysis(self, response_text: str, original_signal: Dict) -> Dict:
        """Parse response từ AI cho external signal"""
        import json
        
        try:
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'recommendation': result.get('recommendation', 'SKIP'),
                    'confidence': result.get('confidence', 0),
                    'risk_reward': result.get('risk_reward', 'N/A'),
                    'reason': result.get('reason', 'Không có nhận định'),
                    'original_signal': original_signal
                }
        except:
            pass
        
        return {
            'recommendation': 'SKIP',
            'confidence': 0,
            'reason': 'Không parse được response',
            'original_signal': original_signal
        }
    
    def _build_prompt(self, market_data: str, indicators: Dict,
                      wyckoff: Dict = None, smc: Dict = None, 
                      news: str = None) -> str:
        """Xây dựng prompt đầy đủ"""
        
        sections = [WYCKOFF_EXPERT_PROMPT]
        
        sections.append(f"""
═══════════════════════════════════════
📊 DỮ LIỆU THỊ TRƯỜNG HIỆN TẠI
═══════════════════════════════════════
{market_data}
""")
        
        # Technical indicators
        indicators_str = "\n".join([f"   • {k}: {v}" for k, v in indicators.items()])
        sections.append(f"""
═══════════════════════════════════════
📈 CHỈ BÁO KỸ THUẬT
═══════════════════════════════════════
{indicators_str}
""")
        
        # Wyckoff analysis
        if wyckoff:
            sections.append(f"""
═══════════════════════════════════════
🔮 PHÂN TÍCH WYCKOFF (Pre-computed)
═══════════════════════════════════════
   • Phase: {wyckoff.get('phase', 'N/A')}
   • Events: {[e.event_type for e in wyckoff.get('events', [])]}
   • VSA Signal: {wyckoff.get('vsa', {}).get('signal', 'N/A')}
""")
        
        # SMC analysis
        if smc:
            sections.append(f"""
═══════════════════════════════════════
🎯 PHÂN TÍCH SMC (Pre-computed)
═══════════════════════════════════════
   • Structure: {smc.get('structure', {}).get('trend', 'N/A')}
   • FVGs: {len(smc.get('fvgs', []))} active
   • Order Blocks: {len(smc.get('order_blocks', []))} active
   • Sweep: {smc.get('sweep', {}).get('type', 'None') if smc.get('sweep') else 'None'}
""")
        
        # News context
        if news:
            sections.append(f"""
═══════════════════════════════════════
📰 BỐI CẢNH TIN TỨC
═══════════════════════════════════════
{news}
""")
        
        sections.append("""
═══════════════════════════════════════
🎯 YÊU CẦU
═══════════════════════════════════════
Dựa trên tất cả dữ liệu trên, hãy phân tích và đưa ra quyết định giao dịch.
Trả về KẾT QUẢ theo format JSON đã định nghĩa.
NHỚ: Confidence < 70 → action PHẢI là "WAIT"
""")
        
        return "\n".join(sections)
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse response từ AI"""
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate and normalize
                action = result.get('action', 'WAIT').upper()
                confidence = result.get('confidence', 0)
                
                # Enforce confidence rule
                if confidence < 70:
                    action = 'WAIT'
                
                return {
                    'action': action,
                    'wyckoff_phase': result.get('wyckoff_phase', 'UNKNOWN'),
                    'event_detected': result.get('event_detected', 'NONE'),
                    'smc_trigger': result.get('smc_trigger', 'NONE'),
                    'entry': result.get('entry'),
                    'stoploss': result.get('stoploss'),
                    'takeprofit': result.get('takeprofit'),
                    'confidence': confidence,
                    'reason': result.get('reason', 'Không có lý do cụ thể')
                }
            
            return self._get_wait_signal("Không parse được JSON từ AI")
            
        except json.JSONDecodeError:
            return self._get_wait_signal("Lỗi parse JSON")
    
    def _get_wait_signal(self, reason: str) -> Dict:
        """Trả về tín hiệu WAIT"""
        return {
            'action': 'WAIT',
            'wyckoff_phase': 'UNKNOWN',
            'event_detected': 'NONE',
            'smc_trigger': 'NONE',
            'entry': None,
            'stoploss': None,
            'takeprofit': None,
            'confidence': 0,
            'reason': reason
        }
    
    def _get_demo_signal(self) -> Dict:
        """Demo signal khi không có API"""
        import random
        
        if random.random() < 0.6:  # 60% WAIT
            return self._get_wait_signal("Demo mode: Không có tín hiệu rõ ràng")
        
        action = random.choice(['BUY', 'SELL'])
        base_price = 2620.0
        
        if action == 'BUY':
            return {
                'action': 'BUY',
                'wyckoff_phase': 'ACCUMULATION',
                'event_detected': 'SPRING',
                'smc_trigger': 'LIQUIDITY_SWEEP',
                'entry': base_price,
                'stoploss': base_price - 8,
                'takeprofit': base_price + 15,
                'confidence': random.randint(72, 88),
                'reason': 'Demo: Phát hiện Spring tại vùng hỗ trợ + Liquidity sweep'
            }
        else:
            return {
                'action': 'SELL',
                'wyckoff_phase': 'DISTRIBUTION',
                'event_detected': 'UPTHRUST',
                'smc_trigger': 'ORDER_BLOCK',
                'entry': base_price,
                'stoploss': base_price + 8,
                'takeprofit': base_price - 15,
                'confidence': random.randint(72, 88),
                'reason': 'Demo: Phát hiện Upthrust tại Order Block bearish'
            }
    
    def analyze_chart_image(self, image_url: str, signal_data: Dict = None) -> Dict:
        """
        Phân tích ảnh chart từ Telegram bằng Gemini Vision
        
        Args:
            image_url: URL ảnh chart từ Telegram
            signal_data: Thông tin tín hiệu (nếu có) để cross-check
            
        Returns:
            Dict với: trend, support_levels, resistance_levels, 
                     recommendation, confidence, reason
        """
        if not self.model:
            return {
                'trend': 'UNKNOWN',
                'support_levels': [],
                'resistance_levels': [],
                'recommendation': 'SKIP',
                'confidence': 0,
                'reason': 'AI không khả dụng'
            }
        
        try:
            # Download image
            import requests
            from PIL import Image
            from io import BytesIO
            
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content))
            
            # Build prompt
            signal_context = ""
            if signal_data:
                signal_context = f"""
THÔNG TIN TÍN HIỆU:
- Action: {signal_data.get('action', 'N/A')}
- Entry: {signal_data.get('entry', 'N/A')}
- Stop Loss: {signal_data.get('stoploss', 'N/A')}
- Take Profit: {signal_data.get('takeprofit', 'N/A')}
"""
            
            prompt = f"""
🎯 PHÂN TÍCH CHART VÀNG (XAU/USD)

Bạn là chuyên gia phân tích kỹ thuật. Hãy phân tích chart này và trả lời:

{signal_context}

📊 YÊU CẦU PHÂN TÍCH:
1. **XU HƯỚNG**: Uptrend / Downtrend / Sideways / Consolidation
2. **CẤU TRÚC**: Higher Highs/Higher Lows hay Lower Highs/Lower Lows?
3. **SUPPORT/RESISTANCE**: Xác định các mức giá quan trọng (tối đa 3 mức mỗi loại)
4. **PATTERN**: Phát hiện pattern (Triangle, H&S, Double Top/Bottom, Flag, Wedge...)
5. **ĐỘNG LỰC**: Price action vs tín hiệu có phù hợp không?
6. **KHUYẾN NGHỊ**: Nên THEO hay BỎ QUA tín hiệu này?

Trả lời theo format JSON:
```json
{{
    "trend": "UPTREND | DOWNTREND | SIDEWAYS | CONSOLIDATION",
    "structure": "BULLISH | BEARISH | NEUTRAL",
    "support_levels": [2650, 2645, 2640],
    "resistance_levels": [2670, 2680, 2690],
    "pattern": "tên pattern nếu có",
    "recommendation": "FOLLOW | CAUTION | SKIP",
    "confidence": 0-100,
    "reason": "lý do ngắn gọn bằng tiếng Việt (max 100 chữ)"
}}
```

⚠️ LƯU Ý:
- Nếu không thấy rõ support/resistance thì để mảng rỗng []
- Reason phải NGẮN GỌN, DỄ HIỂU
- Confidence dựa trên độ rõ ràng của chart
"""
            
            # Call Gemini Vision
            response = self.model.generate_content([prompt, img])
            result_text = response.text.strip()
            
            # Parse JSON response
            import json
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                return {
                    'trend': result.get('trend', 'UNKNOWN'),
                    'structure': result.get('structure', 'NEUTRAL'),
                    'support_levels': result.get('support_levels', []),
                    'resistance_levels': result.get('resistance_levels', []),
                    'pattern': result.get('pattern', ''),
                    'recommendation': result.get('recommendation', 'CAUTION'),
                    'confidence': result.get('confidence', 50),
                    'reason': result.get('reason', 'Phân tích chart'),
                    'raw_analysis': result_text[:300]  # Backup
                }
            
            # Fallback if can't parse JSON
            return {
                'trend': 'UNKNOWN',
                'support_levels': [],
                'resistance_levels': [],
                'recommendation': 'CAUTION',
                'confidence': 0,
                'reason': 'Không parse được kết quả AI',
                'raw_analysis': result_text[:300]
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Image download error: {e}")
            return {
                'trend': 'UNKNOWN',
                'recommendation': 'SKIP',
                'confidence': 0,
                'reason': f'Không tải được ảnh: {str(e)[:50]}'
            }
        except Exception as e:
            print(f"❌ Chart analysis error: {e}")
            return {
                'trend': 'UNKNOWN',
                'recommendation': 'SKIP',
                'confidence': 0,
                'reason': f'Lỗi phân tích: {str(e)[:50]}'
            }
    
    def translate_to_vietnamese(self, text: str) -> str:
        """Dịch text sang tiếng Việt"""
        if not self.model:
            return text
        
        try:
            prompt = f"Dịch đoạn text sau sang tiếng Việt một cách tự nhiên:\n{text}"
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except:
            return text


# Backwards compatibility alias
AIAnalyst = WyckoffAIEngine


# Quick test
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    engine = WyckoffAIEngine(api_key)
    
    test_data = """
    📊 DỮ LIỆU NẾN:
    Time | Close
    10:00 | 2618.50
    10:15 | 2615.20
    10:30 | 2612.00 (Low - phá support)
    10:45 | 2619.80 (Recovery - nến xanh lớn)
    """
    
    test_indicators = {
        'RSI': 42,
        'Trend': 'SIDEWAYS',
        'MACD': 'Bullish crossover'
    }
    
    test_wyckoff = {
        'phase': 'ACCUMULATION',
        'events': [],
        'vsa': {'signal': 'ABSORPTION_SUPPORT'}
    }
    
    result = engine.analyze(test_data, test_indicators, test_wyckoff)
    print("\n🤖 AI Analysis Result:")
    for k, v in result.items():
        print(f"   {k}: {v}")
