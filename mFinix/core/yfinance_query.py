"""
YFinance Query Module.

This module provides classes and utilities for querying financial data
from yfinance, including stock prices and corporate actions.

"""

from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
import yfinance as yf

import mFinix.constants.columns as col
from mFinix.util import log

# ============================================================================
# Custom Exceptions
# ============================================================================


class YFinanceQueryError(Exception):
    """Base exception for yfinance query operations."""

    pass


class YFinancePriceError(YFinanceQueryError):
    """Raised when stock price retrieval fails."""

    pass


class YFinanceCorporateActionsError(YFinanceQueryError):
    """Raised when corporate actions retrieval fails."""

    pass


# ============================================================================
# Data Response Types
# ============================================================================


class StockActionsData:
    """Container for stock corporate actions data.

    Encapsulates actions data returned from yfinance Ticker.actions.

    Attributes
    ----------
    actions : pd.DataFrame
        DataFrame containing stock actions (dividends, splits, etc.)
    ticker : str
        The stock ticker symbol
    """

    def __init__(self, actions: pd.DataFrame, ticker: str) -> None:
        """Initialize StockActionsData.

        Parameters
        ----------
        actions : pd.DataFrame
            Stock actions DataFrame
        ticker : str
            Stock ticker symbol
        """
        self.actions = actions
        self.ticker = ticker

    @property
    def is_empty(self) -> bool:
        """Check if actions data is empty.

        Returns
        -------
        bool
            True if actions DataFrame is empty
        """
        return self.actions.empty

    def get_ticker_name(self) -> str:
        """Extract base ticker name from full ticker.

        Removes exchange suffix (e.g., ".NS" from "TCS.NS").

        Returns
        -------
        str
            Base ticker name without exchange suffix
        """
        return self.ticker.split(".")[0]


# ============================================================================
# Data Parsers (Abstraction for parsing logic)
# ============================================================================


class StockDataParserInterface(ABC):
    """Abstract interface for stock data parsers."""

    @abstractmethod
    def parse(self, ticker_obj: yf.Ticker) -> Union[pd.DataFrame, Dict]:
        """Parse ticker data into structured format.

        Parameters
        ----------
        ticker_obj : yf.Ticker
            yfinance Ticker object

        Returns
        -------
        Union[pd.DataFrame, Dict]
            Parsed data in appropriate format

        Raises
        ------
        YFinanceQueryError
            If parsing fails
        """
        pass


class StockActionsParser(StockDataParserInterface):
    """Parser for stock corporate actions (dividends, splits).

    Extracts actions data from yfinance Ticker object and transforms
    into a structured StockActionsData object.
    """

    def parse(self, ticker_obj: yf.Ticker) -> StockActionsData:
        """Parse stock actions from yfinance Ticker.

        Parameters
        ----------
        ticker_obj : yf.Ticker
            yfinance Ticker object

        Returns
        -------
        StockActionsData
            Structured actions data with ticker and DataFrame

        Notes
        -----
        Converts timezone-aware datetime index to timezone-naive if necessary.
        """
        try:
            actions_data = ticker_obj.actions

            # Remove timezone information if present
            if isinstance(actions_data.index, pd.DatetimeIndex):
                if actions_data.index.tz is not None:
                    actions_data = actions_data.copy()
                    actions_data.index = actions_data.index.tz_localize(None)

            return StockActionsData(actions_data, ticker_obj.ticker)

        except Exception as exc:
            raise YFinanceCorporateActionsError(
                f"Failed to parse stock actions for {ticker_obj.ticker}: {str(exc)}"
            ) from exc


# ============================================================================
# YFinance Client Interface
# ============================================================================


