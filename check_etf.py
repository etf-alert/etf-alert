import yfinance as yf
import pandas as pd
import requests
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# =====================
# 기본 설정
# =====================
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TICKERS = ["QQQ", "QLD"]
DAYS = 300
STATE_FILE = "state.csv"

TODAY_UTC = datetime.utcnow().date()

# =====================
# 유틸
# =====================
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
    state = pd.DataFrame(columns=["Ticker", "Stage", "DaysLeft", "StageDate"])

def save_state():
    state.to_csv(STATE_FILE, index=False)

# =====================
# 메인 로직
# =====================
for ticker in TICKERS:
    df = yf.download(ticker, period=f"{DAYS}d", interval="1d")
    if len(df) < 130:
        continue

    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()
    df["RSI"] = calc_rsi(df["Close"])

    LAST_TRADING_DATE = df.index[-1].date()

    # ✅ 실행 허용 조건
    # 1) 오늘이 거래일
    # 2) 월요일 아침(UTC 기준)이고, 마지막 거래일이 금요일
    is_today_trade = LAST_TRADING_DATE == TODAY_UTC
    is_monday_morning = (
        TODAY_UTC.weekday() == 0 and
        LAST_TRADING_DATE == TODAY_UTC - timedelta(days=3)
    )

    if not (is_today_trade or is_monday_morning):
        continue

    trade_day_str = df.index[-1].strftime("%Y-%m-%d (%a)")

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

    # =====================
    # 📊 차트 생성 (항상 1회)
    # =====================
    img = f"{ticker}.png"

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 8),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True
    )

    ax1.plot(df["Close"], label="Close", linewidth=1.5)
    ax1.plot(df["MA60"], label="MA60", linestyle="--")
    ax1.plot(df["MA120"], label="MA120", linestyle="--", color="red")
    ax1.set_title(f"{ticker} Daily Chart")
    ax1.legend()
    ax1.grid(True)

    ax2.plot(df["RSI"], label="RSI (70/30)", color="purple")
    ax2.axhline(30, color="red", linestyle="--", linewidth=1)
    ax2.axhline(70, color="gray", linestyle="--", linewidth=1)
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig(img)
    plt.close()

    # 🔹 차트 먼저 전송
    send_photo(
        f"🗓️ {trade_day_str}\n"
        f"📈 {ticker}\n"
        f"종가: {close:.2f}\n"
        f"MA60: {ma60:.2f}\n"
        f"MA120: {ma120:.2f}\n"
        f"RSI: {rsi:.1f}",
        img,
    )

    # =====================
    # Stage 판단
    # =====================
    new_stage = None
    new_days = 0
    message = None

    if close < ma120 and rsi <= 30:
        new_stage = "RSI"
        new_days = 40
        message = (
            f"🗓️ {TODAY_UTC}\n"
            f"🔥 {ticker} 3차 매수 재개\n"
            f"RSI {rsi:.1f} ≤ 30\n"
            f"MA120 하단 유지\n"
            f"➡️ 40거래일 분할 (Day 1)"
        )

    elif prev_close > prev_ma120 and close <= ma120:
        new_stage = "MA120"
        new_days = 5
        message = (
            f"🗓️ {TODAY_UTC}\n"
            f"📉 {ticker} MA120 하향 돌파\n"
            f"➡️ 2차 매수 시작 (50% / 5일)"
        )

    elif prev_close > prev_ma60 and close <= ma60:
        new_stage = "MA60"
        new_days = 5
        message = (
            f"🗓️ {TODAY_UTC}\n"
            f"📉 {ticker} MA60 하향 돌파\n"
            f"➡️ 1차 매수 시작 (50% / 5일)"
        )

    # =====================
    # Stage 처리
    # =====================
    if new_stage:
        state = state[state["Ticker"] != ticker]
        state.loc[len(state)] = [
            ticker, new_stage, new_days, TODAY_UTC
        ]
        send_message(message)

    elif not row.empty:
        idx = row.index[0]
        days = int(row.iloc[0]["DaysLeft"])

        if days > 0:
            send_message(
                f"🗓️ {TODAY_UTC}\n"
                f"⏳ {ticker} 분할매수 진행\n"
                f"Stage: {row.iloc[0]['Stage']}\n"
                f"남은 거래일: {days}"
            )
            state.loc[idx, "DaysLeft"] = days - 1
        else:
            state = state.drop(idx)

save_state()
