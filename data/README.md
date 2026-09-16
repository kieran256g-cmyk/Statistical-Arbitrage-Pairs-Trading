# Price inputs

The default run uses real company histories in [market/](market/README.md).
Run `python run.py` to choose a pair or the three-stock basket. The following
synthetic file is only used when explicitly selecting `--demo`.

`sample_prices.csv` contains 400 **synthetic** observations for invented assets A
and B. They are generated from a common random trend and an artificial
mean-reverting spread, with seed 7. Dates are weekdays starting 2020-01-02;
they are not an exchange calendar and do not represent real securities.

Regenerate with `python scripts/generate_demo.py`.

For your own data, supply `date,price_a,price_b` with ISO dates (YYYY-MM-DD),
positive finite prices, one row per aligned daily session, and strictly
increasing dates. Use the same currency and comparable closing times for both
assets. Clean missing observations upstream; the loader does not forward fill.

Handle splits consistently before loading. This simplified ledger does not
separately book dividends, so adjusted series and their economic interpretation
need care. Weekly or irregular observations also invalidate the default
252-session annualization assumption. Record the provider, adjustment policy,
download date, symbols, and formation/hold-out periods with real experiments.
