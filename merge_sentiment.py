import json
import os

# === Load Warren Screener Data ===
with open("warrensoutputfile.json", "r") as f:
    warren_data = json.load(f)

# === Load SwaggyStocks Sentiment Data ===
with open("sentiment/swaggystocks_sentiment.json", "r") as f:
    swaggy_data = json.load(f)

# === Load EU Snapshot Data ===
eu_snapshot_path = "sentiment/eu_snapshot.json"
eu_snapshot = {}
if os.path.exists(eu_snapshot_path):
    with open(eu_snapshot_path, "r") as f:
        eu_snapshot = json.load(f)

# === Merge Logic ===
combined = {}

for stock in warren_data:
    ticker = stock.get("ticker")
    if not ticker:
        continue

    combined[ticker] = {
        "ticker": ticker,
        "name": stock.get("name"),
        "price": stock.get("price"),
        "percentChange": stock.get("percentChange"),
        "volume": stock.get("volume"),
        "rsi": stock.get("rsi"),
        "pe": stock.get("pe"),
        "sector": stock.get("sector"),
        "dividendYield": stock.get("dividendYield"),
        "source": "warren",
    }

# Add SwaggyStocks sentiment (if it's not already there)
for entry in swaggy_data:
    if not isinstance(entry, dict):
        print(f"⚠️ Skipping malformed sentiment entry: {entry}")
        continue

    ticker = entry.get("symbol")
    if not ticker:
        continue

    if ticker not in combined:
        combined[ticker] = {"ticker": ticker}

    combined[ticker]["swaggy_mentions"] = entry.get("mentions")
    combined[ticker]["swaggy_sentiment"] = entry.get("sentiment")

# Add EU snapshot overlays (rsi, oversold etc.)
for ticker, data in eu_snapshot.items():
    if not isinstance(data, dict):
        continue
    if ticker not in combined:
        combined[ticker] = {"ticker": ticker}
    combined[ticker].update({
        "price": data.get("price"),
        "percentChange": data.get("percentChange"),
        "rsi": data.get("rsi"),
        "oversold": data.get("oversold"),
        "country": data.get("country"),
        "inPortfolio": data.get("inPortfolio"),
        "sector": data.get("sector"),
        "source": combined[ticker].get("source", "eu_snapshot")
    })

# === Save merged output ===
with open("combined_output.json", "w") as f:
    json.dump(combined, f, indent=2)

print(f"✅ Saved {len(combined)} merged records to combined_output.json")
