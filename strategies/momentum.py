"""Illustrative relative momentum; follows a deviation instead of fading it."""
from pairs_trading.strategy import signals, entry_side as reversion_entry, exit_reason as reversion_exit

DESCRIPTION = "Relative momentum of the rolling log-price ratio"


def signal(history, config):
    return signals(history[-(config.lookback + 1):], config.lookback)[-1]


def entry_side(z, config):
    return -reversion_entry(z, config)


def exit_reason(z, side, next_holding_bars, net_unrealized, entry_gross, config):
    # Exit when momentum fades back into the band, or a stop/time limit triggers.
    reason = reversion_exit(z, -side, next_holding_bars, net_unrealized, entry_gross, config)
    return "momentum_faded" if reason == "mean_reversion" else reason
