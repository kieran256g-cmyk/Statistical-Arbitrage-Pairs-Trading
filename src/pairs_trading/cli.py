import argparse
import hashlib
from pathlib import Path

from .backtest import backtest
from .config import Config, load_config
from .data import load_prices, make_demo
from .report import write_report


def main(argv=None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Basic pairs-trading research backtest; defaults to synthetic demo prices.")
    parser.add_argument("--input", type=Path, help="Daily CSV with date,price_a,price_b")
    parser.add_argument("--config", type=Path, help="JSON settings; defaults to repository config.json")
    parser.add_argument("--output", type=Path, default=Path("results"), help="Report directory (default: results)")
    args = parser.parse_args(argv)
    try:
        config_path = args.config if args.config is not None else root / "config.json"
        config = load_config(config_path) if args.config is not None or config_path.exists() else Config()
        demo_path = root / "data" / "sample_prices.csv"
        synthetic = args.input is None or args.input.resolve() == demo_path.resolve()
        if args.input is not None:
            for filename in ("equity.csv", "trades.csv", "summary.json", "report.html"):
                if args.input.resolve() == (args.output / filename).resolve():
                    raise ValueError("Input file would be overwritten by the report; choose another output directory")
            bars = load_prices(args.input)
            source = str(args.input)
        else:
            bars = load_prices(demo_path) if demo_path.exists() else make_demo()
            source = "Synthetic demo; generator seed=7, 400 rows"
        normalized = "\n".join(f"{b.date.isoformat()},{b.price_a:.17g},{b.price_b:.17g}" for b in bars)
        metadata = {"synthetic_data": synthetic, "source": source,
                    "normalized_input_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
                    "execution": "signal at close t; fill at close t+1",
                    "strategy": "rolling log-price-ratio z-score; fixed shares; equal notionals at entry"}
        result = backtest(bars, config)
        write_report(result, args.output, metadata)
    except (OSError, ValueError, OverflowError) as error:
        print(f"Error: {error}")
        return 1
    print("SYNTHETIC DEMO - not market performance" if synthetic else "Historical simulation on supplied prices")
    print(f"Closed trades: {result.summary['closed_trades']}")
    print(f"Ending equity: {result.summary['ending_equity']:,.2f}")
    print(f"Total return: {result.summary['total_return']:.2%}")
    print(f"Max drawdown: {result.summary['max_drawdown']:.2%}")
    print(f"Open the report: {(args.output / 'report.html').resolve()}")
    return 0
