from datetime import date

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.webapp.webapp_constants as webapp_const
from mFinix.util import log
from mFinix.webapp.tab_stocks.corporate_events_manager import IPOInputsManager
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
        self.transactions_data = self.data_dict["transactions_data"]
        self.widgets = widgets["event_wids"] = {
            "submit_button": pn.widgets.Button(name="Submit", button_type="primary"),
            "cancel_button": pn.widgets.Button(name="Cancel", button_type="danger"),
        }

        self._event_layout_mapping = {}

        self._event_submit_cb_mapping = {}

        self._event_selected = None

        self._layout = pn.Column(pn.Spacer(height=500))

        self._ipo_manager = None

    @run_once
    def initialize(self):
        self._ipo_manager = IPOInputsManager(
            self.transactions_data,
            self.widgets,
            self._layout,
        )

        self._event_layout_mapping: dict[str, callable] = {
            webapp_const.EventOptions.ADD_BONUS: self._show_add_bonus_layout,
            webapp_const.EventOptions.ADD_SPLIT: self._show_add_split_layout,
            webapp_const.EventOptions.ADD_TRANSACTION: self._show_add_transactions_layout,
            webapp_const.EventOptions.ADD_IPO: self._ipo_manager.show_layout,
        }

        self._initialize_common_widgets()

        self._add_callbacks()

        log.info("Initialize manual events entry layout")

    @property
    def layout(self):
        return [
            pn.Row(self.widgets["stock_select"], self.widgets["isin_input"]),
            self.widgets["events_menu"],
            self._layout,
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

        # Add callback for auto-fill IPO data when stock is selected for IPO event
        self._ipo_manager.set_auto_fill_callback(self._auto_fill_ipo_data)

    def show_add_event_inputs_layout(self, event):
        self._event_selected = event.new
        self._event_layout_mapping[event.new]()

    def _show_add_bonus_layout(self):
        pass

    def _show_add_transactions_layout(self):
        pass

    def _show_add_split_layout(self):
        pass

    def _on_click_submit_cb(self, _):
        # Delegate data processing to appropriate manager
        if self._event_selected == webapp_const.EventOptions.ADD_IPO:
            self._ipo_manager.process_submission()

    def _update_isin(self, event):
        self.widgets["isin_input"].value = self.transactions_data[
            self.transactions_data[col.SYMBOL] == event.new
        ][col.ISIN].iloc[-1]

    def _auto_fill_ipo_data(self, event):
        """Callback to auto-fill IPO data when stock is selected (called when ADD_IPO event is active)."""
        # Only auto-fill if IPO event is currently selected
        if self._event_selected == webapp_const.EventOptions.ADD_IPO:
            self._ipo_manager.fetch_ipo_data(event.new)
