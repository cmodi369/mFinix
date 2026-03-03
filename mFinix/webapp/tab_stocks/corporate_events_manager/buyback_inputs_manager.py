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


class BuybackInputsManager(CorporateEventHandler):
    def show_layout(self) -> None:
        self.layout.objects = [
            "## Add Buyback Details",
            self.widgets["transactions_date_select"],
            self.widgets["quantity_input"],
            pn.Row(
                self.widgets["submit_button"],
                align="end",
            ),
        ]

    def process_submission(self) -> Dict[str, Any]:
        symbol = self.widgets["stock_select"].value
        qty = self.widgets["quantity_input"].value
        event_date = self.widgets["transactions_date_select"].value

        # Validation: check holdings
        applicable_trade_data = self.transactions_data[
            (self.transactions_data[col.SYMBOL] == symbol)
            & (self.transactions_data[col.TRADE_DATE] < event_date)
        ]

        current_holding = 0
        if not applicable_trade_data.empty:
            current_holding = applicable_trade_data[col.TOTAL_QUANTITY].iloc[-1]

        if current_holding < qty:
            msg = f"Insufficient holdings for {symbol} on {event_date}. Current: {current_holding}, Requested: {qty}"
            pn.state.notifications.error(msg)
            log.warning(msg)
            return {}

        data = {
            col.SYMBOL: symbol,
            col.TRADE_DATE: event_date,
            col.QUANTITY: -float(qty),  # Buyback reduces quantity
        }

        self.append_row_to_csv(Path(const.LOCAL_DATA_PATH / const.BUYBACK_CSV), data)
        return data
