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
function escapeCsv(value) { return `"${String(value ?? '').replaceAll('"', '""')}"`; }
function fingerprint(strategy) { return crypto.createHash('sha256').update(JSON.stringify(strategy)).digest('hex'); }
function strategiesFrom(config) {
  if (Array.isArray(config.strategies) && config.strategies.length) return config.strategies;
  if (config.strategy) return [{ name: 'default', ...config.strategy }];
  throw new Error('Configure at least one strategy in the strategies array.');
}

async function getPrices(ticker, years) {
  const end = Math.floor(Date.now() / 1000);
  const start = end - years * 366 * 86400;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?period1=${start}&period2=${end}&interval=1d&events=history&includeAdjustedClose=true`;
  const response = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 pair-screener/1.0' } });
  if (!response.ok) throw new Error(`${ticker}: price download returned ${response.status}`);
  const json = await response.json();
  const item = json.chart?.result?.[0];
  if (!item) throw new Error(`${ticker}: price data was empty`);
  const adjusted = item.indicators?.adjclose?.[0]?.adjclose ?? item.indicators?.quote?.[0]?.close;
  const rows = new Map();
  item.timestamp.forEach((time, i) => { if (number(adjusted[i]) && adjusted[i] > 0) rows.set(toDate(time), adjusted[i]); });
  return rows;
}

function testPair(leftTicker, rightTicker, left, right, strategy) {
  const dates = [...left.keys()].filter(date => right.has(date)).sort();
  const prices = dates.map(date => [left.get(date), right.get(date)]);
  const start = Math.max(strategy.formationDays, dates.length - strategy.backtestDays);
  let position = 0, equity = 1, peak = 1, maxDrawdown = 0, trades = 0;
  const dailyReturns = [];
  for (let i = start; i < dates.length; i++) {
    const window = prices.slice(i - strategy.formationDays, i);
    const x = window.map(p => Math.log(p[1])), y = window.map(p => Math.log(p[0]));
    const fit = linearFit(x, y);
    const residuals = window.map(p => Math.log(p[0]) - (fit.intercept + fit.beta * Math.log(p[1])));
    const z = (Math.log(prices[i][0]) - (fit.intercept + fit.beta * Math.log(prices[i][1])) - mean(residuals)) / std(residuals);
    const previous = prices[i - 1];
    const longReturn = (prices[i][0] / previous[0] - 1) - fit.beta * (prices[i][1] / previous[1] - 1);
    let returned = position * longReturn / (1 + Math.abs(fit.beta));
    const nextPosition = position === 0 ? (z >= strategy.entryZ ? -1 : z <= -strategy.entryZ ? 1 : 0) : (Math.abs(z) <= strategy.exitZ ? 0 : position);
    if (nextPosition !== position) { returned -= strategy.costBps / 10000; if (nextPosition !== 0) trades++; }
    position = nextPosition;
    equity *= 1 + returned;
    peak = Math.max(peak, equity); maxDrawdown = Math.min(maxDrawdown, equity / peak - 1);
    dailyReturns.push(returned);
  }
  const volatility = std(dailyReturns);
  const sharpe = volatility ? mean(dailyReturns) / volatility * Math.sqrt(252) : 0;
  const totalReturn = equity - 1;
  const profitable = totalReturn > 0 && trades >= strategy.minTrades;
  return { pair: `${leftTicker}/${rightTicker}`, leftTicker, rightTicker, observations: dates.length, testedFrom: dates[start], testedTo: dates.at(-1), trades, totalReturn, maxDrawdown, sharpe, profitable };
}

async function loadJson(file, fallback) { try { return JSON.parse(await fs.readFile(file, 'utf8')); } catch { return fallback; } }
function round(result) { for (const key of ['totalReturn', 'maxDrawdown', 'sharpe']) result[key] = Number(result[key].toFixed(4)); return result; }

async function main() {
  const config = await loadJson(CONFIG_PATH, null);
  if (!config) throw new Error(`Missing ${CONFIG_PATH}`);
  const strategies = strategiesFrom(config);
  if (new Set(strategies.map(strategy => strategy.name)).size !== strategies.length) throw new Error('Every strategy needs a unique name.');
  const term = valueAfter('--search')?.toUpperCase();
  const old = await loadJson(CACHE_PATH, { results: [] });
  if (args.has('--search')) {
    const matching = old.results.filter(row => !term || Object.values(row).join(' ').toUpperCase().includes(term));
    console.table(matching);
    return;
  }
  await fs.mkdir(OUTPUT, { recursive: true });
  const prices = new Map();
  for (const ticker of config.tickers) { process.stdout.write(`Downloading ${ticker}...\n`); prices.set(ticker, await getPrices(ticker, config.historyYears)); }
  const prior = new Map(old.results.map(row => [`${row.pair}|${row.strategyName ?? 'default'}`, row]));
  const results = [];
  for (let i = 0; i < config.tickers.length; i++) for (let j = i + 1; j < config.tickers.length; j++) {
    const a = config.tickers[i], b = config.tickers[j], pair = `${a}/${b}`;
    for (const strategy of strategies) {
      const strategyFingerprint = fingerprint(strategy);
      const cacheKey = `${pair}|${strategy.name}`;
      const cached = prior.get(cacheKey);
      if (cached && !cached.profitable && cached.strategyFingerprint === strategyFingerprint && !args.has('--refresh-negatives')) {
        results.push({ ...cached, reused: true, checkedAt: new Date().toISOString() });
        continue;
      }
      try { results.push({ ...round(testPair(a, b, prices.get(a), prices.get(b), strategy)), strategyName: strategy.name, strategyFingerprint, reused: false, checkedAt: new Date().toISOString() }); }
      catch (error) { results.push({ pair, leftTicker: a, rightTicker: b, strategyName: strategy.name, error: error.message, profitable: false, strategyFingerprint, reused: false, checkedAt: new Date().toISOString() }); }
    }
  }
  results.sort((a, b) => (b.totalReturn ?? -Infinity) - (a.totalReturn ?? -Infinity));
  const output = { generatedAt: new Date().toISOString(), strategies, results };
  await fs.writeFile(CACHE_PATH, JSON.stringify(output, null, 2));
  const columns = ['pair', 'strategyName', 'profitable', 'totalReturn', 'maxDrawdown', 'sharpe', 'trades', 'observations', 'testedFrom', 'testedTo', 'reused', 'error'];
  await fs.writeFile(CSV_PATH, [columns.join(','), ...results.map(row => columns.map(col => escapeCsv(row[col])).join(','))].join('\n'));
  console.table(results.filter(row => row.profitable).map(row => ({ pair: row.pair, strategy: row.strategyName, returnPct: `${(row.totalReturn * 100).toFixed(1)}%`, maxDrawdownPct: `${(row.maxDrawdown * 100).toFixed(1)}%`, sharpe: row.sharpe, trades: row.trades })));
  console.log(`Saved ${results.length} pair-strategy tests. ${results.filter(x => x.profitable).length} met the profitability rule.`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
