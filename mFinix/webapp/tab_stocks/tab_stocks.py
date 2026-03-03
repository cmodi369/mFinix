from typing import Any, Optional

import numpy as np
import panel as pn
from bokeh.models.widgets.tables import NumberFormatter

import mFinix.constants.columns as col
import mFinix.constants.constants as const
import mFinix.constants.panel_constants as pn_const
import mFinix.webapp.webapp_constants as webapp_const
from mFinix.util import log
from mFinix.webapp.panel_modal import PanelModal
from mFinix.webapp.tab_stocks.auto_corporate_actions_manager import (
    AutoCorporateActionsManager,
)
from mFinix.webapp.tab_stocks.event_entry_layout import EventDataManager
from mFinix.webapp.tab_stocks.manual_data_fetch_manager import ManualDataFetchManager
from mFinix.webapp.tab_stocks.transactions_layout import TransactionsManager
from mFinix.webapp.tab_stocks.utility import (
    check_data_files_up_to_date,
    prepare_stocks_tab_data,
)
from mFinix.webapp.webapp_constants import UIStyles


class TabStocks:
    NAME: str = "Stocks"

    ICON: str = "clipboard-data"

    def __init__(self, data: dict[str, Any], widgets: dict[str, Any], dashboard=None):
        self.data = data
        self.dashboard = dashboard
        self.panel_modal = PanelModal(dashboard) if dashboard else None
        self.widgets = widgets

        if "stocks_tab" not in self.data:
            # initialize stocks tab data dictionary
            self.tab_data = self.data["stocks_tab"] = {}

            # prepare all required datasets
            self.tab_data.update(prepare_stocks_tab_data())

        # initialize tab widgets
        self.tab_widgets = self._initialize_widgets()
        self.widgets["stocks_tab"] = self.tab_widgets

        # initialize event data manager
        self.event_manager = EventDataManager(self.tab_data, self.tab_widgets)

        # initialize transactions manager
        self.transactions_manager = TransactionsManager(self.tab_data, self.tab_widgets)

        # initialize auto corporate actions manager
        self.auto_corp_manager = AutoCorporateActionsManager(
            self.tab_data, self.tab_widgets, panel_modal=self.panel_modal
        )

        # initialize manual data fetch manager
        self.manual_data_manager = ManualDataFetchManager(
            self.tab_data, self.tab_widgets, self._refresh_tables, self.panel_modal
        )

        # add callbacks
        self._add_callbacks()

        # initialize tab layout
        self._menu_layout = pn.Row(
            self.tab_widgets["tools_menu"],
            pn.Spacer(sizing_mode="stretch_width"),
            self.tab_widgets["update_data_btn"],
            styles={
                "border-bottom": "1px solid black",
                "padding-bottom": "10px",
                "align-items": "center",
            },
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

        is_up_to_date = check_data_files_up_to_date()
        btn_type = "primary" if is_up_to_date else "warning"
        icon = "cloud-check" if is_up_to_date else "exclamation-triangle"
        name = "Update Data" if is_up_to_date else "Data Outdated - Update Now"

        widgets["update_data_btn"] = pn.widgets.Button(
            name=name,
            icon=icon,
            button_type=btn_type,
            width=250,
            margin=0,
            styles={"font-weight": "bold"},
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
            col.STATUS_ICON: "Status",
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
                col.STATUS_ICON: "html",
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
                "tooltipGenerationMode": "hover",
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
            widths={col.STATUS_ICON: 60},
        )

        # Summary Badge
        discrepancy_count = self.tab_data["stocks_xirr_data"][col.IS_DISCREPANCY].sum()
        widgets["discrepancy_badge"] = pn.pane.HTML(
            (
                f"""
            <div style="background-color: {'#e74c3c' if discrepancy_count > 0 else '#2ecc71'}; 
                        color: white; padding: 5px 15px; border-radius: 20px; 
                        font-weight: bold; display: flex; align-items: center; gap: 8px;">
                <i class="fa fa-{'exclamation-triangle' if discrepancy_count > 0 else 'check-circle'}"></i>
                {discrepancy_count} Discrepancies Found
            </div>
            """
                if discrepancy_count > 0
                else ""
            ),
            align="center",
        )

        # add styles
        widgets["stocks_xirr_table"].style.apply(
            self._apply_pnl_color,
            subset=[col.PNL, col.PNL_PERCENTAGE, col.XIRR],
        )
        widgets["stocks_xirr_table"].style.apply(
            self._apply_discrepancy_row_style,
            axis=1,
        )

        return widgets

    def _add_callbacks(self) -> None:
        """Add all callbacks"""

        self.tab_widgets["stocks_xirr_table"].on_click(self._table_click_cb)
        self.tab_widgets["tools_menu"].on_click(self._open_selected_layout)
        self.tab_widgets["update_data_btn"].on_click(
            self._open_manual_data_fetch_window
        )

    def _open_selected_layout(self, event):
        """Open Selected Layout"""
        layout_mapping_dict = {
            webapp_const.StockMenuOptions.SHOW_PORTFOLIO: self._initial_layout,
            webapp_const.StockMenuOptions.SHOW_TRANSACTIONS: self._open_transactions_window,
            webapp_const.StockMenuOptions.AUTO_CORP_ACTIONS: self._open_auto_corp_actions_window,
            webapp_const.StockMenuOptions.ADD_MANUAL_EVENTS: self._open_event_entry_window,
        }

        layout_mapping_dict[event.new]()

    @staticmethod
    def _apply_discrepancy_row_style(row):
        """Highlight rows with discrepancies"""
        if row[col.IS_DISCREPANCY]:
            return [
                "background-color: rgba(231, 76, 60, 0.15); font-weight: 500"
            ] * len(row)
        return [""] * len(row)

    @staticmethod
    def _apply_pnl_color(val):
        """Color-code P&L, P&L % and XIRR values"""
        return np.where(
            val > 0,
            f"color: {UIStyles.POSITIVE_COLOR} !important; font-weight: bold",
            np.where(
                val < 0,
                f"color: {UIStyles.NEGATIVE_COLOR} !important; font-weight: bold",
                f"color: {UIStyles.NEUTRAL_COLOR} !important",
            ),
        )

    def _open_transactions_window(self, selected_isin: Optional[str] = None):
        self.transactions_manager.initialize()
        self.transactions_manager.show_selected_transactions(selected_isin)
        if self.panel_modal:
            self.panel_modal.open(self.transactions_manager.layout, "📋 Transactions")
        else:
            self.layout.objects = [self._menu_layout] + self.transactions_manager.layout

    def _open_auto_corp_actions_window(self):
        self.auto_corp_manager.initialize()
        if self.panel_modal:
            self.panel_modal.open(
                self.auto_corp_manager.layout, "⚡ Auto Corporate Actions"
            )
        else:
            self.layout.objects = [self._menu_layout] + self.auto_corp_manager.layout

    def _open_event_entry_window(self):
        self.event_manager.initialize()
        if self.panel_modal:
            self.panel_modal.open(self.event_manager.layout, "✏️ Add Manual Events")
        else:
            self.layout.objects = [self._menu_layout] + self.event_manager.layout

    def _table_click_cb(self, event):
        selected_isin = self.tab_data["stocks_xirr_data"][
            self.tab_data["stocks_xirr_data"].index == event.row
        ][col.ISIN].item()
        if event.column == "open":
            self._open_transactions_window(selected_isin)

        elif event.column == "edit":
            self._open_event_entry_window()

    def _open_manual_data_fetch_window(self, event=None):
        self.manual_data_manager.initialize()
        if self.panel_modal:
            self.panel_modal.open(
                self.manual_data_manager.layout, "Update Data from Zerodha"
            )
        else:
            self.layout.objects = [self._menu_layout] + self.manual_data_manager.layout

    def _refresh_tables(self):
        """Update tables and indicators with new data."""
        self.tab_widgets["portfolio_xirr_text"].value = self.tab_data["portfolio_xirr"]

        portfolio_value = self.tab_data["portfolio_value"]
        if portfolio_value < 100000:
            display_value = portfolio_value / 1000
            format_str = "₹ {value:.2f} K"
        else:
            display_value = portfolio_value / 100000
            format_str = "₹ {value:.2f} L"

        self.tab_widgets["portfolio_value_text"].value = display_value
        self.tab_widgets["portfolio_value_text"].format = format_str

        # Tabulator requires .value update with scoped columns
        display_columns = [
            col.STATUS_ICON,
            col.SYMBOL,
            col.TOTAL_QUANTITY,
            col.AVG_BUY_PRICE,
            col.BUY_VALUE,
            col.CURRENT_PRICE,
            col.PRESENT_VALUE,
            col.PNL,
            col.PNL_PERCENTAGE,
            col.XIRR,
        ]
        self.tab_widgets["stocks_xirr_table"].value = self.tab_data["stocks_xirr_data"][
            display_columns
        ]

        # Discrepancy badge update
        discrepancy_count = self.tab_data["stocks_xirr_data"][col.IS_DISCREPANCY].sum()
        self.tab_widgets["discrepancy_badge"].object = (
            f"""
            <div style="background-color: {'#e74c3c' if discrepancy_count > 0 else '#2ecc71'}; 
                        color: white; padding: 5px 15px; border-radius: 20px; 
                        font-weight: bold; display: flex; align-items: center; gap: 8px;">
                <i class="fa fa-{'exclamation-triangle' if discrepancy_count > 0 else 'check-circle'}"></i>
                {discrepancy_count} Discrepancies Found
            </div>
            """
            if discrepancy_count > 0
            else ""
        )

        # update button state if data is now up to date
        is_up_to_date = check_data_files_up_to_date()
        if is_up_to_date:
            self.tab_widgets["update_data_btn"].name = "Update Data"
            self.tab_widgets["update_data_btn"].button_type = "primary"
            self.tab_widgets["update_data_btn"].icon = "cloud-check"

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
            pn.Row(
                pn.pane.Markdown(
                    "### Holdings",
                    styles={
                        "font-size": "1.2rem",
                        "font-weight": "600",
                        "color": "#2c3e50",
                    },
                ),
                pn.Spacer(),
                self.tab_widgets["discrepancy_badge"],
                sizing_mode="stretch_width",
                styles={"align-items": "center", "gap": "15px"},
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
