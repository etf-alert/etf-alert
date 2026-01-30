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

DAYS = 100
RSI_PERIOD = 14
IMG_PATH = "rsi_table.png"

# =====================
# 유틸
# =====================
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
    df = yf.download(ticker, period=f"{DAYS}d", interval="1d", progress=False)
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

# RSI 색상 강조
for i, rsi in enumerate(df_table["RSI"], start=1):
    if rsi <= 30:
        table[(i, 2)].set_facecolor("#ffcccc")  # 빨강
    elif rsi >= 70:
        table[(i, 2)].set_facecolor("#dddddd")  # 회색

plt.tight_layout()
plt.savefig(IMG_PATH, dpi=200)
plt.close()

# =====================
# 전송
# =====================
send_photo(
    caption=f"📊 ETF RSI & 종가\n🗓 기준일: {trade_date}",
    path=IMG_PATH
)
