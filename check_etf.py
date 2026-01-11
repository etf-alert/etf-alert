import yfinance as yf
import pandas as pd
import requests
import os
import matplotlib.pyplot as plt
from datetime import datetime

# =====================
# 환경 변수
# =====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TICKERS = ["QQQ", "QLD"]
DAYS = 300

STATE_FILE = "state.csv"

# =====================
# 텔레그램 전송
# =====================
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def send_photo(caption, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as f:
        requests.post(url, data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": f})

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
    return 100 - (100 / (1 + rs))

# =====================
# 상태 저장 / 로드
# =====================
if os.path.exists(STATE_FILE):
    state = pd.read_csv(STATE_FILE)
else:
    state = pd.DataFrame(columns=["Ticker", "Stage", "DaysLeft"])

def save_state():
    state.to_csv(STATE_FILE, index=False)

# =====================
# 메인 로직
# =====================
for ticker in TICKERS:
    df = yf.download(ticker, period=f"{DAYS}d", interval="1d")
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()
    df["RSI"] = calc_rsi(df["Close"])

    prev = df.iloc[-2]
    last = df.iloc[-1]

    close = float(last["Close"])
    ma60 = float(last["MA60"])
    ma120 = float(last["MA120"])
    rsi = float(last["RSI"])

    row = state[state["Ticker"] == ticker]

    # =====================
    # 1차 MA60 터치
    # =====================
    if prev["Close"] > prev["MA60"] and close <= ma60:
        send_message(f"📉 {ticker} MA60 하향 터치\n1차 매수 시작 (50% / 5일)")
        state = state[state["Ticker"] != ticker]
        state.loc[len(state)] = [ticker, "MA60", 5]

    # =====================
    # 2차 MA120 터치
    # =====================
    if prev["Close"] > prev["MA120"] and close <= ma120:
        send_message(f"📉 {ticker} MA120 하향 터치\n2차 매수 시작 (50% / 5일)")
        state = state[state["Ticker"] != ticker]
        state.loc[len(state)] = [ticker, "MA120", 5]

    # =====================
    # 3차 RSI
    # =====================
    if close < ma120 and rsi <= 30:
        send_message(f"🔥 {ticker} RSI {rsi:.1f}\n3차 매수 시작 (잔여금 / 40일)")
        state = state[state["Ticker"] != ticker]
        state.loc[len(state)] = [ticker, "RSI", 40]

    # =====================
    # 분할 매수 진행 알림
    # =====================
    if not row.empty:
        idx = row.index[0]
        stage = row.iloc[0]["Stage"]
        days = int(row.iloc[0]["DaysLeft"])

        if days > 0:
            send_message(f"📆 {ticker} 분할매수 진행 중\n단계: {stage}\n남은 일수: {days}")
            state.loc[idx, "DaysLeft"] = days - 1
        else:
            state = state.drop(idx)

    # =====================
    # 차트 생성
    # =====================
    plt.figure(figsize=(10, 6))
    plt.plot(df["Close"], label="Close")
    plt.plot(df["MA60"], label="MA60")
    plt.plot(df["MA120"], label="MA120")
    plt.legend()
    plt.title(f"{ticker} Daily Chart")
    img = f"{ticker}.png"
    plt.savefig(img)
    plt.close()

    send_photo(
        f"{ticker}\n종가: {close:.2f}\nRSI: {rsi:.1f}",
        img
    )

save_state()
