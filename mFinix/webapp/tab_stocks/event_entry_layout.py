import csv
from datetime import date
from pathlib import Path

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.constants.constants as const
import mFinix.webapp.webapp_constants as webapp_const
from mFinix.core.nse_webscraping import NSEDataNotFoundError, extract_past_ipo_data
from mFinix.util import log
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

    @run_once
    def initialize(self):
        self._event_layout_mapping: dict[str, callable] = {
            webapp_const.EventOptions.ADD_BONUS: self._show_add_bonus_layout,
            webapp_const.EventOptions.ADD_SPLIT: self._show_add_split_layout,
            webapp_const.EventOptions.ADD_TRANSACTION: self._show_add_transactions_layout,
            webapp_const.EventOptions.ADD_IPO: self._show_add_ipo_layout,
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
        self.widgets["stock_select"].param.watch(self._auto_fill_ipo_data, "value")

    def show_add_event_inputs_layout(self, event):
        self._event_selected = event.new
        self._event_layout_mapping[event.new]()

    def _show_add_ipo_layout(self):
        """Display IPO entry layout with auto-fetch button."""
        # Create fetch IPO data button
        fetch_ipo_button = pn.widgets.Button(
            name="Fetch IPO Data", button_type="success", width=150
        )
        fetch_ipo_button.on_click(self._on_fetch_ipo_data)

        self._layout.objects = [
            "## Add IPO Buy Details",
            pn.Row(
                pn.Column(
                    pn.pane.Markdown("**Fetch from NSE:**"),
                    fetch_ipo_button,
                ),
                align="start",
            ),
            self.widgets["transactions_date_select"],
            self.widgets["quantity_input"],
            self.widgets["price_input"],
            pn.Row(
                self.widgets["submit_button"],
                self.widgets["cancel_button"],
                align="end",
            ),
        ]

    def _show_add_bonus_layout(self):
        pass

    def _show_add_transactions_layout(self):
        pass

    def _show_add_split_layout(self):
        pass

    def _on_click_submit_cb(self, _):
        # add notification
        msg = f"{self._event_selected.split(' ')[1]} data is added for {self.widgets['stock_select'].value}."
        pn.state.notifications.success(msg)
        log.info(msg)

        # add data in csv file
        data = {
            col.SYMBOL: self.widgets["stock_select"].value,
            col.ISIN: self.widgets["isin_input"].value,
            col.TRADE_DATE: self.widgets["transactions_date_select"].value,
            col.QUANTITY: self.widgets["quantity_input"].value,
            col.PRICE: self.widgets["price_input"].value,
        }

        self._append_row_to_csv(Path(const.LOCAL_DATA_PATH / const.IPO_CSV), data)

        # add data in transactions data
        self.transactions_data.loc[len(self.transactions_data)] = data

    @staticmethod
    def _append_row_to_csv(file_path: Path, new_row: dict):
        file_exists = file_path.exists()

        # Append the row to the CSV file
        with open(file_path, mode="a" if file_exists else "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(new_row.keys()))

            if not file_exists:
                writer.writeheader()  # Write the header if creating a new file

            writer.writerow(new_row)  # Append the new row

    def _update_isin(self, event):
        self.widgets["isin_input"].value = self.transactions_data[
            self.transactions_data[col.SYMBOL] == event.new
        ][col.ISIN].iloc[-1]

    def _auto_fill_ipo_data(self, event):
        """Callback to auto-fill IPO data when stock is selected (called when ADD_IPO event is active)."""
        # Only auto-fill if IPO event is currently selected
        if self._event_selected == webapp_const.EventOptions.ADD_IPO:
            self._fetch_and_fill_ipo_data(event.new)

    def _on_fetch_ipo_data(self, _):
        """Button callback to manually fetch IPO data."""
        stock_name = self.widgets["stock_select"].value
        if stock_name:
            self._fetch_and_fill_ipo_data(stock_name)
        else:
            pn.state.notifications.warning("Please select a stock first.")

    def _fetch_and_fill_ipo_data(self, stock_name: str):
        """Fetch IPO data from NSE and populate form fields.

        Parameters
        ----------
        stock_name : str
            Stock symbol to fetch IPO data for
        """
        try:
            # Fetch IPO data from NSE
            ipo_data = extract_past_ipo_data(stock_name)

            # Auto-fill the form fields
            self.widgets["price_input"].value = float(ipo_data["ipo_price"])
            self.widgets["transactions_date_select"].value = pd.Timestamp(
                ipo_data["ipo_date"]
            ).date()

            # Auto-fill quantity if available
            if not pd.isna(ipo_data["ipo_quantity"]):
                self.widgets["quantity_input"].value = float(ipo_data["ipo_quantity"])

            log.info(
                "IPO data fetched and auto-filled for %s: price=%.2f, date=%s",
                stock_name,
                ipo_data["ipo_price"],
                ipo_data["ipo_date"],
            )
            pn.state.notifications.success(
                f"IPO data fetched for {stock_name}: "
                f"Price Rs.{ipo_data['ipo_price']}, "
                f"Date {ipo_data['ipo_date'].strftime('%Y-%m-%d')}"
            )

        except NSEDataNotFoundError:
            log.warning("No IPO data found for %s", stock_name)
            pn.state.notifications.warning(
                f"No IPO data found for {stock_name}. Please enter manually."
            )

        except Exception as exc:
            log.error("Error fetching IPO data for %s: %s", stock_name, str(exc))
            pn.state.notifications.error(
                f"Error fetching IPO data: {str(exc)}. Please enter manually."
            )
