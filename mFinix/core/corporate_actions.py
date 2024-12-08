from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import List

import pandas as pd
import yfinance as yf

import mFinix.constants.constants as const
from mFinix.constants.columns import (
    DIVIDEND,
    DIVIDEND_COL,
    ISIN,
    PRICE,
    QUANTITY,
    STOCK_SPLITS,
    STOCK_SPLITS_COL,
    SYMBOL,
    TOTAL_QUANTITY,
    TRADE_DATE,
    TRADE_TYPE,
    TRANSACTION_AMOUNT,
)
from mFinix.util import log


def update_corporate_actions_data(trade_data: pd.DataFrame):
    # read/initialize required datasets
    dividend_data, splits_data, last_date = _read_local_corporate_actions_data()

    # TODO: Optimize looping methodology
    for stock_id in trade_data[ISIN].unique():
        log.info("Querying corporate actions for %s", stock_id)

        stock_trade_data = trade_data[trade_data[ISIN].eq(stock_id)]
        stock = yf.Ticker(stock_id)
        actions_data = stock.actions

        if actions_data.empty:
            log.info(
                "Corporate actions are not available for %s", stock.ticker.split(".")[0]
            )
            continue

        actions_data.index = actions_data.index.tz_localize(None)
        stock_name = stock.ticker.split(".")[0]

        log.info("Corporate actions are retrieved for %s", stock_name)

        for date, row in actions_data[last_date:].iterrows():
            applicable_data = stock_trade_data[stock_trade_data[TRADE_DATE].lt(date)]
            if (
                len(applicable_data) > 0
                and (quantity := applicable_data[TOTAL_QUANTITY].iloc[-1]) > 0
            ):
                if row[DIVIDEND] > 0:
                    # add dividend information
                    dividend_data.loc[len(dividend_data)] = [
                        stock_name,
                        stock_id,
                        date,
                        quantity,
                        row[DIVIDEND],
                        quantity * row[DIVIDEND],
                    ]

                    log.info(
                        "Dividend information added: %s",
                        {
                            "Stock": stock_name,
                            "Date": date,
                            "Dividend": row[DIVIDEND],
                            "Quantity": quantity,
                        },
                    )

                if row[STOCK_SPLITS] > 0:
                    # add stock split information
                    splits_data.loc[len(splits_data)] = [
                        stock_name,
                        stock_id,
                        date,
                        quantity,
                        row[STOCK_SPLITS],
                        quantity * row[STOCK_SPLITS],
                    ]

                    log.info(
                        "Stock splits information added: %s",
                        {
                            "Stock": stock_name,
                            "Date": date,
                            "Split Ratio": row[STOCK_SPLITS],
                            "Quantity": quantity,
                        },
                    )

    log.info("Updated Data Saving Started")
    log.info("New data for dividends: %s", dividend_data.shape)
    # save new data
    dividend_data.to_csv(Path(const.LOCAL_DATA_PATH / const.DIVIDEND_CSV), index=False)

    log.info("New data for stock splits: %s", splits_data.shape)
    splits_data.to_csv(
        Path(const.LOCAL_DATA_PATH / const.SPLIT_ACTIONS_CSV), index=False
    )

    last_date = datetime.now()
    log.info("New date: %s", last_date)
    # Open the file in write mode using with statement
    with Path(const.LOCAL_DATA_PATH / const.LAST_DATE_TXT).open("w") as file:
        # Write content to the file
        file.write(str(last_date))

    log.info("Corporate actions data is successfully updated")


def add_corporate_actions_in_tradebook(trade_data: pd.DataFrame):
    # read/initialize required datasets
    dividend_data, splits_data, last_date = _read_local_corporate_actions_data()

    return reduce(
        lambda left, right: pd.merge(left, right, on=["DATE"], how="outer"),
        [trade_data, dividend_data, splits_data],
    )


def _read_local_corporate_actions_data():
    # check if local corporate actions data is available
    dividend_file = Path(const.LOCAL_DATA_PATH / const.DIVIDEND_CSV)
    if dividend_file.exists():
        log.info("Reading local corporate actions data.")
        dividend_data = pd.read_csv(dividend_file)

        log.info("Dividends data is pulled: %s", dividend_data.shape)
        splits_data = pd.read_csv(Path(const.LOCAL_DATA_PATH / const.SPLIT_ACTIONS_CSV))

        log.info("Stock splits data is pulled: %s", splits_data.shape)
        last_date = pd.to_datetime(
            Path(const.LOCAL_DATA_PATH / const.LAST_DATE_TXT).read_text()
        )

        log.info("Latest corporate data update was on: %s", last_date)

    else:
        log.info("Local corporate actions data is not available.")
        const.LOCAL_DATA_PATH.mkdir(parents=True, exist_ok=True)
        dividend_data = pd.DataFrame(
            columns=[
                SYMBOL,
                ISIN,
                TRADE_DATE,
                QUANTITY,
                DIVIDEND_COL,
                TRANSACTION_AMOUNT,
            ]
        )
        splits_data = pd.DataFrame(
            columns=[SYMBOL, ISIN, TRADE_DATE, QUANTITY, STOCK_SPLITS_COL, QUANTITY]
        )
        last_date = const.DEFAULT_LAST_DATE

    return dividend_data, splits_data, last_date


# Function to apply mergers
def _apply_mergers(transactions, holdings, old_stock, new_stock, ratio):
    # Adjust holdings
    if old_stock in holdings["Stock"].values:
        old_quantity = holdings.loc[
            holdings["Stock"] == old_stock, "Total_Quantity"
        ].values[0]
        old_cost = holdings.loc[holdings["Stock"] == old_stock, "Avg_Cost"].values[0]

        # Calculate new holdings
        new_quantity = old_quantity * ratio
        new_cost = old_cost / ratio

        # Remove old stock and add new stock to holdings
        holdings = holdings[holdings["Stock"] != old_stock]
        holdings = holdings.append(
            {"Stock": new_stock, "Total_Quantity": new_quantity, "Avg_Cost": new_cost},
            ignore_index=True,
        )

    # Adjust transactions
    transactions.loc[transactions["Stock"] == old_stock, "Stock"] = new_stock
    transactions.loc[transactions["Stock"] == new_stock, "Quantity"] *= ratio
    transactions.loc[transactions["Stock"] == new_stock, "Price"] /= ratio

    return transactions, holdings
