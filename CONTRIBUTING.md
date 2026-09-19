# Extending the template

Keep strategy decisions in `strategy.py`, execution/accounting in `backtest.py`,
and file validation in `data.py`. Add new settings to the validated `Config`
dataclass and document units and defaults.

Before changing results, add a small deterministic example with a hand-calculated
answer. Keep the no-lookahead and P&L reconciliation tests passing:

```text
python -m unittest discover -s tests -v
```

Possible extensions include a formation-period cointegration test, estimated
hedge ratios, walk-forward evaluation, more detailed transaction costs, and a
multi-pair portfolio. Pair selection and parameter tuning must use training
observations only. Keep live brokerage integration separate from this research
backtest and do not commit credentials or licensed market datasets.
