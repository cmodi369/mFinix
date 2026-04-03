"""Merger event inputs management for corporate events entry.

This module encapsulates all merger-related user input handling, layouts,
callbacks, and processing logic, following the pattern established by
DemergerInputsManager.
"""

from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Optional

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


class MergerInputsManager(CorporateEventHandler):
    """Manager for Merger corporate event data entry and processing.

    Handles all merger-related user inputs including layout creation,
    historical balance calculation, and data submission to merger.csv.
    """

    def __init__(
        self,
        transactions_data: pd.DataFrame,
        holdings_data: pd.DataFrame,
        widgets: dict,
        layout: pn.Column,
    ) -> None:
        super().__init__(transactions_data, holdings_data, widgets, layout)

        # Initialize merger-specific widgets if not already present
        if "stock_select" not in self.widgets:
            self.widgets["stock_select"] = CustomAutoCompleteInput(
                name="Old Stock (Merged Out)",
                options=self.transactions_data[col.SYMBOL].unique().tolist(),
                case_sensitive=False,
            )

        if "isin_input" not in self.widgets:
            self.widgets["isin_input"] = CustomTextInput(name="ISIN", disabled=True)

        if "transactions_date_select" not in self.widgets:
            self.widgets["transactions_date_select"] = CustomDatePicker(
                name="Merger Date", end=date.today()
            )

        if "quantity_input" not in self.widgets:
            self.widgets["quantity_input"] = CustomFloatInput(
                name="New Shares Received", disabled=True
            )

        if "original_quantity_input" not in self.widgets:
            self.widgets["original_quantity_input"] = CustomFloatInput(
                name="Original Shares (Historical Balance)", disabled=False
            )

        if "new_stock_input" not in self.widgets:
            self.widgets["new_stock_input"] = CustomAutoCompleteInput(
                name="New Stock Symbol (Resulting)",
                options=self.transactions_data[col.SYMBOL].unique().tolist(),
                case_sensitive=False,
            )

        if "ratio_input" not in self.widgets:
            self.widgets["ratio_input"] = CustomFloatInput(
                name="Swap Ratio (New shares per Old share)",
                value=1.0,
                step=0.01,
            )
            self.widgets["ratio_input"].param.watch(
                self._on_ratio_or_base_qty_change, "value"
            )

        # Watchers for auto-calculation
        self.widgets["stock_select"].param.watch(self._on_stock_or_date_change, "value")
        self.widgets["transactions_date_select"].param.watch(
            self._on_stock_or_date_change, "value"
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

        # Convert trade date to datetime for comparison if needed
        df[col.TRADE_DATE] = pd.to_datetime(df[col.TRADE_DATE]).dt.date

        # Filter transactions on or before the event date
        df = df[df[col.TRADE_DATE] <= event_date]

        if df.empty:
            return 0.0

        # Take the last row's Total Quantity
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
        """Auto-update resulting quantity when ratio or base quantity changes."""
        original_qty = self.widgets["original_quantity_input"].value
        ratio = self.widgets["ratio_input"].value

        if original_qty is not None and ratio is not None:
            self.widgets["quantity_input"].value = round(original_qty * ratio, 1)

    def show_layout(self) -> None:
        """Construct and display the merger entry UI layout."""
        objs = [
            pn.pane.Markdown("## Add Merger Details", styles={"margin-bottom": "0px"}),
            pn.layout.Divider(),
        ]

        objs.extend(
            [
                pn.Row(
                    self.widgets["stock_select"],
                    self.widgets["transactions_date_select"],
                    sizing_mode="stretch_width",
                    styles={"gap": "16px"},
                ),
                self.widgets["new_stock_input"],
                pn.Row(
                    self.widgets["original_quantity_input"],
                    self.widgets["ratio_input"],
                    self.widgets["quantity_input"],
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
        """Process merger submission and save to merger.csv."""
        new_stock = self.widgets["new_stock_input"].value
        qty = self.widgets["quantity_input"].value
        event_date = self.widgets["transactions_date_select"].value
        ratio = self.widgets["ratio_input"].value
        old_stock = self.widgets["stock_select"].value
        original_qty = self.widgets["original_quantity_input"].value

        if not new_stock:
            pn.state.notifications.warning("Please enter the new stock symbol.")
            return {}

        if not old_stock:
            pn.state.notifications.warning("Please select the old stock symbol.")
            return {}

        # Data structure for merger.csv (single row)
        data = {
            col.SYMBOL: new_stock,
            col.TRADE_DATE: event_date,
            col.QUANTITY: float(qty),
            col.PARENT_SYMBOL: old_stock,
            col.PARENT_QUANTITY: float(original_qty),
            col.RATIO: float(ratio),
        }

        try:
            self.append_row_to_csv(Path(const.LOCAL_DATA_PATH / const.MERGER_CSV), data)
            return data

        except Exception as e:
            log.error("Failed to save merger event: %s", e)
            pn.state.notifications.error(f"Failed to save: {e}")
            return {}
