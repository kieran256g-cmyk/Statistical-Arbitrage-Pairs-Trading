"""Two-leg cash ledger with next-close fills and fixed shares per trade."""
from dataclasses import dataclass, asdict
import math
from statistics import mean, stdev

from .config import Config
from .data import Bar, validate_bars
from .strategy import signals, entry_side, exit_reason


@dataclass
class Position:
    side: int
    shares_a: float
    shares_b: float
    entry_a: float
    entry_b: float
    entry_date: str
    entry_signal_date: str
    entry_index: int
    entry_gross: float
    entry_cost: float
    borrow_cost: float = 0.0


@dataclass(frozen=True)
class Order:
    side: int  # Zero closes; +/-1 opens a position.
    signal_date: str
    reason: str


@dataclass(frozen=True)
class Result:
    curve: list[dict]
    trades: list[dict]
    summary: dict


def transaction_cost(notional: float, config: Config) -> float:
    return notional * (config.fee_bps + config.slippage_bps) / 10000.0


def close_position(position: Position, bar: Bar, index: int, order: Order,
                   config: Config) -> tuple[float, dict]:
    market_value = position.shares_a * bar.price_a + position.shares_b * bar.price_b
    notional = abs(position.shares_a) * bar.price_a + abs(position.shares_b) * bar.price_b
    cost = transaction_cost(notional, config)
    gross_pnl = (position.shares_a * (bar.price_a - position.entry_a)
                 + position.shares_b * (bar.price_b - position.entry_b))
    trade = {
        "entry_signal_date": position.entry_signal_date,
        "entry_date": position.entry_date,
        "exit_signal_date": order.signal_date,
        "exit_date": bar.date.isoformat(),
        "side": "long_A_short_B" if position.side == 1 else "short_A_long_B",
        "shares_a": position.shares_a, "shares_b": position.shares_b,
        "entry_price_a": position.entry_a, "entry_price_b": position.entry_b,
        "exit_price_a": bar.price_a, "exit_price_b": bar.price_b,
        "holding_bars": index - position.entry_index,
        "entry_gross": position.entry_gross,
        "gross_pnl": gross_pnl,
        "transaction_cost": position.entry_cost + cost,
        "borrow_cost": position.borrow_cost,
        "net_pnl": gross_pnl - position.entry_cost - cost - position.borrow_cost,
        "exit_reason": order.reason,
    }
    return market_value - cost, trade


