import math
from dataclasses import dataclass

# Costs are stored as integer micro-units so SQLite sums are exact.
SCALE = 1_000_000


def to_units(value):
    if not math.isfinite(value) or value < 0:
        raise ValueError("Cost and budget values must be finite and non-negative")
    return math.ceil(value * SCALE)


@dataclass(frozen=True)
class Budget:
    daily: float
    monthly: float
    reserve: float = 0
    unit: str = "credits"

    def __post_init__(self):
        for value in (self.daily, self.monthly, self.reserve):
            to_units(value)
        if self.reserve > self.monthly:
            raise ValueError("Reserved budget cannot exceed the monthly limit")
