from datetime import date
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.webapp.tab_stocks.corporate_events_manager.ipo_inputs_manager import CorporateEventHandler
from mFinix.util import log

class DemergerInputsManager(CorporateEventHandler):
    def show_layout(self) -> None:
        self.layout.objects = [
            "## Add Demerger Details",
            self.widgets["transactions_date_select"],
            self.widgets["quantity_input"],
            pn.Row(
                self.widgets["submit_button"],
                self.widgets["cancel_button"],
                align="end",
            ),
        ]

    def process_submission(self) -> Dict[str, Any]:
        symbol = self.widgets["stock_select"].value
        qty = self.widgets["quantity_input"].value
        event_date = self.widgets["transactions_date_select"].value

        data = {
            col.SYMBOL: symbol,
            col.TRADE_DATE: event_date,
            col.QUANTITY: float(qty),
        }

        self.append_row_to_csv(Path(const.LOCAL_DATA_PATH / const.DEMERGER_CSV), data)
        return data
