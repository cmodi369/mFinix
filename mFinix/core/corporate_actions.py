from datetime import datetime
import re
from functools import reduce
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.core.nse_webscraping import (
    extract_all_corporate_actions,
)
from mFinix.core.yfinance_query import extract_corporate_actions
from mFinix.util import log


def automatic_update_corporate_actions_data(trade_data: pd.DataFrame):
    # read/initialize required datasets
    (
        dividend_data,
        splits_data,
        ipo_data,
        merger_data,
        demerger_data,
        bonus_data,
        buyback_data,
        last_date,
    ) = _read_local_corporate_actions_data()

    # TODO: Optimize looping methodology
    for stock_id in trade_data[col.ISIN].unique():
        log.info("Querying corporate actions for %s", stock_id)

        stock_trade_data = trade_data[trade_data[col.ISIN].eq(stock_id)]
        actions_data_obj = extract_corporate_actions(stock_id)
        actions_data = actions_data_obj.actions
        stock_name = actions_data_obj.get_ticker_name()

        if actions_data.empty:
            log.info("Corporate actions are not available for %s", stock_name)
            if const.USE_WEBSCRAPPING:
                all_actions = extract_all_corporate_actions(stock_name)
                
                # Update Dividends
                if not all_actions.get(const.DIVIDEND, pd.DataFrame()).empty:
                    div_df = all_actions[const.DIVIDEND]
                    for date, row in div_df[div_df.index.date >= last_date].iterrows():
                        applicable_data = stock_trade_data[stock_trade_data[col.TRADE_DATE].lt(date)]
                        if not applicable_data.empty and (quantity := applicable_data[col.TOTAL_QUANTITY].iloc[-1]) > 0:
                            dividend_data.loc[len(dividend_data)] = [stock_name, stock_id, date, quantity, row[col.DIVIDEND], quantity * row[col.DIVIDEND]]
                            log.info("Dividend information added for %s", stock_name)

                # Update Bonus
                if not all_actions.get(const.BONUS, pd.DataFrame()).empty:
                    bonus_df = all_actions[const.BONUS]
                    for date, row in bonus_df[bonus_df.index.date >= last_date].iterrows():
                        applicable_data = stock_trade_data[stock_trade_data[col.TRADE_DATE].lt(date)]
                        if not applicable_data.empty and (quantity := applicable_data[col.TOTAL_QUANTITY].iloc[-1]) > 0:
                            # Note: quantity update for bonus usually 1:1 if not found, 
                            # but we mostly track the event here for manual validation if needed
                            bonus_data.loc[len(bonus_data)] = [stock_name, date, 0] # 0 used as placeholder or needs ratio
                            log.info("Bonus action detected for %s", stock_name)

                # Update Merger/Demerger
                for key, target_df in [(const.MERGER, merger_data), (const.DEMERGER, demerger_data)]:
                    if not all_actions.get(key, pd.DataFrame()).empty:
                        act_df = all_actions[key]
                        for date, row in act_df[act_df.index.date >= last_date].iterrows():
                            applicable_data = stock_trade_data[stock_trade_data[col.TRADE_DATE].lt(date)]
                            if not applicable_data.empty and (quantity := applicable_data[col.TOTAL_QUANTITY].iloc[-1]) > 0:
                                target_df.loc[len(target_df)] = [stock_name, date, 0]
                                log.info("%s action detected for %s", key.capitalize(), stock_name)
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

    # Automatically detect buybacks from ledger and update buyback_data
    log.info("Detecting buybacks from ledger...")
    new_buybacks = automatic_update_buyback_from_ledger(trade_data)
    if not new_buybacks.empty:
        buyback_data = pd.concat([buyback_data, new_buybacks]).drop_duplicates(
            subset=[col.SYMBOL, col.TRADE_DATE]
        ).reset_index(drop=True)

    log.info("Updated Data Saving Started")
    log.info("New data for dividends: %s", dividend_data.shape)
    # save new data
    dividend_data.to_csv(Path(const.LOCAL_DATA_PATH / const.DIVIDEND_CSV), index=False)

    log.info("New data for stock splits: %s", splits_data.shape)
    splits_data.to_csv(
        Path(const.LOCAL_DATA_PATH / const.SPLIT_ACTIONS_CSV), index=False
    )

    log.info("New data for buybacks: %s", buyback_data.shape)
    buyback_data.to_csv(Path(const.LOCAL_DATA_PATH / const.BUYBACK_CSV), index=False)

    log.info("New data for mergers: %s", merger_data.shape)
    merger_data.to_csv(Path(const.LOCAL_DATA_PATH / const.MERGER_CSV), index=False)

    log.info("New data for demergers: %s", demerger_data.shape)
    demerger_data.to_csv(Path(const.LOCAL_DATA_PATH / const.DEMERGER_CSV), index=False)

    log.info("New data for bonus: %s", bonus_data.shape)
    bonus_data.to_csv(Path(const.LOCAL_DATA_PATH / const.BONUS_CSV), index=False)

    last_date = datetime.now()
    log.info("New date: %s", last_date)
    # Open the file in write mode using with statement
    with Path(const.LOCAL_DATA_PATH / const.LAST_DATE_TXT).open("w") as file:
        # Write content to the file
        file.write(str(last_date))

    log.info("Corporate actions data is successfully updated")