def backtest(bars: list[Bar], config: Config, strategy=None) -> Result:
    validate_bars(bars)
    if len(bars) < config.lookback + 3:
        raise ValueError(f"Need at least {config.lookback + 3} rows for warm-up and next-close execution")
    if strategy is None:
        observations = signals(bars, config.lookback)
    else:
        observations = [None] * len(bars)
    entry_fn = entry_side if strategy is None else strategy.entry_side
    exit_fn = exit_reason if strategy is None else strategy.exit_reason
    cash = config.initial_capital
    previous_equity = cash
    position = None
    pending = None
    curve, trades = [], []
    for i, (bar, signal) in enumerate(zip(bars, observations)):
        if strategy is not None:
            try:
                signal = strategy.signal(tuple(bars[:i+1]), config)
                if not math.isfinite(signal.spread) or (signal.zscore is not None and not math.isfinite(signal.zscore)):
                    raise ValueError("signal must contain finite spread and finite zscore (or None)")
            except Exception as error:
                raise ValueError(f"Strategy signal failed on {bars[i].date}: {error}") from error
        today = bar.date.isoformat()
        fees_today = 0.0
        borrow_today = 0.0
        action = "hold" if position else "flat"
        closed_today = False
        # Accrue the cost of yesterday's short position over elapsed calendar days.
        if position is not None and i:
            previous = bars[i-1]
            short_value = (max(-position.shares_a, 0) * previous.price_a
                           + max(-position.shares_b, 0) * previous.price_b)
            days = (bar.date - previous.date).days
            borrow_today = short_value * config.annual_borrow_rate * days / 365.0
            cash -= borrow_today
            position.borrow_cost += borrow_today

        if pending is not None:
            if pending.side == 0 and position is not None:
                proceeds, trade = close_position(position, bar, i, pending, config)
                fees_today += trade["transaction_cost"] - position.entry_cost
                cash += proceeds
                trades.append(trade)
                position = None
                action = "exit_" + pending.reason
                closed_today = True
            elif pending.side != 0 and position is None:
                if i == len(bars)-1:
                    action = "entry_cancelled_end_of_data"
                elif cash <= 0:
                    raise ValueError("Portfolio equity is nonpositive; the backtest cannot open another trade")
                else:
                    gross = cash * config.gross_allocation
                    shares_a = pending.side * gross / (2 * bar.price_a)
                    shares_b = -pending.side * gross / (2 * bar.price_b)
                    fees_today = transaction_cost(gross, config)
                    cash -= shares_a * bar.price_a + shares_b * bar.price_b + fees_today
                    position = Position(pending.side, shares_a, shares_b, bar.price_a, bar.price_b,
                                        today, pending.signal_date, i, gross, fees_today)
                    action = "enter_long_A" if pending.side == 1 else "enter_short_A"
            pending = None

        # Terminal liquidation is a reporting convention, not a strategy signal.
        if i == len(bars)-1 and position is not None:
            order = Order(0, "", "end_of_data")
            proceeds, trade = close_position(position, bar, i, order, config)
            fees_today += trade["transaction_cost"] - position.entry_cost
            cash += proceeds
            trades.append(trade)
            position = None
            action = "exit_end_of_data"
            closed_today = True

        value = 0.0 if position is None else position.shares_a * bar.price_a + position.shares_b * bar.price_b
        equity = cash + value
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError(f"Portfolio insolvent or non-finite on {today}; assumptions need review")

        # Decide at today's close; a queued order is executed at the next close.
        if i < len(bars)-1:
            if position is not None:
                unrealized = (position.shares_a * (bar.price_a-position.entry_a)
                              + position.shares_b * (bar.price_b-position.entry_b)
                              - position.entry_cost - position.borrow_cost)
                try:
                    reason = exit_fn(signal.zscore, position.side, i-position.entry_index+1,
                                     unrealized, position.entry_gross, config)
                    if reason is not None and (not isinstance(reason, str) or not reason):
                        raise ValueError("exit_reason must return a nonempty string or None")
                except Exception as error:
                    raise ValueError(f"Strategy exit failed on {today}: {error}") from error
                if strategy is not None:
                    if unrealized <= -config.stop_loss_fraction * position.entry_gross:
                        reason = "loss_stop"
                    elif i-position.entry_index+1 >= config.max_holding_bars:
                        reason = "time_exit"
                if reason:
                    pending = Order(0, today, reason)
            elif not closed_today and (strategy is None or i >= config.lookback):
                try:
                    side = entry_fn(signal.zscore, config)
                    if type(side) is not int or side not in (-1, 0, 1):
                        raise ValueError("entry_side must return -1, 0 or 1")
                except Exception as error:
                    raise ValueError(f"Strategy entry failed on {today}: {error}") from error
                if strategy is not None and i < config.lookback:
                    side = 0
                if side:
                    pending = Order(side, today, "entry")

        curve.append({
            "date": today, "price_a": bar.price_a, "price_b": bar.price_b,
            "spread": signal.spread, "zscore": signal.zscore,
            "position": 0 if position is None else position.side,
            "shares_a": 0.0 if position is None else position.shares_a,
            "shares_b": 0.0 if position is None else position.shares_b,
            "cash": cash, "equity": equity,
            "daily_pnl": equity-previous_equity,
            "daily_return": equity/previous_equity-1,
            "transaction_cost": fees_today, "borrow_cost": borrow_today,
            "action": action,
            "next_order": "" if pending is None else ("exit_"+pending.reason if pending.side == 0 else "enter_"+str(pending.side)),
        })
        previous_equity = equity

    returns = [row["daily_return"] for row in curve[1:]]
    sigma = stdev(returns) if len(returns) > 1 else 0.0
    peak = config.initial_capital
    max_drawdown = 0.0
    for row in curve:
        peak = max(peak, row["equity"])
        drawdown = row["equity"]/peak - 1
        row["drawdown"] = drawdown
        max_drawdown = min(max_drawdown, drawdown)
    summary = {
        "start": curve[0]["date"], "end": curve[-1]["date"], "rows": len(curve),
        "initial_capital": config.initial_capital, "ending_equity": curve[-1]["equity"],
        "total_return": curve[-1]["equity"]/config.initial_capital-1,
        "max_drawdown": max_drawdown,
        "annualized_sharpe_252_zero_risk_free": None if sigma < 1e-15 else mean(returns)/sigma*math.sqrt(252),
        "closed_trades": len(trades),
        "win_rate": None if not trades else sum(t["net_pnl"] > 0 for t in trades)/len(trades),
        "total_transaction_cost": sum(row["transaction_cost"] for row in curve),
        "total_borrow_cost": sum(row["borrow_cost"] for row in curve),
        "config": asdict(config),
    }
    return Result(curve, trades, summary)
