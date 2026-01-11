import yfinance as yf
import pandas as pd
import requests
import os
import matplotlib.pyplot as plt

# =====================
# 환경 변수
# =====================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TICKERS = ["QQQ", "QLD"]
DAYS = 300
STATE_FILE = "state.csv"

def v(x):
    return float(x.iloc[0]) if hasattr(x, "iloc") else float(x)

# =====================
# 텔레그램 전송
# =====================
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def send_photo(caption, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as f:
        requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": f},
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
    return 100 - (100 / (1 + rs))

# =====================
# 상태 로드
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
    # Stage 판단 (우선순위)
    # =====================
    new_stage = None
    new_days = 0
    msg = ""

    # 3차: RSI
    if close < ma120 and rsi <= 30:
        new_stage = "RSI"
        new_days = 40
        msg = (
            f"🔥 {ticker}\n"
            f"RSI {rsi:.1f} (30 이하)\n"
            f"MA120 아래에서 RSI 30이하\n"
            f"➡️ 3차 매수 시작 (잔여금 / 40일)"
        )

    # 2차: MA120
    elif prev["Close"] > prev["MA120"] and close <= ma120:
        new_stage = "MA120"
        new_days = 5
        msg = (
            f"📉 {ticker}\n"
            f"MA120 터치\n"
            f"➡️ 2차 매수 시작 (50% / 5일)"
        )

    # 1차: MA60
    elif prev["Close"] > prev["MA60"] and close <= ma60:
        new_stage = "MA60"
        new_days = 5
        msg = (
            f"📉 {ticker}\n"
            f"MA60 터치\n"
            f"➡️ 1차 매수 시작 (50% / 5일)"
        )

    # =====================
    # 새 Stage 시작 → 기존 Stage 즉시 종료
    # =====================
    if new_stage:
        state = state[state["Ticker"] != ticker]
        state.loc[len(state)] = [ticker, new_stage, new_days]
        send_message(msg)

    # =====================
    # 분할매수 진행 알림
    # =====================
    elif not row.empty:
        idx = row.index[0]
        stage = row.iloc[0]["Stage"]
        days = int(row.iloc[0]["DaysLeft"])

        if days > 0:
            send_message(
                f"📆 {ticker} 분할매수 진행 중\n"
                f"단계: {stage}\n"
                f"남은 일수: {days}"
            )
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
        img,
    )

save_state()
