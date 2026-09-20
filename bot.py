import os, datetime, requests
from twelvedata import TDClient
from telegram.ext import Updater, CommandHandler

# Load API keys
td = TDClient(apikey=os.getenv("TWELVE_DATA_KEY"))
telegram_token = os.getenv("TELEGRAM_TOKEN")

# Danger zones (illiquid hours + example news times)
danger_hours = range(0, 3)  # midnight to 3am UTC
news_times = ["13:30", "19:00"]  # example: NFP, FOMC

def in_danger_zone():
    now = datetime.datetime.utcnow()
    if now.hour in danger_hours:
        return True
    if now.strftime("%H:%M") in news_times:
        return True
    return False

def detect_patterns(closes):
    # Simple candlestick pattern detection
    if closes[-1] < closes[-2] and closes[-2] > closes[-3]:
        return "Double Top"
    if closes[-1] > closes[-2] and closes[-2] < closes[-3]:
        return "Double Bottom"
    if closes[-2] < closes[-3] and closes[-1] > closes[-2]:
        return "Engulfing Bullish"
    if closes[-2] > closes[-3] and closes[-1] < closes[-2]:
        return "Engulfing Bearish"
    return None

def support_resistance(closes):
    support = min(closes[-20:])
    resistance = max(closes[-20:])
    return support, resistance

def get_prediction(short_ma, long_ma, rsi, pattern, support, resistance, price):
    forecast = "Neutral"
    reasons = []

    if short_ma > long_ma and rsi < 70:
        forecast = "Bullish"
        reasons.append("MA crossover + RSI healthy")
    elif short_ma < long_ma and rsi > 30:
        forecast = "Bearish"
        reasons.append("MA crossover + RSI weak")

    if pattern == "Double Bottom":
        forecast = "Bullish"
        reasons.append("Double Bottom reversal")
    elif pattern == "Double Top":
        forecast = "Bearish"
        reasons.append("Double Top reversal")

    if price > resistance * 0.98:
        forecast = "Possible breakout up"
        reasons.append("Near resistance with momentum")
    elif price < support * 1.02:
        forecast = "Possible breakdown down"
        reasons.append("Near support with weakness")

    return f"🔮 Prediction: {forecast}\nReasons: {', '.join(reasons)}"

def get_signal():
    if in_danger_zone():
        return "⚠️ No trade — dangerous market time."

    # Fetch gold data
    data = td.time_series(symbol="XAU/USD", interval="5min", outputsize=50).as_json()
    closes = [float(candle['close']) for candle in data]
    price = closes[-1]

    short_ma = sum(closes[-5:]) / 5
    long_ma = sum(closes[-20:]) / 20
    pattern = detect_patterns(closes)
    support, resistance = support_resistance(closes)

    # RSI calculation
    gains = [closes[i+1]-closes[i] for i in range(len(closes)-1) if closes[i+1]>closes[i]]
    losses = [closes[i]-closes[i+1] for i in range(len(closes)-1) if closes[i+1]<closes[i]]
    avg_gain = sum(gains[-14:]) / 14 if gains else 0
    avg_loss = sum(losses[-14:]) / 14 if losses else 1
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Probability scoring
    score = 0
    if short_ma > long_ma: score += 20
    if pattern in ["Double Bottom", "Engulfing Bullish"]: score += 20
    if pattern in ["Double Top", "Engulfing Bearish"]: score += 20
    if 30 < rsi < 70: score += 20
    if price > support and price < resistance: score += 20

    prediction = get_prediction(short_ma, long_ma, rsi, pattern, support, resistance, price)

    if score >= 75:
        if short_ma > long_ma and pattern in ["Double Bottom", "Engulfing Bullish"]:
            return f"📈 Buy Signal\nEntry: {price}\nSL: {support}\nTP: {resistance}\nSuccess %: {score}\n{prediction}"
        elif short_ma < long_ma and pattern in ["Double Top", "Engulfing Bearish"]:
            return f"📉 Sell Signal\nEntry: {price}\nSL: {resistance}\nTP: {support}\nSuccess %: {score}\n{prediction}"
        else:
            return f"⚠️ No trade — filters not aligned despite {score}% score.\n{prediction}"
    else:
        return f"⚠️ No trade — success probability only {score}%, below safe threshold.\n{prediction}"

def signal(update, context):
    update.message.reply_text(get_signal())

updater = Updater(telegram_token)
updater.dispatcher.add_handler(CommandHandler("signal", signal))
updater.start_polling()
