import yfinance as yf
import pandas as pd
import requests
import os
import matplotlib.pyplot as plt

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TICKERS = ["QQQ", "QLD"]
DAYS = 300
STATE_FILE = "state.csv"

def v(x):
    return float(x.iloc[0]) if hasattr(x, "iloc") else float(x)

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def send_photo(caption, path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(path, "rb") as f:
        requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": f},
        )

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(period).mean() / loss.rolling(period).mean()
    return 100 - (100 / (1 + rs))

# =====================
# State 로드
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

    close = v(last["Close"])
    ma60 = v(last["MA60"])
    ma120 = v(last["MA120"])
    rsi = v(last["RSI"])

    prev_close = v(prev["Close"])
    prev_ma60 = v(prev["MA60"])
    prev_ma120 = v(prev["MA120"])

    row = state[state["Ticker"] == ticker]

    new_stage = None
    new_days = 0
    message = None

    # ===== 3차 (최우선) =====
    if close < ma120 and rsi <= 30:
        new_stage = "RSI"
        new_days = 40
        message = (
            f"🔥 {ticker} 3차 매수 재개\n"
            f"RSI {rsi:.1f} ≤ 30\n"
            f"MA120 하단 유지\n"
            f"➡️ 잔여금 / 40거래일 분할 (Day 1)"
        )

    # ===== 2차 =====
    elif prev_close > prev_ma120 and close <= ma120:
        new_stage = "MA120"
        new_days = 5
        message = (
            f"📉 {ticker} MA120 하향 돌파\n"
            f"➡️ 2차 매수 시작\n"
            f"50% / 5거래일"
        )

    # ===== 1차 =====
    elif prev_close > prev_ma60 and close <= ma60:
        new_stage = "MA60"
        new_days = 5
        message = (
            f"📉 {ticker} MA60 하향 돌파\n"
            f"➡️ 1차 매수 시작\n"
            f"50% / 5거래일"
        )

    # ===== 새 Stage 시작 =====
    if new_stage:
        state = state[state["Ticker"] != ticker]
        state.loc[len(state)] = [ticker, new_stage, new_days]

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
            message + f"\n\n종가: {close:.2f}\nRSI: {rsi:.1f}",
            img,
        )

    # ===== 분할 진행 =====
    elif not row.empty:
        idx = row.index[0]
        stage = row.iloc[0]["Stage"]
        days = int(row.iloc[0]["DaysLeft"])

        if days > 0:
            send_message(
                f"📆 {ticker} 분할매수 진행\n"
                f"Stage: {stage}\n"
                f"남은 거래일: {days}"
            )
            state.loc[idx, "DaysLeft"] = days - 1
        else:
            state = state.drop(idx)

save_state()
