# Limitations and true-return gaps

This project is a simplified research backtest. It is useful for testing pair
rules in a consistent format, but it is not a full broker, tax, margin, or
portfolio-return simulator.

The code does not calculate a complete real-world return. In particular, it does
not model:

- Interest earned on idle cash while no pair trade is open.
- Cash ISA, savings account, money-market fund, Treasury bill, gilt, or
  short-term bond parking returns between trades.
- A benchmark index return for capital that could have been left in the market.
- ETF tracking difference, ETF fees, creation/redemption effects, securities
  lending income, or ETF tax treatment.
- Margin requirements, margin calls, margin interest, account-level leverage
  limits, or broker-specific buying-power rules.
- Taxes, stamp duty, withholding tax, or account wrapper effects.
- Dividend cash flows, short dividend payments, corporate-action cash, or
  exact historical share quantities.
- Borrow availability, borrow recalls, changing borrow fees, hard-to-borrow
  stocks, or locate failures.
- Market impact, order book depth, intraday stops, partial fills, minimum lots,
  currency conversion, or exchange-specific calendars.

The Python backtest only applies the explicit assumptions in `config.json`,
including proportional fees, slippage, and the simple annual short-borrow cost.
The screener uses each strategy's `screener` block for its own quick ranking
model. Treat all outputs as research estimates, not complete true-return
figures.

For more realistic work, compare the strategy against an investable benchmark,
track what idle capital would earn in the intended account type, model broker
margin rules separately, and rerun sensitivity checks over fees, borrow costs,
execution delays, and data sources.
