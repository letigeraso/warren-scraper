import json
import os

def load_json(path):
    if not os.path.exists(path):
        print(f"⚠️ File not found: {path}")
        return None
    with open(path, "r") as f:
        return json.load(f)

def extract_list(data, expected_keys):
    """
    Given a JSON object or list, find the list of records to iterate over.
    expected_keys: possible keys under which list can be nested.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in expected_keys:
            if key in data and isinstance(data[key], list):
                return data[key]
    print(f"⚠️ Could not find expected list in data keys {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
    return []

def get_ticker_key(record):
    for key in ["ticker", "symbol", "s", "name"]:
        if key in record:
            return key
    return None

# Load data
warren_raw = load_json("warrensoutputfile.json")
swaggy_raw = load_json("sentiment/swaggystocks_sentiment.json")
eu_snapshot_raw = load_json("sentiment/eu_snapshot.json")

warren_list = extract_list(warren_raw, expected_keys=["data", "stocks", "results"])
swaggy_list = extract_list(swaggy_raw, expected_keys=["data", "tickers", "sentiment"])
eu_snapshot_dict = eu_snapshot_raw if isinstance(eu_snapshot_raw, dict) else {}

combined = {}

# Merge Warren data
for stock in warren_list:
    ticker_key = get_ticker_key(stock)
    if not ticker_key:
        print(f"⚠️ Skipping Warren record with no ticker: {stock}")
        continue
    ticker = stock[ticker_key]
    combined.setdefault(ticker, {})
    combined[ticker].update({
        "ticker": ticker,
        "name": stock.get("name") or stock.get("description"),
        "price": stock.get("price"),
        "change": stock.get("percentChange") or stock.get("change"),
        "volume": stock.get("volume"),
        "rsi": stock.get("rsi") or stock.get("RSI"),
        "pe": stock.get("pe") or stock.get("price_earnings_ttm"),
        "sector": stock.get("sector") or stock.get("sector.tr"),
        "dividendYield": stock.get("dividendYield") or stock.get("dividends_yield_current"),
        "source_warren": True
    })

# Merge SwaggyStocks sentiment
for entry in swaggy_list:
    if not isinstance(entry, dict):
        print(f"⚠️ Skipping malformed swaggy sentiment entry: {entry}")
        continue
    ticker_key = get_ticker_key(entry)
    if not ticker_key:
        continue
    ticker = entry[ticker_key]
    combined.setdefault(ticker, {})
    combined[ticker].update({
        "swaggy_mentions": entry.get("mentions"),
        "swaggy_sentiment": entry.get("sentiment"),
        "source_swaggy": True
    })

# Merge EU snapshot
for ticker, data in eu_snapshot_dict.items():
    if not isinstance(data, dict):
        continue
    combined.setdefault(ticker, {})
    combined[ticker].update({
        "price_eu": data.get("price"),
        "change_eu": data.get("percentChange"),
        "rsi_eu": data.get("rsi"),
        "oversold_eu": data.get("oversold"),
        "country_eu": data.get("country"),
        "inPortfolio": data.get("inPortfolio"),
        "sector_eu": data.get("sector"),
        "source_eu_snapshot": True
    })

# Write output
with open("combined_output.json", "w") as f:
    json.dump(combined, f, indent=2)

print(f"✅ Saved {len(combined)} merged records to combined_output.json")
