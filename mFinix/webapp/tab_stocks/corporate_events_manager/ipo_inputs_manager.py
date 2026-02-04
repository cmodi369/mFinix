"""
This module encapsulates all IPO-related user input handling, layouts, callbacks,
and processing logic.
"""

import csv
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.core.nse_webscraping import NSEDataNotFoundError, extract_past_ipo_data
from mFinix.util import log

# ============================================================================
# Abstract Base Class for Corporate Events
# ============================================================================


class CorporateEventHandler(ABC):
    """Abstract base class for corporate event handling.

    Defines the interface for handling different types of corporate events
    (IPO, splits, dividends, etc.). Subclasses implement specific event logic
    while maintaining a consistent interface for layout creation and data submission.

    Parameters
    ----------
    transactions_data : pd.DataFrame
        DataFrame containing existing transaction data with stock symbols and ISINs
    holdings_data : pd.DataFrame
        DataFrame containing existing equity holdings data with stock symbols and quantities
    widgets : dict
        Dictionary of UI widgets including common widgets and event-specific widgets
    layout : pn.Column
        Panel Column object to render the event entry layout
    """

    def __init__(
        self,
        transactions_data: pd.DataFrame,
        holdings_data: pd.DataFrame,
        widgets: dict,
        layout: pn.Column,
    ) -> None:
        self.transactions_data = transactions_data
        self.equity_holdings_data = holdings_data
        self.widgets = widgets
        self.layout = layout

    @abstractmethod
    def show_layout(self) -> None:
        """Display the event entry layout.

        Subclasses implement this to create and display their specific
        event entry UI components.
        """
        pass

    @abstractmethod
    def process_submission(self) -> Dict[str, Any]:
        """Process the submitted event data.

        Subclasses implement this to validate, parse, and prepare data
        for submission (CSV storage and in-memory updates).

        Returns
        -------
        dict
            Dictionary containing event data to be stored, with column names
            as keys and values as the data to store
        """
        pass

    @staticmethod
    def append_row_to_csv(file_path: Path, new_row: Dict[str, Any]) -> None:
        """Append a row to a CSV file.

        Creates file and header if it doesn't exist. Appends the new row
        to the CSV file.

        Parameters
        ----------
        file_path : Path
            Path to the CSV file
        new_row : dict
            Dictionary containing row data to append (keys are column names)
        """
        file_exists = file_path.exists()

        # if same entry is already present, skip appending and raise error message
        if file_exists:
            with open(file_path, mode="r", newline="") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if all(
                        str(row[key]) == str(value) for key, value in new_row.items()
                    ):
                        log.warning(
                            "Duplicate entry found in CSV for %s. Skipping append.",
                            new_row,
                        )
                        pn.state.notifications.warning(
                            "Duplicate entry found in records. Entry not added."
                        )
                        return

        with open(file_path, mode="a" if file_exists else "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(new_row.keys()))

            if not file_exists:
                writer.writeheader()

            writer.writerow(new_row)

            # add notification
            msg = f"Data is added for {new_row[col.SYMBOL]}."
            pn.state.notifications.success(msg)
            log.info(msg)


# ============================================================================
# IPO Inputs Manager
# ============================================================================


class IPOInputsManager(CorporateEventHandler):
    """Manager for IPO (Initial Public Offering) data entry and processing.

    Handles all IPO-related user inputs including layout creation, NSE data
    fetching, form population, and data submission. Supports both automatic
    data fetching from NSE and manual entry.

    Parameters
    ----------
    transactions_data : pd.DataFrame
        DataFrame containing existing transaction data with stock symbols and ISINs
    equity_holdings_data : pd.DataFrame
        DataFrame containing existing equity holdings data with stock symbols and quantities
    widgets : dict
        Dictionary of UI widgets including common widgets shared across events
    layout : pn.Column
        Panel Column object to render the IPO entry layout
    """

    def __init__(
        self,
        transactions_data: pd.DataFrame,
        equity_holdings_data: pd.DataFrame,
        widgets: dict,
        layout: pn.Column,
    ) -> None:
        super().__init__(transactions_data, equity_holdings_data, widgets, layout)
        self._fetch_ipo_button = pn.widgets.Button(
            name="Fetch IPO Data", button_type="success", width=150
        )
        self._fetch_ipo_button.on_click(self._on_fetch_ipo_button_click)

    def show_layout(self) -> None:
        """
        Display the IPO entry layout with auto-fetch button.
        """
        self.layout.objects = [
            "## Add IPO Buy Details",
            pn.Row(
                pn.Column(
                    pn.pane.Markdown("**Fetch from NSE:**"),
                    self._fetch_ipo_button,
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

    def process_submission(self) -> Dict[str, Any]:
        """Process submitted IPO data and store to CSV and DataFrame.

        Collects IPO data from form fields, stores to CSV file, and updates
        the transactions DataFrame.

        Returns
        -------
        dict
            Dictionary with IPO transaction data including symbol, ISIN, date,
            quantity, and price
        """
        data = {
            col.SYMBOL: self.widgets["stock_select"].value,
            col.ISIN: self.widgets["isin_input"].value,
            col.TRADE_DATE: self.widgets["transactions_date_select"].value,
            col.QUANTITY: self.widgets["quantity_input"].value,
            col.PRICE: self.widgets["price_input"].value,
            col.TRANSACTION_AMOUNT: self.widgets["quantity_input"].value
            * self.widgets["price_input"].value,
        }

        self.append_row_to_csv(Path(const.LOCAL_DATA_PATH / const.IPO_CSV), data)
        self.transactions_data.loc[len(self.transactions_data)] = data.update(
            {
                col.TRADE_TYPE: const.BUY,
                col.TOTAL_QUANTITY: self.widgets["quantity_input"].value,
            }
        )

        return data

    def fetch_ipo_data(self, stock_name: str) -> bool:
        """Fetch and populate IPO data from NSE for a given stock.

        Retrieves IPO information (price, date, quantity) from NSE for the
        specified stock and auto-fills the corresponding form fields.

        Parameters
        ----------
        stock_name : str
            Stock symbol/name to fetch IPO data for

        Returns
        -------
        bool
            True if data was successfully fetched and populated, False otherwise
        """
        if not stock_name:
            pn.state.notifications.warning("Please select a stock first.")
            return False

        try:
            ipo_data = extract_past_ipo_data(stock_name)
            self._populate_ipo_form_fields(ipo_data)
            log.info(
                "IPO data fetched and auto-filled for %s: price=%.2f, date=%s",
                stock_name,
                ipo_data["ipo_price"],
                ipo_data["link_removal_date"],
            )
            pn.state.notifications.success(
                f"IPO data fetched for {stock_name}: "
                f"Price Rs.{ipo_data['ipo_price']}, "
                f"Date {ipo_data['link_removal_date'].strftime('%Y-%m-%d')}"
            )
            return True

        except NSEDataNotFoundError:
            log.warning("No IPO data found for %s", stock_name)
            pn.state.notifications.warning(
                f"No IPO data found for {stock_name}. Please enter manually."
            )
            return False

        except Exception as exc:
            log.error("Error fetching IPO data for %s: %s", stock_name, str(exc))
            pn.state.notifications.error(
                f"Error fetching IPO data: {str(exc)}. Please enter manually."
            )
            return False

    def set_auto_fill_callback(self, callback: Callable) -> None:
        """Set the callback for auto-fill when stock selection changes.

        Parameters
        ----------
        callback : Callable
            Callback function to execute when stock is selected for IPO entry
        """
        self.widgets["stock_select"].param.watch(callback, "value")

    # ========================================================================
    # Private Methods - Request Handling
    # ========================================================================

    def _on_fetch_ipo_button_click(self, _) -> None:
        """Handle button click for manual IPO data fetch."""
        stock_name = self.widgets["stock_select"].value
        self.fetch_ipo_data(stock_name)

    # ========================================================================
    # Private Methods - Data Fetching and Transformation
    # ========================================================================

    def calculate_ipo_quantity_from_holdings(self, stock_name: str) -> Optional[float]:
        """Calculate IPO quantity from quantity difference with holdings and transactions data.

        Parameters
        ----------
        stock_name : str
            Stock symbol to calculate IPO quantity for

        Returns
        -------
        float or None
            The IPO quantity if found,
            None otherwise
        """
        if not stock_name:
            return None

        if stock_name in self.equity_holdings_data[col.SYMBOL]:
            # Calculate latest quantity from holdings data
            quantity_from_holdings = self.equity_holdings_data.loc[
                self.equity_holdings_data[col.SYMBOL] == stock_name
            ][col.QUANTITY].item()

        else:
            quantity_from_holdings = 0

        # Calculate total quantity from transactions data
        quantity_from_transactions = (
            self.transactions_data.loc[self.transactions_data[col.SYMBOL] == stock_name]
            .sort_values(by=col.TRADE_DATE)
            .iloc[-1][col.TOTAL_QUANTITY]
        )

        # Calculate difference in quantity to infer IPO quantity
        ipo_quantity = int(quantity_from_holdings - quantity_from_transactions)

        # Check if quantity is negative (indicating IPO allotment)
        if ipo_quantity != 0:
            log.info(
                "IPO quantity calculated from transaction data and holdings data for %s: %.2f",
                stock_name,
                ipo_quantity,
            )
            return ipo_quantity

        # If quantity is zero or positive, no IPO data found in transactions
        log.info(
            "Transaction and holdings data for stock %s does not indicate IPO.",
            stock_name,
        )
        pn.state.notifications.info(
            f"Transaction and holdings data for {stock_name} does not indicate IPO. "
            "Please fetch IPO data from NSE or enter manually."
        )
        return None

    def _populate_ipo_form_fields(self, ipo_data: Dict[str, Any]) -> None:
        """Populate form fields with fetched IPO data.

        Parameters
        ----------
        ipo_data : dict
            Dictionary containing ipo_price, ipo_date, and optionally ipo_quantity
        """
        self.widgets["price_input"].value = float(ipo_data["ipo_price"])
        self.widgets["transactions_date_select"].value = pd.Timestamp(
            ipo_data[
                "link_removal_date"
            ]  # link removal date is considered as IPO date for XIRR calculation else it returns None
        ).date()
        self.widgets["quantity_input"].value = (
            self.calculate_ipo_quantity_from_holdings(
                self.widgets["stock_select"].value
            )
        )
