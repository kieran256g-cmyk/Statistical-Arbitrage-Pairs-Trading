from dataclasses import replace
from datetime import date, timedelta
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pairs_trading.backtest import backtest
from pairs_trading.config import Config, load_config
from pairs_trading.data import Bar, load_prices, make_demo
from pairs_trading.strategy import Signal, signals, entry_side, exit_reason


def price_bars(prices):
    return [Bar(date(2020, 1, 1)+timedelta(days=i), price, 100.0) for i, price in enumerate(prices)]


def controlled_run(prices, zs, **kwargs):
    config = Config(lookback=2, fee_bps=0, slippage_bps=0, annual_borrow_rate=0, **kwargs)
    with patch("pairs_trading.backtest.signals", return_value=[Signal(0.0, z) for z in zs]):
        return backtest(price_bars(prices), config)


class SignalTests(unittest.TestCase):
    def test_rolling_window_excludes_current_and_future(self):
        bars = [Bar(date(2020, 1, 1)+timedelta(days=i), math.exp(x), 1.0)
                for i, x in enumerate([0.0, 1.0, 2.0, 9.0, -2.0])]
        got = signals(bars, 3)
        self.assertIsNone(got[2].zscore)
        self.assertAlmostEqual(got[3].zscore, 8.0)  # mean(0,1,2)=1; sample sd=1.
        changed = bars[:4] + [replace(bars[4], price_a=100000.0)]
        self.assertEqual(got[:4], signals(changed, 3)[:4])

    def test_entry_directions_and_extreme_skip(self):
        cfg = Config()
        self.assertEqual(entry_side(2.5, cfg), -1)
        self.assertEqual(entry_side(-2.5, cfg), 1)
        for z in [None, 0.0, 4.0, -4.0]:
            self.assertEqual(entry_side(z, cfg), 0)

    def test_exit_rules_and_zero_crossings(self):
        cfg = Config()
        self.assertEqual(exit_reason(0.8, 1, 2, 0, 10000, cfg), "mean_reversion")
        self.assertEqual(exit_reason(-0.8, -1, 2, 0, 10000, cfg), "mean_reversion")
        self.assertEqual(exit_reason(-4.5, 1, 2, 0, 10000, cfg), "extreme_z")
        self.assertEqual(exit_reason(-2.5, 1, 20, 0, 10000, cfg), "time_exit")
        self.assertEqual(exit_reason(-2.5, 1, 2, -501, 10000, cfg), "loss_stop")
        self.assertEqual(exit_reason(None, 1, 2, 0, 10000, cfg), "unavailable_signal")


