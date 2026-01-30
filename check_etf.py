import yfinance as yf
import pandas as pd
import requests
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# =====================
# 설정
# =====================
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TICKERS = [
    "TQQQ", "SOXL", "TNA", "BULZ",
    "TECL", "WEBL", "UPRO", "WANT"
]

DAYS = 120
RSI_PERIOD = 14
IMG_PATH = "rsi_table.png"

# =====================
# 유틸
# =====================
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
# 데이터 수집
# =====================
rows = []

for ticker in TICKERS:
    try:
        df = yf.download(
            ticker,
            period=f"{DAYS}d",
            interval="1d",
            progress=False,
            auto_adjust=False,
        )

        if len(df) < RSI_PERIOD + 1:
            continue

        df["RSI"] = calc_rsi(df["Close"], RSI_PERIOD)
        last = df.iloc[-1]

        rows.append({
            "Ticker": ticker,
            "Close": round(float(last["Close"]), 2),
            "RSI": round(float(last["RSI"]), 1),
            "Date": df.index[-1].strftime("%Y-%m-%d")
        })

    except Exception as e:
        print(f"{ticker} error:", e)

# 데이터 없으면 종료 (exit code 0)
if len(rows) == 0:
    send_message("⚠️ RSI 데이터 수집 실패 (휴장 또는 yfinance 오류)")
    exit(0)

df_table = pd.DataFrame(rows).sort_values("RSI")
trade_date = df_table.iloc[0]["Date"]

# =====================
# 표 이미지 생성
# =====================
fig, ax = plt.subplots(figsize=(6, 0.6 + 0.5 * len(df_table)))
ax.axis("off")

table = ax.table(
    cellText=df_table[["Ticker", "Close", "RSI"]].values,
    colLabels=["Ticker", "Close", "RSI"],
    loc="center",
    cellLoc="center",
)

table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1, 1.4)

# RSI 강조
for i, rsi in enumerate(df_table["RSI"], start=1):
    if rsi <= 30:
        table[(i, 2)].set_facecolor("#ffcccc")  # 과매도
    elif rsi >= 70:
        table[(i, 2)].set_facecolor("#dddddd")  # 과매수

plt.tight_layout()
plt.savefig(IMG_PATH, dpi=200)
plt.close()

if not os.path.exists(IMG_PATH):
    send_message("⚠️ 이미지 생성 실패")
    exit(0)

# =====================
# 전송
# =====================
send_photo(
    caption=f"📊 ETF RSI & 종가\n🗓 기준일: {trade_date}",
    path=IMG_PATH
)
print(ticker, df.index[-1])
