"""Refresh every bundled market snapshot; downloads each company once."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pairs_trading.market import PAIRS, refresh_pairs

if __name__ == "__main__":
    try:
        refresh_pairs(ROOT / "data" / "market", PAIRS)
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        raise SystemExit(1)
    print("Updated all pair and basket snapshots in data/market.")