class AccountingTests(unittest.TestCase):
    def test_next_close_fills_no_profit_before_entry(self):
        result = controlled_run([100, 100, 100, 110, 120, 130, 130],
                                [None, None, -2.5, -1.0, -0.2, None, None])
        trade = result.trades[0]
        self.assertEqual(trade["entry_signal_date"], "2020-01-03")
        self.assertEqual(trade["entry_date"], "2020-01-04")
        self.assertEqual(trade["exit_date"], "2020-01-06")
        self.assertEqual(result.curve[2]["position"], 0)
        self.assertAlmostEqual(result.curve[3]["equity"], 10000)
        self.assertAlmostEqual(trade["net_pnl"], 5000/110*20)
        self.assertAlmostEqual(result.summary["ending_equity"], 10000+5000/110*20)

    def test_short_A_direction_earns_when_A_falls(self):
        result = controlled_run([100, 100, 100, 110, 100, 90, 90],
                                [None, None, 2.5, 1.0, 0.2, None, None])
        self.assertLess(result.trades[0]["shares_a"], 0)
        self.assertGreater(result.trades[0]["shares_b"], 0)
        self.assertAlmostEqual(result.trades[0]["net_pnl"], 5000/110*20)

    def test_costs_on_both_legs_and_borrow_across_calendar_gap(self):
        bars = price_bars([100, 100, 100, 110, 120, 130, 130])
        bars[4] = replace(bars[4], date=date(2020, 1, 7))
        bars[5] = replace(bars[5], date=date(2020, 1, 8))
        bars[6] = replace(bars[6], date=date(2020, 1, 9))
        cfg = Config(lookback=2, fee_bps=1, slippage_bps=2, annual_borrow_rate=0.03)
        with patch("pairs_trading.backtest.signals", return_value=[Signal(0, z) for z in [None, None, -2.5, -1, -0.2, None, None]]):
            result = backtest(bars, cfg)
        trade = result.trades[0]
        expected_cost = 10000*0.0003+(5000/110*130+5000)*0.0003
        expected_borrow = 5000*0.03*4/365
        expected_profit = 5000/110*20-expected_cost-expected_borrow
        self.assertAlmostEqual(trade["transaction_cost"], expected_cost)
        self.assertAlmostEqual(trade["borrow_cost"], expected_borrow)
        self.assertAlmostEqual(trade["net_pnl"], expected_profit)
        self.assertAlmostEqual(result.summary["ending_equity"], 10000+expected_profit)
        self.assertAlmostEqual(sum(r["daily_pnl"] for r in result.curve), expected_profit)

    def test_time_exit_holds_exactly_configured_intervals(self):
        result = controlled_run([100]*8, [None, None, -2.5, -2, -2, -2, -2, -2], max_holding_bars=2)
        self.assertEqual(result.trades[0]["holding_bars"], 2)
        self.assertEqual(result.trades[0]["exit_reason"], "time_exit")

    def test_loss_stop_is_delayed_and_can_overshoot(self):
        result = controlled_run([100, 100, 100, 100, 80, 70, 70], [None, None, -2.5, -2, -2, -2, -2])
        trade = result.trades[0]
        self.assertEqual(trade["exit_reason"], "loss_stop")
        self.assertEqual(trade["exit_price_a"], 70)
        self.assertAlmostEqual(trade["net_pnl"], -1500)

    def test_terminal_liquidation_and_final_bar_entry_cancellation(self):
        result = controlled_run([100]*6, [None, None, -2.5, -2, -2, -2])
        self.assertEqual(result.trades[0]["exit_reason"], "end_of_data")
        self.assertEqual(result.curve[-1]["position"], 0)
        last_signal = controlled_run([100]*6, [None, None, None, None, -2.5, -2])
        self.assertEqual(len(last_signal.trades), 0)
        self.assertEqual(last_signal.curve[-1]["action"], "entry_cancelled_end_of_data")

    def test_constant_ratio_produces_no_trades_and_no_nan_metrics(self):
        result = backtest(price_bars([100]*10), Config(lookback=3))
        self.assertEqual(result.trades, [])
        self.assertEqual(result.summary["total_return"], 0.0)
        self.assertEqual(result.summary["max_drawdown"], 0.0)
        self.assertIsNone(result.summary["annualized_sharpe_252_zero_risk_free"])
        self.assertIsNone(result.summary["win_rate"])

    def test_future_prices_cannot_change_prior_ledger(self):
        bars = make_demo()
        changed = bars[:200] + [replace(b, price_a=b.price_a*1.01) for b in bars[200:]]
        self.assertEqual(backtest(bars, Config()).curve[:200], backtest(changed, Config()).curve[:200])

    def test_demo_reconciles_cash_pnl_and_trade_costs(self):
        result = backtest(make_demo(), Config())
        self.assertGreater(len(result.trades), 0)
        self.assertAlmostEqual(result.summary["ending_equity"]-10000, sum(t["net_pnl"] for t in result.trades), places=7)
        self.assertAlmostEqual(result.summary["total_transaction_cost"], sum(t["transaction_cost"] for t in result.trades))
        self.assertAlmostEqual(result.summary["total_borrow_cost"], sum(t["borrow_cost"] for t in result.trades))
        self.assertAlmostEqual(result.curve[-1]["cash"], result.curve[-1]["equity"])


class InputTests(unittest.TestCase):
    def test_invalid_config(self):
        for kwargs in [{"lookback": 1}, {"entry_z": 0}, {"stop_z": 1}, {"gross_allocation": 2},
                       {"max_holding_bars": 0}, {"fee_bps": -1}, {"entry_z": float("nan")},
                       {"initial_capital": True}, {"lookback": 4.5}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Config(**kwargs)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"config.json"
            path.write_text('{"typo": 10}')
            with self.assertRaises(ValueError):
                load_config(path)

    def test_csv_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"prices.csv"
            for content in ["wrong,headers\n1,2\n", "date,price_a,price_b\n2020-01-01,nan,1\n",
                            "date,price_a,price_b\n2020-01-01,0,1\n",
                            "date,price_a,price_b\n2020-01-02,1,2\n2020-01-01,1,2\n",
                            "date,price_a,price_b\n2020-01-01,1,2\n2020-01-01,1,2\n"]:
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    load_prices(path)


if __name__ == "__main__":
    unittest.main()
