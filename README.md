# Statistical Arbitrage: Pairs and Baskets

Choose companies from editable groups, build a two-company pair or a larger
two-sided basket, and switch between your own trading strategies. Includes real
historical prices, next-close execution, trading costs and offline HTML reports.
Python 3.10+, no external packages or API keys required. This is a research
backtest, with no broker connection or live orders.

## Start here

Download or pull the latest repository, open its folder, then run:

```powershell
python run.py --choose
```

The menu asks you to:

1. Choose a company group.
2. Select two or more companies by number, separated by commas.
3. Choose which selected companies belong on side A; the rest become side B.
4. Choose a strategy.

For example, select Dell, Micron and NVIDIA; put Dell on side A and leave the
other two on side B. Or select only Coke and Pepsi for a normal pair.
Storage has four companies, so you can also choose two versus two.

Run **run.py**, not a strategy file directly. In VS Code with its Python debugger,
F5 uses the included "Choose companies and strategy" launch configuration, even
when you are editing a strategy file. In a noninteractive terminal, running with
no selection defaults to Dell versus NVIDIA and mean reversion.

The terminal prints the report path. Outputs go under
**results/<selection>/<strategy>/report.html**, alongside the trade log, daily
ledger and summary. Different selections and strategies get separate folders.
Rerunning the same selection replaces its reports; use `--output` to preserve
separate experiments.

## Company groups

| Group | Available companies |
| --- | --- |
| `technology` | Dell (DELL), Micron (MU), NVIDIA (NVDA) |
| `drinks` | Coca-Cola (KO), PepsiCo (PEP), Keurig Dr Pepper (KDP) |
| `storage` | Seagate (STX), Western Digital (WDC), Sandisk (SNDK), Micron (MU) |
| `payments` | Visa (V), Mastercard (MA), PayPal (PYPL) |
| `energy` | ExxonMobil (XOM), Chevron (CVX), ConocoPhillips (COP) |

These are convenience groups, not a claim that their business models are
identical or their prices form profitable trading relationships. PayPal is a
payments platform; ConocoPhillips is an exploration and production company.

Edit **[company_groups.json](company_groups.json)** to add companies or groups.
Use USD-listed Yahoo Finance tickers. Then download the updated histories:

```powershell
python scripts/import_company_data.py
```

Or refresh only the companies selected in the menu:

```powershell
python run.py --choose --refresh
```

Cached real data works offline. Downloads start in January 2023, or the first
available date for newer listings, and exclude today's potentially incomplete
session. Only dates shared by every selected company are used. Sandisk's newer
listing means baskets containing it have shorter histories. The actual date
range, download times, source URLs and checksums are recorded in the output.
See [data details](data/symbols/README.md).

## Change settings or add your own strategy

Two editable examples are included:

- **mean_reversion**: buy the relatively cheaper side and short the dearer side,
  expecting the price relationship to return toward its average.
- **momentum**: follow a large relative-price deviation and exit when it fades.

To add your own:

1. Copy **[strategies/_template.py](strategies/_template.py)** to
   `strategies/my_strategy.py`.
2. Change the entry and exit rules in your copy.
3. Optionally copy `strategies/mean_reversion.json` to
   `strategies/my_strategy.json` and change its thresholds.
4. Run again; **my_strategy** automatically appears in the menu.

Read [the strategy guide](strategies/README.md) for the three simple functions,
signal calculations and parameter overrides. Strategies receive only history
through the current day, while the engine keeps next-close execution, costs,
holding limits and loss limits consistent.

| File | What to edit |
| --- | --- |
| `company_groups.json` | Company lists and group names |
| `strategies/<name>.py` | Your signal, entry and exit logic |
| `strategies/<name>.json` | That strategy's settings |
| `config.json` | Shared defaults for capital, costs and risk limits |
| `src/pairs_trading/backtest.py` | Execution/accounting model, for advanced changes |

Strategy JSON settings override matching fields in `config.json`.
An explicit `--config file.json` takes precedence over both; omitted fields in
that explicit file use the built-in defaults. The report always records the
effective configuration and a checksum of the selected strategy source.

