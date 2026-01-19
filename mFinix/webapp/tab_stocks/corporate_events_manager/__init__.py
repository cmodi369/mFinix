"""Corporate events management module for stock data entry.

This package provides input managers for different types of corporate events
(IPO, stock splits, bonuses, transactions, etc.). Each manager encapsulates
event-specific logic for user input handling, layouts, and data processing.
"""

from mFinix.webapp.tab_stocks.corporate_events_manager.bonus_inputs_manager import (
    BonusInputsManager,
)
from mFinix.webapp.tab_stocks.corporate_events_manager.ipo_inputs_manager import (
    CorporateEventHandler,
    IPOInputsManager,
)
from mFinix.webapp.tab_stocks.corporate_events_manager.split_inputs_manager import (
    SplitInputsManager,
)
from mFinix.webapp.tab_stocks.corporate_events_manager.transaction_inputs_manager import (
    TransactionInputsManager,
)

__all__ = [
    "CorporateEventHandler",
    "IPOInputsManager",
    "BonusInputsManager",
    "SplitInputsManager",
    "TransactionInputsManager",
]
