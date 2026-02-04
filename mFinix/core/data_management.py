"""
Data management utilities for stock price fetching and general data operations.

This module provides utilities for fetching historical stock prices and
data transformation operations. For reading trading data from the Kite
platform, use the read_kite_data module.

"""

from datetime import date, timedelta
from typing import Iterator, List, Union

import numpy as np
import pandas as pd
import yfinance as yf


def fetch_stocks_price(
    stocks: Union[str, Iterator],
    on_date: date = date.today(),
    start_offset_days: int = 4,
    end_offset_days: int = 1,
) -> pd.Series:
    """Fetch the latest stock price for given ticker symbols.

    Retrieves the closing price for one or more stock tickers as of a specified
    date. Downloads historical price data from yfinance covering the date range
    from (on_date - offset_days) to on_date.

    Parameters
    ----------
    stocks : Union[str, Iterator]
        A single ticker symbol (str) or an iterable of ticker symbols.
    on_date : date, optional
        The target date for which to fetch prices. Defaults to today's date.
    start_offset_days : int, optional
        Number of days to offset backwards from on_date for the start of the
        download range. Defaults to 4 days to account for weekends/holidays.
    end_offset_days : int, optional
        Number of days to offset forwards from on_date for the end of the
        download range. Defaults to 1.

    Returns
    -------
    pd.Series
        A pandas Series with ticker symbols as index and their latest closing
        prices as values. Returns np.nan for tickers with no data.

    Examples
    --------
    >>> fetch_stocks_price('RELIANCE.NS')  # doctest: +SKIP
    RELIANCE.NS    2500.50
    Name: latest_close, dtype: float64

    >>> fetch_stocks_price(['TCS.NS', 'INFY.NS'])  # doctest: +SKIP
    TCS.NS     3500.25
    INFY.NS    1800.75
    Name: latest_close, dtype: float64
    """
    stocks = _coerce_to_list(stocks)

    start = on_date - timedelta(start_offset_days)

    end = on_date + timedelta(end_offset_days)

    data = _download_tickers_price_from_yfinance(stocks, start, end)

    return data


def _download_tickers_price_from_yfinance(
    tickers: List[str], start_date: date, end_date: date
) -> pd.Series:
    """Download ticker prices from yfinance and extract latest closing prices.

    Parameters
    ----------
    tickers : List[str]
        List of ticker symbols to download.
    start_date : date
        Start date for the price download range.
    end_date : date
        End date for the price download range.

    Returns
    -------
    pd.Series
        Series with ticker symbols as index and their latest closing prices.
    """
    df = yf.download(
        tickers,
        start=start_date,
        end=end_date,
        group_by="ticker",
        progress=False,
        threads=True,
    )

    out = {}

    for t in tickers:
        if t in df.columns.get_level_values(0):
            out[t] = df[t]["Close"].iloc[-1]
        else:
            out[t] = np.nan

    ret_data = pd.Series(out, name="latest_close")

    return ret_data


def _coerce_to_list(inputs) -> list:
    """Convert input to a list format.

    Parameters
    ----------
    inputs : Union[str, Iterable]
        A string or iterable input.

    Returns
    -------
    list
        The input as a list.
    """
    if isinstance(inputs, str):
        return [inputs]
    return list(inputs)
