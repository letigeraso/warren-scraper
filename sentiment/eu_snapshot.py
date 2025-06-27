import json
import os
import yfinance as yf
import pandas as pd
from datetime import datetime

# === Load tickers from CSV ===
ticker_file = "sentiment/eu_tickers.csv"
portfolio_tickers = {
    "NOVO-B.CO", "ASML.AS", "NKT.CO", "ALV.DE", "BESI.AS",
    "ORSTED.CO", "EVO.ST", "TEP.PA", "RELX.AS"
}

if not os.path.exists(ticker_file):
    raise FileNotFoundError(f"CSV not found: {ticker_file}")

universe = pd.read_csv(ticker_file)
snapshot = {}

# === RSI Calculation ===
def calculate_rsi(prices, period=14):
    deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

print("📈 Fetching EU tickers from yfinance...")

for _, row in universe.iterrows():
    ticker = row["ticker"]
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="21d")
        prices = hist["Close"].tolist()

        if len(prices) < 15:
            rsi = None
            pct_change = None
        else:
            rsi = calculate_rsi(prices)
            pct_change = round(((prices[-1] - prices[-2]) / prices[-2]) * 100, 2)

        snapshot[ticker] = {
            "name": row["name"],
            "country": row["country"],
            "sector": row["sector"],
            "price": round(prices[-1], 2) if prices else None,
            "percentChange": pct_change,
            "rsi": rsi,
            "oversold": rsi is not None and rsi < 32,
            "inPortfolio": ticker in portfolio_tickers
        }

    except Exception as e:
        print(f"⚠️ Error for {ticker}: {e}")
        snapshot[ticker] = {
            "name": row["name"],
            "country": row["country"],
            "sector": row["sector"],
            "price": None,
            "percentChange": None,
            "rsi": None,
            "oversold": False,
            "inPortfolio": ticker in portfolio_tickers
        }

# === Save snapshot with date ===
snapshot["_date"] = datetime.utcnow().isoformat()
os.makedirs("sentiment", exist_ok=True)
with open("sentiment/eu_snapshot.json", "w") as f:
    json.dump(snapshot, f, indent=2)

print(f"✅ Saved {len(snapshot)-1} tickers to sentiment/eu_snapshot.json")
