import json
import os

# Load US data
with open("warrensoutputfile.json", "r") as f:
    warren_data = json.load(f)

with open("sentiment/swaggystocks_sentiment.json", "r") as f:
    swaggy_data = json.load(f)

# Load EU snapshot
with open("sentiment/eu_snapshot.json", "r") as f:
    eu_data = json.load(f)

# Normalize EU data into same format as other sources
eu_formatted = []
for entry in eu_data:
    eu_formatted.append({
        "ticker": entry.get("symbol"),
        "price": entry.get("price"),
        "percentChange": entry.get("changePercent"),
        "rsi": entry.get("rsi"),
        "volume": None,
        "source": "eu_snapshot",
        "in_portfolio": True  # All EU tickers are your portfolio holdings
    })

# Normalize Swaggy sentiment data
swaggy_formatted = []
for entry in swaggy_data:
    swaggy_formatted.append({
        "ticker": entry.get("ticker"),
        "mentions": entry.get("mentions"),
        "sentimentScore": entry.get("sentimentScore"),
        "source": "swaggy"
    })

# Merge all data by ticker
combined = {}

for entry in warren_data:
    ticker = entry.get("ticker")
    if not ticker:
        continue
    combined[ticker] = entry.copy()
    combined[ticker]["source"] = "warren"

for entry in swaggy_formatted:
    ticker = entry.get("ticker")
    if not ticker:
        continue
    if ticker not in combined:
        combined[ticker] = {}
    combined[ticker].update(entry)

for entry in eu_formatted:
    ticker = entry.get("ticker")
    if not ticker:
        continue
    if ticker not in combined:
        combined[ticker] = {}
    combined[ticker].update(entry)

# Write to combined file
with open("combined_output.json", "w") as f:
    json.dump(list(combined.values()), f, indent=2)

print("✅ Combined output updated with Warren, Swaggy, and EU snapshot data.")
