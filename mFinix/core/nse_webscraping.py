"""
NSE (National Stock Exchange) Web Scraping Module.

This module provides classes and utilities for scraping corporate actions data
(dividends, stock splits, IPOs, etc.) from the NSE website.

"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd
import requests

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.util import log

# ============================================================================
# Custom Exceptions
# ============================================================================


class NSEScraperError(Exception):
    """Base exception for NSE scraping operations."""

    pass


class NSEConnectionError(NSEScraperError):
    """Raised when connection to NSE fails."""

    pass


class NSEParsingError(NSEScraperError):
    """Raised when parsing NSE response data fails."""

    pass


class NSEDataNotFoundError(NSEScraperError):
    """Raised when expected data is not found in NSE response."""

    pass


# ============================================================================
# HTTP Client (Abstraction for HTTP operations)
# ============================================================================


@dataclass
class HttpResponse:
    """Represents an HTTP response.

    Attributes
    ----------
    status_code : int
        HTTP status code
    json_data : Optional[dict]
        Parsed JSON data from response
    text : str
        Raw response text
    """

    status_code: int
    json_data: Optional[dict]
    text: str


class HttpClientInterface(ABC):
    """Abstract interface for HTTP client."""

    @abstractmethod
    def get(self, url: str, **kwargs) -> HttpResponse:
        """Make GET request.

        Parameters
        ----------
        url : str
            URL to request
        **kwargs
            Additional arguments to pass to requests

        Returns
        -------
        HttpResponse
            HTTP response object

        Raises
        ------
        NSEConnectionError
            If request fails
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the HTTP client session."""
        pass


class NSEHttpClient(HttpClientInterface):
    """NSE-specific HTTP client with session management.

    Handles session setup, headers, and cookie persistence for NSE requests.

    Parameters
    ----------
    headers : Optional[Dict[str, str]]
        Custom headers for requests. Defaults to NSE user-agent headers.
    base_url : Optional[str]
        Base URL for NSE. Defaults to NSE_URL constant.

    """

    def __init__(
        self,
        headers: Optional[Dict[str, str]] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Initialize NSE HTTP client."""
        self._session = requests.Session()
        self._headers = headers or const.HEADERS
        self._base_url = base_url or const.NSE_URL

        # Initialize session with base URL to establish cookies
        self._initialize_session()

    def _initialize_session(self) -> None:
        """Initialize session by accessing base NSE URL.

        This ensures cookies are set and session is properly established.
        """
        try:
            self._session.get(self._base_url, headers=self._headers)
            log.debug("NSE HTTP client session initialized successfully")
        except requests.RequestException as exc:
            raise NSEConnectionError(f"Failed to initialize NSE session: {str(exc)}")

    def get(self, url: str, **kwargs) -> HttpResponse:
        """Make GET request with NSE headers.

        Parameters
        ----------
        url : str
            URL to request
        **kwargs
            Additional arguments for requests.Session.get

        Returns
        -------
        HttpResponse
            HTTP response object

        """
        try:
            headers = kwargs.pop("headers", self._headers)
            response = self._session.get(url, headers=headers, **kwargs)
            response.raise_for_status()

            # Try to parse JSON, but don't fail if it's not JSON
            json_data = None
            try:
                json_data = response.json()
            except ValueError:
                pass  # Response might not be JSON

            return HttpResponse(
                status_code=response.status_code,
                json_data=json_data,
                text=response.text,
            )
        except requests.RequestException as exc:
            raise NSEConnectionError(f"NSE request failed: {str(exc)}")

    def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            self._session.close()
            log.debug("NSE HTTP client session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ============================================================================
# Data Parsers (Abstraction for parsing logic)
# ============================================================================


class DataParserInterface(ABC):
    """Abstract interface for data parsers.

    Allows extension to different data types (dividends, splits, IPOs, etc.)
    without modifying existing code (Open/Closed Principle).
    """

    @abstractmethod
    def parse(self, response_data: dict) -> pd.DataFrame:
        """Parse response data into DataFrame.

        Parameters
        ----------
        response_data : dict
            Parsed JSON response from NSE API

        Returns
        -------
        pd.DataFrame
            Structured data with appropriate columns

        """
        pass


class DividendParser(DataParserInterface):
    """Parser for NSE dividend corporate actions.

    Extracts dividend information from NSE corporate actions API response
    and transforms into a DataFrame suitable for portfolio analysis.

    Notes
    -----
    The NSE API returns dividend information in the "subject" field.
    This parser extracts float values and dates from the response.
    """

    @staticmethod
    def _extract_float_sum(text: str) -> float:
        """Extract and sum all float values from text.

        Parameters
        ----------
        text : str
            Text containing numeric values

        Returns
        -------
        float
            Sum of all extracted float values

        Examples
        --------
        >>> parser = DividendParser()
        >>> parser._extract_float_sum("Dividend Rs. 5.50 per share")
        5.5
        >>> parser._extract_float_sum("Special Dividend Rs. 10")
        10.0
        """
        pattern = r"\b\d+\.\d+|\b\d+\b"
        floats = [float(x) for x in re.findall(pattern, text)]
        return sum(floats)

    def parse(self, response_data: dict) -> pd.DataFrame:
        """Parse dividend data from NSE corporate actions response.

        Parameters
        ----------
        response_data : dict
            Response from NSE corporate actions API

        Returns
        -------
        pd.DataFrame
            A DataFrame with columns: dividend (float), stock_splits (NaN)
            and date index from exDate

        Notes
        -----
        The response should be a list of records with 'subject' and 'exDate' fields.
        Only records with 'Dividend' in the subject are processed.
        """
        try:
            if not isinstance(response_data, list):
                raise NSEParsingError(
                    f"Expected list response, got {type(response_data)}"
                )

            corp_df = pd.DataFrame(response_data)

            # Replace dashes with NaN
            corp_df = corp_df.replace("-", np.nan)

            # Filter for dividend records
            dividend_data = corp_df[
                corp_df["subject"].str.contains("Dividend", na=False)
            ]

            if dividend_data.empty:
                raise NSEDataNotFoundError("No dividend data found in NSE response")

            # Extract dividend values and create result DataFrame
            result_df = pd.DataFrame(
                {
                    col.DIVIDEND: dividend_data["subject"]
                    .apply(self._extract_float_sum)
                    .values,
                    col.STOCK_SPLITS: np.nan,
                },
                index=pd.to_datetime(dividend_data["exDate"]),
            )

            log.info(
                "Successfully parsed %d dividend records from NSE",
                len(result_df),
            )
            return result_df

        except (KeyError, ValueError) as exc:
            raise NSEParsingError(f"Failed to parse dividend data: {str(exc)}") from exc


class IPOParser(DataParserInterface):
    """Parser for NSE IPO data.

    Extracts IPO information from NSE public issues API response
    and transforms into a dictionary with IPO details.

    """

    def parse(self, response_data: dict) -> dict:
        """Parse IPO data from NSE public issues response.

        Parameters
        ----------
        response_data : dict
            Response from NSE public issues API

        Returns
        -------
        dict
            Dictionary with keys: ipo_price, ipo_date

        """
        try:
            if not isinstance(response_data, list):
                raise NSEParsingError(
                    f"Expected list response, got {type(response_data)}"
                )

            if not response_data:
                raise NSEDataNotFoundError("No IPO data found in NSE response")

            # Get the first IPO record (most recent)
            ipo_record = response_data[0]

            # Extract required fields
            if "issuePrice" not in ipo_record or "listingDate" not in ipo_record:
                raise NSEDataNotFoundError(
                    "Required IPO fields (issuePrice, listingDate) not found"
                )

            # Parse IPO price
            ipo_price = float(ipo_record["issuePrice"])

            # Parse IPO date
            ipo_date = pd.to_datetime(ipo_record["listingDate"])

            result_dict = {
                "ipo_price": ipo_price,
                "ipo_date": ipo_date,
            }

            log.info(
                "Successfully parsed IPO data: price=%.2f, date=%s, quantity=%s",
                ipo_price,
                ipo_date,
            )
            return result_dict

        except (KeyError, ValueError, TypeError) as exc:
            raise NSEParsingError(f"Failed to parse IPO data: {str(exc)}") from exc


# ============================================================================
# Data Extractor (Orchestrator)
# ============================================================================


class NSEDataExtractor:
    """Orchestrator for NSE data extraction operations.

    Coordinates HTTP client and parsers to extract corporate actions data.

    Parameters
    ----------
    http_client : HttpClientInterface
        HTTP client implementation for making requests
    parser : DataParserInterface
        Parser implementation for processing responses

    """

    def __init__(
        self,
        http_client: HttpClientInterface,
        parser: DataParserInterface,
    ) -> None:
        """Initialize NSE data extractor."""
        self._client = http_client
        self._parser = parser

    def extract_corporate_actions(self, stock_name: str) -> pd.DataFrame:
        """Extract corporate actions data for a stock.

        Performs necessary API calls and data parsing to retrieve corporate
        actions information for the specified stock.

        Parameters
        ----------
        stock_name : str
            Stock symbol/name for extraction

        Returns
        -------
        pd.DataFrame
            A DataFrame with extracted corporate actions data

        Notes
        -----
        The method makes two API calls:
        1. To the stock quote endpoint to establish cookies
        2. To the corporate actions endpoint for the actual data
        """
        try:
            log.info(
                "Extracting corporate actions for stock: %s",
                stock_name,
            )

            # Access stock URL to set cookies
            stock_url = const.NSE_STOCK_URL.format(stock_name=stock_name)
            stock_response = self._client.get(stock_url)
            log.debug(
                "Stock quote accessed: %s (status: %s)",
                stock_name,
                stock_response.status_code,
            )

            # Get corporate actions data
            corp_actions_url = const.NSE_CORP_ACTIONS_URL.format(stock_name=stock_name)
            corp_response = self._client.get(corp_actions_url)

            if not corp_response.json_data:
                raise NSEDataNotFoundError(
                    f"No JSON response for corporate actions: {stock_name}"
                )

            # Parse the response
            result = self._parser.parse(corp_response.json_data)
            log.info(
                "Successfully extracted corporate actions for %s",
                stock_name,
            )
            return result

        except NSEScraperError:
            raise
        except Exception as exc:
            log.error(
                "Unexpected error extracting corporate actions for %s: %s",
                stock_name,
                str(exc),
            )
            raise NSEScraperError(
                f"Failed to extract corporate actions for {stock_name}: {str(exc)}"
            ) from exc

    def extract_past_ipo_data(self, stock_name: str) -> dict:
        """Extract IPO data for a stock.

        Performs necessary API calls and data parsing to retrieve IPO
        information for the specified stock.

        Parameters
        ----------
        stock_name : str
            Stock symbol/name for extraction

        Returns
        -------
        dict
            Dictionary with keys: ipo_price, ipo_date, ipo_quantity

        Notes
        -----
        The method makes two API calls:
        1. To the stock quote endpoint to establish cookies
        2. To the public issues endpoint for IPO data
        """
        try:
            log.info(
                "Extracting IPO data for stock: %s",
                stock_name,
            )

            # Get IPO data from public issues API
            ipo_response = self._client.get(
                const.NSE_PAST_IPO_URL.format(stock_name=stock_name)
            )

            if not ipo_response.json_data:
                raise NSEDataNotFoundError(
                    f"No JSON response for IPO data: {stock_name}"
                )

            # Parse the response
            result = self._parser.parse(ipo_response.json_data)
            log.info(
                "Successfully extracted IPO data for %s: %s",
                stock_name,
                result,
            )
            return result

        except NSEScraperError:
            raise
        except Exception as exc:
            log.error(
                "Unexpected error extracting IPO data for %s: %s",
                stock_name,
                str(exc),
            )
            raise NSEScraperError(
                f"Failed to extract IPO data for {stock_name}: {str(exc)}"
            ) from exc


# ============================================================================
# Public API Functions
# ============================================================================


def extract_dividend_data(
    stock_name: str, client: Optional[HttpClientInterface] = None
) -> pd.DataFrame:
    """Extract dividend corporate actions data for a stock from NSE.

    Convenience function that creates necessary components and extracts
    dividend data in a single call.

    Parameters
    ----------
    stock_name : str
        Stock symbol/name for extraction
    client : Optional[HttpClientInterface]
        HTTP client to use. If None, creates new client.
        If provided, caller is responsible for closing it.

    Returns
    -------
    pd.DataFrame
        DataFrame with dividend data, indexed by ex-date

    Examples
    --------
    >>> df = extract_dividend_data("TCS")
    >>> print(df.head())

    """
    should_close_client = client is None
    if client is None:
        client = NSEHttpClient()

    try:
        parser = DividendParser()
        extractor = NSEDataExtractor(client, parser)
        return extractor.extract_corporate_actions(stock_name)
    finally:
        if should_close_client:
            client.close()


def extract_past_ipo_data(
    stock_name: str, client: Optional[HttpClientInterface] = None
) -> dict:
    """Extract IPO data for a stock from NSE.

    Convenience function that creates necessary components and extracts
    IPO data (price, date) in a single call.

    Parameters
    ----------
    stock_name : str
        Stock symbol/name for extraction
    client : Optional[HttpClientInterface]
        HTTP client to use. If None, creates new client.
        If provided, caller is responsible for closing it.

    Returns
    -------
    dict
        Dictionary with keys: ipo_price (float), ipo_date (Timestamp)

    Examples
    --------
    >>> ipo_data = extract_past_ipo_data("BAJAJHFL")
    >>> print(ipo_data)
    {'ipo_price': 500.0, 'ipo_date': Timestamp('2023-01-15')}

    """
    should_close_client = client is None
    if client is None:
        client = NSEHttpClient()

    try:
        parser = IPOParser()
        extractor = NSEDataExtractor(client, parser)
        return extractor.extract_past_ipo_data(stock_name)
    finally:
        if should_close_client:
            client.close()
