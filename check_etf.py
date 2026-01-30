import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
import os

# =====================
# 환경변수
# =====================
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# =====================
# 설정
# =====================
TICKERS = ["TQQQ", "SOXL", "TNA", "BULZ", "TECL", "WEBL", "UPRO", "WANT"]
DAYS = 300
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
last_trade_date = None

for ticker in TICKERS:
    df = yf.download(
        ticker,
        period=f"{DAYS}d",
        interval="1d",
        progress=False,
        group_by="column"
    )

    if df.empty:
        rows.append([ticker, "N/A", "N/A"])
        continue

    # ✅ MultiIndex 방지
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if "Close" not in df.columns:
        rows.append([ticker, "N/A", "N/A"])
        continue

    df = df.copy()
    df["RSI"] = calc_rsi(df["Close"])

    # ✅ RSI가 존재하는 가장 최근 거래일 사용
    valid = df.dropna(subset=["RSI"])
    if valid.empty:
        rows.append([ticker, "N/A", "N/A"])
        continue

    last = valid.iloc[-1]
    trade_date = valid.index[-1]

    close = float(last["Close"])
    rsi = float(last["RSI"])

    rows.append([ticker, f"{close:.2f}", f"{rsi:.1f}"])

    if last_trade_date is None:
        last_trade_date = trade_date

# =====================
# 표 생성
# =====================
table_df = pd.DataFrame(rows, columns=["Ticker", "Price", "RSI"])

fig, ax = plt.subplots(figsize=(6, 0.5 + len(table_df) * 0.5))
ax.axis("off")

table = ax.table(
    cellText=table_df.values,
    colLabels=table_df.columns,
    loc="center",
    cellLoc="center",
)

table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 1.4)

# ✅ RSI 색상
for i in range(len(table_df)):
    try:
        rsi_val = float(table_df.iloc[i]["RSI"])
        if rsi_val <= 30:
            table[(i + 1, 2)].set_facecolor("#ffcccc")  # 과매도
        elif rsi_val >= 70:
            table[(i + 1, 2)].set_facecolor("#ccccff")  # 과매수
    except:
        pass

plt.tight_layout()
plt.savefig(IMG_PATH)
plt.close()

# =====================
# 전송
# =====================
date_str = (
    last_trade_date.strftime("%Y-%m-%d (%a)")
    if last_trade_date is not None
    else "N/A"
)

send_photo(
    f"📊 레버리지 ETF RSI 현황\n🗓️ 기준일: {date_str}",
    IMG_PATH
)
