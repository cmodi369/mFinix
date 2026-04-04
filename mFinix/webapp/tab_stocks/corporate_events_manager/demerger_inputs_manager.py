from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.core.corporate_actions import save_approved_action
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


class DemergerInputsManager(CorporateEventHandler):
    def __init__(
        self,
        transactions_data: pd.DataFrame,
        holdings_data: pd.DataFrame,
        widgets: dict,
        layout: pn.Column,
    ) -> None:
        super().__init__(transactions_data, holdings_data, widgets, layout)

        # Initialize demerger-specific widgets if not present
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

        if "quantity_input" not in self.widgets:
            self.widgets["quantity_input"] = CustomFloatInput(
                name="New Shares Received"
            )

        if "original_quantity_input" not in self.widgets:
            self.widgets["original_quantity_input"] = CustomFloatInput(
                name="Original Shares (on record date)"
            )

        if "new_stock_input" not in self.widgets:
            self.widgets["new_stock_input"] = CustomAutoCompleteInput(
                name="New Stock Symbol (received from demerger)",
                options=self.transactions_data[col.SYMBOL].unique().tolist(),
                case_sensitive=False,
            )

        if "ratio_input" not in self.widgets:
            self.widgets["ratio_input"] = CustomFloatInput(
                name="Ratio (new shares per original share)",
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

        # If it's the latest data and matched with recent holdings,
        # but here we specifically want the historical balance.
        # Most of our transaction DataFrames have a 'Total Quantity' column representing running balance.
        # Let's sort and take the last row's Total Quantity.
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
        objs = [
            pn.pane.Markdown(
                "## Add Demerger Details", styles={"margin-bottom": "0px"}
            ),
            pn.layout.Divider(),
        ]

        objs.extend(
            [
                self.widgets["stock_select"],
                self.widgets["isin_input"],
                self.widgets["transactions_date_select"],
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
        new_stock = self.widgets["new_stock_input"].value
        qty = self.widgets["quantity_input"].value
        event_date = self.widgets["transactions_date_select"].value
        ratio = self.widgets["ratio_input"].value

        if not new_stock:
            pn.state.notifications.warning("Please enter the new stock symbol.")
            return {}

        data = {
            col.SYMBOL: new_stock,
            col.TRADE_DATE: event_date,
            col.QUANTITY: float(qty),
            col.PARENT_SYMBOL: self.widgets["stock_select"].value,
            col.PARENT_QUANTITY: float(self.widgets["original_quantity_input"].value),
            col.RATIO: float(ratio),
        }

        try:
            self.append_row_to_csv(
                Path(const.LOCAL_DATA_PATH / const.DEMERGER_CSV), data
            )

        except Exception as e:
            log.error("Failed to save demerger event: %s", e)
            pn.state.notifications.error(f"Failed to save: {e}")
            return {}
