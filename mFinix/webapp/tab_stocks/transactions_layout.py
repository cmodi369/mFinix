import numpy as np
import pandas as pd
import panel as pn
from bokeh.models.widgets.tables import NumberFormatter

import mFinix.constants.columns as col
import mFinix.webapp.webapp_constants as webapp_const
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
            layout="fit_columns",
            pagination="local",
            page_size=15,
            disabled=True,
            theme=webapp_const.UIStyles.TABLE_THEME,
            configuration={
                "columnHeaderVertAlign": "middle",
                "renderVertical": "basic",
            },
            text_align={
                col.QUANTITY: "right",
                col.PRICE: "right",
                col.TRANSACTION_AMOUNT: "right",
                col.TOTAL_QUANTITY: "right",
            },
            formatters={
                col.QUANTITY: NumberFormatter(format="0,0"),
                col.PRICE: NumberFormatter(format="0,0.00"),
                col.TRANSACTION_AMOUNT: NumberFormatter(format="0,0.00"),
                col.TOTAL_QUANTITY: NumberFormatter(format="0,0"),
            },
            sizing_mode="stretch_width",
            min_height=550,
        )

        # Apply styles for TRADE_TYPE
        self.widgets["transactions_table"].style.apply(
            self._apply_trade_type_color,
            subset=[col.TRADE_TYPE],
        )

        self._add_callbacks()

        log.info("Initialize transactions table layout")

    @property
    def layout(self):
        """Return the layout components for the modal or inline display."""
        return [
            pn.Column(
                self.widgets.get("discrepancy_alert", pn.Spacer(height=0)),
                self.widgets["transactions_table"],
                sizing_mode="stretch_width",
            )
        ]

    def _add_callbacks(self):
        pass

    @staticmethod
    def _apply_trade_type_color(val):
        """Color-code Trade Type values"""
        styles = []
        for v in val:
            v_upper = str(v).upper()
            if v_upper == "BUY":
                color = webapp_const.UIStyles.POSITIVE_COLOR
            elif v_upper == "SELL":
                color = webapp_const.UIStyles.NEGATIVE_COLOR
            elif v_upper in ["SPLIT", "BONUS", "MERGER", "DEMERGER"]:
                color = webapp_const.UIStyles.ACCENT_COLOR
            else:
                color = webapp_const.UIStyles.NEUTRAL_COLOR
            styles.append(f"color: {color} !important; font-weight: bold")
        return styles

    def show_selected_transactions(self, selected_isin: str):
        log.info("Open transactions table for %s.", selected_isin)

        stocks_xirr_data = self.data_dict["stocks_xirr_data"]
        discrepancy_info = None

        if selected_isin is None:
            transactions_data = self.data_dict["transactions_data"]
        else:
            transactions_data = self.data_dict["transactions_data"][
                self.data_dict["transactions_data"][col.ISIN] == selected_isin
            ].reset_index(drop=True)

            # Check for discrepancy
            stock_row = stocks_xirr_data[stocks_xirr_data[col.ISIN] == selected_isin]
            if not stock_row.empty and stock_row[col.IS_DISCREPANCY].iloc[0]:
                discrepancy_info = {
                    "calculated": stock_row[col.TOTAL_QUANTITY].iloc[0],
                    "broker": stock_row[col.HOLDING_QUANTITY].iloc[0],
                }

        # Update alert
        if discrepancy_info:
            self.widgets["discrepancy_alert"] = pn.pane.Alert(
                f"### ⚠️ Holding Discrepancy Detected\n"
                f"The calculated quantity based on your transactions (**{discrepancy_info['calculated']}**) "
                f"does not match the actual quantity reported by the broker (**{discrepancy_info['broker']}**). "
                f"Please manually verify and add any missing transactions.",
                alert_type="danger",
            )
        else:
            self.widgets["discrepancy_alert"] = pn.Spacer(height=0)

        # update transactions data in table
        self.widgets["transactions_table"].value = transactions_data[self._columns]
        self.widgets["transactions_table"].param.trigger("value")
