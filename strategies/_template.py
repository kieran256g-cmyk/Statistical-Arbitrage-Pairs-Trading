"""Copy to my_strategy.py. Files starting with _ do not appear in the menu."""
from pairs_trading.strategy import signals

DESCRIPTION = "My custom basket strategy"


def signal(history, config):
    # Each item has .date, .price_a and .price_b. No future bars are supplied.
    # Return Signal(spread, zscore); zscore=None means not ready to trade.
    return signals(history[-(config.lookback + 1):], config.lookback)[-1]


def entry_side(z, config):
    # +1 buys side A and shorts B. -1 shorts A and buys B. 0 stays flat.
    if z is None or abs(z) >= config.stop_z:
        return 0
    if z >= config.entry_z:
        return -1
    if z <= -config.entry_z:
        return 1
    return 0


def exit_reason(z, side, next_holding_bars, net_unrealized, entry_gross, config):
    # Return a short reason to close, or None to keep holding.
    # The engine also enforces config's loss and maximum holding limits.
    if z is None:
        return "no_signal"
    if abs(z) >= config.stop_z:
        return "extreme_signal"
    if (side == 1 and z >= -config.exit_z) or (side == -1 and z <= config.exit_z):
        return "back_to_average"
    return None
