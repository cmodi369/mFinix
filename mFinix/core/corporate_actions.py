import re
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import requests
import yfinance as yf

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.util import log


def automatic_update_corporate_actions_data(trade_data: pd.DataFrame):
    # read/initialize required datasets
    dividend_data, splits_data, last_date = _read_local_corporate_actions_data()

    # TODO: Optimize looping methodology
    for stock_id in trade_data[col.ISIN].unique():
        log.info("Querying corporate actions for %s", stock_id)

        stock_trade_data = trade_data[trade_data[col.ISIN].eq(stock_id)]
        stock = yf.Ticker(stock_id)
        actions_data = stock.actions
        stock_name = stock.ticker.split(".")[0]

        if not stock.ticker:
            log.info(
                "Information is not available for %s, Check for merger/name change",
                stock_id,
            )
            if const.USE_WEBSCRAPPING:
                stock_name = trade_data[trade_data[col.ISIN] == stock_id][
                    col.SYMBOL
                ].unique()[0]
                actions_data = _read_corporate_actions_from_nse_webscrapping(stock_name)

        else:
            actions_data.index = actions_data.index.tz_localize(None)

        if actions_data.empty:
            log.info(
                "Corporate actions are not available for %s", stock.ticker.split(".")[0]
            )
            continue

        log.info("Corporate actions are retrieved for %s", stock_name)

        for date, row in actions_data[actions_data.index.date >= last_date].iterrows():
            applicable_data = stock_trade_data[
                stock_trade_data[col.TRADE_DATE].lt(date)
            ]
            if (
                len(applicable_data) > 0
                and (quantity := applicable_data[col.TOTAL_QUANTITY].iloc[-1]) > 0
            ):
                if row[col.DIVIDEND] > 0:
                    # add dividend information
                    dividend_data.loc[len(dividend_data)] = [
                        stock_name,
                        stock_id,
                        date,
                        quantity,
                        row[col.DIVIDEND],
                        quantity * row[col.DIVIDEND],
                    ]

                    log.info(
                        "Dividend information added: %s",
                        {
                            "Stock": stock_name,
                            "Date": date,
                            "Dividend": row[col.DIVIDEND],
                            "Quantity": quantity,
                        },
                    )

                if row[col.STOCK_SPLITS] > 0:
                    # add stock split information
                    new_quantity = quantity * (row[col.STOCK_SPLITS] - 1)
                    splits_data.loc[len(splits_data)] = [
                        stock_name,
                        stock_id,
                        date,
                        row[col.STOCK_SPLITS],
                        new_quantity,
                    ]

                    log.info(
                        "Stock splits information added: %s",
                        {
                            "Stock": stock_name,
                            "Date": date,
                            "Split Ratio": row[col.STOCK_SPLITS],
                            "Quantity": quantity,
                        },
                    )

                    # update total quantity in stock trade data after split update
                    stock_trade_data.loc[
                        stock_trade_data[col.TRADE_DATE].gt(date), col.TOTAL_QUANTITY
                    ] = (stock_trade_data[col.TOTAL_QUANTITY] + quantity)

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

    # add trade type
    dividend_data[col.TRADE_TYPE] = const.DIVIDEND
    splits_data[col.TRADE_TYPE] = const.STOCK_SPLIT
    splits_data[col.TRANSACTION_AMOUNT] = 0

    # add splits data and adjust total quantity
    ret_data = pd.concat([trade_data, splits_data])
    ret_data = ret_data.sort_values(by=[col.TRADE_DATE, col.TRADE_TYPE]).reset_index(
        drop=True
    )

    # adjust total quantity column based on splits data
    ret_data[col.TOTAL_QUANTITY] = ret_data.groupby(col.ISIN)[col.QUANTITY].cumsum()

    # add dividend data
    ret_data = pd.concat([ret_data, dividend_data])
    ret_data = ret_data.sort_values(by=[col.TRADE_DATE, col.TRADE_TYPE]).reset_index(
        drop=True
    )

    return ret_data


def _read_corporate_actions_from_nse_webscrapping(stock_name: str):
    log.info("Pull information through web scrapping for %s", stock_name)
    ret_data = pd.DataFrame()
    try:
        session = requests.session()
        session.get(const.NSE_URL, headers=const.HEADERS)
        session.get(
            const.NSE_STOCK_URL.format(stock_name=stock_name), headers=const.HEADERS
        )  # to save cookies
        webdata = session.get(
            const.NSE_CORP_ACTIONS_URL.format(stock_name=stock_name),
            headers=const.HEADERS,
        )
        corp_data = pd.DataFrame(webdata.json())

        # get dividend information before merger
        corp_data = corp_data.replace("-", np.nan)
        dividend_data = corp_data[corp_data["subject"].str.contains("Dividend")]

        if not dividend_data.empty:
            # Create a new DataFrame with dates and summed float dividend values
            ret_data = pd.DataFrame(
                {
                    col.DIVIDEND: dividend_data["subject"].apply(_sum_floats).values,
                    col.STOCK_SPLITS: np.nan,
                },
                index=pd.to_datetime(dividend_data["exDate"]),
            )

    except Exception as exc:
        log.warning("NSE data query failed for %s with %s", stock_name, str(exc))
    return ret_data


def _sum_floats(text):
    # Function to extract all float values and sum them
    # Regular expression to match floats
    pattern = r"\b\d+\.\d+|\b\d+\b"
    floats = [float(x) for x in re.findall(pattern, text)]
    return sum(floats)


def _read_local_corporate_actions_data():
    # check if local corporate actions data is available
    dividend_file = Path(const.LOCAL_DATA_PATH / const.DIVIDEND_CSV)
    if dividend_file.exists():
        log.info("Reading local corporate actions data.")
        dividend_data = pd.read_csv(dividend_file)
        dividend_data[col.TRADE_DATE] = pd.to_datetime(
            dividend_data[col.TRADE_DATE]
        ).dt.date

        log.info("Dividends data is pulled for %s entries", len(dividend_data))
        splits_data = pd.read_csv(Path(const.LOCAL_DATA_PATH / const.SPLIT_ACTIONS_CSV))
        splits_data[col.TRADE_DATE] = pd.to_datetime(
            splits_data[col.TRADE_DATE]
        ).dt.date

        log.info("Stock splits data is pulled for %s entries", len(splits_data))
        last_date = pd.to_datetime(
            Path(const.LOCAL_DATA_PATH / const.LAST_DATE_TXT).read_text()
        )

        log.info("Last corporate data was updated on: %s", last_date)

    else:
        log.info("Local corporate actions data is not available.")
        const.LOCAL_DATA_PATH.mkdir(parents=True, exist_ok=True)
        dividend_data = pd.DataFrame(
            columns=[
                col.SYMBOL,
                col.ISIN,
                col.TRADE_DATE,
                col.QUANTITY,
                col.DIVIDEND_COL,
                col.TRANSACTION_AMOUNT,
            ]
        )
        splits_data = pd.DataFrame(
            columns=[
                col.SYMBOL,
                col.ISIN,
                col.TRADE_DATE,
                col.STOCK_SPLITS_COL,
                col.QUANTITY,
            ]
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