class YFinanceClientInterface(ABC):
    """Abstract interface for yfinance client operations."""

    @abstractmethod
    def get_ticker(self, ticker_symbol: str) -> yf.Ticker:
        """Get yfinance Ticker object.

        Parameters
        ----------
        ticker_symbol : str
            Stock ticker symbol

        Returns
        -------
        yf.Ticker
            yfinance Ticker object

        Raises
        ------
        YFinanceQueryError
            If Ticker retrieval fails
        """
        pass

    @abstractmethod
    def download_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Download historical price data.

        Parameters
        ----------
        tickers : List[str]
            List of ticker symbols
        start_date : date
            Start date for download range
        end_date : date
            End date for download range

        Returns
        -------
        pd.DataFrame
            Downloaded price data

        Raises
        ------
        YFinancePriceError
            If download fails
        """
        pass


class DefaultYFinanceClient(YFinanceClientInterface):
    """Default yfinance client implementation.

    Uses yfinance library directly for API calls.
    """

    def get_ticker(self, ticker_symbol: str) -> yf.Ticker:
        """Get yfinance Ticker object.

        Parameters
        ----------
        ticker_symbol : str
            Stock ticker symbol

        Returns
        -------
        yf.Ticker
            yfinance Ticker object
        """
        try:
            return yf.Ticker(ticker_symbol)
        except Exception as exc:
            raise YFinanceQueryError(
                f"Failed to get Ticker for {ticker_symbol}: {str(exc)}"
            ) from exc

    def download_prices(
        self,
        tickers: List[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Download historical price data from yfinance.

        Parameters
        ----------
        tickers : List[str]
            List of ticker symbols
        start_date : date
            Start date for download range
        end_date : date
            End date for download range

        Returns
        -------
        pd.DataFrame
            Downloaded price data with multi-level columns

        Raises
        ------
        YFinancePriceError
            If download fails
        """
        try:
            df = yf.download(
                tickers,
                start=start_date,
                end=end_date,
                group_by="ticker",
                progress=False,
                threads=True,
            )
            return df
        except Exception as exc:
            raise YFinancePriceError(
                f"Failed to download prices for {tickers}: {str(exc)}"
            ) from exc


# ============================================================================
# YFinance Data Extractor
# ============================================================================


class YFinanceCorporateActionsExtractor:
    """Extractor for corporate actions data from yfinance.

    Coordinates yfinance client and parser to retrieve corporate actions
    (dividends, stock splits) for stocks.

    Parameters
    ----------
    client : Optional[YFinanceClientInterface]
        yfinance client implementation. If None, uses DefaultYFinanceClient.
    parser : Optional[StockDataParserInterface]
        Parser for stock actions. If None, uses StockActionsParser.
    """

    def __init__(
        self,
        client: Optional[YFinanceClientInterface] = None,
        parser: Optional[StockDataParserInterface] = None,
    ) -> None:
        """Initialize corporate actions extractor."""
        self._client = client or DefaultYFinanceClient()
        self._parser = parser or StockActionsParser()

    def extract_corporate_actions(
        self, isin: str, symbol: Optional[str] = None
    ) -> StockActionsData:
        """Extract corporate actions for a stock.

        Retrieves actions data (dividends, stock splits) for the specified
        stock ticker from yfinance. If ISIN lookup fails and a symbol is
        provided, it falls back to fetching by 'Symbol.NS'.

        Parameters
        ----------
        isin : str
            Stock ISIN or ticker symbol (may include exchange suffix like ".NS")
        symbol : Optional[str], optional
            Optional symbol for fallback lookup. If provided, lookup will
            be retried using f"{symbol}.NS" if ISIN fails.

        Returns
        -------
        StockActionsData
            Structured actions data with ticker and DataFrame

        Raises
        ------
        YFinanceCorporateActionsError
            If extraction fails
        """
        try:
            log.info("Extracting corporate actions for ISIN: %s", isin)

            try:
                ticker_obj = self._client.get_ticker(isin)
                actions_data = self._parser.parse(ticker_obj)
                log.info("Successfully extracted corporate actions for %s", isin)
                return actions_data
            except (YFinanceQueryError, YFinanceCorporateActionsError) as exc:
                if symbol:
                    fallback_symbol = f"{symbol}.NS"
                    log.info(
                        "ISIN lookup failed for %s (%s). Attempting fallback to symbol: %s",
                        isin,
                        str(exc),
                        fallback_symbol,
                    )
                    ticker_obj = self._client.get_ticker(fallback_symbol)
                    actions_data = self._parser.parse(ticker_obj)
                    log.info(
                        "Successfully extracted corporate actions for %s using fallback %s",
                        isin,
                        fallback_symbol,
                    )
                    return actions_data
                raise

        except YFinanceQueryError:
            raise
        except YFinanceCorporateActionsError:
            raise
        except Exception as exc:
            log.error(
                "Unexpected error extracting corporate actions for %s: %s",
                isin,
                str(exc),
            )
            raise YFinanceCorporateActionsError(
                f"Failed to extract corporate actions for {isin}: {str(exc)}"
            ) from exc


