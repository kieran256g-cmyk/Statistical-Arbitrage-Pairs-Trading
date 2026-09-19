# Model and execution assumptions

## Signal

For positive daily closes A_t and B_t, define:

```text
spread_t = log(A_t) - log(B_t)
mean_t   = mean(spread[t-lookback : t])
std_t    = sample standard deviation(spread[t-lookback : t])
z_t      = (spread_t - mean_t) / std_t
```

The rolling window excludes the current observation. No future values are
used. Before the warm-up completes, or when standard deviation is at most
1e-12, the signal is unavailable. An unavailable signal cannot open a position
and queues an exit if a position is already open.

This is a fixed log-ratio model, not an estimated hedge-ratio or cointegration
model. A separate formation period and out-of-sample pair selection are needed
before using real pairs to investigate performance. The code does not test
whether the spread is stationary or select assets from a universe.

## Order of events

For every supplied close:

1. Charge borrow costs for the position held since the preceding close.
2. Execute the preceding close's queued order at today's prices.
3. Mark both legs to today's close and update equity.
4. Use today's z-score and portfolio state to queue tomorrow's order.

Thus a signal on date t cannot earn the price move from t to t+1: its position
starts at the t+1 close. After an exit, new entry decisions resume at the next
session's close; the model does not immediately reverse at the exit close.

At the final data row, outstanding entry orders are cancelled and open positions
are closed. This terminal liquidation is a reporting convention, labelled
`end_of_data`, with an empty exit signal date. Other exits have a preceding
signal date. All trades in the final report are closed.

## Position and cash accounting

At entry, let gross = current equity * gross_allocation. Each leg gets half that
notional. A long spread holds gross/(2*A) shares of A and -gross/(2*B) shares of B;
a short spread reverses both signs. Fractional shares are allowed.

Entry and exit cash flows use those share quantities and the observed fill
prices. Equity = cash + shares_A*A + shares_B*B. Shares are fixed between entry
and exit. Matching entry notionals is dollar neutrality at entry only; it does
not guarantee beta neutrality or equal notionals later.

Transaction costs are `(fee_bps + slippage_bps)/10000 * traded_notional` at each
fill, summing absolute notional across both legs. Slippage is represented as a
cash penalty, not a change in displayed execution prices.

Short borrow cost uses the preceding close's short market value times
`annual_borrow_rate * elapsed_calendar_days / 365`. Both transaction and borrow
costs reduce equity and each trade's reported net profit. Short-sale proceeds
are accounted for in cash but cannot finance a second concurrent pair trade.

## Exits

In priority order: net loss trigger, unavailable signal, extreme absolute
z-score, mean reversion (including crossing zero), and holding-time limit.
The loss trigger compares unrealized price P&L less entry costs and accrued
borrow with `-stop_loss_fraction * entry_gross`. Exit costs are not known yet.
Stops are decisions at a close, executed at the next close. They cannot cap
the realized loss. The holding limit counts actual close-to-close intervals.

The backtest aborts if marked equity becomes nonpositive or non-finite. It does
not simulate broker liquidation after insolvency.

## Metrics

- Total return: ending equity / starting equity - 1, net of modelled costs.
- Maximum drawdown: minimum of equity / running equity peak - 1; reported as a
  nonpositive fraction.
- Sharpe: mean daily equity return / sample standard deviation * sqrt(252),
  assuming daily sessions and zero risk-free rate. All supplied sessions,
  including warm-up and flat periods, are included. Null when variance is zero.
- Win rate: fraction of closed trades whose net P&L is positive; null if none.

`summary.json` includes the complete configuration and a SHA-256 hash of the
normalized input rows so runs can be compared reproducibly. `equity.csv` exposes
each close's cash, holdings, costs, action, and queued next order.

## Limits

Named market choices use Yahoo Finance adjusted closes. This makes the ledger a
total-return proxy in adjusted-share units, not a reconstruction of actual cash
dividend flows or real share counts. The three-stock choice uses Dell versus a
fixed-coefficient NVIDIA/Micron basket. See [market data and basket construction](../data/market/README.md).

This template omits dividends, cash/financing interest, margin requirements,
short availability and recalls, price impact, minimum lots, exchange calendars,
and intraday stop execution. Costs are constant assumptions, not venue quotes.
Both legs are assumed fillable simultaneously at the supplied next closes.
Do not interpret synthetic performance as evidence of a profitable strategy.
For real experiments, use point-in-time inputs, hold-out periods, sensitivity
checks, and realistic market-specific execution assumptions.

## Background

The mean-reversion entry/exit idea is described in QuantConnect's
[Pairs Trading With Stocks](https://www.quantconnect.com/research/15300/pairs-trading-with-stocks/p1).
That example uses a formation and pair-selection procedure; this template
instead accepts an already-selected pair and uses a rolling log ratio.

Gatev, Goetzmann, and Rouwenhorst's
[Pairs Trading: Performance of a Relative Value Arbitrage Rule](https://www.nber.org/papers/w7032)
is a research reference for the broader strategy family. This template is a
small educational implementation, not a reproduction of that paper's results.
