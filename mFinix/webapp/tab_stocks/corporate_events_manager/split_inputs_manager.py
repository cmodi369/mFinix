"""Stock split event inputs management for corporate events entry.

This module encapsulates all stock split-related user input handling, layouts,
callbacks, and processing logic.
"""

from datetime import date
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.util import log
from mFinix.webapp.tab_stocks.corporate_events_manager.ipo_inputs_manager import (
    CorporateEventHandler,
)
from mFinix.webapp.widgets import (
    CustomAutoCompleteInput,
    CustomDatePicker,
    CustomFloatInput,
    CustomTextInput,
)


class SplitInputsManager(CorporateEventHandler):
    """Manager for Stock Split corporate event data entry and processing.

    Handles all stock split-related user inputs including layout creation and
    data submission.
    """

    def __init__(
        self,
        transactions_data: pd.DataFrame,
        holdings_data: pd.DataFrame,
        widgets: dict,
        layout: pn.Column,
    ) -> None:
        super().__init__(transactions_data, holdings_data, widgets, layout)

        # Initialize split-specific widgets if not present (Defensive pattern)
        if "stock_select" not in self.widgets:
            self.widgets["stock_select"] = CustomAutoCompleteInput(
                name="Stock Name",
                options=self.transactions_data[col.SYMBOL].unique().tolist(),
                case_sensitive=False,
            )

        if "isin_input" not in self.widgets:
            self.widgets["isin_input"] = CustomTextInput(name="ISIN", disabled=True)

        if "transactions_date_select" not in self.widgets:
            self.widgets["transactions_date_select"] = CustomDatePicker(
                name="Date", end=date.today()
            )

        if "ratio_input" not in self.widgets:
            self.widgets["ratio_input"] = CustomFloatInput(
                name="Split Multiplier (e.g. 5 for 1:5)",
                value=1.0,
                step=0.1,
            )

        if "original_quantity_input" not in self.widgets:
            self.widgets["original_quantity_input"] = CustomFloatInput(
                name="Original Shares (on record date)"
            )

        if "extra_quantity_input" not in self.widgets:
            self.widgets["extra_quantity_input"] = CustomFloatInput(
                name="New Shares Received (Extra)"
            )

        # Watchers for auto-calculation
        self.widgets["stock_select"].param.watch(self._on_stock_or_date_change, "value")
        self.widgets["transactions_date_select"].param.watch(
            self._on_stock_or_date_change, "value"
        )
        self.widgets["ratio_input"].param.watch(
            self._on_ratio_or_base_qty_change, "value"
        )
        self.widgets["original_quantity_input"].param.watch(
            self._on_ratio_or_base_qty_change, "value"
        )

    def _get_balance_on_date(self, symbol: str, event_date: date) -> float:
        """Calculate the stock balance as of a specific date from transactions."""
        if self.transactions_data is None or self.transactions_data.empty:
            return 0.0

        # Filter for the symbol
        df = self.transactions_data[self.transactions_data[col.SYMBOL] == symbol].copy()
        if df.empty:
            return 0.0

        # Convert trade date to datetime for comparison
        df[col.TRADE_DATE] = pd.to_datetime(df[col.TRADE_DATE]).dt.date

        # Filter transactions on or before the event date
        df = df[df[col.TRADE_DATE] <= event_date]

        if df.empty:
            return 0.0

        # Sort and take the last row's Total Quantity
        df = df.sort_values(by=col.TRADE_DATE, kind="stable")
        return float(df[col.TOTAL_QUANTITY].iloc[-1])

    def _on_stock_or_date_change(self, event) -> None:
        """Update original quantity when stock or date changes."""
        symbol = self.widgets["stock_select"].value
        event_date = self.widgets["transactions_date_select"].value

        if not symbol or not event_date:
            return

        try:
            balance = self._get_balance_on_date(symbol, event_date)
            self.widgets["original_quantity_input"].value = balance
        except Exception as e:
            log.error(
                "Failed to calculate balance for %s on %s: %s", symbol, event_date, e
            )

    def _on_ratio_or_base_qty_change(self, event) -> None:
        """Auto-update extra quantity when ratio or base quantity changes."""
        original_qty = self.widgets["original_quantity_input"].value
        ratio = self.widgets["ratio_input"].value

        if original_qty is not None and ratio is not None:
            # Extra shares = Original * (Ratio - 1)
            self.widgets["extra_quantity_input"].value = round(
                original_qty * (ratio - 1), 1
            )

    def show_layout(self) -> None:
        """Display the stock split event entry layout."""
        objs = [
            pn.pane.Markdown(
                "## Add Stock Split Details", styles={"margin-bottom": "0px"}
            ),
            pn.layout.Divider(),
        ]

        objs.extend(
            [
                self.widgets["transactions_date_select"],
                pn.Row(
                    self.widgets["original_quantity_input"],
                    self.widgets["ratio_input"],
                    self.widgets["extra_quantity_input"],
                    sizing_mode="stretch_width",
                    styles={"gap": "16px"},
                ),
                pn.layout.Divider(),
                pn.Row(
                    self.widgets["submit_button"],
                    sizing_mode="stretch_width",
                    styles={"justify-content": "flex-end", "gap": "10px"},
                ),
            ]
        )
        self.layout.objects = objs

    def process_submission(self) -> Dict[str, Any]:
        """Process submitted stock split data and save to CSV."""
        symbol = self.widgets["stock_select"].value
        isin = self.widgets["isin_input"].value
        event_date = self.widgets["transactions_date_select"].value
        ratio = self.widgets["ratio_input"].value
        extra_qty = self.widgets["extra_quantity_input"].value

        if not symbol:
            pn.state.notifications.warning("Please select a stock.")
            return {}

        if not event_date:
            pn.state.notifications.warning("Please select a split date.")
            return {}

        # Splits CSV columns: symbol,isin,trade_date,stock_splits,quantity
        data = {
            col.SYMBOL: symbol,
            col.ISIN: isin,
            col.TRADE_DATE: event_date,
            col.STOCK_SPLITS_COL: float(ratio),
            col.QUANTITY: float(extra_qty),
        }

        try:
            self.append_row_to_csv(
                Path(const.LOCAL_DATA_PATH / const.SPLIT_ACTIONS_CSV), data
            )
            return data
        except Exception as e:
            log.error("Failed to save stock split event: %s", e)
            pn.state.notifications.error(f"Failed to save: {e}")
            return {}
