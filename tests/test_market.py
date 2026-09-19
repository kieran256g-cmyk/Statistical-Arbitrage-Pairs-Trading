from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pairs_trading.cli import main
from pairs_trading.market import PAIRS, align_prices, choose_pair, load_pair, parse_history, refresh_pairs


class MarketTests(unittest.TestCase):
    def test_alignment_intersects_without_filling(self):
        a, b, c = date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)
        bars = align_prices({a: 10, b: 20}, {b: 30, c: 40})
        self.assertEqual([(x.date, x.price_a, x.price_b) for x in bars], [(b, 20, 30)])

    def test_provider_adjusted_series_and_missing_dates(self):
        stamps = [int(datetime(2024, 1, d, tzinfo=timezone.utc).timestamp()) for d in (1, 2, 3)]
        payload = {"chart": {"result": [{"meta": {"symbol": "DELL", "currency": "USD"},
                    "timestamp": stamps, "indicators": {"adjclose": [{"adjclose": [10, None, 30]}],
                                                          "quote": [{"close": [100, 200, 300]}]}}]}}
        start, end = date(2024, 1, 1), date(2024, 1, 3)
        self.assertEqual(parse_history(payload, "DELL", start, end), {start: 10})
        with self.assertRaises(ValueError):
            parse_history(payload, "MU", start, end)
        payload["chart"]["result"][0]["indicators"].pop("adjclose")
        with self.assertRaises(ValueError):
            parse_history(payload, "DELL", start, end)

    def test_basket_coefficients_reproduce_constituent_pnl(self):
        days = [date(2024, 1, 1) + timedelta(days=i) for i in range(70)]
        histories = {"DELL": dict(zip(days, [100+i for i in range(70)])),
                     "NVDA": dict(zip(days, [50+2*i for i in range(70)])),
                     "MU": dict(zip(days, [25+i for i in range(70)]))}
        def fake(symbol, start, end):
            return histories[symbol], "https://example.invalid/" + symbol
        with tempfile.TemporaryDirectory() as directory, patch("pairs_trading.market.fetch_history", side_effect=fake), redirect_stdout(io.StringIO()):
            folder = Path(directory)
            refresh_pairs(folder, ["dell-nvidia-micron"], days[0], days[-1]+timedelta(days=1))
            bars, meta = load_pair(folder, "dell-nvidia-micron")
            coefficients = meta["basket_shares_per_unit"]
            self.assertEqual(coefficients, {"NVDA": 1.0, "MU": 2.0})
            self.assertEqual(bars[0].price_b, 100)
            for quantity in (3, -3):
                change = quantity * (bars[-1].price_b-bars[0].price_b)
                constituents = sum(quantity*c*(histories[s][days[-1]]-histories[s][days[0]]) for s, c in coefficients.items())
                self.assertAlmostEqual(change, constituents)
            path = folder / "dell-nvidia-micron.csv"
            path.write_text(path.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "metadata"):
                load_pair(folder, "dell-nvidia-micron")

    def test_download_failure_preserves_cache(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            path = Path(directory) / "coke-pepsi.csv"
            path.write_text("original")
            with patch("pairs_trading.market.fetch_history", side_effect=ValueError("unavailable")):
                with self.assertRaises(ValueError):
                    refresh_pairs(Path(directory), ["coke-pepsi"])
            self.assertEqual(path.read_text(), "original")

    def test_menu_validates_selection(self):
        with patch("builtins.input", side_effect=["bad", "99", "4"]), redirect_stdout(io.StringIO()):
            self.assertEqual(choose_pair(), "dell-nvidia-micron")

    def test_every_bundled_choice_runs_and_reports_real_data(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            for key in PAIRS:
                with self.subTest(pair=key):
                    output = Path(directory) / key
                    self.assertEqual(main(["--pair", key, "--output", str(output)]), 0)
                    summary = json.loads((output / "summary.json").read_text())
                    self.assertFalse(summary["synthetic_data"])
                    self.assertEqual(summary["pair"], key)
                    self.assertGreater(summary["rows"], 63)
                    html = (output / "report.html").read_text(encoding="utf-8")
                    self.assertIn(PAIRS[key][2], html)
                    if key == "dell-nvidia-micron":
                        import csv
                        with (output / "trades.csv").open(newline="") as handle:
                            trades = list(csv.DictReader(handle))
                        self.assertTrue(trades)
                        for trade in trades:
                            for symbol, coefficient in summary["basket_shares_per_unit"].items():
                                self.assertAlmostEqual(float(trade[f"shares_{symbol}"]), float(trade["shares_b"])*coefficient)


if __name__ == "__main__":
    unittest.main()
