"""Refresh individual stock histories for every editable company group."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pairs_trading.groups import load_groups, refresh_symbols

if __name__ == "__main__":
    try:
        groups = load_groups(ROOT / "company_groups.json")
        symbols = {s for group in groups.values() for s in group["companies"]}
        refresh_symbols(ROOT / "data" / "symbols", symbols)
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        raise SystemExit(1)
    print("Company histories updated.")
