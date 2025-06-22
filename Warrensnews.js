const puppeteer = require('puppeteer');
const fs = require('fs');

// --- Helper Functions for Data Normalization ---
function parseCurrency(value) {
    if (!value) return null;
    // Convert unicode minus (U+2212) to standard hyphen-minus (U+002D)
    let cleaned = value.toString().replace(/−/g, '-').replace(/[^0-9.-]+/g, '');
    return parseFloat(cleaned);
}

function parseChange(value) {
    if (!value) return null;
    let cleaned = value.toString().replace(/−/g, '-').replace(/,/g, '');
    return parseFloat(cleaned);
}

function parsePercent(value) {
    if (!value) return null;
    let cleaned = value.toString().replace(/−/g, '-').replace('%', '');
    return parseFloat(cleaned);
}

function parseVolume(value) {
    if (!value) return null;
    // Improved parseVolume to correctly handle all suffixes (T, B, M, K) and remove other text (like 'USD')
    let cleaned = value.toString().replace(/−/g, '-').replace(/,/g, '').trim().toUpperCase(); // Convert to uppercase for consistent suffix checking

    let parsedValue = parseFloat(cleaned); // Attempt to parse before removing suffixes, for cases like "3.55" for 3.55M

    // Check for suffixes and adjust multiplier, then remove suffix from string
    let multiplier = 1;
    if (cleaned.includes('T')) {
        multiplier = 1_000_000_000_000;
        cleaned = cleaned.replace(/T.*$/, ''); // Remove 'T' and everything after it
    } else if (cleaned.includes('B')) {
        multiplier = 1_000_000_000;
        cleaned = cleaned.replace(/B.*$/, '');
    } else if (cleaned.includes('M')) {
        multiplier = 1_000_000;
        cleaned = cleaned.replace(/M.*$/, '');
    } else if (cleaned.includes('K')) {
        multiplier = 1_000;
        cleaned = cleaned.slice(0, -1); // Remove 'K'
    }

    // After attempting to remove a scaling suffix, remove any other non-numeric characters (like 'USD' if present)
    // This step is crucial if the original string was like "477.40 USD" (no scaling suffix) or "3.55 T USD" after T is removed.
    cleaned = cleaned.replace(/[^0-9.-]+/g, '');

    // Re-parse after removing suffixes
    parsedValue = parseFloat(cleaned);

    return parsedValue * multiplier;
}

// --- Scraping Functions ---