def add_corporate_actions_in_tradebook(trade_data: pd.DataFrame):
    # read/initialize required datasets
    (
        dividend_data,
        splits_data,
        ipo_data,
        merger_data,
        demerger_data,
        bonus_data,
        buyback_data,
        last_date,
    ) = _read_local_corporate_actions_data()

    # add trade type
    dividend_data[col.TRADE_TYPE] = const.DIVIDEND
    ipo_data[col.TRADE_TYPE] = const.BUY
    splits_data[col.TRADE_TYPE] = const.STOCK_SPLIT
    splits_data[col.TRANSACTION_AMOUNT] = 0
    merger_data[col.TRADE_TYPE] = const.MERGER
    merger_data[col.TRANSACTION_AMOUNT] = 0
    demerger_data[col.TRADE_TYPE] = const.DEMERGER
    demerger_data[col.TRANSACTION_AMOUNT] = 0
    bonus_data[col.TRADE_TYPE] = const.BONUS
    bonus_data[col.TRANSACTION_AMOUNT] = 0
    buyback_data[col.TRADE_TYPE] = const.BUYBACK
    buyback_data[col.TRANSACTION_AMOUNT] = 0

    # Combine all quantity-affecting transactions
    ret_data = pd.concat(
        [
            trade_data,
            splits_data,
            ipo_data,
            merger_data,
            demerger_data,
            bonus_data,
            buyback_data,
        ]
    )
    ret_data = ret_data.sort_values(by=[col.TRADE_DATE, col.TRADE_TYPE]).reset_index(
        drop=True
    )

    # adjust total quantity column
    ret_data[col.TOTAL_QUANTITY] = ret_data.groupby(col.SYMBOL)[
        col.QUANTITY
    ].cumsum()

    # add dividend data (doesn't affect quantity but needed for XIRR)
    ret_data = pd.concat([ret_data, dividend_data])
    ret_data = ret_data.sort_values(by=[col.TRADE_DATE, col.TRADE_TYPE]).reset_index(
        drop=True
    )

    return ret_data


