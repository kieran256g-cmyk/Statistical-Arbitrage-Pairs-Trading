from contextlib import redirect_stdout
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pairs_trading.cli import main
from pairs_trading.data import make_demo, write_prices, load_prices


class ReportTests(unittest.TestCase):
    def test_sample_file_matches_generator(self):
        self.assertEqual(load_prices(ROOT / "data" / "sample_prices.csv"), make_demo())

    def test_cli_writes_reproducible_report_and_labels_synthetic_data(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results"
            with redirect_stdout(io.StringIO()):
                status = main(["--output", str(output)])
            self.assertEqual(status, 0)
            self.assertEqual({p.name for p in output.iterdir()}, {"equity.csv", "trades.csv", "summary.json", "report.html"})
            summary = json.loads((output / "summary.json").read_text())
            self.assertTrue(summary["synthetic_data"])
            self.assertEqual(summary["rows"], 400)
            self.assertGreater(summary["closed_trades"], 0)
            html = (output / "report.html").read_text(encoding="utf-8")
            self.assertIn("SYNTHETIC DEMO", html)
            self.assertIn("<svg", html)
            HTMLParser().feed(html)
            before = (output / "summary.json").read_bytes()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--output", str(output)]), 0)
            self.assertEqual((output / "summary.json").read_bytes(), before)

    def test_supplied_csv_and_zero_trade_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            from dataclasses import replace
            bars = [replace(bar, price_a=100.0, price_b=100.0) for bar in make_demo(80)]
            write_prices(path, bars)
            output = Path(directory) / "report"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--input", str(path), "--output", str(output)]), 0)
            summary = json.loads((output / "summary.json").read_text())
            self.assertFalse(summary["synthetic_data"])
            self.assertEqual(summary["closed_trades"], 0)
            self.assertIsNone(summary["win_rate"])
            self.assertIn("No trades met", (output / "report.html").read_text())

    def test_cli_reports_input_error_with_failure_exit(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as log:
            self.assertEqual(main(["--input", str(Path(directory)/"missing.csv")]), 1)
            self.assertIn("Error:", log.getvalue())


if __name__ == "__main__":
    unittest.main()
