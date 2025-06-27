import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def scrape_swaggystocks_sentiment(output_path="sentiment/swaggystocks_sentiment.json"):
    url = "https://swaggystocks.com/dashboard/wallstreetbets/ticker-sentiment"
    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_selector("table")

        rows = page.query_selector_all("table tbody tr")
        for row in rows:
            cols = row.query_selector_all("td")
            if len(cols) < 5:
                continue

            ticker = cols[0].inner_text().strip()
            mentions = int(cols[1].inner_text().replace(',', ''))
            bullish = float(cols[2].inner_text().replace('%', ''))
            bearish = float(cols[3].inner_text().replace('%', ''))
            sentiment = float(cols[4].inner_text())

            data.append({
                "ticker": ticker,
                "mentions": mentions,
                "bullish_percent": bullish,
                "bearish_percent": bearish,
                "sentiment_score": sentiment
            })

        browser.close()

    Path("sentiment").mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    return data

if __name__ == "__main__":
    data = scrape_swaggystocks_sentiment()
    print(f"✅ Scraped {len(data)} tickers from SwaggyStocks.")
