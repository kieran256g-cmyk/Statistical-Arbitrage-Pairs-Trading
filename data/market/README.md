# Real historical market snapshots

The CSV/JSON files in this directory contain downloaded Yahoo Finance adjusted
daily closes and their provenance. They are real observations, not generated
example prices. Each CSV has `date,price_a,price_b`; its JSON identifies A and B,
source URLs, requested and actual dates, retrieval time and a file checksum.
The loader checks the checksum before a named backtest. Use `--input` for your own CSV.

Download: `python scripts/import_market_data.py`. Single choice:
`python run.py --pair coke-pepsi --refresh`. Internet is only needed for refresh.
The provider can revise history. Reports record a normalized input checksum for
reproducibility; keep the snapshot alongside results you want to reproduce.

## Adjustment and alignment

The downloader uses the provider's `adjclose` series, never a silent fallback to
unadjusted closes. Yahoo describes adjusted close as adjusted for splits and
dividend/capital-gain distributions ([source](https://finance.yahoo.com/quote/WDC/history/)).
The cash ledger therefore represents trading in adjusted-price units: a convenient
total-return approximation, not exact real share counts or broker statements.
Cash dividends, short dividend payments and corporate actions are not separately
simulated. Check provider handling of restructurings/spinoffs before interpreting
returns across those dates, particularly for Western Digital.

Missing observations are dropped. Pair dates are the intersection of both series;
basket dates intersect all three. No forward filling is performed. All requested
symbols must report USD and their expected ticker. Today's UTC date is excluded
to avoid using an unfinished US session. Each snapshot shows its actual last date.
No automatic pair suitability, correlation or cointegration test is implied.

## Three-stock basket

For the first common date t0, define fixed coefficients:

```
c_NVDA = 50 / NVDA_adjusted_close(t0)
c_MU   = 50 / MU_adjusted_close(t0)
B(t)   = c_NVDA * NVDA_adjusted_close(t) + c_MU * MU_adjusted_close(t)
A(t)   = DELL_adjusted_close(t)
```

The normal log(A/B) algorithm trades Dell against this buy-and-hold basket. Both
basket constituents have the same direction. One basket unit contains c_NVDA and
c_MU adjusted shares; multiply by signed `shares_b` to get constituent exposure.
With the same proportional transaction and borrow rates for both constituents,
the basket cash flows and costs equal the sum of the two constituent legs.
Weights start 50/50 and subsequently drift. Signals still execute next close.
There is no fitted hedge ratio and no three-variable cointegration model.
Coefficients are stored in the JSON; refreshing the dataset can revise them if
the provider changes its historical adjustment factors.
