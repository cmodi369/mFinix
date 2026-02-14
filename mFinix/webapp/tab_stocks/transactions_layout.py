import pandas as pd
import panel as pn

import mFinix.constants.columns as col
from mFinix.util import log
from mFinix.webapp.tab_stocks.utility import run_once
from mFinix.webapp.webapp_constants import COL_NAME_MAPPING, EventOptions


class TransactionsManager:
    def __init__(self, data_dict: dict, widgets: dict):
        self.data_dict = data_dict
        self.transactions_data = self.data_dict["transactions_data"]

        self.widgets = widgets["transactions_wids"] = {}

        self._columns = [
            col.SYMBOL,
            col.TRADE_DATE,
            col.TRADE_TYPE,
            col.QUANTITY,
            col.PRICE,
            col.TRANSACTION_AMOUNT,
            col.TOTAL_QUANTITY,
        ]

    @run_once
    def initialize(self):
        self.widgets["transactions_table"] = pn.widgets.Tabulator(
            self.transactions_data[self._columns],
            titles=COL_NAME_MAPPING,
            show_index=False,
            header_filters=True,
            layout="fit_data",
            pagination="local",
            disabled=True,
        )

        self._add_callbacks()

        log.info("Initialize transactions table layout")

    @property
    def layout(self):
        return [
            pn.Column(
                pn.pane.Markdown(
                    "### Transactions",
                    styles={
                        "font-size": "1.2rem",
                        "font-weight": "600",
                        "color": "#2c3e50",
                    },
                ),
                self.widgets["transactions_table"],
                styles=webapp_const.SidebarStyles.CARD_STYLE,
            )
        ]

    def _add_callbacks(self):
        pass

    def show_selected_transactions(self, selected_isin: str):
        log.info("Open transactions table for %s.", selected_isin)

        if selected_isin is None:
            transactions_data = self.data_dict["transactions_data"]
        else:
            transactions_data = self.data_dict["transactions_data"][
                self.data_dict["transactions_data"][col.ISIN] == selected_isin
            ].reset_index(drop=True)

        # update transactions data in table
        self.widgets["transactions_table"].value = transactions_data[self._columns]