async function scrapeYahooLosers(browser) {
    console.log('Starting Yahoo Finance scraping...');
    const page = await browser.newPage();
    const url = 'https://finance.yahoo.com/markets/stocks/losers/?start=0&count=150'; // Use direct URL with 250 rows

    console.log(`Yahoo: Navigating to direct URL: ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded' });

    console.log('Yahoo: Waiting for table rows to load from direct URL...');
    await page.waitForSelector('table tbody tr');

    const data = await page.evaluate(() => {
        const rows = Array.from(document.querySelectorAll('table tbody tr'));
        return rows.map(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 11) return null;

            // getCleanText is now simpler, so it just trims and replaces unicode minus.
            // Suffixes and currency symbols are handled by parseVolume/parseCurrency
            const getCleanTextForRawData = (td) => td?.innerText.replace(/−/g, '-').trim() || '';

            return {
                ticker: getCleanTextForRawData(cells[0]), // ticker will be cleaned in standardizeAndNormalizeData
                name: getCleanTextForRawData(cells[1]),
                price: getCleanTextForRawData(cells[3]),
                change: getCleanTextForRawData(cells[4]),
                percentChange: getCleanTextForRawData(cells[5]),
                volume: getCleanTextForRawData(cells[6]),
                avgVolume: getCleanTextForRawData(cells[7]),
                marketCap: getCleanTextForRawData(cells[8]), // Raw string like "128.682M" or "2.028"
                peRatio: getCleanTextForRawData(cells[9]),
                fiftyTwoWeekChange: getCleanTextForRawData(cells[10])
            };
        }).filter(item => item !== null);
    });
    await page.close();
    console.log(`Finished Yahoo Finance scraping. Found ${data.length} items.`);
    return data.map(stock => ({ ...stock, source: ['Yahoo Finance'] }));
}

async function scrapeTradingViewLosers(browser) {
    console.log('Starting TradingView Losers (Overview) scraping...');
    const page = await browser.newPage();
    const url = 'https://www.tradingview.com/markets/stocks-usa/market-movers-losers/'; // Correct Overview URL

    console.log('TradingView Losers: Navigating to page...');
    await page.goto(url, { waitUntil: 'domcontentloaded' });

    console.log('TradingView Losers: Scrolling down to ensure table is visible...');
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 1.5));
    await new Promise(r => setTimeout(r, 2000));

    console.log('TradingView Losers: Waiting for table selector and content...');
    const tableSelector = 'table.table-Ngq2xrcG tbody tr';
    try {
        await page.waitForFunction(
            (selector) => document.querySelectorAll(selector).length >= 5, // Wait for at least 5 rows
            { polling: 500, timeout: 30000 },
            tableSelector
        );
        console.log('TradingView Losers: Table rows found and loaded (at least 5).');
    } catch (error) {
        console.warn(`TradingView Losers: No or insufficient table rows found within timeout: ${error.message}. Table might be empty or selector has changed.`);
        await page.close();
        return [];
    }

    const data = await page.evaluate(() => {
        // getCleanText is now simpler
        const getCleanText = (tdElement) => {
            if (tdElement instanceof Element && tdElement.innerText !== undefined) {
                return tdElement.innerText.replace(/−/g, '-').trim(); // Only replace unicode minus and trim
            }
            return '';
        };
        // Robust ticker extraction: Get only the first non-whitespace word/token
        const getSymbol = (tdElement) => {
            const fullText = getCleanText(tdElement);
            return fullText.split(/\s|\n/)[0].trim(); // Split by space or newline and take the first part
        };


        const rows = Array.from(document.querySelectorAll('table.table-Ngq2xrcG tbody tr'));
        const extractedData = [];
        let skippedCount = 0;

        for (const row of rows) {
            const cells = row.querySelectorAll('td');

            if (cells.length === 0) {
                skippedCount++;
                continue;
            }

            // MAPPING FOR 'Biggest Losers - Overview' (from image_d69d3b.png)
            extractedData.push({
                ticker: getSymbol(cells[0]),
                price: getCleanText(cells[2]),       // Price is in cells[2]
                percentChange: getCleanText(cells[1]),// % Change is in cells[1]
                volume: getCleanText(cells[3] || ''),
                relVolume: getCleanText(cells[4] || ''),
                marketCap: getCleanText(cells[5] || ''), // Raw string from cell, will be parsed later
                peRatioTV: getCleanText(cells[6] || ''),
                epsDilTTM: getCleanText(cells[7] || ''),
                epsDilGrowthTTMYOY: getCleanText(cells[8] || ''),
                divYieldTTM: getCleanText(cells[9] || ''),
                sector: getCleanText(cells[10] || ''),
                analystRating: getCleanText(cells[11] || ''),
            });
        }
        console.log(`TradingView Losers (in evaluate): Total rows processed: ${rows.length}, Skipped ${skippedCount} rows due to being empty or having very few cells.`);
        return extractedData;
    });
    await page.close();
    console.log(`Finished TradingView Losers scraping. Found ${data.length} items.`);
    return data.map(stock => ({ ...stock, source: ['TradingView Losers'] }));
}

async function scrapeTradingViewOversold(browser) {
    console.log('Starting TradingView Oversold (Overview) scraping...');
    const page = await browser.newPage();
    const url = 'https://www.tradingview.com/markets/stocks-usa/market-movers-oversold/'; // Correct Overview URL

    console.log('TradingView Oversold: Navigating to page...');
    await page.goto(url, { waitUntil: 'domcontentloaded' });

    console.log('TradingView Oversold: Scrolling down to ensure table is visible...');
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 1.5));
    await new Promise(r => setTimeout(r, 2000));

    console.log('TradingView Oversold: Waiting for table selector and content...');
    const tableSelector = 'table.table-Ngq2xrcG tbody tr';
    try {
        await page.waitForFunction(
            (selector) => document.querySelectorAll(selector).length >= 5, // Wait for at least 5 rows
            { polling: 500, timeout: 30000 },
            tableSelector
        );
        console.log('TradingView Oversold: Table rows found and loaded (at least 5).');
    } catch (error) {
        console.warn(`TradingView Oversold: No or insufficient table rows found within timeout: ${error.message}. Table might be empty or selector has changed.`);
        await page.close();
        return [];
    }

    const data = await page.evaluate(() => {
        // getCleanText is now simpler
        const getCleanText = (tdElement) => {
            if (tdElement instanceof Element && tdElement.innerText !== undefined) {
                return tdElement.innerText.replace(/−/g, '-').trim();
            }
            return '';
        };
        // Robust ticker extraction
        const getSymbol = (tdElement) => {
            const fullText = getCleanText(tdElement);
            return fullText.split(/\s|\n/)[0].trim();
        };

        const rows = Array.from(document.querySelectorAll('table.table-Ngq2xrcG tbody tr'));
        const extractedData = [];
        let skippedCount = 0;

        for (const row of rows) {
            const cells = row.querySelectorAll('td');

            if (cells.length === 0) {
                skippedCount++;
                continue;
            }
            // MAPPING FOR 'Most Undervalued US stocks - Overview' (from image_d646e1.png)
            extractedData.push({
                ticker: getSymbol(cells[0]),
                rsi14: getCleanText(cells[1] || ''),
                price: getCleanText(cells[2]),
                percentChange: getCleanText(cells[3]),
                volume: getCleanText(cells[4] || ''),
                relVolume: getCleanText(cells[5] || ''),
                marketCap: getCleanText(cells[6] || ''), // Raw string from cell
                peRatioTV: getCleanText(cells[7] || ''),
                epsDilTTM: getCleanText(cells[8] || ''),
                epsDilGrowthTTMYOY: getCleanText(cells[9] || ''),
                divYieldTTM: getCleanText(cells[10] || ''),
                sector: getCleanText(cells[11] || ''),
                analystRating: getCleanText(cells[12] || ''),
            });
        }
        console.log(`TradingView Oversold (in evaluate): Total rows processed: ${rows.length}, Skipped ${skippedCount} rows due to being empty or having very few cells.`);
        return extractedData;
    });
    await page.close();
    console.log(`Finished TradingView Oversold scraping. Found ${data.length} items.`);
    return data.map(stock => ({ ...stock, source: ['TradingView Oversold'] }));
}

async function scrapeTradingViewLargeCap(browser) {
    console.log('Starting TradingView Large Cap (Overview) scraping...');
    const page = await browser.newPage();
    // Correct URL for Large Cap Movers
    const url = 'https://www.tradingview.com/markets/stocks-usa/market-movers-large-cap/';

    console.log('TradingView Large Cap: Navigating to page...');
    await page.goto(url, { waitUntil: 'domcontentloaded' });

    console.log('TradingView Large Cap: Scrolling down to ensure table is visible...');
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 1.5));
    await new Promise(r => setTimeout(r, 2000));

    console.log('TradingView Large Cap: Waiting for table selector and content...');
    const tableSelector = 'table.table-Ngq2xrcG tbody tr';
    try {
        await page.waitForFunction(
            (selector) => document.querySelectorAll(selector).length >= 5, // Wait for at least 5 rows
            { polling: 500, timeout: 30000 },
            tableSelector
        );
        console.log('TradingView Large Cap: Table rows found and loaded (at least 5).');
    } catch (error) {
        console.warn(`TradingView Large Cap: No or insufficient table rows found within timeout: ${error.message}. Table might be empty or selector has changed.`);
        await page.close();
        return [];
    }

    const data = await page.evaluate(() => {
        // getCleanText is now simpler
        const getCleanText = (tdElement) => {
            if (tdElement instanceof Element && tdElement.innerText !== undefined) {
                return tdElement.innerText.replace(/−/g, '-').trim();
            }
            return '';
        };
        // Robust ticker extraction
        const getSymbol = (tdElement) => {
            const fullText = getCleanText(tdElement);
            return fullText.split(/\s|\n/)[0].trim();
        };

        const rows = Array.from(document.querySelectorAll('table.table-Ngq2xrcG tbody tr'));
        const extractedData = [];
        let skippedCount = 0;

        for (const row of rows) {
            const cells = row.querySelectorAll('td');

            if (cells.length === 0) {
                skippedCount++;
                continue;
            }

            // Corrected MAPPING for 'Large Cap - Overview' (from image_d6a177.png)
            // This is the order you provided and that matches the screenshot's columns visually.
            // cells[0]: Symbol (Ticker + Name)
            // cells[1]: Market cap
            // cells[2]: Price
            // cells[3]: Change %
            // cells[4]: Volume
            // cells[5]: Rel Volume
            // cells[6]: P/E
            // cells[7]: EPS dil TTM
            // cells[8]: EPS dil growth ttm YOY
            // cells[9]: Div yield % ttm
            // cells[10]: Sector
            // cells[11]: Analyst Rating
            extractedData.push({
                ticker: getSymbol(cells[0]),
                marketCap: getCleanText(cells[1]),    // Raw string (e.g., "3.55 T USD")
                price: getCleanText(cells[2]),       // Raw string (e.g., "477.40 USD")
                percentChange: getCleanText(cells[3]), // Raw string (e.g., "-0.59%")
                volume: getCleanText(cells[4] || ''), // Raw string (e.g., "37.58 M")
                relVolume: getCleanText(cells[5] || ''), // Raw string (e.g., "2.24")
                peRatioTV: getCleanText(cells[6] || ''),
                epsDilTTM: getCleanText(cells[7] || ''),
                epsDilGrowthTTMYOY: getCleanText(cells[8] || ''),
                divYieldTTM: getCleanText(cells[9] || ''),
                sector: getCleanText(cells[10] || ''),
                analystRating: getCleanText(cells[11] || ''),
            });
        }
        console.log(`TradingView Large Cap (in evaluate): Total rows processed: ${rows.length}, Skipped ${skippedCount} rows due to being empty or having very few cells.`);
        return extractedData;
    });
    await page.close();
    console.log(`Finished TradingView Large Cap scraping. Found ${data.length} items.`);
    return data.map(stock => ({ ...stock, source: ['TradingView Large Cap'] }));
}


// --- Data Processing Functions ---

function standardizeAndNormalizeData(data) {
    console.log('Normalizing raw data to common schema...');
    return data.map(item => {
        const standardizedItem = {
            ticker: item.ticker ? item.ticker.toUpperCase() : '',
            price: item.price ? parseCurrency(item.price) : null,
            percentChange: item.percentChange ? parsePercent(item.percentChange) : null,
            volume: item.volume ? parseVolume(item.volume) : null,

            // Yahoo-specific fields
            name: item.name || null,
            change: item.change ? parseChange(item.change) : null,
            avgVolume: item.avgVolume ? parseVolume(item.avgVolume) : null,
            // marketCap and peRatio are handled below for merge/parsing
            fiftyTwoWeekChange: item.fiftyTwoWeekChange ? parsePercent(item.fiftyTwoWeekChange) : null,

            // TradingView-specific fields
            relVolume: item.relVolume ? parseVolume(item.relVolume) : null,
            // peRatioTV is handled below for consolidation
            epsDilTTM: item.epsDilTTM && item.epsDilTTM !== '—' ? parseCurrency(item.epsDilTTM) : null,
            epsDilGrowthTTMYOY: item.epsDilGrowthTTMYOY && item.epsDilGrowthTTMYOY !== '—' ? parsePercent(item.epsDilGrowthTTMYOY) : null,
            divYieldTTM: item.divYieldTTM && item.divYieldTTM !== '—' ? parsePercent(item.divYieldTTM) : null,
            sector: item.sector || null,
            analystRating: item.analystRating && item.analystRating !== '—' ? item.analystRating : null,
            rsi14: item.rsi14 ? parseCurrency(item.rsi14) : null,

            source: item.source || []
        };

        // Handle MarketCap merging and parsing from all sources
        let parsedMarketCap = null;
        if (item.marketCap) { // item.marketCap holds raw string from either Yahoo or TV Large Cap
            parsedMarketCap = parseVolume(item.marketCap); // This will handle T, B, M, K suffixes
        }

        // If the item originated from Yahoo, prioritize its marketCap
        if (item.source.includes('Yahoo Finance')) {
            standardizedItem.marketCap = parsedMarketCap;
        } else if (parsedMarketCap !== null && !isNaN(parsedMarketCap)) {
            // Otherwise (if from TradingView and valid), use it for the main marketCap field
            standardizedItem.marketCap = parsedMarketCap;
        }

        // --- P/E Ratio Consolidation within standardizeAndNormalizeData ---
        let finalPERatio = null;
        const rawYahooPERatio = item.peRatio && item.peRatio !== '--' ? parseFloat(item.peRatio) : null;
        const parsedTVPERatio = item.peRatioTV && item.peRatioTV !== '—' ? parseFloat(item.peRatioTV) : null; // Parse here before comparison

        if (rawYahooPERatio !== null && !isNaN(rawYahooPERatio)) {
            finalPERatio = rawYahooPERatio;
        }

        if (parsedTVPERatio !== null && !isNaN(parsedTVPERatio)) {
            const PE_DEVIATION_THRESHOLD = 0.05; // 5% deviation

            if (finalPERatio !== null && !isNaN(finalPERatio)) {
                // Both exist, check for 5% deviation
                const deviation = Math.abs((finalPERatio - parsedTVPERatio) / finalPERatio);
                if (deviation <= PE_DEVIATION_THRESHOLD) {
                    // Within threshold, keep Yahoo's (finalPERatio already set)
                } else {
                    // If deviation is greater than 5%, and TV's is valid, prefer TV's if Yahoo's is zero or undefined, or just keep Yahoo's.
                    // As per current rules, if both exist and deviate, Yahoo's (finalPERatio) is kept implicitly.
                    // If the user wants specific prioritization logic for deviation, it would go here.
                }
            } else {
                // Yahoo's is missing/invalid, but TV's exists, so use TV's
                finalPERatio = parsedTVPERatio;
            }
        }
        standardizedItem.peRatio = finalPERatio;
        // Explicitly remove peRatioTV from the standardized item before it leaves this function
        delete standardizedItem.peRatioTV;


        return standardizedItem;
    }).filter(item => item.ticker !== '');
}

function deduplicateData(data) {
    console.log('Starting deduplication...');
    const uniqueStocks = new Map();

    for (const item of data) {
        if (!item.ticker) continue;

        if (!uniqueStocks.has(item.ticker)) {
            uniqueStocks.set(item.ticker, item);
        } else {
            const existing = uniqueStocks.get(item.ticker);

            existing.source = Array.from(new Set([...existing.source, ...item.source]));

            // Prioritize non-null/NaN values from item if existing is null/NaN
            existing.price = (existing.price !== null && !isNaN(existing.price)) ? existing.price : item.price;
            existing.percentChange = (existing.percentChange !== null && !isNaN(existing.percentChange)) ? existing.percentChange : item.percentChange;
            existing.volume = (existing.volume !== null && !isNaN(existing.volume)) ? existing.volume : item.volume;
            existing.marketCap = (existing.marketCap !== null && !isNaN(existing.marketCap)) ? existing.marketCap : item.marketCap;
            existing.peRatio = (existing.peRatio !== null && !isNaN(existing.peRatio)) ? existing.peRatio : item.peRatio;

            // Merge Yahoo-specific fields
            if (item.source.includes('Yahoo Finance')) {
                existing.name = existing.name || item.name;
                existing.change = (existing.change !== null && !isNaN(existing.change)) ? existing.change : item.change;
                existing.avgVolume = (existing.avgVolume !== null && !isNaN(existing.avgVolume)) ? existing.avgVolume : item.avgVolume;
                existing.fiftyTwoWeekChange = (existing.fiftyTwoWeekChange !== null && !isNaN(existing.fiftyTwoWeekChange)) ? existing.fiftyTwoWeekChange : item.fiftyTwoWeekChange;
            }

            // Merge TradingView-specific fields
            if (item.source.some(s => s.startsWith('TradingView'))) {
                existing.relVolume = existing.relVolume || item.relVolume;
                existing.epsDilTTM = existing.epsDilTTM || item.epsDilTTM;
                existing.epsDilGrowthTTMYOY = existing.epsDilGrowthTTMYOY || item.epsDilGrowthTTMYOY;
                existing.divYieldTTM = existing.divYieldTTM || item.divYieldTTM;
                existing.sector = existing.sector || item.sector;
                existing.analystRating = existing.analystRating || item.analystRating;
                existing.rsi14 = existing.rsi14 || item.rsi14;
            }

            uniqueStocks.set(item.ticker, existing);
        }
    }
    console.log('Deduplication complete.');
    return Array.from(uniqueStocks.values());
}

// --- Main Execution ---
async function runConsolidatedScraper() {
    let browser;
    try {
        browser = await puppeteer.launch({
            headless: true,
            defaultViewport: null,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });

        const yahooData = await scrapeYahooLosers(browser);
        const tradingViewLosersData = await scrapeTradingViewLosers(browser);
        const tradingViewOversoldData = await scrapeTradingViewOversold(browser);
        const tradingViewLargeCapData = await scrapeTradingViewLargeCap(browser);

        let allRawData = [...yahooData, ...tradingViewLosersData, ...tradingViewOversoldData, ...tradingViewLargeCapData];

        console.log('Standardizing and normalizing data...');
        let processedData = standardizeAndNormalizeData(allRawData);

        // Reinstated filter step: remove entries where marketCap is less than 100M USD
        const minMarketCap = 100_000_000; // 100 million
        let filteredData = processedData.filter(item => {
            // Only filter if marketCap is a valid number and below the threshold
            return item.marketCap === null || isNaN(item.marketCap) || item.marketCap >= minMarketCap;
        });
        console.log(`Filtered out ${processedData.length - filteredData.length} entries with market cap less than $${minMarketCap / 1_000_000}M.`);


        console.log('Deduplicating data...');
        // Pass filtered data to deduplication
        let finalData = deduplicateData(filteredData); 

        // Change output file name
        const outputPath = './warrensoutputfile.json'; 
        fs.writeFileSync(outputPath, JSON.stringify(finalData, null, 2));

        console.log(`✅ Scraping, standardization, normalization, filtering, and deduplication complete.`);
        console.log(`Data saved to ${outputPath}. Total unique stocks: ${finalData.length}`);

    } catch (error) {
        console.error('❌ An error occurred during the scraping process:', error);
    } finally {
        if (browser) {
            await browser.close();
            console.log('Browser closed.');
        }
    }
}

// Run the scraper
runConsolidatedScraper();


// --- Finviz Scraper for Large Cap Losers ---
async function scrapeFinvizLargeCap(page) {
    let finvizData = [];
    for (let i = 1; i <= 41; i++) {
        const url = `https://finviz.com/screener.ashx?v=111&f=cap_large&o=-change&page=${i}`;
        console.log(`Scraping Finviz page ${i}...`);
        await page.goto(url, { waitUntil: 'domcontentloaded' });

        await page.waitForSelector('table.table-light', { timeout: 10000 }).catch(() => {
            console.log(`Timeout on page ${i}`);
            return;
        });

        const pageData = await page.evaluate(() => {
            const rows = Array.from(document.querySelectorAll("table.table-light tr[valign='top']"));
            return rows.map(row => {
                const cols = row.querySelectorAll('td');
                return {
                    ticker: cols[1]?.innerText.trim(),
                    name: cols[2]?.innerText.trim(),
                    price: parseFloat(cols[8]?.innerText.replace(/[^0-9.\-]/g, "")),
                    change: parseFloat(cols[9]?.innerText.replace(/[^0-9.\-]/g, "")),
                    percentChange: parseFloat(cols[10]?.innerText.replace('%', '')),
                    volume: cols[11]?.innerText.trim(),
                    pe: cols[12]?.innerText.trim(),
                    rsi: cols[21]?.innerText.trim()
                };
            });
        });

        finvizData.push(...pageData);
        await new Promise(resolve => setTimeout(resolve, 300)); // throttle
    }
    return finvizData;
}
