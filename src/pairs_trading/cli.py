import argparse
import hashlib
import sys
from pathlib import Path

from .backtest import backtest
from .config import Config, load_config
from .data import load_prices, make_demo
from .report import write_report
from .market import PAIRS, choose_pair, load_pair, refresh_pairs
from .groups import load_groups, choose_group, load_selection, validate_selection
from .plugins import available_strategies, choose_strategy, load_strategy, strategy_config


def main(argv=None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Choose a real-data pair or a three-stock basket and backtest it.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--input", type=Path, help="Daily CSV with date,price_a,price_b")
    selection.add_argument("--pair", choices=PAIRS, help="Named pair; default Dell / NVIDIA")
    selection.add_argument("--choose", action="store_true", help="Show the numbered selection menu")
    selection.add_argument("--demo", action="store_true", help="Use invented example data")
    selection.add_argument("--group", help="Company group from company_groups.json")
    parser.add_argument("--left", help="Side A tickers, comma separated")
    parser.add_argument("--right", help="Side B tickers, comma separated")
    parser.add_argument("--strategy", help="Strategy filename without .py; default mean_reversion")
    parser.add_argument("--list-strategies", action="store_true")
    parser.add_argument("--list-groups", action="store_true")
    parser.add_argument("--list-pairs", action="store_true", help="List choices and exit")
    parser.add_argument("--refresh", action="store_true", help="Download selected pair's history from 2023 through yesterday")
    parser.add_argument("--config", type=Path, help="JSON settings; defaults to repository config.json")
    parser.add_argument("--output", type=Path, help="Report directory (default: results/<pair>)")
    args = parser.parse_args(argv)
    strategy_directory = root / "strategies"
    if args.list_strategies:
        print("\n".join(available_strategies(strategy_directory)))
        return 0
    if args.list_pairs:
        for key, (a, b, name) in PAIRS.items():
            print(f"{key}: {name} ({a} / {b})")
        return 0
    try:
        groups = load_groups(root / "company_groups.json")
        if args.list_groups:
            for name, group in groups.items():
                print(f"{name}: {group['name']} - {', '.join(group['companies'])}")
            return 0
        if args.refresh and (args.demo or args.input):
            raise ValueError("--refresh requires a named pair, not --demo or --input")
        if (args.left or args.right) and not args.group:
            raise ValueError("Use --group with --left and --right")
        key = None
        group = args.group
        left, right = [], []
        interactive = args.choose or (not any((args.group, args.pair, args.input, args.demo)) and sys.stdin.isatty())
        if not args.demo and args.input is None:
            if args.pair:
                key = args.pair
            else:
                if interactive:
                    group, left, right = choose_group(groups)
                elif group:
                    left = [s.strip().upper() for s in (args.left or "").split(",") if s.strip()]
                    right = [s.strip().upper() for s in (args.right or "").split(",") if s.strip()]
                else:
                    group, left, right = "technology", ["DELL"], ["NVDA"]
                validate_selection(groups, group, left, right)
                key = group + "-" + "-".join(left) + "-vs-" + "-".join(right)
        strategy_name = args.strategy or (choose_strategy(strategy_directory) if interactive else "mean_reversion")
        strategy = load_strategy(strategy_directory, strategy_name)
        args.output = args.output or Path("results") / (key or ("demo" if args.demo else "custom")) / strategy_name
        config_path = args.config if args.config is not None else root / "config.json"
        config = load_config(config_path) if args.config is not None or config_path.exists() else Config()
        if args.config is None:
            config = strategy_config(strategy_directory, strategy_name, config)
        demo_path = root / "data" / "sample_prices.csv"
        synthetic = args.demo or (args.input is not None and args.input.resolve() == demo_path.resolve())
        market_metadata = {}
        if args.input is not None:
            for filename in ("equity.csv", "trades.csv", "summary.json", "report.html"):
                if args.input.resolve() == (args.output / filename).resolve():
                    raise ValueError("Input file would be overwritten by the report; choose another output directory")
            bars = load_prices(args.input)
            source = str(args.input)
        elif args.demo:
            bars = load_prices(demo_path) if demo_path.exists() else make_demo()
            source = "Synthetic demo; generator seed=7, 400 rows"
        else:
            if group:
                bars, market_metadata = load_selection(root / "data" / "symbols", groups, group, left, right, args.refresh)
            else:
                cache = root / "data" / "market"
                if args.refresh:
                    refresh_pairs(cache, [key])
                bars, market_metadata = load_pair(cache, key)
            source = market_metadata["source"]
            print(f"{market_metadata['pair_name']}: {bars[0].date} to {bars[-1].date} ({len(bars)} shared sessions)")
        normalized = "\n".join(f"{b.date.isoformat()},{b.price_a:.17g},{b.price_b:.17g}" for b in bars)
        metadata = {**market_metadata, "synthetic_data": synthetic, "source": source,
                    "normalized_input_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
                    "execution": "signal at close t; fill at close t+1",
                    "strategy": strategy_name, "strategy_description": getattr(strategy, "DESCRIPTION", strategy_name),
                    "strategy_source_sha256": strategy.source_sha256}
        print(f"Strategy: {strategy_name}")
        result = backtest(bars, config, strategy)
        if market_metadata.get("side_coefficients"):
            for row in result.trades + result.curve:
                for side, coefficients in market_metadata["side_coefficients"].items():
                    for ticker, coefficient in coefficients.items():
                        row[f"shares_{ticker}"] = row[f"shares_{side.lower()}"] * coefficient
        if market_metadata.get("basket_shares_per_unit"):
            for row in result.trades + result.curve:
                row["shares_DELL"] = row["shares_a"]
                for ticker, coefficient in market_metadata["basket_shares_per_unit"].items():
                    row[f"shares_{ticker}"] = row["shares_b"] * coefficient
        write_report(result, args.output, metadata)
    except (OSError, ValueError, OverflowError, EOFError) as error:
        print(f"Error: {error}")
        return 1
    print("SYNTHETIC DEMO - not market performance" if synthetic else "Historical simulation on supplied prices")
    print(f"Closed trades: {result.summary['closed_trades']}")
    print(f"Ending equity: {result.summary['ending_equity']:,.2f}")
    print(f"Total return: {result.summary['total_return']:.2%}")
    print(f"Max drawdown: {result.summary['max_drawdown']:.2%}")
    print(f"Open the report: {(args.output / 'report.html').resolve()}")
    return 0
