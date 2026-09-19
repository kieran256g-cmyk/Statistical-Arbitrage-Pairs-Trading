"""Named pairs and cached, date-aligned Yahoo Finance adjusted daily closes."""
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .data import Bar, load_prices, write_prices

PAIRS = {
    "dell-nvidia": ("DELL", "NVDA", "Dell / NVIDIA"),
    "dell-micron": ("DELL", "MU", "Dell / Micron"),
    "nvidia-micron": ("NVDA", "MU", "NVIDIA / Micron"),
    "dell-nvidia-micron": ("DELL", "NVDA+MU", "Dell / NVIDIA + Micron basket"),
    "coke-pepsi": ("KO", "PEP", "Coca-Cola / PepsiCo"),
    "seagate-wdc": ("STX", "WDC", "Seagate / Western Digital"),
    "visa-mastercard": ("V", "MA", "Visa / Mastercard"),
    "exxon-chevron": ("XOM", "CVX", "ExxonMobil / Chevron"),
}


def parse_history(payload, symbol, start, end):
    """Use adjusted closes only; reject malformed data, omit missing observations."""
    try:
        chart = payload["chart"]
        if chart.get("error"):
            raise ValueError(str(chart["error"]))
        result = chart["result"][0]
        if result["meta"]["symbol"] != symbol or result["meta"]["currency"] != "USD":
            raise ValueError("Unexpected symbol or currency")
        stamps = result["timestamp"]
        prices = result["indicators"]["adjclose"][0]["adjclose"]
        if len(stamps) != len(prices):
            raise ValueError("Timestamp/price length mismatch")
        history = {}
        for stamp, price in zip(stamps, prices):
            day = datetime.fromtimestamp(stamp, timezone.utc).date()
            if not start <= day < end or price is None:
                continue
            if not math.isfinite(price) or price <= 0 or day in history:
                raise ValueError("Invalid price or duplicate date")
            history[day] = float(price)
        if not history:
            raise ValueError("No adjusted prices returned")
        return history
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"Malformed Yahoo Finance history for {symbol}") from error


def fetch_history(symbol, start, end):
    params = urlencode({"period1": int(datetime.combine(start, datetime.min.time(), timezone.utc).timestamp()),
                        "period2": int(datetime.combine(end, datetime.min.time(), timezone.utc).timestamp()),
                        "interval": "1d", "events": "div,splits", "includeAdjustedClose": "true"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{params}"
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as response:
            payload = json.load(response)
        return parse_history(payload, symbol, start, end), url
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not download {symbol}: {error}. Retry later; existing cached files are unchanged.") from error


def align_prices(left, right):
    return [Bar(day, left[day], right[day]) for day in sorted(left.keys() & right.keys())]


def refresh_pairs(directory: Path, keys, start=date(2023, 1, 1), end=None):
    """Download all needed symbols once. End date is exclusive; omit today's bar."""
    end = end or datetime.now(timezone.utc).date()
    if start >= end:
        raise ValueError("Start must precede end")
    keys = list(keys)
    histories = {}
    for key in keys:
        for symbol in (("DELL", "NVDA", "MU") if key == "dell-nvidia-micron" else PAIRS[key][:2]):
            if symbol not in histories:
                print(f"Downloading {symbol}...")
                histories[symbol] = fetch_history(symbol, start, end)
    prepared = []
    for key in keys:
        a, b, label = PAIRS[key]
        basket = {}
        if key == "dell-nvidia-micron":
            common = sorted(histories["DELL"][0].keys() & histories["NVDA"][0].keys() & histories["MU"][0].keys())
            if not common:
                raise ValueError("No shared dates for three-stock basket")
            basket = {symbol: 50.0 / histories[symbol][0][common[0]] for symbol in ("NVDA", "MU")}
            right = {day: sum(basket[symbol] * histories[symbol][0][day] for symbol in basket) for day in common}
            bars = align_prices(histories[a][0], right)
            symbols = ["DELL", "NVDA", "MU"]
        else:
            bars = align_prices(histories[a][0], histories[b][0])
            symbols = [a, b]
        if len(bars) < 63:
            raise ValueError(f"Not enough shared dates for {label}; cache unchanged")
        metadata = {"pair": key, "pair_name": label, "asset_a": a, "asset_b": b,
                    "source": f"Yahoo Finance adjusted daily closes: {a} / {b}",
                    "price_basis": "split- and distribution-adjusted close; total-return proxy, not executable prices",
                    "currency": "USD", "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "requested_start": start.isoformat(), "requested_end_exclusive": end.isoformat(),
                    "first_date": bars[0].date.isoformat(), "last_date": bars[-1].date.isoformat(),
                    "rows": len(bars), "source_urls": [histories[symbol][1] for symbol in symbols],
                    "basket_shares_per_unit": basket,
                    "basket_rule": "50/50 dollars on first shared date, fixed adjusted-share coefficients thereafter" if basket else None,
                    "unmatched_dates_dropped": len(set().union(*(histories[s][0] for s in symbols))) - len(bars),
                    "alignment": "intersection of available dates; no forward filling"}
        prepared.append((key, bars, metadata))
    for key, bars, metadata in prepared:
        path = directory / f"{key}.csv"
        write_prices(path, bars)
        metadata["csv_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")


def load_pair(directory, key):
    path = directory / f"{key}.csv"
    if not path.exists() or not path.with_suffix(".json").exists():
        raise ValueError(f"No cached prices for {key}. Run python run.py --pair {key} --refresh")
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if metadata.get("pair") != key or metadata.get("csv_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f"Cache metadata does not match {key}; refresh this pair")
    bars = load_prices(path)
    return bars, metadata


def choose_pair():
    keys = list(PAIRS)
    print("Choose a pair:")
    for number, key in enumerate(keys, 1):
        a, b, label = PAIRS[key]
        print(f"  {number}. {label} ({a} / {b})")
    while True:
        answer = input("Pair number [1]: ").strip() or "1"
        if answer.isdigit() and 1 <= int(answer) <= len(keys):
            return keys[int(answer)-1]
        print(f"Enter a number from 1 to {len(keys)}.")
