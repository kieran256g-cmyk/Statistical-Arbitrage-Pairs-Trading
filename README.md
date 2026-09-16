# Statistical Arbitrage: Pairs Trading

A small Python template for researching a basic two-asset mean-reversion strategy.
It includes a configurable algorithm, a cash-and-share backtest, synthetic sample
data, an offline HTML report, CSV trade logs, and accounting tests.

**The bundled data is invented. Demo returns are not market performance.**
This is a research backtest, with no broker connection or live-order execution.

## Run the example

Install Python 3.10 or newer, download or clone the repository, then open its
folder in VS Code. No external Python packages or API keys are required.

In the terminal, run:

```powershell
python run.py
```

On Windows, `py run.py` also works if the Python launcher is installed.
Open **results/report.html** to see the equity curve and trades. The run also
writes `summary.json`, `equity.csv`, and `trades.csv` to that folder.
Running again with the same output directory replaces those four files.

## The basic algorithm

1. Calculate the spread as `log(price_a) - log(price_b)`.
2. Compare today's spread with the preceding 60 sessions' mean and sample
   standard deviation to get a z-score.
3. If z is at least +2 but below +4, short A and buy B. If z is at most -2 but
   above -4, buy A and short B.
4. Exit when the score returns toward zero, becomes extreme, reaches a loss
   threshold, or the holding period expires.

The two legs have equal currency notionals at entry. Shares stay fixed while
the trade is open; equal exposure can drift afterwards. Orders signalled at
one close execute at the **following session's close**. A short borrow charge
and transaction-cost deductions are included.

This assumes a mean-reverting log ratio and does not automatically identify
suitable pairs or test cointegration. It is statistical trading with possible
losses, not a guaranteed arbitrage. See [the methodology](docs/methodology.md)
for timing, formulas, sources, and omitted market effects.

## Change the settings

Edit [config.json](config.json):

| Setting | Default | Meaning |
| --- | ---: | --- |
| `lookback` | 60 | Prior observations for the rolling z-score |
| `entry_z` | 2.0 | Minimum absolute z-score to open |
| `exit_z` | 0.5 | Exit band near the mean; crossing zero also exits |
| `stop_z` | 4.0 | Exit at an extreme score; do not open there |
| `max_holding_bars` | 20 | Maximum close-to-close holding intervals |
| `stop_loss_fraction` | 0.05 | Loss trigger as a fraction of entry gross notional |
| `initial_capital` | 10000 | Starting account value |
| `gross_allocation` | 1.0 | Total entry notional across both legs / equity |
| `fee_bps` | 1.0 | Fee per traded notional, per fill |
| `slippage_bps` | 2.0 | Slippage penalty per traded notional, per fill |
| `annual_borrow_rate` | 0.03 | Annual cost on short market value |

One basis point is 0.01%. The defaults are illustrative assumptions, not
parameters selected for profitability. Stop orders also wait until the next
close and can lose more than their threshold.

## Use your own pair

Prepare a CSV containing aligned daily closes for two assets, in the same
currency, ordered from oldest to newest:

```csv
date,price_a,price_b
2024-01-02,100.00,80.00
2024-01-03,101.00,80.50
```

The format example above is intentionally short; the default configuration
needs at least 63 rows. Use a longer history for meaningful evaluation.

```powershell
python run.py --input data/my_pair.csv --config config.json --output results/my_pair
```

Missing, duplicate, out-of-order, nonpositive, and non-finite prices are rejected.
There is no automatic forward filling or pair selection. See [data guidance](data/README.md).

## Repository layout

```text
run.py                         Simple entry point
config.json                    Editable strategy assumptions
src/pairs_trading/
  data.py                      CSV validation and synthetic generator
  strategy.py                  Rolling signal and entry/exit rules
  backtest.py                  Execution timing and two-leg cash ledger
  report.py                    CSV, JSON, and offline HTML outputs
  cli.py                       Command-line interface
data/sample_prices.csv         Clearly synthetic example
scripts/generate_demo.py       Reproduce the example data
tests/test_backtest.py         Timing, cost, and accounting checks
docs/methodology.md            Model details and limits
results/                       Generated outputs, ignored by Git
```

## Tests and development

```powershell
python -m unittest discover -s tests -v
```

Tests check that future prices cannot change earlier results, fills occur on
the next close, both legs and costs reconcile, stops are delayed, and constant
ratios produce no trades. They also cover bad CSV/config input and final
liquidation. See [CONTRIBUTING.md](CONTRIBUTING.md) for extension points.

To regenerate the synthetic example:

```powershell
python scripts/generate_demo.py
```
