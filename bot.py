import os
import time
import threading
import requests
from flask import Flask
from telegram import Bot
from anthropic import Anthropic

app = Flask(__name__)

# Config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID', '3695615958')
TWELVE_DATA_KEY = os.getenv('TWELVE_DATA_KEY')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

bot = Bot(token=TELEGRAM_TOKEN)
client = Anthropic()

def get_price_data():
    """Fetch XAUUSD candles from Twelve Data"""
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            'symbol': 'XAUUSD',
            'interval': '5min',
            'outputsize': 100,
            'apikey': TWELVE_DATA_KEY
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        return data.get('values', [])
    except Exception as e:
        print(f"Error fetching price: {e}")
        return []

def analyze_with_claude(price_data):
    """Send chart data to Claude for analysis"""
    if not price_data:
        return None
    
    # Build prompt with latest candles
    latest = price_data[:20]
    price_str = ""
    for c in latest:
        price_str += f"Time: {c['datetime']}, Open: {c['open']}, High: {c['high']}, Low: {c['low']}, Close: {c['close']}\n"
    
    prompt = "Analyze this XAUUSD 5min chart data (20 latest candles):\n" + price_str + "\n\nEvaluate ONLY these indicators:\n- RSI (14)\n- EMA 15\n- EMA 45\n- Candle patterns (pin bar, engulfing, consolidation)\n- Support/Resistance from price action\n\nGive me:\n1. Market Strength (0-100%)\n2. Signal: BUY, SELL, or WAIT\n3. One-line reason\n\nFormat:\nSTRENGTH: [number]\nSIGNAL: [BUY/SELL/WAIT]\nREASON: [brief]"

    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude error: {e}")
        return None

def parse_claude_response(response):
    """Extract strength, signal, reason"""
    if not response:
        return None
    
    try:
        lines = response.strip().split('\n')
        strength = None
        signal = None
        reason = ""
        
        for line in lines:
            if 'STRENGTH:' in line:
                strength = int(''.join(filter(str.isdigit, line.split(':')[1])))
            elif 'SIGNAL:' in line:
                signal = line.split(':')[1].strip()
            elif 'REASON:' in line:
                reason = line.split(':')[1].strip()
        
        return {'strength': strength, 'signal': signal, 'reason': reason}
    except:
        return None

def send_alert(signal_data):
    """Send Telegram alert"""
    if not signal_data or signal_data['strength'] < 75:
        return
    
    signal = signal_data['signal']
    strength = signal_data['strength']
    reason = signal_data['reason']
    
    if signal == 'BUY':
        emoji = '🟢'
        entry = 'Entry price: Check chart'
        sl = 'SL: Entry - 2 points'
        tp = 'TP: Entry + 3 points'
    elif signal == 'SELL':
        emoji = '🔴'
        entry = 'Entry price: Check chart'
        sl = 'SL: Entry + 2 points'
        tp = 'TP: Entry - 3 points'
    else:
        return
    
    message = emoji + " " + signal + " SIGNAL\n"
    message += "Market Strength: " + str(strength) + "%\n"
    message += entry + "\n"
    message += sl + "\n"
    message += tp + "\n"
    message += "Reason: " + reason
    
    try:
        bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"Telegram error: {e}")

def scan_loop():
    """Auto-scan every 5 minutes"""
    last_signal = None
    while True:
        try:
            price_data = get_price_data()
            if price_data:
                analysis = analyze_with_claude(price_data)
                signal_data = parse_claude_response(analysis)
                
                if signal_data and signal_data['signal'] != last_signal:
                    send_alert(signal_data)
                    last_signal = signal_data['signal']
            
            time.sleep(300)  # 5 minutes
        except Exception as e:
            print(f"Scan error: {e}")
            time.sleep(300)

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    return {'ok': True}

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    # Start scanner in background
    scanner = threading.Thread(target=scan_loop, daemon=True)
    scanner.start()
    
    app.run(host='0.0.0.0', port=5000)
