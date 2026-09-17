"""Trade toward the average price relationship. Edit or copy this file."""
from pairs_trading.strategy import signals, entry_side, exit_reason

DESCRIPTION = "Mean reversion of the rolling log-price ratio"


def signal(history, config):
    # history contains only observations up to today's close.
    return signals(history[-(config.lookback + 1):], config.lookback)[-1]

# entry_side and exit_reason are imported above. To change the rules themselves,
# copy strategies/_template.py to strategies/my_strategy.py and edit its functions.
