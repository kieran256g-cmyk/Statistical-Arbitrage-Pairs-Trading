from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date, timedelta
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pairs_trading.backtest import backtest
from pairs_trading.cli import main
from pairs_trading.config import Config
from pairs_trading.data import make_demo
from pairs_trading.groups import build_baskets, choose_group, load_groups, load_selection, validate_selection
from pairs_trading.plugins import available_strategies, load_strategy, strategy_config
from pairs_trading.strategy import Signal


class CustomizationTests(unittest.TestCase):
    def test_two_sided_basket_pnl_equals_sum_of_four_constituents(self):
        days = [date(2024, 1, 1)+timedelta(days=i) for i in range(3)]
        histories = {"A": dict(zip(days, [10, 11, 14])), "B": dict(zip(days, [20, 19, 18])),
                     "C": dict(zip(days, [5, 7, 9])), "D": dict(zip(days, [100, 98, 95]))}
        bars, coefficients = build_baskets(histories, ["A", "B"], ["C", "D"])
        self.assertEqual((bars[0].price_a, bars[0].price_b), (100, 100))
        for direction in (1, -1):
            expected = sum(direction*2*c*(histories[s][days[-1]]-histories[s][days[0]]) for s, c in coefficients["A"].items())
            expected += sum(-direction*2*c*(histories[s][days[-1]]-histories[s][days[0]]) for s, c in coefficients["B"].items())
            self.assertAlmostEqual(direction*2*(bars[-1].price_a-bars[0].price_a)-direction*2*(bars[-1].price_b-bars[0].price_b), expected)

    def test_invalid_selections_and_menu(self):
        groups = load_groups(ROOT / "company_groups.json")
        for left, right in [([], ["MU"]), (["DELL"], ["DELL"]), (["DELL"], ["KO"])]:
            with self.assertRaises(ValueError):
                validate_selection(groups, "technology", left, right)
        with patch("builtins.input", side_effect=["1", "1,2,3", "1"]), redirect_stdout(io.StringIO()):
            self.assertEqual(choose_group(groups), ("technology", ["DELL"], ["MU", "NVDA"]))

    def test_copy_template_discovered_and_settings_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "my_rules.py").write_text((ROOT / "strategies" / "_template.py").read_text())
            (path / "_hidden.py").write_text("")
            (path / "my_rules.json").write_text('{"entry_z": 2.5}')
            self.assertEqual(available_strategies(path), ["my_rules"])
            config = strategy_config(path, "my_rules", Config())
            self.assertEqual(config.entry_z, 2.5)
            result = backtest(make_demo(), config, load_strategy(path, "my_rules"))
            self.assertGreater(len(result.trades), 0)
            (path / "bad.py").write_text("x = 1")
            with self.assertRaisesRegex(ValueError, "signal"):
                load_strategy(path, "bad")

    def test_strategy_prefix_causality_and_hooks_chronological(self):
        bars = make_demo(100)
        seen, entries = [], []
        def signal(history, config):
            seen.append(len(history))
            return Signal(0, 0)
        def entry(z, config):
            entries.append(seen[-1])
            return 0
        plugin = SimpleNamespace(signal=signal, entry_side=entry, exit_reason=lambda *args: None)
        before = backtest(bars, Config(lookback=2), plugin)
        self.assertEqual(seen, list(range(1, 101)))
        self.assertEqual(entries, list(range(3, 100)))
        actual = load_strategy(ROOT / "strategies", "mean_reversion")
        original = backtest(bars, Config(), actual)
        changed = bars[:80]+[replace(b, price_a=b.price_a*2) for b in bars[80:]]
        other = backtest(changed, Config(), load_strategy(ROOT / "strategies", "mean_reversion"))
        self.assertEqual(original.curve[:80], other.curve[:80])

    def test_bad_signal_or_side_fails_and_engine_enforces_holding_limit(self):
        bars = make_demo(20)
        plugin = SimpleNamespace(signal=lambda *args: Signal(0, 0), entry_side=lambda *args: 2, exit_reason=lambda *args: None)
        with self.assertRaisesRegex(ValueError, "entry"):
            backtest(bars, Config(lookback=2), plugin)
        plugin.entry_side = lambda *args: 1
        result = backtest(bars, Config(lookback=2, max_holding_bars=2), plugin)
        self.assertTrue(result.trades)
        self.assertTrue(all(t["holding_bars"] <= 2 for t in result.trades))
        plugin.signal = lambda *args: Signal(float("nan"), 0)
        with self.assertRaisesRegex(ValueError, "signal"):
            backtest(bars, Config(lookback=2), plugin)

    def test_all_groups_pairs_and_multi_company_choices_with_both_strategies(self):
        groups = load_groups(ROOT / "company_groups.json")
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            for group, spec in groups.items():
                symbols = list(spec["companies"])
                for selected in (symbols[:2], symbols):
                    for strategy in ("mean_reversion", "momentum"):
                        with self.subTest(group=group, companies=selected, strategy=strategy):
                            output = Path(directory) / f"{group}-{len(selected)}-{strategy}"
                            args = ["--group", group, "--left", selected[0], "--right", ",".join(selected[1:]), "--strategy", strategy, "--output", str(output)]
                            self.assertEqual(main(args), 0)
                            summary = json.loads((output / "summary.json").read_text())
                            self.assertEqual(summary["selected_symbols"], selected)
                            self.assertEqual(summary["strategy"], strategy)
                            self.assertEqual(summary["config"]["lookback"], 40 if strategy == "momentum" else 60)
                            self.assertEqual(set(summary["side_coefficients"]["B"]), set(selected[1:]))


if __name__ == "__main__":
    unittest.main()
