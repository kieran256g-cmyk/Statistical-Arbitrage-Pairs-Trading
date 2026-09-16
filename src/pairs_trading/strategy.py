"""Signals depend only on observations available at each daily close."""
from dataclasses import dataclass
import math
from statistics import mean, stdev

from .config import Config
from .data import Bar


@dataclass(frozen=True)
class Signal:
    spread: float
    zscore: float | None


def signals(bars: list[Bar], lookback: int) -> list[Signal]:
    # Difference of logs avoids overflow in the division for extreme prices.
    spreads = [math.log(bar.price_a) - math.log(bar.price_b) for bar in bars]
    output = []
    for i, spread in enumerate(spreads):
        z = None
        if i >= lookback:
            history = spreads[i - lookback:i]  # Excludes the current close.
            sigma = stdev(history)
            if sigma > 1e-12:
                z = (spread - mean(history)) / sigma
        output.append(Signal(spread, z))
    return output


def entry_side(z: float | None, config: Config) -> int:
    """+1 = long A / short B; -1 = short A / long B; 0 = stay flat."""
    if z is None or abs(z) >= config.stop_z:
        return 0
    if z >= config.entry_z:
        return -1
    if z <= -config.entry_z:
        return 1
    return 0


def exit_reason(z: float | None, side: int, next_holding_bars: int,
                net_unrealized: float, entry_gross: float, config: Config) -> str | None:
    if net_unrealized <= -config.stop_loss_fraction * entry_gross:
        return "loss_stop"
    if z is None:
        return "unavailable_signal"
    if abs(z) >= config.stop_z:
        return "extreme_z"
    if (side == 1 and z >= -config.exit_z) or (side == -1 and z <= config.exit_z):
        return "mean_reversion"
    if next_holding_bars >= config.max_holding_bars:
        return "time_exit"
    return None
