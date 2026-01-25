"""
Data reader module for Kite (Zerodha) trading platform.

This module provides classes and functions to read trading data from Zerodha's
Kite platform exported CSV files.

Classes:
    KiteDataReader: Main reader class for Kite platform data
    _TradeBookProcessor: Private helper class for tradebook data processing
    _LedgerProcessor: Private helper class for ledger data processing
    _HoldingProcessor: Private helper class for holdings data processing

Functions:
    read_tradebook_data: Read and process tradebook CSV files
    read_ledger_data: Read and process ledger CSV files
    read_holding_data: Read and process holdings Excel file
"""

import re
from datetime import date
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

import mFinix.constants.columns as col
import mFinix.constants.constants as const


class _TradeBookProcessor:
    """Private helper class for processing tradebook data.

    Handles the transformation of raw tradebook CSV data into a standardized format.
    """

    @staticmethod
    def process(tradebook_df: pd.DataFrame) -> pd.DataFrame:
        """Process raw tradebook data.

        Parameters
        ----------
        tradebook_df : pd.DataFrame
            Raw tradebook dataframe from CSV files.

        Returns
        -------
        pd.DataFrame
            Processed tradebook with calculated columns and formatted data.
        """
        # Remove duplicates
        tradebook_df = tradebook_df.drop_duplicates(
            subset=["trade_id", "order_id", "order_execution_time"]
        )

        # Format datetime column to date
        tradebook_df[col.TRADE_DATE] = pd.to_datetime(
            tradebook_df[col.TRADE_DATE]
        ).dt.date

        # Sort data based on trading dates and trade type
        tradebook_df = tradebook_df.sort_values(
            by=[col.TRADE_DATE, col.TRADE_TYPE]
        ).reset_index(drop=True)

        # Set negative quantity for sell transactions
        tradebook_df.loc[tradebook_df[col.TRADE_TYPE].eq(const.SELL), col.QUANTITY] = (
            tradebook_df[col.QUANTITY] * -1
        )

        # Calculate transaction amount
        tradebook_df[col.TRANSACTION_AMOUNT] = (
            tradebook_df[col.PRICE] * tradebook_df[col.QUANTITY]
        )

        # Calculate cumulative quantity by ISIN
        tradebook_df[col.TOTAL_QUANTITY] = tradebook_df.groupby(col.ISIN)[
            col.QUANTITY
        ].cumsum()

        # Extract symbol (remove suffix like -EQ)
        tradebook_df[col.SYMBOL] = tradebook_df[col.SYMBOL].str.split("-").str[0]

        return tradebook_df


class _LedgerProcessor:
    """Private helper class for processing ledger data.

    Handles the transformation of raw ledger CSV data.
    """

    @staticmethod
    def process(ledger_df: pd.DataFrame) -> pd.DataFrame:
        """Process raw ledger data.

        Parameters
        ----------
        ledger_df : pd.DataFrame
            Raw ledger dataframe from CSV file.

        Returns
        -------
        pd.DataFrame
            Processed ledger with formatted datetime columns.
        """
        ledger_df = ledger_df.dropna()
        ledger_df[col.POSTING_DATE] = pd.to_datetime(ledger_df[col.POSTING_DATE])

        return ledger_df


class _HoldingProcessor:
    """Private helper class for processing holdings data.

    Handles the transformation of raw holdings Excel data, including extraction
    of metadata (as_on_date) and table data from Zerodha's exported Excel sheets.
    """

    @staticmethod
    def process(holdings_df: pd.DataFrame) -> pd.DataFrame:
        """Process raw holdings data from Zerodha Excel export.

        Removes metadata rows, cleans column names, and adds the as_on_date column.

        Parameters
        ----------
        holdings_df : pd.DataFrame
            Raw holdings dataframe from Excel file containing metadata and table rows.

        Returns
        -------
        pd.DataFrame
            Processed holdings with cleaned data and as_on_date column.
        """

        as_on_date = _HoldingProcessor._extract_as_on_date(holdings_df)

        # Remove rows before the header row (which contains column names)
        # The header row is typically around row 21
        header_row = _HoldingProcessor._find_header_row(holdings_df)
        if header_row is not None:
            holdings_df = holdings_df.iloc[header_row:].reset_index(drop=True)
            holdings_df = holdings_df.rename(columns=holdings_df.iloc[0]).drop(holdings_df.index[0])

        # Use the first row (original header) as column names if not already set
        if header_row is not None and list(holdings_df.columns).count('Unnamed') > 0:
            # Re-read and set proper headers
            pass

        # Remove rows/columns with all NaN values
        holdings_df = holdings_df.dropna(axis=0, how="all").dropna(axis=1, how="all")

        # Add as_on_date column if provided
        if as_on_date is not None:
            holdings_df['as_on_date'] = pd.to_datetime(as_on_date)

        return holdings_df

    @staticmethod
    def _find_header_row(df: pd.DataFrame) -> int:
        """Find the row containing table headers.

        Headers typically contain strings like 'Symbol', 'ISIN', 'Quantity', etc.

        Parameters
        ----------
        df : pd.DataFrame
            The raw dataframe to search.

        Returns
        -------
        int or None
            The index of the header row, or None if not found.
        """
        for idx, row in df.iterrows():
            row_str = ' '.join(str(v) for v in row if pd.notna(v)).lower()
            if 'symbol' in row_str and 'isin' in row_str:
                return idx
        return None

    @staticmethod
    def _extract_as_on_date(df: pd.DataFrame) -> str:
        """Extract the 'as on' date from the holdings statement header.

        The date appears in text like "Equity Holdings Statement as on 2026-01-25"

        Parameters
        ----------
        df : pd.DataFrame
            Raw dataframe from Excel.

        Returns
        -------
        str
            The extracted date string, or None if not found.
        """
        for idx, row in df.iterrows():
            row_str = ' '.join(str(v) for v in row if pd.notna(v))
            if 'as on' in row_str.lower():
                # Try to extract date in format YYYY-MM-DD
                match = re.search(r'(\d{4}-\d{2}-\d{2})', row_str)
                if match:
                    return match.group(1)
        return None


