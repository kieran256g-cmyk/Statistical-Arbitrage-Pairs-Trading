"""Strategy and execution assumptions, all expressed in one configuration."""
from dataclasses import dataclass, fields
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Config:
    lookback: int = 60
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_z: float = 4.0
    max_holding_bars: int = 20
    stop_loss_fraction: float = 0.05
    initial_capital: float = 10000.0
    gross_allocation: float = 1.0
    fee_bps: float = 1.0
    slippage_bps: float = 2.0
    annual_borrow_rate: float = 0.03

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{field.name} must be a finite number")
        if not isinstance(self.lookback, int) or self.lookback < 2:
            raise ValueError("lookback must be an integer >= 2")
        if not isinstance(self.max_holding_bars, int) or self.max_holding_bars < 1:
            raise ValueError("max_holding_bars must be a positive integer")
        if not 0 <= self.exit_z < self.entry_z < self.stop_z:
            raise ValueError("Require 0 <= exit_z < entry_z < stop_z")
        if not 0 < self.stop_loss_fraction < 1:
            raise ValueError("stop_loss_fraction must be between 0 and 1")
        if self.initial_capital <= 0 or not 0 < self.gross_allocation <= 1:
            raise ValueError("initial_capital must be positive and gross_allocation in (0, 1]")
        if not 0 <= self.fee_bps < 10000 or not 0 <= self.slippage_bps < 10000:
            raise ValueError("fee_bps and slippage_bps must be in [0, 10000)")
        if not 0 <= self.annual_borrow_rate <= 1:
            raise ValueError("annual_borrow_rate must be in [0, 1]")


def load_config(path: Path) -> Config:
    values = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(values, dict):
        raise ValueError("Configuration must be a JSON object")
    unknown = set(values) - {field.name for field in fields(Config)}
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(sorted(unknown))}")
    return Config(**values)
