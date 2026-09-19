"""Regenerate the committed artificial example; never downloads market data."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pairs_trading.data import make_demo, write_prices

if __name__ == "__main__":
    target = ROOT / "data" / "sample_prices.csv"
    write_prices(target, make_demo())
    print(f"Wrote synthetic example to {target}")
