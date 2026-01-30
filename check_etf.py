import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
import os

# =====================
# 설정
# =====================
TICKERS = ["TQQQ", "SOXL", "TNA", "BULZ", "TECL", "WEBL", "UPRO", "WANT"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
IMG_PATH = "rsi_table.png"

# =====================
# 텔레그램
# =====================
def send_photo(caption, path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(path, "rb") as f:
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
    rs = gain.rolling(period).mean() / loss.rolling(period).mean()
    return 100 - (100 / (1 + rs))

# =====================
# 데이터 수집
# =====================
rows = []

for ticker in TICKERS:
    df = yf.download(ticker, period="300d", interval="1d", progress=False)

    if df.empty:
        rows.append([ticker, "N/A", "N/A"])
        continue

    df["RSI"] = calc_rsi(df["Close"])

    # ✅ RSI가 존재하는 가장 최근 거래일
    valid = df.dropna(subset=["RSI"])
    if valid.empty:
        rows.append([ticker, "N/A", "N/A"])
        continue

    last = valid.iloc[-1]
    trade_date = valid.index[-1].strftime("%Y-%m-%d")

    rows.append([
        ticker,
        f"{last['Close']:.2f}",
        f"{last['RSI']:.1f}"
    ])

# =====================
# 표 생성
# =====================
table_df = pd.DataFrame(rows, columns=["Ticker", "Close", "RSI"])

fig, ax = plt.subplots(figsize=(6, 0.6 + len(table_df)*0.5))
ax.axis("off")

table = ax.table(
    cellText=table_df.values,
    colLabels=table_df.columns,
    cellLoc="center",
    loc="center"
)

table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1, 1.5)

# RSI 색상
for i, rsi in enumerate(table_df["RSI"], start=1):
    try:
        r = float(rsi)
        if r <= 30:
            table[i, 2].set_facecolor("#ffcccc")  # 과매도
        elif r >= 70:
            table[i, 2].set_facecolor("#d0e8ff")  # 과매수
    except:
        pass

plt.tight_layout()
plt.savefig(IMG_PATH, dpi=200)
plt.close()

# =====================
# 전송
# =====================
send_photo(
    caption="📊 ETF RSI 현황 (최근 거래일 기준)",
    path=IMG_PATH
)
