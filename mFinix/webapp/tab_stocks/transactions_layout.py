import numpy as np
import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.webapp.webapp_constants as webapp_const
from mFinix.util import log
from mFinix.webapp.tab_stocks.utility import run_once
from mFinix.webapp.webapp_constants import UIStyles


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
        # We will use Python-side formatting to prepare HTML strings in the dataframe,
        # exactly like the holdings table in tab_stocks.py.
        self.widgets["transactions_table"] = pn.widgets.Tabulator(
            pd.DataFrame(columns=self._columns),
            titles={
                col.SYMBOL: "STOCK NAME",
                col.TRADE_DATE: "TRADE DATE",
                col.TRADE_TYPE: "TRADE TYPE",
                col.QUANTITY: "QUANTITY",
                col.PRICE: "PRICE",
                col.TRANSACTION_AMOUNT: "TRANSACTION AMOUNT",
                col.TOTAL_QUANTITY: "TOTAL QUANTITY",
            },
            show_index=False,
            header_filters=True,
            layout="fit_columns",
            pagination="local",
            page_size=12,
            disabled=True,
            theme=webapp_const.UIStyles.TABLE_THEME,
            css_classes=["transactions-table"],
            configuration={
                "columnHeaderVertAlign": "middle",
            },
            formatters={
                col.SYMBOL: "html",
                col.TRADE_TYPE: "html",
                col.QUANTITY: "html",
                col.PRICE: "html",
                col.TRANSACTION_AMOUNT: "html",
                col.TOTAL_QUANTITY: "html",
            },
            sizing_mode="stretch_width",
            min_height=500,
            row_height=60,
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

    def show_selected_transactions(self, selected_isin: str):
        log.info("Open transactions table for %s.", selected_isin)

        stocks_xirr_data = self.data_dict["stocks_xirr_data"]
        discrepancy_info = None

        if selected_isin is None:
            df = self.data_dict["transactions_data"].copy()
        else:
            df = (
                self.data_dict["transactions_data"][
                    self.data_dict["transactions_data"][col.ISIN] == selected_isin
                ]
                .copy()
                .reset_index(drop=True)
            )

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

        # Handle NaNs and data preparation
        df = df.fillna(0)

        # Apply HTML formatting exactly like in tab_stocks.py
        def format_stock_cell(row):
            s = row[col.SYMBOL]
            return f"""
                <div class="transaction-stock-cell">
                    <div class="stock-name" style="font-weight: 700;">{s}</div>
                </div>
            """

        def format_trade_type_cell(row):
            t = str(row[col.TRADE_TYPE]).upper()
            badge_class = f"badge-{t.lower()}"
            return f'<span class="trade-badge {badge_class}">{t}</span>'

        def format_qty_cell(row):
            t = str(row[col.TRADE_TYPE]).upper()
            v = row[col.QUANTITY]
            if t in ["SPLIT", "BONUS", "MERGER", "DEMERGER"]:
                fmt = f"{v}" if v != 0 else "--"
            else:
                fmt = f"{v:,.2f}"
            return f'<div style="text-align: right; font-weight: 500;">{fmt}</div>'

        def format_price_cell(row):
            t = str(row[col.TRADE_TYPE]).upper()
            v = row[col.PRICE]
            if t == "DIVIDEND":
                fmt = f"₹{v:,.2f} / share"
            elif t in ["SPLIT", "BONUS", "MERGER", "DEMERGER"]:
                fmt = "--"
            else:
                fmt = f"₹{v:,.2f}"
            return f'<div style="text-align: right; font-weight: 500;">{fmt}</div>'

        def format_amount_cell(row):
            v = row[col.TRANSACTION_AMOUNT]
            if v == 0:
                return '<div style="text-align: right; color: var(--neutral-foreground-hint);">--</div>'
            color = UIStyles.POSITIVE_COLOR if v > 0 else UIStyles.NEGATIVE_COLOR
            sign = "+" if v > 0 else "-"
            return f'<div style="text-align: right; font-weight: 700; color: {color};">{sign} ₹{abs(v):,.2f}</div>'

        def format_total_qty_cell(row):
            v = row[col.TOTAL_QUANTITY]
            return f'<div style="text-align: right; font-weight: 500;">{v:,.1f}</div>'

        # Apply formatters to the relevant columns
        display_df = df.copy()
        display_df[col.SYMBOL] = df.apply(format_stock_cell, axis=1)
        display_df[col.TRADE_TYPE] = df.apply(format_trade_type_cell, axis=1)
        display_df[col.QUANTITY] = df.apply(format_qty_cell, axis=1)
        display_df[col.PRICE] = df.apply(format_price_cell, axis=1)
        display_df[col.TRANSACTION_AMOUNT] = df.apply(format_amount_cell, axis=1)
        display_df[col.TOTAL_QUANTITY] = df.apply(format_total_qty_cell, axis=1)

        # Update table value
        self.widgets["transactions_table"].value = display_df[self._columns]
        # Force a hard refresh
        self.widgets["transactions_table"].param.trigger("value")
