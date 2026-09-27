"""Use stricter mean-reversion entry rules for fewer, more selective trades."""
from pairs_trading.signals import signals as rolling_signals
from pairs_trading.signals import entry_side as mean_reversion_entry
from pairs_trading.signals import exit_reason as mean_reversion_exit

DESCRIPTION = "Selective mean reversion of the rolling log-price ratio"


def signal(history, config):
    """Calculate today's score from the available price history."""
    recent_history = history[-(config.lookback + 1):]
    return rolling_signals(recent_history, config.lookback)[-1]


def entry_side(z, config):
    """Choose the opening direction while flat."""
    return mean_reversion_entry(z, config)


def exit_reason(z, side, next_holding_bars, net_unrealized, entry_gross, config):
    """Return a reason to close the trade, or None to keep holding."""
    return mean_reversion_exit(
        z, side, next_holding_bars, net_unrealized, entry_gross, config
    )
