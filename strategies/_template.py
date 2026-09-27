"""Copy to my_strategy.py. Files starting with _ do not appear in the menu."""
from pairs_trading.signals import signals as rolling_signals

DESCRIPTION = "My custom basket strategy"


def signal(history, config):
    """Calculate today's score from the available price history."""
    recent_history = history[-(config.lookback + 1):]
    return rolling_signals(recent_history, config.lookback)[-1]


def entry_side(z, config):
    """Choose the opening direction while flat."""
    if z is None or abs(z) >= config.stop_z:
        return 0
    if z >= config.entry_z:
        return -1
    if z <= -config.entry_z:
        return 1
    return 0


def exit_reason(z, side, next_holding_bars, net_unrealized, entry_gross, config):
    """Return a reason to close the trade, or None to keep holding."""
    if z is None:
        return "no_signal"
    if abs(z) >= config.stop_z:
        return "extreme_signal"
    if (side == 1 and z >= -config.exit_z) or (side == -1 and z <= config.exit_z):
        return "back_to_average"
    return None
