#!/usr/bin/env node
/**
 * Relative-value pair screener for the memory / storage / AI-server supply chain.
 * Downloads daily adjusted-close data from Yahoo Finance, then tests each unique
 * pair with a simple rolling z-score mean-reversion strategy.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT = path.join(ROOT, 'outputs');
const CONFIG_PATH = path.join(ROOT, 'pairs.config.json');
const CACHE_PATH = path.join(OUTPUT, 'pair-results.json');
const CSV_PATH = path.join(OUTPUT, 'pair-results.csv');
const PRICE_CACHE_DIR = path.join(OUTPUT, 'price-cache');

const args = new Set(process.argv.slice(2));
const valueAfter = (name) => {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
};

function toDate(seconds) { return new Date(seconds * 1000).toISOString().slice(0, 10); }
function number(v) { return Number.isFinite(v) ? v : null; }
function mean(xs) { return xs.reduce((a, b) => a + b, 0) / xs.length; }
function std(xs) {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1));
}
function linearFit(x, y) {
  const xm = mean(x), ym = mean(y);
  let covariance = 0, variance = 0;
  for (let i = 0; i < x.length; i++) { covariance += (x[i] - xm) * (y[i] - ym); variance += (x[i] - xm) ** 2; }
  const beta = variance === 0 ? 1 : covariance / variance;
  return { beta, intercept: ym - beta * xm };
}
function adfTStat(residuals) {
  const x = residuals.slice(0, -1);
  const y = residuals.slice(1).map((value, index) => value - residuals[index]);
  if (x.length < 10) return null;
  const fit = linearFit(x, y);
  const errors = y.map((value, index) => value - (fit.intercept + fit.beta * x[index]));
  const variance = errors.reduce((sum, value) => sum + value ** 2, 0) / Math.max(1, x.length - 2);
  const denominator = x.reduce((sum, value) => sum + (value - mean(x)) ** 2, 0);
  return denominator > 0 ? fit.beta / Math.sqrt(variance / denominator) : null;
}
function pairFit(prices) {
  const x = prices.map(p => Math.log(p[1]));
  const y = prices.map(p => Math.log(p[0]));
  const fit = linearFit(x, y);
  return { ...fit, residuals: prices.map(p => Math.log(p[0]) - (fit.intercept + fit.beta * Math.log(p[1]))) };
}
function escapeCsv(value) { return `"${String(value ?? '').replaceAll('"', '""')}"`; }
function fingerprint(strategy) { return crypto.createHash('sha256').update(JSON.stringify(strategy)).digest('hex'); }
function strategiesFrom(config) {
  if (Array.isArray(config.strategies) && config.strategies.length) return config.strategies;
  if (config.strategy) return [{ name: 'default', ...config.strategy }];
  throw new Error('Configure at least one strategy in the strategies array.');
}
function candidatePairs(config) {
  const order = new Map(config.tickers.map((ticker, index) => [ticker, index]));
  const pairs = new Map();
  const addPair = (a, b, group) => {
    if (a === b) return;
    const [leftTicker, rightTicker] = order.get(a) < order.get(b) ? [a, b] : [b, a];
    const key = `${leftTicker}/${rightTicker}`;
    const row = pairs.get(key) ?? { leftTicker, rightTicker, pair: key, relationship: [] };
    row.relationship.push(group);
    pairs.set(key, row);
  };
  if (config.screenMode === 'all') {
    for (let i = 0; i < config.tickers.length; i++) for (let j = i + 1; j < config.tickers.length; j++) addPair(config.tickers[i], config.tickers[j], 'all companies');
  } else {
    for (const [group, members] of Object.entries(config.pairGroups ?? {})) {
      for (const ticker of members) if (!order.has(ticker)) throw new Error(`${ticker} in pairGroups is not in tickers`);
      for (let i = 0; i < members.length; i++) for (let j = i + 1; j < members.length; j++) addPair(members[i], members[j], group);
    }
  }
  return [...pairs.values()].map(row => ({ ...row, relationship: [...new Set(row.relationship)].join('; ') }));
}

async function getPrices(ticker, years) {
  const cacheFile = path.join(PRICE_CACHE_DIR, `${ticker.replaceAll(/[^A-Z0-9.-]/gi, '_')}.json`);
  const cached = await loadJson(cacheFile, null);
  const today = new Date().toISOString().slice(0, 10);
  if (cached?.asOf === today && cached.historyYears >= years && !args.has('--refresh-prices')) return new Map(cached.rows);
  const end = Math.floor(Date.now() / 1000);
  const start = end - years * 366 * 86400;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?period1=${start}&period2=${end}&interval=1d&events=history&includeAdjustedClose=true`;
  const response = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 pair-screener/1.0' } });
  if (!response.ok) {
    if (cached?.rows) return new Map(cached.rows);
    throw new Error(`${ticker}: price download returned ${response.status}`);
  }
  const json = await response.json();
  const item = json.chart?.result?.[0];
  if (!item) throw new Error(`${ticker}: price data was empty`);
  const adjusted = item.indicators?.adjclose?.[0]?.adjclose ?? item.indicators?.quote?.[0]?.close;
  const rows = new Map();
  item.timestamp.forEach((time, i) => { if (number(adjusted[i]) && adjusted[i] > 0) rows.set(toDate(time), adjusted[i]); });
  await fs.mkdir(PRICE_CACHE_DIR, { recursive: true });
  await fs.writeFile(cacheFile, JSON.stringify({ ticker, asOf: today, historyYears: years, rows: [...rows] }));
  return rows;
}

function testPair(leftTicker, rightTicker, left, right, strategy) {
  const dates = [...left.keys()].filter(date => right.has(date)).sort();
  const prices = dates.map(date => [left.get(date), right.get(date)]);
  const testStart = dates.length - strategy.testDays;
  const trainingStart = testStart - strategy.trainingDays;
  if (trainingStart < 0) throw new Error(`Needs ${strategy.trainingDays + strategy.testDays} shared trading days; found ${dates.length}`);
  const training = prices.slice(trainingStart, testStart);
  const trainFit = pairFit(training);
  const midpoint = Math.floor(training.length / 2);
  const firstBeta = pairFit(training.slice(0, midpoint)).beta;
  const secondBeta = pairFit(training.slice(midpoint)).beta;
  const betaDrift = Math.abs(firstBeta - secondBeta) / Math.max(Math.abs(trainFit.beta), 0.01);
  const adf = adfTStat(trainFit.residuals);
  const adfPass = adf !== null && adf <= strategy.adfCriticalValue;
  const stabilityPass = betaDrift <= strategy.maxHedgeRatioDrift;
  const base = { pair: `${leftTicker}/${rightTicker}`, leftTicker, rightTicker, observations: dates.length, trainingFrom: dates[trainingStart], trainingTo: dates[testStart - 1], testedFrom: dates[testStart], testedTo: dates.at(-1), trainHedgeRatio: trainFit.beta, adfTStat: adf, hedgeRatioDrift: betaDrift, adfPass, stabilityPass, qualified: adfPass && stabilityPass };
  if (!base.qualified) return { ...base, trades: 0, totalReturn: 0, maxDrawdown: 0, sharpe: 0, profitable: false, rejectReason: !adfPass ? 'training residual did not pass the mean-reversion threshold' : 'training hedge ratio was unstable' };
  const start = testStart;
  let position = 0, equity = 1, peak = 1, maxDrawdown = 0, trades = 0;
  const dailyReturns = [];
  for (let i = start; i < dates.length; i++) {
    const window = prices.slice(i - strategy.formationDays, i);
    if (window.length < strategy.formationDays) continue;
    const x = window.map(p => Math.log(p[1])), y = window.map(p => Math.log(p[0]));
    const fit = linearFit(x, y);
    const residuals = window.map(p => Math.log(p[0]) - (fit.intercept + fit.beta * Math.log(p[1])));
    const z = (Math.log(prices[i][0]) - (fit.intercept + fit.beta * Math.log(prices[i][1])) - mean(residuals)) / std(residuals);
    const previous = prices[i - 1];
    const longReturn = (prices[i][0] / previous[0] - 1) - fit.beta * (prices[i][1] / previous[1] - 1);
    const gross = 1 + Math.abs(fit.beta);
    let returned = position * longReturn / gross;
    const shortWeight = position > 0 ? Math.abs(fit.beta) / gross : 1 / gross;
    if (position !== 0) returned -= (strategy.shortBorrowBpsAnnual / 10000 / 252) * shortWeight;
    const nextPosition = position === 0 ? (z >= strategy.entryZ ? -1 : z <= -strategy.entryZ ? 1 : 0) : (Math.abs(z) <= strategy.exitZ ? 0 : position);
    if (nextPosition !== position) { returned -= (strategy.costBpsPerLeg / 10000) * 2; if (nextPosition !== 0) trades++; }
    position = nextPosition;
    equity *= 1 + returned;
    peak = Math.max(peak, equity); maxDrawdown = Math.min(maxDrawdown, equity / peak - 1);
    dailyReturns.push(returned);
  }
  const volatility = std(dailyReturns);
  const sharpe = volatility ? mean(dailyReturns) / volatility * Math.sqrt(252) : 0;
  const totalReturn = equity - 1;
  const profitable = totalReturn > 0 && trades >= strategy.minTrades;
  return { ...base, trades, totalReturn, maxDrawdown, sharpe, profitable, rejectReason: profitable ? null : 'out-of-sample return or minimum-trade requirement failed' };
}

async function loadJson(file, fallback) { try { return JSON.parse(await fs.readFile(file, 'utf8')); } catch { return fallback; } }
function round(result) { for (const key of ['totalReturn', 'maxDrawdown', 'sharpe', 'trainHedgeRatio', 'adfTStat', 'hedgeRatioDrift']) if (Number.isFinite(result[key])) result[key] = Number(result[key].toFixed(4)); return result; }

async function main() {
  const config = await loadJson(CONFIG_PATH, null);
  if (!config) throw new Error(`Missing ${CONFIG_PATH}`);
  const strategies = strategiesFrom(config);
  if (new Set(strategies.map(strategy => strategy.name)).size !== strategies.length) throw new Error('Every strategy needs a unique name.');
  const term = valueAfter('--search')?.toUpperCase();
  const old = await loadJson(CACHE_PATH, { results: [] });
  const pairs = candidatePairs(config);
  if (args.has('--search')) {
    const matching = old.results.filter(row => !term || Object.values(row).join(' ').toUpperCase().includes(term));
    console.table(matching);
    return;
  }
  await fs.mkdir(OUTPUT, { recursive: true });
  const prices = new Map();
  const downloadErrors = new Map();
  for (const ticker of config.tickers) {
    process.stdout.write(`Downloading ${ticker}...\n`);
    try { prices.set(ticker, await getPrices(ticker, config.historyYears)); }
    catch (error) { downloadErrors.set(ticker, error.message); console.warn(`Skipping ${ticker}: ${error.message}`); }
  }
  const prior = new Map(old.results.map(row => [`${row.pair}|${row.strategyName ?? 'default'}`, row]));
  const results = [];
  for (const candidate of pairs) {
    const { leftTicker: a, rightTicker: b, pair, relationship } = candidate;
    for (const strategy of strategies) {
      const strategyFingerprint = fingerprint(strategy);
      const cacheKey = `${pair}|${strategy.name}`;
      const cached = prior.get(cacheKey);
      const missing = downloadErrors.get(a) ?? downloadErrors.get(b);
      if (missing) {
        results.push({ pair, leftTicker: a, rightTicker: b, relationship, strategyName: strategy.name, error: missing, qualified: false, profitable: false, strategyFingerprint, reused: false, checkedAt: new Date().toISOString() });
        continue;
      }
      if (cached && !cached.profitable && cached.strategyFingerprint === strategyFingerprint && !args.has('--refresh-negatives')) {
        results.push({ ...cached, relationship, reused: true, checkedAt: new Date().toISOString() });
        continue;
      }
      try { results.push({ ...round(testPair(a, b, prices.get(a), prices.get(b), strategy)), relationship, strategyName: strategy.name, strategyFingerprint, reused: false, checkedAt: new Date().toISOString() }); }
      catch (error) { results.push({ pair, leftTicker: a, rightTicker: b, relationship, strategyName: strategy.name, error: error.message, profitable: false, strategyFingerprint, reused: false, checkedAt: new Date().toISOString() }); }
    }
  }
  results.sort((a, b) => (b.totalReturn ?? -Infinity) - (a.totalReturn ?? -Infinity));
  const output = { generatedAt: new Date().toISOString(), strategies, results };
  await fs.writeFile(CACHE_PATH, JSON.stringify(output, null, 2));
  const columns = ['pair', 'relationship', 'strategyName', 'qualified', 'profitable', 'totalReturn', 'maxDrawdown', 'sharpe', 'trades', 'adfTStat', 'hedgeRatioDrift', 'trainingFrom', 'trainingTo', 'testedFrom', 'testedTo', 'reused', 'rejectReason', 'error'];
  await fs.writeFile(CSV_PATH, [columns.join(','), ...results.map(row => columns.map(col => escapeCsv(row[col])).join(','))].join('\n'));
  console.table(results.filter(row => row.profitable).map(row => ({ pair: row.pair, relationship: row.relationship, strategy: row.strategyName, returnPct: `${(row.totalReturn * 100).toFixed(1)}%`, maxDrawdownPct: `${(row.maxDrawdown * 100).toFixed(1)}%`, sharpe: row.sharpe, trades: row.trades })));
  console.log(`Saved ${results.length} pair-strategy tests across ${pairs.length} economically related pairs. ${results.filter(x => x.profitable).length} met the profitability rule.`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
