import yfinance as yf
import json

eu_tickers = ["NOVO-B.CO", "ASML.AS", "NKT.CO", "ALV.DE", "RELX.AS", "BESI.AS", "ORSTED.CO", "EVO.ST", "TEP.PA"]
data = {}

for ticker in eu_tickers:
    stock = yf.Ticker(ticker)
    info = stock.history(period="5d")
    if info.empty: continue
    price = info["Close"].iloc[-1]
    delta = (price - info["Close"].iloc[-2]) / info["Close"].iloc[-2] * 100
    rsi = 100 - (100 / (1 + (info["Close"].diff().fillna(0).gt(0).rolling(14).mean()/info["Close"].diff().fillna(0).lt(0).rolling(14).mean())))
    data[ticker] = {"price": price, "percentChange": round(delta,2), "rsi": round(rsi.iloc[-1],1)}

with open("eu_snapshot.json","w") as f:
    json.dump(data, f, indent=2)