class YFinancePriceExtractor:
    """Extractor for historical stock price data from yfinance.

    Coordinates yfinance client to retrieve historical closing prices
    for one or more stock tickers.

    Parameters
    ----------
    client : Optional[YFinanceClientInterface]
        yfinance client implementation. If None, uses DefaultYFinanceClient.
    """

    def __init__(
        self,
        client: Optional[YFinanceClientInterface] = None,
    ) -> None:
        """Initialize price extractor."""
        self._client = client or DefaultYFinanceClient()

    def extract_latest_prices(
        self,
        tickers: List[str],
        on_date: date = None,
        start_offset_days: int = 4,
        end_offset_days: int = 1,
    ) -> pd.Series:
        """Extract latest closing prices for given tickers.

        Downloads historical price data covering the specified date range
        and extracts the latest available closing price for each ticker.

        Parameters
        ----------
        tickers : List[str]
            List of ticker symbols to fetch prices for
        on_date : date, optional
            Target date for price extraction. Defaults to today's date.
        start_offset_days : int, optional
            Days to offset backwards from on_date for download start.
            Defaults to 4 to account for weekends/holidays.
        end_offset_days : int, optional
            Days to offset forwards from on_date for download end.
            Defaults to 1.

        Returns
        -------
        pd.Series
            Series with ticker symbols as index and their latest closing
            prices as values. Returns np.nan for tickers with no data.

        Raises
        ------
        YFinancePriceError
            If price extraction fails
        """
        if on_date is None:
            on_date = date.today()

        try:
            log.info(
                "Extracting latest prices for %d tickers on %s",
                len(tickers),
                on_date,
            )

            start = on_date - timedelta(days=start_offset_days)
            end = on_date + timedelta(days=end_offset_days)

            df = self._client.download_prices(tickers, start, end)

            prices = self._extract_latest_closing_prices(df, tickers)

            log.info(
                "Successfully extracted latest prices for %d tickers", len(tickers)
            )
            return prices

        except YFinanceQueryError:
            raise
        except Exception as exc:
            log.error(
                "Unexpected error extracting prices: %s",
                str(exc),
            )
            raise YFinancePriceError(f"Failed to extract prices: {str(exc)}") from exc

    @staticmethod
    def _extract_latest_closing_prices(
        df: pd.DataFrame,
        tickers: List[str],
    ) -> pd.Series:
        """Extract latest closing prices from downloaded DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Downloaded price data from yfinance
        tickers : List[str]
            List of ticker symbols

        Returns
        -------
        pd.Series
            Series with ticker symbols as index and latest closing prices.
            Returns np.nan for tickers with no data.
        """
        out = {}

        for t in tickers:
            if t in df.columns.get_level_values(0):
                ticker_series = df[t]["Close"]
                if not ticker_series.empty:
                    out[t] = ticker_series.iloc[-1]
                else:
                    out[t] = np.nan
            else:
                out[t] = np.nan

        return pd.Series(out, name="latest_close")


# ============================================================================
# Public API Functions
# ============================================================================


def _fetch_raw_stocks_price(
    stocks: Union[str, List[str]],
    on_date: date = None,
    start_offset_days: int = 4,
    end_offset_days: int = 1,
    client: Optional[YFinanceClientInterface] = None,
) -> pd.Series:
    """Fetch raw stock prices from yfinance without fallback logic.

    Internal method used by fetch_stocks_price.
    """
    # Coerce input to list
    if isinstance(stocks, str):
        tickers = [stocks]
    else:
        tickers = list(stocks)

    if on_date is None:
        on_date = date.today()

    extractor = YFinancePriceExtractor(client=client)
    return extractor.extract_latest_prices(
        tickers,
        on_date=on_date,
        start_offset_days=start_offset_days,
        end_offset_days=end_offset_days,
    )


