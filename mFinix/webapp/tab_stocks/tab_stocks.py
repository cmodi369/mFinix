from typing import Any, Optional

import numpy as np
import panel as pn
from bokeh.models.widgets.tables import NumberFormatter

import mFinix.constants.columns as col
import mFinix.constants.constants as const
import mFinix.constants.panel_constants as pn_const
import mFinix.webapp.webapp_constants as webapp_const
from mFinix.util import log
from mFinix.webapp.tab_stocks.event_entry_layout import EventDataManager
from mFinix.webapp.tab_stocks.transactions_layout import TransactionsManager
from mFinix.webapp.tab_stocks.utility import prepare_stocks_tab_data
from mFinix.webapp.webapp_constants import UIStyles


class TabStocks:
    NAME: str = "Stocks"

    ICON: str = "clipboard-data"

    def __init__(self, data: dict[str, Any], widgets: dict[str, Any]):
        self.data = data
        self.widgets = widgets

        if "stocks_tab" not in self.data:
            # initialize stocks tab data dictionary
            self.tab_data = self.data["stocks_tab"] = {}

            # prepare all required datasets
            self.tab_data.update(prepare_stocks_tab_data())

        # initialize tab widgets
        self.tab_widgets = self.widgets["stocks_tab"] = {}
        self.tab_widgets = self._initialize_widgets()

        # initialize event data manager
        self.event_manager = EventDataManager(self.tab_data, self.tab_widgets)

        # initialize transactions manager
        self.transactions_manager = TransactionsManager(self.tab_data, self.tab_widgets)

        # add callbacks
        self._add_callbacks()

        # initialize tab layout
        self._menu_layout = pn.Row(
            self.tab_widgets["tools_menu"],
            styles={"border-bottom": "1px solid black"},
            sizing_mode="stretch_width",
        )
        self.layout = pn.Column()
        self._initial_layout()

        log.info("%s tab initialized successfully.", self.NAME)

    def _initialize_widgets(self):
        """Initialize tab widgets"""

        widgets = {}

        widgets["tools_menu"] = pn.widgets.MenuButton(
            name="Tools",
            icon="category",
            items=webapp_const.STOCK_MENU_OPTIONS,
            button_type="light",
            width=200,
            margin=0,
        )

        widgets["portfolio_xirr_text"] = pn.indicators.Number(
            name="XIRR",
            value=self.tab_data["portfolio_xirr"],
            format="{value:.2f}%",
            font_size=UIStyles.INDICATOR_VALUE_SIZE,
            title_size=UIStyles.INDICATOR_TITLE_SIZE,
            colors=[(0, UIStyles.NEGATIVE_COLOR), (100, UIStyles.POSITIVE_COLOR)],
            styles={
                "background-color": UIStyles.INDICATOR_BG_COLOR,
                "border-radius": "10px",
                "padding": "15px",
                "box-shadow": "var(--elevation-shadow-1)",
                "margin": "10px",
                "border": "3px solid var(--neutral-stroke-input-rest)",
            },
        )

        portfolio_value = self.tab_data["portfolio_value"]
        if portfolio_value < 100000:
            display_value = portfolio_value / 1000
            format_str = "₹ {value:.2f} K"
        else:
            display_value = portfolio_value / 100000
            format_str = "₹ {value:.2f} L"

        widgets["portfolio_value_text"] = pn.indicators.Number(
            name="Total Value",
            value=display_value,
            format=format_str,
            font_size=UIStyles.INDICATOR_VALUE_SIZE,
            title_size=UIStyles.INDICATOR_TITLE_SIZE,
            styles={
                "background-color": UIStyles.INDICATOR_BG_COLOR,
                "border-radius": "10px",
                "padding": "15px",
                "box-shadow": "var(--elevation-shadow-1)",
                "margin": "10px",
                "border": "1px solid var(--neutral-stroke-input-rest)",
            },
        )

        col_name_mapping = {
            col.ISIN: "Symbol",
            col.SYMBOL: "Stock Name",
            col.TOTAL_QUANTITY: "Quantity",
            col.AVG_BUY_PRICE: "Buy Avg.",
            col.BUY_VALUE: "Buy Value",
            col.CURRENT_PRICE: "LTP",
            col.PRESENT_VALUE: "Present Value",
            col.PNL: "P&L",
            col.PNL_PERCENTAGE: "P&L %",
            col.XIRR: "XIRR",
        }
        widgets["stocks_xirr_table"] = pn.widgets.Tabulator(
            self.tab_data["stocks_xirr_data"][col_name_mapping.keys()],
            header_filters=True,
            layout="fit_data",
            pagination="local",
            formatters={
                col.XIRR: NumberFormatter(format="0.00%"),
                col.PNL_PERCENTAGE: NumberFormatter(format="0.00%"),
                col.QUANTITY: NumberFormatter(format="0,0"),
                col.CURRENT_PRICE: NumberFormatter(format="0,0.00"),
                col.AVG_BUY_PRICE: NumberFormatter(format="0,0.00"),
                col.BUY_VALUE: NumberFormatter(format="0,0.00"),
                col.PRESENT_VALUE: NumberFormatter(format="0,0.00"),
                col.PNL: NumberFormatter(format="0,0.00"),
            },
            buttons={
                "open": "<i class='fa fa-list-alt'></i>",
                "edit": "<i class='fa fa-pencil-square'></i>",
            },
            titles=col_name_mapping,
            disabled=True,
            theme=UIStyles.TABLE_THEME,
            configuration={
                "columnHeaderVertAlign": "middle",
            },
            text_align={
                col.TOTAL_QUANTITY: "right",
                col.AVG_BUY_PRICE: "right",
                col.BUY_VALUE: "right",
                col.CURRENT_PRICE: "right",
                col.PRESENT_VALUE: "right",
                col.PNL: "right",
                col.PNL_PERCENTAGE: "right",
                col.XIRR: "right",
            },
            row_height=UIStyles.TABLE_ROW_HEIGHT,
            show_index=False,
            sizing_mode="stretch_width",
        )

        # add styles
        widgets["stocks_xirr_table"].style.apply(
            self._apply_table_row_color,
            props="color:white;background-color:#e74c3c",
            axis=1,
            subset=[col.TOTAL_QUANTITY],
        )
        widgets["stocks_xirr_table"].style.apply(
            self._apply_pnl_color,
            subset=[col.PNL, col.PNL_PERCENTAGE, col.XIRR],
        )

        return widgets

    def _add_callbacks(self) -> None:
        """Add all callbacks"""

        self.tab_widgets["stocks_xirr_table"].on_click(self._table_click_cb)
        self.tab_widgets["tools_menu"].on_click(self._open_selected_layout)

    def _open_selected_layout(self, event):
        """Open Selected Layout"""
        layout_mapping_dict = {
            webapp_const.StockMenuOptions.SHOW_PORTFOLIO: self._initial_layout,
            webapp_const.StockMenuOptions.SHOW_TRANSACTIONS: self._open_transactions_window,
            webapp_const.StockMenuOptions.ADD_MANUAL_EVENTS: self._open_event_entry_window,
        }

        layout_mapping_dict[event.new]()

    @staticmethod
    def _apply_table_row_color(val, props=""):
        """Function to highlight rows with negative values in the 'quantity' column"""
        return np.where(val < 0, props, "")

    @staticmethod
    def _apply_pnl_color(val):
        """Color-code P&L, P&L % and XIRR values"""
        return np.where(
            val > 0,
            f"color: {UIStyles.POSITIVE_COLOR}; font-weight: bold",
            np.where(
                val < 0,
                f"color: {UIStyles.NEGATIVE_COLOR}; font-weight: bold",
                f"color: {UIStyles.NEUTRAL_COLOR}",
            ),
        )

    def _open_transactions_window(self, selected_isin: Optional[str] = None):
        self.transactions_manager.initialize()
        self.transactions_manager.show_selected_transactions(selected_isin)
        self.layout.objects = [self._menu_layout] + self.transactions_manager.layout

    def _open_event_entry_window(self):
        self.event_manager.initialize()
        self.layout.objects = [self._menu_layout] + self.event_manager.layout

    def _table_click_cb(self, event):
        selected_isin = self.tab_data["stocks_xirr_data"][
            self.tab_data["stocks_xirr_data"].index == event.row
        ][col.ISIN].item()
        if event.column == "open":
            self._open_transactions_window(selected_isin)

        elif event.column == "edit":
            self._open_event_entry_window()

    def _initial_layout(self):
        """Initialize tab layout"""

        # Portfolio Summary Card
        portfolio_summary_card = pn.Column(
            pn.pane.Markdown(
                "### Portfolio Summary",
                styles={
                    "font-size": "1.2rem",
                    "font-weight": "600",
                    "color": "#2c3e50",
                },
            ),
            pn.Row(
                self.tab_widgets["portfolio_xirr_text"],
                self.tab_widgets["portfolio_value_text"],
                sizing_mode="stretch_width",
                styles={"justify-content": "space-around"},
            ),
            styles=webapp_const.UIStyles.CARD_STYLE,
        )

        # Holdings Card
        holdings_card = pn.Column(
            pn.pane.Markdown(
                "### Holdings",
                styles={
                    "font-size": "1.2rem",
                    "font-weight": "600",
                    "color": "#2c3e50",
                },
            ),
            self.tab_widgets["stocks_xirr_table"],
            styles=webapp_const.UIStyles.CARD_STYLE,
        )

        self.layout.objects = [
            self._menu_layout,
            pn.Column(
                portfolio_summary_card,
                holdings_card,
                sizing_mode="stretch_width",
                styles={"gap": "20px", "padding": "20px"},
            ),
        ]
