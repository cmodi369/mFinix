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
            self.data["stocks_tab"] = prepare_stocks_tab_data()

        self.tab_data = self.data["stocks_tab"]

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

        self.layout = pn.Column()
        self._initial_layout()

        log.info("%s tab initialized successfully.", self.NAME)

    def _initialize_widgets(self):
        """Initialize tab widgets"""

        widgets = {}

        is_up_to_date = check_data_files_up_to_date()
        btn_type = "primary" if is_up_to_date else "warning"
        icon = "cloud-check" if is_up_to_date else "exclamation-triangle"
        name = "Update Data" if is_up_to_date else "Data Outdated - Update Now"

        widgets["update_data_btn"] = pn.widgets.Button(
            name=name,
            icon=icon,
            button_type=btn_type,
            width=200,
            margin=(0, 10),
            css_classes=["action-button"],
        )

        # Summary Cards - Initialized as HTML panes
        widgets["portfolio_value_card"] = pn.pane.HTML(
            self._get_summary_card_html("Total Value", 0),
            css_classes=["summary-card"],
            sizing_mode="stretch_width",
        )

        widgets["portfolio_xirr_card"] = pn.pane.HTML(
            self._get_summary_card_html("Portfolio XIRR", 0, is_percent=True),
            css_classes=["summary-card"],
            sizing_mode="stretch_width",
        )

        widgets["discrepancies_card"] = pn.pane.HTML(
            self._get_discrepancy_card_html(0), sizing_mode="stretch_width"
        )

        widgets["fix_discrepancy_btn"] = pn.widgets.Button(
            name="Fix Now",
            css_classes=["fix-now-btn"],
            width=80,
            margin=(12, 0, 0, 0),
            visible=False,
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
            layout="fit_data",
            pagination="local",
            formatters={
                col.XIRR: "html",
                col.PNL_PERCENTAGE: "html",
                col.QUANTITY: NumberFormatter(format="0,0.0"),
                col.CURRENT_PRICE: NumberFormatter(format="0,0.00"),
                col.AVG_BUY_PRICE: NumberFormatter(format="0,0.00"),
                col.BUY_VALUE: NumberFormatter(format="0,0.00"),
                col.PRESENT_VALUE: NumberFormatter(format="0,0.00"),
                col.PNL: "html",
                col.STATUS_ICON: "html",
                col.SYMBOL: "html",
            },
            buttons={
                "open": "<i class='fa fa-list-alt'></i>",
                "edit": "<i class='fa fa-pencil-square'></i>",
            },
            titles=col_name_mapping,
            disabled=True,
            theme=UIStyles.TABLE_THEME,
            css_classes=["holdings-table"],
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
            row_height=55,
            show_index=False,
            sizing_mode="stretch_width",
            widths={col.STATUS_ICON: 60},
        )

        return widgets

    def _get_summary_card_html(self, label, value, is_percent=False):
        """Generate HTML for summary cards without badges"""
        val_str = f"{value:.2f}%" if is_percent else f"₹ {value:.2f} L"

        return f"""
        <div class="summary-label">{label}</div>
        <div class="summary-value-container">
            <div class="summary-value">{val_str}</div>
        </div>
        """

    def _get_discrepancy_card_html(self, count):
        """Generate HTML for discrepancy card label and value"""
        status_color = "#e74c3c" if count > 0 else "#2ecc71"
        return f"""
        <div class="summary-label">Discrepancies</div>
        <div style="font-size: 2.2rem; font-weight: 700; color: {status_color};">{count:02d}</div>
        """

    def _add_callbacks(self) -> None:
        """Add all callbacks"""

        self.tab_widgets["stocks_xirr_table"].on_click(self._table_click_cb)
        self.tab_widgets["update_data_btn"].on_click(
            self._open_manual_data_fetch_window
        )
        self.tab_widgets["fix_discrepancy_btn"].on_click(
            lambda e: self._open_event_entry_window()
        )

    def _initialize_tab_data(self):
        """Update summary cards with actual data"""
        portfolio_value = self.tab_data["portfolio_value"] / 100000
        portfolio_xirr = self.tab_data["portfolio_xirr"]
        discrepancy_count = self.tab_data["stocks_xirr_data"][col.IS_DISCREPANCY].sum()

        self.tab_widgets["portfolio_value_card"].object = self._get_summary_card_html(
            "Total Value", portfolio_value
        )
        self.tab_widgets["portfolio_xirr_card"].object = self._get_summary_card_html(
            "Portfolio XIRR", portfolio_xirr, is_percent=True
        )
        self.tab_widgets["discrepancies_card"].object = self._get_discrepancy_card_html(
            discrepancy_count
        )

        self.tab_widgets["fix_discrepancy_btn"].visible = bool(discrepancy_count > 0)
        status_color = "#e74c3c" if discrepancy_count > 0 else "#2ecc71"
        self.tab_widgets["fix_discrepancy_btn"].styles = {"color": status_color}

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
            self.layout.objects = self.transactions_manager.layout

    def _open_auto_corp_actions_window(self):
        self.auto_corp_manager.initialize()
        if self.panel_modal:
            self.panel_modal.open(
                self.auto_corp_manager.layout, "⚡ Auto Corporate Actions"
            )
        else:
            self.layout.objects = self.auto_corp_manager.layout

    def _open_event_entry_window(self):
        self.event_manager.initialize()
        if self.panel_modal:
            self.panel_modal.open(self.event_manager.layout, "✏️ Add Manual Events")
        else:
            self.layout.objects = self.event_manager.layout

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
            self.layout.objects = self.manual_data_manager.layout

    def _refresh_tables(self):
        """Update tables and indicators with new data."""
        self._initialize_tab_data()

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

        # Apply HTML formatters to the dataframe before updating table value
        df = self.tab_data["stocks_xirr_data"].copy()

        # Status Icon Formatter
        def format_status(row):
            is_discrepancy = row[col.IS_DISCREPANCY]
            color = "#e74c3c" if is_discrepancy else "#2ecc71"
            bg = (
                "rgba(231, 76, 60, 0.1)"
                if is_discrepancy
                else "rgba(46, 204, 113, 0.1)"
            )
            icon = "exclamation" if is_discrepancy else "check"
            return f'<div class="status-icon" style="background-color: {bg}; color: {color};"><i class="fa-solid fa-{icon}"></i></div>'

        # Stock Name Formatter
        def format_stock_name(row):
            symbol = row[col.SYMBOL]
            isin = row.get(col.ISIN, "")
            return f'<div class="stock-info"><div class="stock-name">{symbol}</div><div class="stock-isin">{isin}</div></div>'

        # P&L Formatter
        def format_pnl(row):
            val = row[col.PNL]
            perc = row[col.PNL_PERCENTAGE]
            color = UIStyles.POSITIVE_COLOR if val >= 0 else UIStyles.NEGATIVE_COLOR
            sign = "+" if val >= 0 else ""
            return f'<div class="pnl-container"><div class="pnl-value" style="color: {color};">{sign}₹ {val:,.2f}</div><div class="pnl-percent" style="color: {color};">{perc:+.2f}%</div></div>'

        df[col.STATUS_ICON] = df.apply(format_status, axis=1)
        df[col.SYMBOL] = df.apply(format_stock_name, axis=1)
        df[col.PNL] = df.apply(format_pnl, axis=1)
        df[col.PNL_PERCENTAGE] = ""  # Hidden or merged
        df[col.XIRR] = df[col.XIRR].apply(
            lambda x: f'<div style="font-weight: 700; color: {UIStyles.POSITIVE_COLOR if x>=0 else UIStyles.NEGATIVE_COLOR};">{x:+.2f}%</div>'
        )

        self.tab_widgets["stocks_xirr_table"].value = df[display_columns]

    def _initial_layout(self):
        """Initialize tab layout"""
        self._initialize_tab_data()
        self._refresh_tables()  # Initial format

        # Custom Buttons for Header
        auto_corp_btn = pn.widgets.Button(
            name="Auto Corp Actions",
            icon="bolt",
            button_type="light",
            width=160,
            css_classes=["action-button"],
        )
        auto_corp_btn.on_click(lambda e: self._open_auto_corp_actions_window())

        add_manual_btn = pn.widgets.Button(
            name="Add Manual Event",
            icon="circle-plus",
            button_type="light",
            width=160,
            css_classes=["action-button"],
        )
        add_manual_btn.on_click(lambda e: self._open_event_entry_window())

        # Header Row
        header_row = pn.Row(
            auto_corp_btn,
            add_manual_btn,
            pn.widgets.MenuButton(
                name="More",
                items=["Show Portfolio", "All Transactions"],
                button_type="light",
                width=100,
            ),
            pn.Spacer(sizing_mode="stretch_width"),
            self.tab_widgets["update_data_btn"],
            sizing_mode="stretch_width",
            align="center",
        )

        # Summary Section
        summary_row = pn.Row(
            self.tab_widgets["portfolio_value_card"],
            self.tab_widgets["portfolio_xirr_card"],
            pn.Row(
                self.tab_widgets["discrepancies_card"],
                self.tab_widgets["fix_discrepancy_btn"],
                css_classes=["summary-card"],
                sizing_mode="stretch_width",
                styles={"align-items": "center"},
            ),
            sizing_mode="stretch_width",
            styles={"gap": "20px"},
        )

        # Holdings Section Header
        holdings_header = pn.Row(
            pn.pane.HTML(
                f'<div style="font-size: 1.5rem; font-weight: 700;">Your Holdings <span style="font-size: 0.9rem; background: var(--neutral-fill-rest); padding: 4px 12px; border-radius: 12px; color: var(--neutral-foreground-hint); margin-left: 10px;">{len(self.tab_data["stocks_xirr_data"])} Stocks</span></div>'
            ),
            pn.Spacer(sizing_mode="stretch_width"),
            align="center",
            margin=(20, 0, 10, 0),
        )

        # Pagination Footer
        footer = pn.Row(
            pn.pane.Markdown(
                "*Note: XIRR calculation requires transaction history for at least 3 months.*",
                styles={
                    "color": "var(--neutral-foreground-hint)",
                    "font-size": "0.85rem",
                },
            ),
            pn.Spacer(sizing_mode="stretch_width"),
            pn.widgets.Button(name="Previous", button_type="light", width=80),
            pn.widgets.Button(name="Next", button_type="primary", width=60),
            sizing_mode="stretch_width",
            margin=(20, 0),
        )

        self.layout.objects = [
            pn.Column(
                header_row,
                pn.layout.Divider(),
                summary_row,
                holdings_header,
                self.tab_widgets["stocks_xirr_table"],
                footer,
                css_classes=["main-container"],
                sizing_mode="stretch_width",
            )
        ]
