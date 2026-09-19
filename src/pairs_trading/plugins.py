"""Discover and load user-editable strategy files from strategies/."""
from dataclasses import asdict
import hashlib
import importlib.util
import json
import re

from .config import Config


def available_strategies(directory):
    return sorted(p.stem for p in directory.glob("*.py")
                  if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", p.stem))


def choose_strategy(directory):
    names = available_strategies(directory)
    if "mean_reversion" in names:
        names.remove("mean_reversion")
        names.insert(0, "mean_reversion")
    if not names:
        raise ValueError("No strategy files found in strategies/")
    print("\nChoose a strategy:")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    while True:
        answer = input("Strategy number [1]: ").strip() or "1"
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            return names[int(answer)-1]
        print("Choose a number from the list.")


def load_strategy(directory, name):
    if name not in available_strategies(directory):
        raise ValueError(f"Unknown strategy {name!r}. Add a .py file to strategies/ or use --list-strategies.")
    path = directory / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"user_strategy_{name}", path)
    module = importlib.util.module_from_spec(spec)
    try:
        # Compile current source directly; editing rules is reflected on every run.
        exec(compile(path.read_text(encoding="utf-8-sig"), str(path), "exec"), module.__dict__)
    except Exception as error:
        raise ValueError(f"Cannot load strategy {name}: {error}") from error
    for hook in ("signal", "entry_side", "exit_reason"):
        if not callable(getattr(module, hook, None)):
            raise ValueError(f"Strategy {name} must define {hook}()")
    module.source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    module.strategy_name = name
    return module


def strategy_config(directory, name, base):
    path = directory / f"{name}.json"
    if not path.exists():
        return base
    overrides = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(overrides, dict) or set(overrides) - asdict(base).keys():
        raise ValueError(f"Invalid setting names in {path.name}")
    return Config(**{**asdict(base), **overrides})
