import json
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import re
import time

# --- Function for WallStreetBets Ticker Sentiment (no changes needed) ---
def scrape_swaggystocks_sentiment(output_path="sentiment/swaggystocks_sentiment.json"):
    url = "https://swaggystocks.com/dashboard/wallstreetbets/ticker-sentiment"
    data = []

    CARD_CLASS = "styles_card__4HWKI"
    TICKER_NAME_CLASS = "styles_name__fT9wO"
    MENTIONS_CLASS = "styles_mentions__YtuyJ"
    ENTRY_INFO_CLASS = "styles_entry__UNrRv"

    sentiment_dir = Path("sentiment")
    sentiment_dir.mkdir(exist_ok=True, parents=True)
    debug_failed_sentiment_path = sentiment_dir / "debug_failed_sentiment.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("🌐 Navigating to SwaggyStocks - WallStreetBets Sentiment...")
        page.goto(url, timeout=90000)

        try:
            print("⏳ Waiting for sentiment cards to load...")
            page.wait_for_selector(f"div.{CARD_CLASS}", timeout=30000)
            print("✅ Sentiment cards found.")
        except PlaywrightTimeout:
            print("⛔ Timeout: Sentiment cards not found. This might indicate a change in website structure or a slow load.")
            page.screenshot(path=str(debug_failed_sentiment_path), full_page=True)
            print(f"Debug screenshot saved to: {debug_failed_sentiment_path}")
            browser.close()
            return []

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_=CARD_CLASS)

    if not cards:
        print(f"⚠️ No elements found with class '{CARD_CLASS}' in the scraped HTML. This could mean the page loaded, but the expected elements were not present.")
        return []

    print(f"Found {len(cards)} potential sentiment cards.")

    for i, card in enumerate(cards):
        try:
            stock_data = {
                "ticker": "N/A",
                "mentions": 0,
                "earnings": None,
                "market_cap": None,
                "call_to_put_oi_ratio": None,
                "thirty_day_iv": None,
                "option_activity_7d": None
            }

            ticker_p_tag = card.find("p", class_=TICKER_NAME_CLASS)
            if ticker_p_tag:
                stock_data["ticker"] = ticker_p_tag.get_text(strip=True)
            else:
                print(f"⚠️ Card {i}: Ticker element with class '{TICKER_NAME_CLASS}' not found. Skipping card.")
                continue

            mentions_p_tag = card.find("p", class_=MENTIONS_CLASS)
            if mentions_p_tag:
                mentions_text = mentions_p_tag.get_text(strip=True)
                match = re.search(r'(\d+)\s*Mentions', mentions_text)
                if match:
                    stock_data["mentions"] = int(match.group(1))
                else:
                    print(f"⚠️ Card {stock_data['ticker']}: Could not parse mentions number from '{mentions_text}'.")
            else:
                print(f"⚠️ Card {stock_data['ticker']}: Mentions element with class '{MENTIONS_CLASS}' not found.")

            info_entries = card.find_all("p", class_=ENTRY_INFO_CLASS)
            for entry in info_entries:
                text = entry.get_text(strip=True)

                if text.startswith("Earnings:"):
                    stock_data["earnings"] = text.replace("Earnings: ", "").strip()
                elif text.startswith("Market Cap:"):
                    stock_data["market_cap"] = text.replace("Market Cap: ", "").strip()
                elif text.startswith("Call-To-Put OI Ratio:"):
                    ratio_match = re.search(r'([\d.]+)', text)
                    if ratio_match:
                        try:
                            stock_data["call_to_put_oi_ratio"] = float(ratio_match.group(1))
                        except ValueError:
                            stock_data["call_to_put_oi_ratio"] = text.replace("Call-To-Put OI Ratio: ", "").strip()
                    else:
                         stock_data["call_to_put_oi_ratio"] = text.replace("Call-To-Put OI Ratio: ", "").strip()

                elif text.startswith("30-Day IV:"):
                    iv_match = re.search(r'([\d.]+%?)', text)
                    if iv_match:
                        stock_data["thirty_day_iv"] = iv_match.group(1).strip()
                    else:
                        stock_data["thirty_day_iv"] = text.replace("30-Day IV: ", "").strip()

                elif text.startswith("Option Activity (7d):"):
                    activity_match = re.search(r'(\d+)', text)
                    if activity_match:
                        try:
                            stock_data["option_activity_7d"] = int(activity_match.group(1))
                        except ValueError:
                            stock_data["option_activity_7d"] = text.replace("Option Activity (7d): ", "").strip()
                    else:
                        stock_data["option_activity_7d"] = text.replace("Option Activity (7d): ", "").strip()

            data.append(stock_data)

        except Exception as e:
            print(f"⚠️ Failed to parse card {i} (Ticker: {stock_data.get('ticker', 'N/A')}): {e}. Card HTML snippet: {str(card)[:500]}")
            continue

    if data:
        Path("sentiment").mkdir(exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Scraped and saved {len(data)} tickers to {output_path}")
    else:
        print("⚠️ No data extracted. This could be due to parsing errors or no cards being found after initial load.")

    return data

# --- Function for Unusual Options Activity ---
def scrape_unusual_options_activity(output_path="options/unusual_options_activity.json"):
    url = "https://swaggystocks.com/dashboard/unusual-options-activity"
    options_data = []

    # Define selectors based on the provided HTML snippet
    MAIN_CONTENT_SELECTOR = "div.styles_content__uVpvM" # Outer most container from your HTML
    HEADER_ROW_SELECTOR = "div.styles_container__IuRgX.styles_header__XI6EA.styles_sortable__3o7wg"
    DATA_ROW_SELECTOR = "div.styles_container__IuRgX.styles_path__ng9lW"
    TICKER_IN_ROW_SELECTOR = "p.styles_name__M_BGb" # Class for the ticker text within a data row
    INFO_CELL_SELECTOR = "div.styles_info__8BsWp" # Class for general info cells within a data row

    options_dir = Path("options")
    options_dir.mkdir(exist_ok=True, parents=True)
    debug_failed_options_path = options_dir / "debug_failed_options.png"
    debug_failed_options_html_path = options_dir / "debug_failed_options.html"
    debug_after_initial_wait_path = options_dir / "debug_after_initial_wait.png"
    debug_full_options_page_path = options_dir / "debug_full_options_page.png"
    debug_full_options_html_path = options_dir / "debug_full_options_html.html"

    with sync_playwright() as p:
        # ABSOLUTELY ESSENTIAL FOR THIS DEBUGGING STEP: Run HEADLESS=FALSE
        # If this works, you can change it back to True for efficiency.
        browser = p.chromium.launch(headless=True) # Set headless to FALSE to see browser
        page = browser.new_page()
        print("🌐 Navigating to SwaggyStocks - Unusual Options Activity...")
        page.goto(url, timeout=90000)

        try:
            print(f"⏳ Waiting for the main content container '{MAIN_CONTENT_SELECTOR}' to be attached...")
            # Wait for the outermost content div to be attached, which should encompass everything
            page.wait_for_selector(MAIN_CONTENT_SELECTOR, state='attached', timeout=60000)
            print(f"✅ Main content container '{MAIN_CONTENT_SELECTOR}' confirmed attached.")

            # Now, wait for at least one data row to be attached within that container
            print(f"⏳ Waiting for at least one data row ('{DATA_ROW_SELECTOR}') to be attached...")
            page.wait_for_selector(f"{MAIN_CONTENT_SELECTOR} {DATA_ROW_SELECTOR}", state='attached', timeout=30000)
            print("✅ First data row confirmed attached.")

            page.screenshot(path=str(debug_after_initial_wait_path), full_page=True)
            print(f"Debug screenshot after initial elements attached saved to: {debug_after_initial_wait_path}")

        except PlaywrightTimeout as e:
            print(f"⛔ Timeout: Required page elements not found after initial load ({e}). This indicates the page content is not loading as expected or the selector is incorrect.")
            page.screenshot(path=str(debug_failed_options_path), full_page=True)
            print(f"Debug screenshot saved to: {debug_failed_options_path}")
            failed_html = page.content()
            debug_failed_options_html_path.write_text(failed_html, encoding="utf-8")
            print(f"Debug HTML saved to: {debug_failed_options_html_path}")
            browser.close()
            return []
        except Exception as e:
            print(f"An unexpected error occurred during initial page load: {e}")
            page.screenshot(path=str(debug_failed_options_path), full_page=True)
            print(f"Debug screenshot saved to: {debug_failed_options_path}")
            failed_html = page.content()
            debug_failed_options_html_path.write_text(failed_html, encoding="utf-8")
            print(f"Debug HTML saved to: {debug_failed_options_html_path}")
            browser.close()
            return []

        # --- SCROLLING LOGIC ---
        # We know the page is very long and data is loaded on scroll.
        print("📈 Scrolling to load all data...")
        # Your HTML shows no direct scroller element like MuiDataGrid-virtualScroller.
        # It seems the entire styles_content__uVpvM might be the scrollable area,
        # or the body of the document. Let's try to scroll the main page.
        
        # Determine the scrollable element. It could be the 'body' or 'html' element,
        # or the 'styles_content__uVpvM' div itself if it has overflow.
        # Let's try scrolling the page's main scrollbar (document.body.scrollHeight)
        # If this doesn't load all data, we'll need to find the specific scrollable div.

        last_scroll_height = -1
        scroll_attempts = 0
        max_scroll_attempts = 100 # Increased max attempts, as this page can be very long

        while scroll_attempts < max_scroll_attempts:
            # Scroll to the bottom of the page
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            # Wait for content to load after scrolling. Adjust this time based on observation.
            time.sleep(2) # Increased sleep slightly

            current_scroll_height = page.evaluate("document.body.scrollHeight")
            
            if current_scroll_height == last_scroll_height:
                print(f"  Reached end of scrollable content. Height {current_scroll_height}px, after {scroll_attempts+1} attempts.")
                break

            print(f"  Attempt {scroll_attempts+1}: Scrolled to {current_scroll_height}px.")
            last_scroll_height = current_scroll_height
            scroll_attempts += 1
        
        print("✅ Finished scrolling.")
        page.screenshot(path=str(debug_full_options_page_path), full_page=True)
        print(f"Full page screenshot saved to: {debug_full_options_page_path}")

        html = page.content()
        browser.close()

    # --- Save the FULL HTML content for inspection (This should now always be reached if scrolling succeeds) ---
    debug_full_options_html_path.write_text(html, encoding="utf-8")
    print(f"📄 Full page HTML saved to {debug_full_options_html_path} for detailed inspection.")

    soup = BeautifulSoup(html, "html.parser")

    # --- BeautifulSoup parsing logic ---
    # We are now using the specific class names identified from your provided HTML snippet.
    # The main container for all entries (headers + rows) is styles_entries__dTOx1
    main_entries_container = soup.find("div", class_="styles_entries__dTOx1")
    if not main_entries_container:
        print("⚠️ Could not find the main entries container (styles_entries__dTOx1) in the scraped HTML.")
        return []

    # Find the header row within the main entries container
    header_row_bs = main_entries_container.find("div", class_="styles_container__IuRgX styles_header__XI6EA styles_sortable__3o7wg")
    if header_row_bs:
        # Extract header names from the header row (excluding the ticker in the sticky column)
        header_names = [p.get_text(strip=True) for p in header_row_bs.select('p.styles_name__M_BGb')] # Ticker header
        info_headers = [div.get_text(strip=True) for div in header_row_bs.select('div.styles_info__8BsWp')] # Other headers
        # Combine the "Ticker" header with the rest of the info headers
        # The Ticker header seems to be "Ticker"
        # The others are "Shares Closed @ Price", "Side", etc.
        column_headers = header_names + info_headers
    else:
        # Fallback to a predefined list if header row cannot be found in HTML
        print("⚠️ Could not find the header row in the scraped HTML. Using predefined headers.")
        column_headers = [
            "Ticker", "Shares Closed @ Price", "Side", "Expiration", "DTE", "Updated",
            "Strike", "Last", "Bid", "Ask", "Volume", "OI", "IV (%)", "Delta",
            "OTM (%)", "Est. Total Premium"
        ]

    print(f"Detected Headers: {column_headers}")


    # Find all data rows. They have styles_container__IuRgX styles_path__ng9lW
    table_rows = main_entries_container.find_all("div", class_="styles_container__IuRgX styles_path__ng9lW")

    if not table_rows:
        print("⚠️ No data rows found using the specific class names. Check HTML structure in debug_full_options_html.html.")
        return []

    print(f"Found {len(table_rows)} options activity rows from HTML for parsing.")

    for i, row in enumerate(table_rows):
        try:
            row_data = {}
            
            # Extract Ticker from the sticky column part of the row
            ticker_element = row.find("p", class_="styles_name__M_BGb")
            if ticker_element:
                row_data["ticker"] = ticker_element.get_text(strip=True)
            else:
                # If ticker isn't found for a row, skip or assign N/A and log
                print(f"⚠️ Row {i}: Ticker element not found. Skipping row.")
                continue

            # Extract other info cells
            cells = row.find_all("div", class_="styles_info__8BsWp")

            # Match cells to headers by position, assuming consistent order
            # Start from the 1st column header since 'Ticker' is handled separately
            # and it's a fixed-width column
            start_index_for_info_cells = 1 # Because 'Ticker' is the 0th header conceptually
            
            if len(cells) != len(column_headers) - start_index_for_info_cells:
                 print(f"⚠️ Row {i} ({row_data['ticker']}): Mismatch in number of data cells ({len(cells)}) and expected headers ({len(column_headers) - start_index_for_info_cells}). Skipping row. Raw cells: {[c.get_text(strip=True) for c in cells]}")
                 continue

            for col_idx, cell in enumerate(cells):
                # Map to the corresponding header starting from the 2nd header
                header = column_headers[start_index_for_info_cells + col_idx]
                value = cell.get_text(strip=True)

                # Type conversion and cleaning based on column header
                if header in ["Shares Closed @ Price", "Strike", "Last", "Bid", "Ask", "IV (%)", "Delta", "OTM (%)"]:
                    value = value.replace('$', '').replace('%', '').strip()
                    try:
                        value = float(value)
                    except ValueError:
                        pass # Keep as string if conversion fails
                elif header in ["Volume", "OI", "DTE", "Est. Total Premium"]: # Assuming Est. Total Premium is also numeric
                    value = value.replace('K', '000').replace('M', '000000').replace('B', '000000000').replace('$', '').replace(',', '').strip()
                    try:
                        # Handle 'K', 'M' suffixes for Volume/OI/Premium if needed
                        # Simplistic conversion:
                        if 'K' in value:
                            value = float(value.replace('K', '')) * 1000
                        elif 'M' in value:
                            value = float(value.replace('M', '')) * 1000000
                        elif 'B' in value:
                            value = float(value.replace('B', '')) * 1000000000
                        else:
                            value = float(value)
                        
                        # For integer types like Volume, OI, DTE, convert to int if possible
                        if header in ["Volume", "OI", "DTE"]:
                            value = int(value)
                        elif header == "Est. Total Premium": # Can be float
                            pass

                    except ValueError:
                        pass
                
                row_data[header.lower().replace(' ', '_').replace('@', 'at').replace('%', 'percent')] = value

            options_data.append(row_data)

        except Exception as e:
            print(f"⚠️ Failed to parse row {i} (HTML: {str(row)[:500]}): {e}")
            continue

    if options_data:
        Path("options").mkdir(exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(options_data, f, indent=2)
        print(f"✅ Scraped and saved {len(options_data)} unusual options activities to {output_path}")
    else:
        print("⚠️ No unusual options activity data extracted. This could be due to parsing errors or an empty table.")

    return options_data

# --- Main execution block to combine results into one file ---
if __name__ == "__main__":
    print("--- Starting WallStreetBets Ticker Sentiment Scrape ---")
    sentiment_data = scrape_swaggystocks_sentiment()

    print("\n--- Starting Unusual Options Activity Scrape ---")
    options_activity_data = scrape_unusual_options_activity()

    # Define the single output file path
    final_combined_output_path = Path("sentiment/swaggystocks_sentiment.json")
    
    # Ensure the parent directory exists
    final_combined_output_path.parent.mkdir(exist_ok=True, parents=True)

    # Combine and save all collected data into this single JSON file
    combined_results_dict = {}
    if sentiment_data:
        combined_results_dict['wallstreetbets_sentiment'] = sentiment_data
    else:
        combined_results_dict['wallstreetbets_sentiment'] = []
        print("❗ WallStreetBets Sentiment data not collected for combined output.")

    if options_activity_data:
        combined_results_dict['unusual_options_activity'] = options_activity_data
    else:
        combined_results_dict['unusual_options_activity'] = []
        print("❗ Unusual Options Activity data not collected for combined output.")

    if combined_results_dict:
        with open(final_combined_output_path, "w") as f:
            json.dump(combined_results_dict, f, indent=2)
        print(f"\n✅ All collected data successfully saved to: {final_combined_output_path}")
    else:
        print("\n❌ No data collected from either scraper. Combined JSON file not created.")