import yfinance as yf
import pandas as pd
import requests
import os
import matplotlib.pyplot as plt

# =====================
# 설정값
# =====================
TICKERS = ["QQQ", "QLD"]
DAYS = 200
TOUCH_THRESHOLD = 5  # 0.3% 기준 (MA 근접 알림)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# =====================
# 텔레그램 전송 함수
# =====================
def send_telegram_photo(msg, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as img:
        requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": msg},
            files={"photo": img}
        )

# =====================
# RSI 계산
# =====================
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# =====================
# 차트 생성 (가격 + MA + RSI)
# =====================
def make_chart(df, ticker):
    recent = df.tail(120).copy()
    recent["RSI"] = calc_rsi(recent["Close"])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]}
    )

    # 📈 가격 + MA60 + MA120
    ax1.plot(recent.index, recent["Close"], label="Close", linewidth=2)
    ax1.plot(recent.index, recent["MA60"], label="MA60", linestyle="--")
    ax1.plot(recent.index, recent["MA120"], label="MA120", linestyle="--")
    ax1.set_title(f"{ticker} (Daily)")
    ax1.legend()
    ax1.grid(True)

    # 📉 RSI
    ax2.plot(recent.index, recent["RSI"], color="purple", linewidth=1.5)
    ax2.axhline(70, color="red", linestyle="--", linewidth=1)
    ax2.axhline(30, color="blue", linestyle="--", linewidth=1)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI")
    ax2.grid(True)

    filename = f"{ticker}_MA60_MA120_RSI.png"
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    return filename
    
# =====================
# 메인 로직
# =====================
for ticker in TICKERS:
    df = yf.download(ticker, period=f"{DAYS}d", interval="1d")

    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()

    today = df.iloc[-1]
    yesterday = df.iloc[-2]

    close_today = float(today["Close"])
    close_yesterday = float(yesterday["Close"])

    for ma_name in ["MA60", "MA120"]:
        ma_today = float(today[ma_name])
        ma_yesterday = float(yesterday[ma_name])

        # 📍 1️⃣ MA 근접 알림
        diff = abs(close_today - ma_today) / ma_today * 100
        if diff <= TOUCH_THRESHOLD:
            img = make_chart(df, ticker)
            send_telegram_photo(
                f"📍 {ticker} {ma_name} 근접\n"
                f"종가: {close_today:.2f}\n"
                f"{ma_name}: {ma_today:.2f}",
                img
            )

        # 🚨 2️⃣ 하락 이탈 알림 (위 → 아래, 1회)
        elif close_yesterday >= ma_yesterday and close_today < ma_today:
            img = make_chart(df, ticker)
            send_telegram_photo(
                f"🚨 {ticker} {ma_name} 하락 이탈\n"
                f"종가: {close_today:.2f}\n"
                f"{ma_name}: {ma_today:.2f}",
                img
            )
