# trader/strategies/__init__.py

from .basic import BasicStrategy
from .scalping import StandardOpportunityStrategy
from .daytrade import DaytradeStrategy
from .swing import SwingStrategy
from .position import PositionStrategy

__all__ = [
    "BasicStrategy",
    "StandardOpportunityStrategy",
    "DaytradeStrategy",
    "SwingStrategy",
    "PositionStrategy"
]