def automatic_update_buyback_from_ledger(trade_data: pd.DataFrame) -> pd.DataFrame:
    """Detect buyback entries from ledger data and fetch prices dynamically.

    Parameters
    ----------
    trade_data : pd.DataFrame
        Trade data to check holdings during the buyback period.

    Returns
    -------
    pd.DataFrame
        Buyback transactions detected from the ledger.
    """
    from mFinix.core.read_kite_data import read_ledger_data
    from mFinix.core.nse_webscraping import extract_buyback_data

    try:
        ledger_df = read_ledger_data()
    except Exception as e:
        log.warning("Could not read ledger data: %s", e)
        return pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])

    # Look for "Buyback amount credit"
    credits = ledger_df[
        ledger_df[col.PARTICULARS].str.contains(
            "Buyback amount credit", case=False, na=False
        )
    ].copy()

    buybacks = []

    for _, row in credits.iterrows():
        particulars = row[col.PARTICULARS]
        posting_date = row[col.POSTING_DATE].date()

        # Extract symbol
        symbol_match = re.search(r"for\s+([A-Z\s]+?)\s+Limited", particulars, re.I)
        if symbol_match:
            raw_name = symbol_match.group(1).strip().upper()
            # Map common names to symbols
            symbol_map = {
                "TANLA PLATFORMS": "TANLA",
                "WIPRO": "WIPRO",
            }
            symbol = symbol_map.get(raw_name, raw_name)

            # Check if stock was part of holdings during the day of transaction
            applicable_trade_data = trade_data[
                (trade_data[col.SYMBOL] == symbol)
                & (trade_data[col.TRADE_DATE] < posting_date)
            ]

            if not applicable_trade_data.empty and applicable_trade_data[col.TOTAL_QUANTITY].iloc[-1] > 0:
                # Fetch buyback price dynamically
                buyback_info = extract_buyback_data(symbol)

                if not buyback_info.empty:
                    # Find the nearest buyback date before posting_date
                    valid_buybacks = buyback_info[buyback_info.index.date <= posting_date]
                    if not valid_buybacks.empty:
                        # Get the most recent one
                        price = valid_buybacks.iloc[-1]["buyback_price"]
                        credit_amount = row[col.CREDIT]
                        qty = -round(credit_amount / price)
                        buybacks.append(
                            {
                                col.SYMBOL: symbol,
                                col.TRADE_DATE: posting_date,
                                col.QUANTITY: float(qty),
                            }
                        )
                        log.info(
                            "Detected buyback for %s: Date=%s, Price=%.2f, Qty=%.2f",
                            symbol, posting_date, price, qty
                        )
                else:
                    log.warning("No buyback data found for %s near %s", symbol, posting_date)
            else:
                log.info("Skipping buyback for %s on %s as it was not in holdings", symbol, posting_date)

    return pd.DataFrame(buybacks)


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

        ipo_data = pd.read_csv(Path(const.LOCAL_DATA_PATH / const.IPO_CSV))
        ipo_data[col.TRADE_DATE] = pd.to_datetime(ipo_data[col.TRADE_DATE]).dt.date
        log.info("IPO data is pulled for %s entries", len(ipo_data))

        merger_file = Path(const.LOCAL_DATA_PATH / const.MERGER_CSV)
        if merger_file.exists():
            merger_data = pd.read_csv(merger_file)
            merger_data[col.TRADE_DATE] = pd.to_datetime(
                merger_data[col.TRADE_DATE]
            ).dt.date
            log.info("Merger data is pulled for %s entries", len(merger_data))
        else:
            merger_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])

        demerger_file = Path(const.LOCAL_DATA_PATH / const.DEMERGER_CSV)
        if demerger_file.exists():
            demerger_data = pd.read_csv(demerger_file)
            demerger_data[col.TRADE_DATE] = pd.to_datetime(
                demerger_data[col.TRADE_DATE]
            ).dt.date
            log.info("Demerger data is pulled for %s entries", len(demerger_data))
        else:
            demerger_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])

        bonus_file = Path(const.LOCAL_DATA_PATH / const.BONUS_CSV)
        if bonus_file.exists():
            bonus_data = pd.read_csv(bonus_file)
            bonus_data[col.TRADE_DATE] = pd.to_datetime(
                bonus_data[col.TRADE_DATE]
            ).dt.date
            log.info("Bonus data is pulled for %s entries", len(bonus_data))
        else:
            bonus_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])

        buyback_file = Path(const.LOCAL_DATA_PATH / const.BUYBACK_CSV)
        if buyback_file.exists():
            buyback_data = pd.read_csv(buyback_file)
            buyback_data[col.TRADE_DATE] = pd.to_datetime(
                buyback_data[col.TRADE_DATE]
            ).dt.date
            log.info("Buyback data is pulled for %s entries", len(buyback_data))
        else:
            buyback_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])

        last_date = pd.to_datetime(
            Path(const.LOCAL_DATA_PATH / const.LAST_DATE_TXT).read_text()
        ).date()

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
        ipo_data = pd.DataFrame(
            columns=[
                col.SYMBOL,
                col.ISIN,
                col.TRADE_DATE,
                col.QUANTITY,
                col.PRICE,
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
        merger_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        demerger_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        bonus_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        buyback_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        last_date = const.DEFAULT_LAST_DATE

    return (
        dividend_data,
        splits_data,
        ipo_data,
        merger_data,
        demerger_data,
        bonus_data,
        buyback_data,
        last_date,
    )


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
