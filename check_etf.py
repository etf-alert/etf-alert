import yfinance as yf
import pandas as pd
import requests
import os

TICKERS = ["QQQ", "QLD"]
DAYS = 200
THRESHOLD = 0.3  # 이동평균선과 0.3% 이내면 터치로 판단

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

for ticker in TICKERS:
    df = yf.download(ticker, period=f"{DAYS}d", interval="1d")
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()

    last = df.iloc[-1]
    close = float(df["Close"].iloc[-1])

    for ma_name in ["MA60", "MA120"]:
        ma = float(last[ma_name])
        diff = abs(close - ma) / ma * 100
        if diff <= THRESHOLD:
            send_telegram(
                f"{ticker} 종가 {close:.2f} → {ma_name} ({ma:.2f}) 근접"
            )