def fetch_stocks_price(
    stocks: Union[List[str], Dict[str, str]],
    on_date: date = None,
    start_offset_days: int = 4,
    end_offset_days: int = 1,
    client: Optional[YFinanceClientInterface] = None,
) -> pd.Series:
    """Fetch the latest stock price for given ticker symbols with fallback support.

    Retrieves the closing price for one or more stock tickers. If a dictionary
    mapping {ISIN: Symbol} is provided, it attempts to fetch by ISIN first.
    If ISIN fetch fails (returns NaN), it falls back to fetching by 'Symbol.NS'.

    Parameters
    ----------
    stocks : Union[List[str], Dict[str, str]]
        - If List[str]: A list of ticker symbols/ISINs. No fallback logic.
        - If Dict[str, str]: A dictionary mapping {ISIN: Symbol}.
          Fallback logic is enabled (ISIN -> Symbol.NS).
    on_date : date, optional
        The target date for which to fetch prices. Defaults to today's date.
    start_offset_days : int, optional
        Number of days to offset backwards from on_date. Defaults to 4.
    end_offset_days : int, optional
        Number of days to offset forwards from on_date. Defaults to 1.
    client : Optional[YFinanceClientInterface]
        yfinance client to use.

    Returns
    -------
    pd.Series
        A pandas Series with ticker symbols/ISINs as index and their latest closing
        prices as values.
    """
    if isinstance(stocks, list):
        # Legacy behavior: just fetch what's requested
        return _fetch_raw_stocks_price(
            stocks,
            on_date=on_date,
            start_offset_days=start_offset_days,
            end_offset_days=end_offset_days,
            client=client,
        )

    if isinstance(stocks, dict):
        # Fallback logic behavior
        isins = list(stocks.keys())
        latest_prices = _fetch_raw_stocks_price(
            isins,
            on_date=on_date,
            start_offset_days=start_offset_days,
            end_offset_days=end_offset_days,
            client=client,
        )

        # Check for missing prices
        missing_prices = latest_prices[latest_prices.isna()]
        if not missing_prices.empty:
            missing_isins = missing_prices.index
            log.info(
                f"Price fetch failed for {len(missing_isins)} ISINs. Attempting fallback to Symbol.NS."
            )

            # Prepare fallback symbols map {ISIN: Symbol.NS}
            fallback_map = {}
            for isin in missing_isins:
                symbol = stocks.get(isin)
                if symbol:
                    fallback_map[isin] = f"{symbol}.NS"

            if fallback_map:
                # Fetch prices for symbols
                symbol_prices = _fetch_raw_stocks_price(
                    list(fallback_map.values()),
                    on_date=on_date,
                    start_offset_days=start_offset_days,
                    end_offset_days=end_offset_days,
                    client=client,
                )

                # Update original series with fallback results
                for isin, symbol_ns in fallback_map.items():
                    if symbol_ns in symbol_prices and not pd.isna(
                        symbol_prices[symbol_ns]
                    ):
                        latest_prices[isin] = symbol_prices[symbol_ns]
                        log.info(
                            f"Fallback success: {isin} -> {symbol_ns} -> {symbol_prices[symbol_ns]}"
                        )
                    else:
                        log.warning(f"Fallback failed for {isin} (Symbol: {symbol_ns})")

        return latest_prices

    raise ValueError("stocks argument must be a List[str] or Dict[str, str]")


def extract_corporate_actions(
    isin: str,
    symbol: Optional[str] = None,
    client: Optional[YFinanceClientInterface] = None,
) -> StockActionsData:
    """Extract corporate actions data for a stock from yfinance.

    Retrieves dividend and stock split information for the specified stock.
    Supports fallback to Symbol.NS if ISIN lookup fails.

    Parameters
    ----------
    isin : str
        Stock ISIN or ticker symbol (may include exchange suffix like ".NS")
    symbol : Optional[str], optional
        Optional symbol for fallback lookup. If provided, lookup will
        be retried using f"{symbol}.NS" if ISIN fails.
    client : Optional[YFinanceClientInterface]
        yfinance client to use. If None, creates new client.
        If provided, caller is responsible for lifecycle management.

    Returns
    -------
    StockActionsData
        Structured actions data with ticker and DataFrame

    Examples
    --------
    >>> actions = extract_corporate_actions("TCS.NS")
    >>> print(actions.actions.head())

    """
    extractor = YFinanceCorporateActionsExtractor(client=client)
    return extractor.extract_corporate_actions(isin, symbol=symbol)
