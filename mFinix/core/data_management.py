from datetime import datetime, timedelta
from typing import List

import pandas as pd
import yfinance as yf

# module specific constants
import mFinix.constants.constants as const
from mFinix.constants.columns import (
    ISIN,
    POSTING_DATE,
    PRICE,
    QUANTITY,
    SYMBOL,
    TOTAL_QUANTITY,
    TRADE_DATE,
    TRADE_TYPE,
    TRANSACTION_AMOUNT,
)


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
    ledger_data[POSTING_DATE] = pd.to_datetime(ledger_data[POSTING_DATE])

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
    ret_data[TRADE_DATE] = pd.to_datetime(ret_data[TRADE_DATE])

    # sort data based on trading dates
    ret_data = ret_data.sort_values(by=[TRADE_DATE, TRADE_TYPE]).reset_index(drop=True)

    # set negative price for sell transactions
    ret_data.loc[ret_data[TRADE_TYPE].eq("sell"), QUANTITY] = ret_data[QUANTITY] * -1
    ret_data[TRANSACTION_AMOUNT] = ret_data[PRICE] * ret_data[QUANTITY]

    # calculate total quantity
    ret_data[TOTAL_QUANTITY] = ret_data.groupby(ISIN)[QUANTITY].cumsum()

    ret_data[SYMBOL] = ret_data[SYMBOL].str.split("-").str[0]

    return ret_data


def fetch_latest_stock_prices(stocks: List[str]):
    start = datetime.today() - timedelta(
        3
    )  # Always retrieve data for past 3 days and re-adjust local file.
    data = yf.download(stocks, start=start)["Adj Close"]

    return data
