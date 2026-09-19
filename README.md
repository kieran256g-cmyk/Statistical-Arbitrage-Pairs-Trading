# Memory and storage pairs screener

Run the screener with the bundled Node runtime:

```powershell
& 'C:\Users\green\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' .\pair_screener.mjs
```

It tests every unique combination of the tickers in `pairs.config.json` with every strategy in its `strategies` list, using daily adjusted closing prices. Adding a ticker automatically adds every new pair; adding a named strategy automatically tests it against every pair. Each strategy uses a rolling hedge ratio and z-score, and includes its configured trading cost.

Results are saved in `outputs/pair-results.json` and `outputs/pair-results.csv`. A result is called profitable only when its backtest return is positive and it made at least three entries; it is not a recommendation or a live signal.

On later runs, negative results are reused only for the same named strategy with unchanged settings. Profitable pair-strategy results are retested. To retest all negative results, add `--refresh-negatives`. Changing a strategy’s settings automatically makes that strategy eligible for retesting, while leaving the other strategies’ caches intact.

Search stored results without downloading prices:

```powershell
& 'C:\Users\green\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' .\pair_screener.mjs --search MU
```
