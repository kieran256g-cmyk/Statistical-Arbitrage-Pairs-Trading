"""Strict, aligned daily close inputs and a reproducible synthetic demo."""
import csv
from dataclasses import dataclass
from datetime import date, timedelta
import math
from pathlib import Path
import random


@dataclass(frozen=True)
class Bar:
    date: date
    price_a: float
    price_b: float


def validate_bars(bars: list[Bar]) -> None:
    if not bars:
        raise ValueError("No price rows provided")
    previous = None
    for i, bar in enumerate(bars):
        if previous is not None and bar.date <= previous:
            raise ValueError(f"Row {i + 1}: dates must be unique and strictly increasing")
        for value in (bar.price_a, bar.price_b):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Row {i + 1}: prices must be finite and positive")
        previous = bar.date


def load_prices(path: Path) -> list[Bar]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not {"date", "price_a", "price_b"} <= set(reader.fieldnames):
            raise ValueError("CSV requires columns: date,price_a,price_b")
        bars = []
        for line, row in enumerate(reader, 2):
            try:
                bars.append(Bar(date.fromisoformat(row["date"]), float(row["price_a"]), float(row["price_b"])))
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid CSV row {line}: {error}") from error
    validate_bars(bars)
    return bars


def make_demo(count: int = 400, seed: int = 7) -> list[Bar]:
    """Artificial common trend plus a mean-reverting log-price ratio."""
    rng = random.Random(seed)
    day = date(2020, 1, 2)
    log_b = math.log(100.0)
    spread = 0.0
    bars = []
    while len(bars) < count:
        if day.weekday() < 5:
            i = len(bars)
            log_b += 0.0002 + rng.gauss(0.0, 0.006)
            spread = 0.86 * spread + rng.gauss(0.0, 0.009)
            if i > 0 and i % 55 == 0:
                spread += 0.07 if (i // 55) % 2 else -0.07
            bars.append(Bar(day, round(1.2 * math.exp(log_b + spread), 6), round(math.exp(log_b), 6)))
        day += timedelta(days=1)
    return bars


def write_prices(path: Path, bars: list[Bar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "price_a", "price_b"])
        writer.writerows((bar.date.isoformat(), bar.price_a, bar.price_b) for bar in bars)