class KiteDataReader:
    """Reader class for Kite (Zerodha) platform trading data.

    This class handles reading and processing CSV files exported from Zerodha's
    Kite trading platform.

    Parameters
    ----------
    docs_path : Path, optional
        Path to the directory containing data files. Defaults to the configured
        DOCS_PATH from constants.

    """

    def __init__(self, docs_path: Path = None) -> None:
        """Initialize KiteDataReader.

        Parameters
        ----------
        docs_path : Path, optional
            Path to the directory containing data files. If None, uses the
            configured DOCS_PATH from constants.
        """
        self.docs_path = docs_path or const.DOCS_PATH

    def read_tradebook(self) -> pd.DataFrame:
        """Read and process tradebook data from Kite CSV files.

        Reads all tradebook CSV files matching the Zerodha tradebook identifier,
        combines them, removes duplicates, and applies standardized processing.

        Returns
        -------
        pd.DataFrame
            Processed tradebook data with calculated columns.

        """
        ret_data = pd.DataFrame()
        for file in self.docs_path.glob(f"{const.TRADEBOOK_ID_ZERODHA}*"):
            ret_data = pd.concat([ret_data, pd.read_csv(file)])

        if ret_data.empty:
            raise FileNotFoundError(
                f"No tradebook files found in {self.docs_path} "
                f"starting with '{const.TRADEBOOK_ID_ZERODHA}'"
            )

        return _TradeBookProcessor.process(ret_data)

    def read_ledger(self) -> pd.DataFrame:
        """Read and process ledger data from Kite CSV file.

        Reads the latest ledger CSV file matching the Zerodha ledger identifier
        and applies standardized processing.

        Returns
        -------
        pd.DataFrame
            Processed ledger data with formatted datetime columns.

        """
        files = [
            file
            for file in self.docs_path.glob(f"{const.LEDGER_ID_ZERODHA}*.csv")
            if file.is_file()
        ]

        if not files:
            raise FileNotFoundError(
                f"No ledger files found in {self.docs_path} "
                f"matching pattern '{const.LEDGER_ID_ZERODHA}*.csv'"
            )

        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        ledger_data = pd.read_csv(latest_file)

        return _LedgerProcessor.process(ledger_data)

    def read_holdings(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Read and process holdings data from Kite Excel file.

        Reads the holdings Excel file from the configured directory, extracts
        separate data for Equity and Mutual Funds, and applies standardized processing.

        """
        holdings_file = self.docs_path / const.HOLDING_EXCEL_ZERODHA

        if not holdings_file.is_file():
            raise FileNotFoundError(f"Holdings file not found at {holdings_file}")

        # Read the Excel file with all sheets
        sheets = pd.read_excel(holdings_file, sheet_name=['Equity', 'Mutual Funds'], header=None)

        # Process Equity sheet
        equity_df = sheets['Equity']
        equity_df = _HoldingProcessor.process(equity_df)

        # Process Mutual Funds sheet
        mf_df = sheets['Mutual Funds']
        mf_df = _HoldingProcessor.process(mf_df)

        return equity_df, mf_df

# Module-level convenience functions for backward compatibility and ease of use
_DEFAULT_READER: KiteDataReader = None


def _get_default_reader() -> KiteDataReader:
    """Get or create the default KiteDataReader instance.

    Returns
    -------
    KiteDataReader
        The default reader instance.
    """
    global _DEFAULT_READER
    if _DEFAULT_READER is None:
        _DEFAULT_READER = KiteDataReader()
    return _DEFAULT_READER


def read_tradebook_data() -> pd.DataFrame:
    """Read and process tradebook data from Kite CSV files.

    This is a convenience function that uses the default KiteDataReader instance.
    For more control over the reader, instantiate KiteDataReader directly.

    Returns
    -------
    pd.DataFrame
        Processed tradebook data with calculated columns.

    See Also
    --------
    KiteDataReader.read_tradebook : Direct method for reading tradebook data
    """
    return _get_default_reader().read_tradebook()


def read_ledger_data() -> pd.DataFrame:
    """Read and process ledger data from Kite CSV file.

    This is a convenience function that uses the default KiteDataReader instance.
    For more control over the reader, instantiate KiteDataReader directly.

    Returns
    -------
    pd.DataFrame
        Processed ledger data with formatted datetime columns.

    See Also
    --------
    KiteDataReader.read_ledger : Direct method for reading ledger data
    """
    return _get_default_reader().read_ledger()


def read_holding_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read and process holdings data from Kite Excel file.

    This is a convenience function that uses the default KiteDataReader instance.
    For more control over the reader, instantiate KiteDataReader directly.

    Returns
    -------
    dict
        Dictionary with keys:
        - 'equity': DataFrame with equity holdings data
        - 'mutual_funds': DataFrame with mutual funds holdings data
        Both dataframes include an 'as_on_date' column extracted from the Excel file.

    Raises
    ------
    FileNotFoundError
        If no holdings file is found in the configured directory.

    See Also
    --------
    KiteDataReader.read_holdings : Direct method for reading holdings data
    """
    return _get_default_reader().read_holdings()
