# Add and change your own strategies

Run the program with `python run.py --choose`, then choose your strategy from the
menu. The same strategy works with a two-company pair or either side containing
multiple companies. Run `run.py`, not the strategy file itself.

## Quick start

1. Copy `_template.py` to `my_strategy.py` in this folder.
2. Edit `entry_side` and `exit_reason` in your copy to change the trading rules.
3. Optionally copy `mean_reversion.json` to `my_strategy.json` and change settings.
4. Run again. `my_strategy` appears automatically in the strategy menu.

Use a filename made of letters, digits and underscores, beginning with a letter.
Files beginning with `_` are hidden from the menu. Each run loads the current
file contents; no registry change or installation is needed. A strategy is Python
code executed locally with your permissions, so only use files you trust.

## Settings versus logic

- `config.json`: shared capital, costs, risk limits and default signal settings.
- `strategies/<name>.json`: the editable parameters for that strategy.
- `--config path.json`: explicitly replaces both layers for a run (unspecified
  fields take the Config class defaults). Reports record the effective settings.
- `strategies/<name>.py`: signal calculation, entry direction and exit rules.

The top-level JSON keys use the Python runner names, such as `entry_z` and
`exit_z`. The nested `screener` block uses the batch screener names, such as
`entryZ`, `formationDays` and `scoreField`.

Strategy settings do not include idle-cash interest, ISA or short-term bond
returns, index benchmarks, ETF mechanics, or margin financing. Those are outside
the simplified return model; see [limitations](../LIMITATIONS.md).

## Three functions

`signal(history, config)` receives an immutable tuple of Bars from the first
observation through today's close, never future observations. Each Bar has
`date`, `price_a`, `price_b`; basket prices represent the two selected sides.
Return `pairs_trading.signals.Signal(spread, zscore)` with finite numbers or
`zscore=None` during warm-up. The second field can carry your own scalar score;
the CSV column is still called `zscore`. The engine enforces `lookback` warm-up.

`entry_side(z, config)` returns `1` to buy A / short B, `-1` to short A / buy B,
or `0` to stay flat. It is called only while flat and outside the warm-up.

`exit_reason(z, side, next_holding_bars, net_unrealized, entry_gross, config)`
returns a nonempty text reason to close or `None` to hold. The engine always
enforces configured loss and maximum-holding limits, plus final liquidation.
Stops still fill at the next close and can overshoot. No same-bar fills are added.

Hooks run chronologically. Keep them deterministic; do not read external future
data or retain state across different runs. Each CLI run reloads the strategy.
The strategy source checksum and effective settings are saved with the report.

## Included examples

- `mean_reversion`: fades large deviations in the rolling log ratio.
- `momentum`: follows those deviations, exiting as they fade or hit limits.

These are editable examples, not optimized or validated profitable strategies.
This interface controls signals and rules; the execution model remains a
two-sided, equal-notional long/short trade with fixed holdings until exit.
It does not provide arbitrary independent orders or per-stock weights.

## Screener settings

The batch screener uses the matching `<name>.json` file in this folder.
Edit the `screener` block there to change training windows, thresholds, costs
and scoring:

- `scoreField`: which score to trade, such as `z`, `distanceZ` or `factorZ`.
- `highScoreSide`: what to do when the score is high. `-1` shorts the left side
  and buys the right side; `1` buys the left side and shorts the right side.

Reference the strategy filename without `.py` or `.json` in `pairs.config.json`.
