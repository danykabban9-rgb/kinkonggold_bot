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
        url = f"https://api.twelvedata.com/time_series"
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
    price_str = "\n".join([f"Time: {c['datetime']}, Open: {c['open']}, High: {c['high']}, Low: {c['low']}, Close: {c['close']}" for c in latest])
    
    prompt = f"""Analyze this XAUUSD 5min chart d
