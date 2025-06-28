import fetch from 'node-fetch';
import fs from 'fs/promises';

const regionByPreset = {
  large_cap: 'america',
  losers: 'america',
  oversold: 'america',
  // For European markets we override region in calls
};

const sortConfigs = {
  large_cap: {
    nullsFirst: false,
    sortBy: "market_cap_basic",
    sortOrder: "desc"
  },
  losers: {
    nullsFirst: false,
    sortBy: "change",
    sortOrder: "asc"
  },
  oversold: {
    nullsFirst: false,
    sortBy: "change",
    sortOrder: "asc"
  }
};

const columnsByPreset = {
  large_cap: [
    "name", "description", "logoid", "update_mode", "type", "typespecs",
    "market_cap_basic", "fundamental_currency_code", "close", "pricescale", "minmov", "fractional", "minmove2",
    "currency", "change", "volume", "relative_volume_10d_calc", "price_earnings_ttm",
    "earnings_per_share_diluted_ttm", "dividends_yield_current", "sector.tr", "market", "sector", "recommendation_mark",
    "Recommend.All", "RSI", "Mom", "MACD.macd", "MACD.signal", "CCI20"
  ],
  losers: [
    "name", "description", "logoid", "update_mode", "type", "typespecs",
    "change", "close", "pricescale", "minmov", "fractional", "minmove2",
    "currency", "volume", "relative_volume_10d_calc", "market_cap_basic", "fundamental_currency_code",
    "price_earnings_ttm", "earnings_per_share_diluted_ttm", "earnings_per_share_diluted_yoy_growth_ttm",
    "dividends_yield_current", "sector.tr", "market", "sector", "recommendation_mark",
    "Recommend.All", "RSI", "Mom", "MACD.macd", "MACD.signal", "CCI20"
  ],
  oversold: [
    "name", "description", "logoid", "update_mode", "type", "typespecs",
    "change", "close", "pricescale", "minmov", "fractional", "minmove2",
    "currency", "volume", "relative_volume_10d_calc", "market_cap_basic", "fundamental_currency_code",
    "price_earnings_ttm", "earnings_per_share_diluted_ttm", "earnings_per_share_diluted_yoy_growth_ttm",
    "dividends_yield_current", "sector.tr", "market", "sector", "recommendation_mark",
    "Recommend.All", "RSI", "Mom", "MACD.macd", "MACD.signal", "CCI20"
  ]
};

function extractFields(item, columns, category) {
  // item.d array indexes correspond to columns order
  let obj = { category };
  columns.forEach((col, idx) => {
    obj[col] = item.d[idx] ?? null;
  });
  // Add annotation about volume fields
  obj.volume_note = "Volume represents 1-day trading volume";
  obj.relative_volume_10d_calc_note = "Relative volume is 1-day relative to 10-day average";
  return obj;
}

async function fetchTradingViewBatch(preset, start = 0, batchSize = 100, regionOverride = null) {
  const region = regionOverride || regionByPreset[preset] || "america";
  const url = `https://scanner.tradingview.com/${region}/scan?label-product=markets-screener`;

  const columns = columnsByPreset[preset] || columnsByPreset.large_cap;

  const payload = {
    columns,
    ignore_unknown_fields: false,
    options: {},
    lang: "en",
    preset,
    range: [start, start + batchSize - 1],
    sort: sortConfigs[preset] || sortConfigs.large_cap
  };

  const response = await fetch(url, {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'Mozilla/5.0 (compatible; scraping-bot/1.0)',
      'Accept': 'application/json'
    }
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status} for preset ${preset} region ${region}`);
  }

  const data = await response.json();

  if (!data.data || data.data.length === 0) return [];

  return data.data.map(item => extractFields(item, columns, preset));
}

async function fetchAllByPreset(preset, regionOverride = null) {
  const batchSize = 100;
  let start = 0;
  let allData = [];

  while (true) {
    console.log(`Fetching ${preset} from ${start} to ${start + batchSize - 1}...`);
    const batch = await fetchTradingViewBatch(preset, start, batchSize, regionOverride);
    if (batch.length === 0) break;

    allData = allData.concat(batch);
    start += batchSize;

    if (batch.length < batchSize) break;
  }

  return allData;
}

async function main() {
  try {
    const largeCaps = await fetchAllByPreset('large_cap');
    const losers = await fetchAllByPreset('losers');
    const oversold = await fetchAllByPreset('oversold');

    // Germany and Netherlands large caps from region overrides
    const germanyLargeCaps = await fetchAllByPreset('large_cap', 'germany');
    const netherlandsLargeCaps = await fetchAllByPreset('large_cap', 'netherlands');

    const combinedData = {
      america: {
        large_cap: largeCaps,
        losers: losers,
        oversold: oversold
      },
      germany: {
        large_cap: germanyLargeCaps
      },
      netherlands: {
        large_cap: netherlandsLargeCaps
      }
    };

    await fs.writeFile('combined_output.json', JSON.stringify(combinedData, null, 2), 'utf-8');
    console.log('Data saved to combined_output.json');
  } catch (error) {
    console.error('Error fetching data:', error);
  }
}

main();
