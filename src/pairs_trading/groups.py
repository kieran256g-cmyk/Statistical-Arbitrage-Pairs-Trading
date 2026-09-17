"""Editable company groups and arbitrary two-sided, fixed-share baskets."""
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

from .data import Bar
from .market import fetch_history


def load_groups(path):
    groups = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(groups, dict) or not groups:
        raise ValueError("company_groups.json must contain at least one group")
    for key, group in groups.items():
        if not re.fullmatch(r"[a-z0-9_-]+", key) or not isinstance(group, dict):
            raise ValueError("Invalid company group")
        companies = group.get("companies")
        if not isinstance(group.get("name"), str) or not isinstance(companies, dict) or len(companies) < 2:
            raise ValueError(f"Group {key} needs a name and at least two companies")
        for ticker, name in companies.items():
            if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", ticker) or not isinstance(name, str):
                raise ValueError(f"Invalid company in {key}")
    return groups


def validate_selection(groups, group, left, right):
    if group not in groups:
        raise ValueError(f"Unknown group: {group}")
    if not left or not right:
        raise ValueError("Choose at least one company on each side")
    symbols = left + right
    if len(set(symbols)) != len(symbols):
        raise ValueError("Each company can appear only once across both sides")
    if not set(symbols) <= groups[group]["companies"].keys():
        raise ValueError(f"Choose companies from the {group} group only")


def ask_numbers(prompt, size, default):
    while True:
        raw = input(prompt).strip() or default
        try:
            numbers = [int(s.strip()) for s in raw.split(",")]
            if len(set(numbers)) == len(numbers) and all(1 <= n <= size for n in numbers):
                return [n-1 for n in numbers]
        except ValueError:
            pass
        print("Enter valid, distinct numbers separated by commas.")


def choose_group(groups):
    keys = list(groups)
    print("\nChoose a company group:")
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {groups[key]['name']}")
    while True:
        indexes = ask_numbers("Group number [1]: ", len(keys), "1")
        if len(indexes) == 1:
            break
        print("Choose one group.")
    key = keys[indexes[0]]
    tickers = list(groups[key]["companies"])
    for i, ticker in enumerate(tickers, 1):
        print(f"  {i}. {groups[key]['companies'][ticker]} ({ticker})")
    while True:
        indexes = ask_numbers("Companies to include, e.g. 1,2 or 1,2,3 [1,2]: ", len(tickers), "1,2")
        if len(indexes) >= 2:
            break
        print("Choose at least two companies.")
    selected = [tickers[i] for i in indexes]
    print("\nSplit your selected companies into side A and side B:")
    for i, ticker in enumerate(selected, 1):
        print(f"  {i}. {ticker}")
    while True:
        indexes = ask_numbers("Companies on side A [1]; all others go on side B: ", len(selected), "1")
        if len(indexes) < len(selected):
            break
        print("Leave at least one company on side B.")
    left = [selected[i] for i in indexes]
    right = [s for s in selected if s not in left]
    print(f"Selected: {' + '.join(left)} versus {' + '.join(right)}")
    return key, left, right


def refresh_symbols(directory, symbols):
    end = datetime.now(timezone.utc).date()
    prepared = []
    for symbol in sorted(set(symbols)):
        print(f"Downloading {symbol}...")
        history, url = fetch_history(symbol, date(2023, 1, 1), end)
        prepared.append((symbol, history, url))
    directory.mkdir(parents=True, exist_ok=True)
    for symbol, history, url in prepared:
        path = directory / f"{symbol}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "adjusted_close"])
            writer.writerows((d.isoformat(), p) for d, p in sorted(history.items()))
        meta = {"symbol": symbol, "currency": "USD", "source": "Yahoo Finance", "source_url": url,
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "requested_end_exclusive": end.isoformat(), "rows": len(history),
                "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2)+"\n", encoding="utf-8")


def load_symbol(directory, symbol):
    path = directory / f"{symbol}.csv"
    if not path.exists() or not path.with_suffix(".json").exists():
        raise ValueError(f"Missing {symbol} history. Run again with --refresh to download your selection.")
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if meta.get("symbol") != symbol or meta.get("csv_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f"Invalid cache for {symbol}; refresh it")
    history = {}
    previous = None
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            day, value = date.fromisoformat(row["date"]), float(row["adjusted_close"])
            if not math.isfinite(value) or value <= 0 or (previous is not None and day <= previous):
                raise ValueError(f"Invalid prices for {symbol}")
            history[day] = value
            previous = day
    return history, meta


def build_baskets(histories, left, right):
    if not left or not right or len(set(left + right)) != len(left + right):
        raise ValueError("Basket sides must be nonempty and disjoint")
    days = sorted(set.intersection(*(set(histories[s]) for s in left+right)))
    if len(days) < 3:
        raise ValueError("Not enough shared dates across selected companies")
    # Normalize each side to 100 using only the first shared date. No fitted weights.
    coefficients = [{s: 100 / len(side) / histories[s][days[0]] for s in side} for side in (left, right)]
    bars = [Bar(d, *(sum(c*histories[s][d] for s, c in side.items()) for side in coefficients)) for d in days]
    return bars, {"A": coefficients[0], "B": coefficients[1]}


def load_selection(directory, groups, group, left, right, refresh=False):
    validate_selection(groups, group, left, right)
    if refresh:
        refresh_symbols(directory, left+right)
    histories, provenance = {}, {}
    for symbol in left+right:
        histories[symbol], provenance[symbol] = load_symbol(directory, symbol)
    bars, coefficients = build_baskets(histories, left, right)
    a, b = " + ".join(left), " + ".join(right)
    return bars, {"pair_name": f"{a} / {b}", "group": group, "asset_a": a, "asset_b": b,
                  "source": "Yahoo Finance adjusted daily closes", "constituent_sources": provenance,
                  "price_basis": "split- and distribution-adjusted close; total-return proxy, not executable prices",
                  "side_coefficients": coefficients, "selected_symbols": left+right,
                  "basket_description": "Each side starts at 100 with equal dollars per selected company on the first shared date. Adjusted-share coefficients then stay fixed; weights drift. CSVs show every constituent holding.",
                  "alignment": "intersection of all selected companies; no forward filling",
                  "unmatched_dates_dropped": len(set.union(*(set(h) for h in histories.values()))) - len(bars)}