Common settings: `lookback`, `entry_z`, `exit_z`, `stop_z`,
`max_holding_bars`, `stop_loss_fraction`, `initial_capital`,
`gross_allocation`, `fee_bps`, `slippage_bps`, `annual_borrow_rate`.
The defaults are examples, not parameters selected for profitability.

## Run directly without the menu

```powershell
python run.py --group drinks --left KO --right PEP,KDP --strategy mean_reversion
python run.py --group storage --left STX,WDC --right SNDK,MU --strategy momentum
python run.py --group technology --left DELL --right NVDA --strategy my_strategy
python run.py --list-groups
python run.py --list-strategies
```

The selected companies must come from the same group, with at least one on
each side and no duplicates. Each side starts with equal dollar amounts per
company on the first shared date. Its adjusted-share coefficients stay fixed,
so weights drift. Each trade starts with equal total dollars on A and B.
This is one basket-versus-basket trade, not all possible independent pair trades.
The CSVs show the signed holdings of every constituent.

## Data and execution assumptions

Real data uses Yahoo Finance adjusted closes, including split/distribution
adjustments. It is a total-return proxy in adjusted-share units, not exact
executable historical prices or a reconstruction of cash dividends. Histories
can be revised by the provider. Missing dates are never forward filled and
download failures never fall back to invented data.

Signals execute at the following close. Shares stay fixed until exit. Costs
include proportional fees/slippage and short borrowing; stops can overshoot
because they also execute at the next close. The engine enforces loss and
maximum holding limits for custom strategies and liquidates at the final close.
There is no automatic cointegration test, fitted basket weight model or live
order execution. See [methodology](docs/methodology.md).

## Existing presets and custom CSVs

Older commands still work, including:

```powershell
python run.py --pair coke-pepsi
python run.py --pair dell-nvidia-micron
python run.py --list-pairs
python run.py --input data/my_pair.csv --strategy mean_reversion
python run.py --demo
```

Custom CSVs require `date,price_a,price_b`, positive finite prices, unique
ascending ISO dates and at least `lookback + 3` rows. The `--demo` data is
explicitly synthetic. Legacy preset snapshots in `data/market/` are separate
from the flexible company histories in `data/symbols/`; `--pair ... --refresh`
updates a legacy preset, while `scripts/import_company_data.py` updates groups.

## Project layout

```text
run.py                         Start here
company_groups.json            Editable company groups
config.json                    Shared settings
strategies/                    Editable strategy files, settings and guide
src/pairs_trading/              Data, basket building, engine and reporting
data/symbols/                  Individual real company histories
data/market/                   Legacy preset snapshots
scripts/import_company_data.py Refresh all group companies
tests/                         Accounting, strategy, basket and input checks
results/                       Generated outputs, ignored by Git
```

Run the checks with:

```powershell
python -m unittest discover -s tests -v
```

## Batch multi-strategy screener

`pair_screener.mjs` tests every unique pair listed in
`pairs.config.json` against each named strategy in that file. Add a ticker to
automatically test its pairs with every existing ticker; add a strategy to test
it against every pair. Results are written to `outputs/pair-results.json` and
`outputs/pair-results.csv`.

Negative results are reused on later runs only when the named strategy’s
settings have not changed. Profitable results are retested. Use
`--refresh-negatives` to force all negatives to run again, or `--search MU` to
search saved results.

Each strategy has separate training and out-of-sample test windows. A pair must
pass the training residual mean-reversion threshold and hedge-ratio stability
threshold before its out-of-sample return can qualify. The backtest charges
costs for both legs on entry and exit and applies an annual short-borrow cost.

The included universe covers memory, storage, semiconductors, networking,
servers, hyperscalers, beverages, payments and energy. The screener downloads
up to ten years of daily history, trains on five years, then tests on a separate
two years. Daily price downloads are cached under `outputs/price-cache/`; use
`--refresh-prices` to replace that cache immediately.

By default, `screenMode` is `withinGroups`: only companies that share a named
group in `pairGroups` are compared. This prevents accidental matches such as a
chipmaker against a beverage company. A company may belong to more than one
group, and the results record every shared relationship. Set `screenMode` to
`all` only when deliberately exploring every possible combination.

```powershell
& 'C:\Users\green\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' .\pair_screener.mjs
```
