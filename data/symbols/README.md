# Individual company histories

These real Yahoo Finance adjusted daily closes are used to construct arbitrary
selections from `company_groups.json`. Refresh with
`python scripts/import_company_data.py`, or use `--refresh` on a selected run.
Each CSV has a JSON provenance file with URL, timestamp and checksum. Histories
are never silently replaced by synthetic prices.

Only dates shared by every selected company are used. New listings therefore
shorten a combined backtest. Sandisk's current independent listing started in
2025 ([company announcement](https://www.sandisk.com/company/newsroom/press-releases/2025/sandisk-celebrates-nasdaq-listing-after-completing-separation));
the downloader can include provider-supplied when-issued observations before the
regular-way listing. Always inspect the actual reported date range.

Each side is normalized to 100 on the first shared date, equally divided in
dollars across its companies. Its adjusted-share coefficients are then fixed.
At trade entry, side A and side B have equal total dollar notionals, but company
weights within a side can have drifted. No daily rebalancing is performed.
The reports expose each constituent's signed adjusted-share holdings.

Adjusted prices approximate total returns; they are not executable historical
quotes. Corporate actions and cash dividends are not separately booked. Fees and
borrow rates are shared across all constituents. Sector groups are convenience
lists, not claims of identical businesses or statistical suitability. PayPal is a
payments platform rather than the same type of card network as Visa/Mastercard;
ConocoPhillips focuses on production rather than an integrated oil business.

Other company references: [Keurig Dr Pepper](https://www.keurigdrpepper.com/keurig-dr-pepper-reports-q2-results-and-reaffirms-guidance-for-2026/),
[ConocoPhillips](https://www.conocophillips.com/investor-relations/stock-information/).
