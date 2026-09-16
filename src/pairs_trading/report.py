"""Portable CSV, JSON, and offline HTML output using only the standard library."""
import csv
from html import escape
import json
from pathlib import Path

from .backtest import Result


TRADE_FIELDS = ["entry_signal_date", "entry_date", "exit_signal_date", "exit_date", "side",
                "shares_a", "shares_b", "entry_price_a", "entry_price_b", "exit_price_a",
                "exit_price_b", "holding_bars", "entry_gross", "gross_pnl", "transaction_cost",
                "borrow_cost", "net_pnl", "exit_reason"]


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def equity_chart(result: Result) -> str:
    values = [row["equity"] for row in result.curve]
    low, high = min(values), max(values)
    pad = max((high-low)*0.1, high*0.001)
    low -= pad
    high += pad
    points = " ".join(f"{65+i/(len(values)-1)*850:.2f},{230-(value-low)/(high-low)*200:.2f}"
                      for i, value in enumerate(values))
    return f'''<svg viewBox="0 0 950 275" role="img" aria-label="Portfolio equity over the backtest">
      <line x1="65" y1="230" x2="915" y2="230" stroke="#d7dfeb"/>
      <line x1="65" y1="30" x2="915" y2="30" stroke="#e8edf4"/>
      <text x="5" y="35">{high:,.0f}</text><text x="5" y="235">{low:,.0f}</text>
      <polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="2.5"/>
      <text x="65" y="263">{result.curve[0]['date']}</text>
      <text x="915" y="263" text-anchor="end">{result.curve[-1]['date']}</text>
    </svg>'''


def write_report(result: Result, output: Path, metadata: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    summary = {**result.summary, **metadata}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    write_csv(output / "equity.csv", result.curve, list(result.curve[0]))
    write_csv(output / "trades.csv", result.trades, TRADE_FIELDS)
    sharpe = summary["annualized_sharpe_252_zero_risk_free"]
    sharpe_text = "N/A" if sharpe is None else f"{sharpe:.2f}"
    cards = [("Ending equity", f"{summary['ending_equity']:,.2f}"),
             ("Total return", f"{summary['total_return']:.2%}"),
             ("Max drawdown", f"{summary['max_drawdown']:.2%}"),
             ("Closed trades", str(summary['closed_trades']))]
    card_html = "".join(f'<div class="card"><span>{label}</span><strong>{value}</strong></div>' for label, value in cards)
    table_rows = "".join(
        f"<tr><td>{t['entry_date']}</td><td>{t['exit_date']}</td><td>{escape(t['side'])}</td>"
        f"<td>{t['net_pnl']:,.2f}</td><td>{escape(t['exit_reason'])}</td></tr>" for t in result.trades)
    if not table_rows:
        table_rows = '<tr><td colspan="5">No trades met the configured rules.</td></tr>'
    banner = ("SYNTHETIC DEMO · These invented prices demonstrate the code, not market performance."
              if metadata["synthetic_data"] else "HISTORICAL SIMULATION · Results depend on the supplied data and execution assumptions.")
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pairs trading backtest</title><style>
body{{margin:0;background:#f3f6fa;color:#142238;font:16px system-ui,sans-serif}}main{{max-width:1050px;margin:40px auto;padding:0 24px}}
h1{{font-size:36px;margin:8px 0}}h2{{font-size:21px}}p{{line-height:1.6}}.eyebrow{{letter-spacing:.13em;font-size:12px;color:#45617d}}
.banner{{background:#fff3d6;border-left:4px solid #d28b00;padding:15px;margin:24px 0}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.card,section{{background:white;border:1px solid #e1e7f0;border-radius:10px;padding:20px}}.card span{{display:block;color:#52637a;font-size:14px}}
.card strong{{display:block;font-size:25px;margin-top:8px}}section{{margin-top:20px}}svg{{width:100%;font:12px system-ui;fill:#52637a}}
table{{width:100%;border-collapse:collapse;text-align:left;font-size:14px}}td,th{{border-bottom:1px solid #e5eaf1;padding:10px 8px}}.scroll{{overflow:auto}}
.muted{{color:#52637a;font-size:14px}}a{{color:#1d4ed8}}@media(max-width:650px){{.cards{{grid-template-columns:repeat(2,1fr)}}h1{{font-size:28px}}}}
</style></head><body><main><div class="eyebrow">RESEARCH TEMPLATE / PAIRS TRADING</div>
<h1>Mean-reversion backtest</h1><p>{summary['start']} to {summary['end']} · Long/short pair · Next-close fills</p>
<div class="banner">{banner}</div><div class="cards">{card_html}</div>
<section><h2>Portfolio equity</h2>{equity_chart(result)}
<p class="muted">Includes modelled transaction and borrow costs. Equity is in the same currency as the input prices.
Sharpe (252 sessions, zero risk-free rate): {sharpe_text}. Warm-up sessions are included.</p></section>
<section><h2>Closed trades</h2><div class="scroll"><table><thead><tr><th>Entry</th><th>Exit</th><th>Position</th><th>Net P&amp;L</th><th>Exit reason</th></tr></thead>
<tbody>{table_rows}</tbody></table></div></section>
<section><h2>Assumptions</h2><p>Signals use the log-price ratio and the preceding rolling window. Orders fill at the following close.
Shares stay fixed until exit. Dollar exposure is matched at entry and can drift afterwards. The final position is liquidated at the last close.</p>
<p class="muted">No cointegration or pair-selection test, live orders, financing interest, dividends, margin calls, borrow availability, or liquidity model.
Statistical arbitrage can lose money. A delayed stop can fill beyond its threshold.</p>
<p><a href="summary.json">Configuration and metrics</a> · <a href="equity.csv">Daily ledger</a> · <a href="trades.csv">Trade log</a></p>
<p class="muted">Data source: {escape(str(metadata['source']))}</p></section></main></body></html>'''
    (output / "report.html").write_text(document, encoding="utf-8")
