from datetime import date

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.webapp.webapp_constants as webapp_const
from mFinix.util import log
from mFinix.webapp.tab_stocks.corporate_events_manager import (
    BonusInputsManager,
    BuybackInputsManager,
    DemergerInputsManager,
    IPOInputsManager,
    MergerInputsManager,
    SplitInputsManager,
    TransactionInputsManager,
)
from mFinix.webapp.tab_stocks.utility import run_once
from mFinix.webapp.widgets import (
    CustomAutoCompleteInput,
    CustomDatePicker,
    CustomFloatInput,
    CustomTextInput,
)


class EventDataManager:
    def __init__(self, data_dict: dict, widgets: dict):
        self.data_dict = data_dict
        self.recalculate_cb = None
        self.transactions_data = self.data_dict["transactions_data"]
        self.equity_holdings_data = self.data_dict["equity_holdings"]
        self.widgets = widgets["event_wids"] = {
            "submit_button": pn.widgets.Button(name="Submit", button_type="primary"),
        }

        self._event_layout_mapping = {}

        self._event_submit_cb_mapping = {}

        self._event_selected = None

        self._layout = pn.Column(pn.Spacer(height=500))

        self._ipo_manager = None

    @run_once
    def initialize(self):
        self._initialize_common_widgets()

        self._add_callbacks()

        self._ipo_manager = IPOInputsManager(
            self.transactions_data,
            self.equity_holdings_data,
            self.widgets,
            self._layout,
        )
        # Add callback for auto-fill IPO data when stock is selected for IPO event
        self._ipo_manager.set_auto_fill_callback(self._auto_fill_ipo_data)

        self._bonus_manager = BonusInputsManager(
            self.transactions_data,
            self.equity_holdings_data,
            self.widgets,
            self._layout,
        )

        self._split_manager = SplitInputsManager(
            self.transactions_data,
            self.equity_holdings_data,
            self.widgets,
            self._layout,
        )

        self._transaction_manager = TransactionInputsManager(
            self.transactions_data,
            self.equity_holdings_data,
            self.widgets,
            self._layout,
        )

        self._buyback_manager = BuybackInputsManager(
            self.transactions_data,
            self.equity_holdings_data,
            self.widgets,
            self._layout,
        )

        self._merger_manager = MergerInputsManager(
            self.transactions_data,
            self.equity_holdings_data,
            self.widgets,
            self._layout,
        )

        self._demerger_manager = DemergerInputsManager(
            self.transactions_data,
            self.equity_holdings_data,
            self.widgets,
            self._layout,
        )

        self._event_layout_mapping: dict[str, callable] = {
            webapp_const.EventOptions.ADD_BONUS: self._bonus_manager.show_layout,
            webapp_const.EventOptions.ADD_SPLIT: self._split_manager.show_layout,
            webapp_const.EventOptions.ADD_TRANSACTION: self._transaction_manager.show_layout,
            webapp_const.EventOptions.ADD_IPO: self._ipo_manager.show_layout,
            webapp_const.EventOptions.ADD_BUYBACK: self._buyback_manager.show_layout,
            webapp_const.EventOptions.ADD_MERGER: self._merger_manager.show_layout,
            webapp_const.EventOptions.ADD_DEMERGER: self._demerger_manager.show_layout,
        }

        log.info("Initialize manual events entry layout")

    @property
    def layout(self):
        """Return the layout components for the modal or inline display."""
        return [
            pn.Column(
                pn.Row(self.widgets["stock_select"], self.widgets["isin_input"]),
                self.widgets["events_menu"],
                self._layout,
                sizing_mode="stretch_width",
            )
        ]

    def _initialize_common_widgets(self):
        self.widgets["events_menu"] = pn.widgets.MenuButton(
            name="Add Event",
            items=webapp_const.EVENTS_OPTIONS,
            button_type="primary",
            width=200,
        )

        self.widgets["stock_select"] = CustomAutoCompleteInput(
            name="Stock Name",
            options=self.transactions_data[col.SYMBOL].unique().tolist(),
            case_sensitive=False,
        )

        self.widgets["isin_input"] = CustomTextInput(name="ISIN", disabled=True)

        self.widgets["transactions_date_select"] = CustomDatePicker(
            name="Date", end=date.today()
        )

        self.widgets["quantity_input"] = CustomFloatInput(name="Quantity")

        self.widgets["price_input"] = CustomFloatInput(name="Price")

    def _add_callbacks(self):
        self.widgets["events_menu"].on_click(self.show_add_event_inputs_layout)

        # add callbacks on button click
        self.widgets["submit_button"].on_click(self._on_click_submit_cb)

        self.widgets["stock_select"].param.watch(self._update_isin, "value")

    def show_add_event_inputs_layout(self, event):
        self._event_selected = event.new
        self._event_layout_mapping[event.new]()

    def _on_click_submit_cb(self, _):
        # Delegate data processing to appropriate manager
        manager_mapping = {
            webapp_const.EventOptions.ADD_IPO: self._ipo_manager,
            webapp_const.EventOptions.ADD_BONUS: self._bonus_manager,
            webapp_const.EventOptions.ADD_SPLIT: self._split_manager,
            webapp_const.EventOptions.ADD_TRANSACTION: self._transaction_manager,
            webapp_const.EventOptions.ADD_BUYBACK: self._buyback_manager,
            webapp_const.EventOptions.ADD_MERGER: self._merger_manager,
            webapp_const.EventOptions.ADD_DEMERGER: self._demerger_manager,
        }

        manager = manager_mapping.get(self._event_selected)
        if manager:
            result = manager.process_submission()
            if result and "state" in self.data_dict:
                self.data_dict["state"].param.trigger("refresh_event")

    def _update_isin(self, event):
        self.widgets["isin_input"].value = self.transactions_data[
            self.transactions_data[col.SYMBOL] == event.new
        ][col.ISIN].iloc[-1]

    def _auto_fill_ipo_data(self, event):
        """Callback to auto-fill IPO data when stock is selected (called when ADD_IPO event is active)."""
        # Only auto-fill if IPO event is currently selected
        if self._event_selected == webapp_const.EventOptions.ADD_IPO:
            self._ipo_manager.fetch_ipo_data(event.new)
