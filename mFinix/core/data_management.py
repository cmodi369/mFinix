from datetime import date, datetime, timedelta
from typing import Iterator, List, Union

import numpy as np
import pandas as pd
import yfinance as yf

import mFinix.constants.columns as col

# module specific constants
import mFinix.constants.constants as const


def read_ledger_data():
    # Get all files starting with ledger in the directory
    files = [
        file
        for file in const.DOCS_PATH.glob(f"{const.LEDGER_ID_ZERODHA}*.csv")
        if file.is_file()
    ]

    # Find the latest file based on modification time
    if not files:
        raise FileNotFoundError("No files found in the directory starting with ledger.")

    latest_file = max(files, key=lambda f: f.stat().st_mtime)

    ledger_data = pd.read_csv(latest_file).dropna()
    ledger_data[col.POSTING_DATE] = pd.to_datetime(ledger_data[col.POSTING_DATE])

    return ledger_data


def read_tradebook_data():
    ret_data = pd.DataFrame()
    for file in const.DOCS_PATH.glob(f"{const.TRADEBOOK_ID_ZERODHA}*"):
        ret_data = pd.concat([ret_data, pd.read_csv(file)])

    # remove duplicates
    ret_data = ret_data.drop_duplicates(
        subset=["trade_id", "order_id", "order_execution_time"]
    )

    # format datetime column
    ret_data[col.TRADE_DATE] = pd.to_datetime(ret_data[col.TRADE_DATE]).dt.date

    # sort data based on trading dates
    ret_data = ret_data.sort_values(by=[col.TRADE_DATE, col.TRADE_TYPE]).reset_index(
        drop=True
    )

    # set negative price for sell transactions
    ret_data.loc[ret_data[col.TRADE_TYPE].eq(const.SELL), col.QUANTITY] = (
        ret_data[col.QUANTITY] * -1
    )
    ret_data[col.TRANSACTION_AMOUNT] = ret_data[col.PRICE] * ret_data[col.QUANTITY]

    # calculate total quantity
    ret_data[col.TOTAL_QUANTITY] = ret_data.groupby(col.ISIN)[col.QUANTITY].cumsum()

    ret_data[col.SYMBOL] = ret_data[col.SYMBOL].str.split("-").str[0]

    return ret_data


def fetch_stocks_price(
    stocks: Union[str, Iterator], on_date: date = date.today(), offset_days: int = 4
) -> pd.Series:
    stocks = coerce_to_list(stocks)

    start = on_date - timedelta(offset_days)

    data = _download_tickers_price_from_yfinance(stocks, start, on_date)

    return data


def _download_tickers_price_from_yfinance(
    tickers: List[str], start_date: date, end_date: date
) -> pd.Series:
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


def coerce_to_list(inputs) -> list:
    if isinstance(inputs, str):
        return [inputs]
    return list(inputs)
