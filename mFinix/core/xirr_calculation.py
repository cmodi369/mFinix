# standard imports
from datetime import date

import pandas as pd
from pyxirr import xirr

import mFinix.constants.columns as col

# module specific constants
import mFinix.constants.constants as const
import mFinix.core.data_management as dm
import mFinix.core.data_processing as dp
from mFinix.core.corporate_actions import (
    add_corporate_actions_in_tradebook,
    automatic_update_corporate_actions_data,
)
from mFinix.core.data_management import fetch_stocks_price


def calculate_portfolio_xirr_from_ledger(
    ledger_df: pd.DataFrame, latest_value: float
) -> float:
    """
    Calculate XIRR from zerodha ledger
    """

    combined_flow = ledger_df.apply(
        lambda row: (
            -row["credit"]
            if row["voucher_type"] == "Bank Receipts"
            else (row["debit"] if row["voucher_type"] == "Bank Payments" else 0)
        ),
        axis=1,
    )

    return (
        xirr(
            ledger_df["posting_date"].tolist() + [pd.Timestamp.today()],
            combined_flow.tolist() + [latest_value],
        )
        * 100
    )


def calculate_stock_xirr_from_transactions(transactions_data: pd.DataFrame) -> dict:
    """
    Calculate XIRR from zerodha tradebook
    """
    ret_data_dict = {}

    # get all years from data
    years = pd.to_datetime(transactions_data[col.TRADE_DATE]).dt.year.unique().tolist()

    # TODO: calculate portfolio value for all years, save them in local data in json till last year
    # TODO: Use them next time to calculate calendar year wise XIRR and portfolio XIRR
    # ret_data_dict["portfolio_value_df"] = {}
    # for year in years:
    #     ret_data_dict["portfolio_value_df"][year] = calculate_portfolio_value_as_on_date(
    #         transactions_data[transactions_data[col.TRADE_DATE].dt.year <= year],
    #         _get_query_date(year))

    # get current portfolio stocks
    portfolio_stocks = dp.get_portfolio_stocks(transactions_data)

    # fetch latest stock price
    latest_stock_price_data = fetch_stocks_price(portfolio_stocks.index.unique())
    latest_stock_price_data.name = col.CURRENT_PRICE

    # add latest price in portfolio and transactions data
    portfolio_stocks = portfolio_stocks.merge(
        latest_stock_price_data, left_index=True, right_index=True, how="left"
    ).reset_index()
    portfolio_stocks = portfolio_stocks.dropna(subset=col.CURRENT_PRICE)
    portfolio_stocks[col.TRADE_DATE] = date.today()
    portfolio_stocks[col.TRANSACTION_AMOUNT] = (
        -portfolio_stocks[col.TOTAL_QUANTITY] * portfolio_stocks[col.CURRENT_PRICE]
    )
    full_xirr_data = pd.concat([transactions_data, portfolio_stocks])

    # calculate individual stocks XIRR
    stocks_xirr_df = (
        full_xirr_data.groupby([col.ISIN, col.SYMBOL], as_index=False)
        .apply(
            lambda group: xirr(
                group[col.TRADE_DATE].tolist(), group[col.TRANSACTION_AMOUNT].tolist()
            )
            if (
                group[col.TRANSACTION_AMOUNT].gt(0).any()
                and group[col.TRANSACTION_AMOUNT].lt(0).any()
            )
            else None
        )
        .rename(columns={None: col.XIRR})
    )

    # calculate portfolio XIRR
    ret_data_dict["portfolio_xirr"] = (
        xirr(
            full_xirr_data[col.TRADE_DATE].tolist(),
            full_xirr_data[col.TRANSACTION_AMOUNT].tolist(),
        )
        * 100
    )

    # calculate stocks XIRR
    ret_data_dict["stocks_xirr_data"] = portfolio_stocks.merge(
        stocks_xirr_df, how="inner", on=[col.ISIN, col.SYMBOL]
    )

    return ret_data_dict


def calculate_portfolio_value_as_on_date(transactions: pd.DataFrame, as_on_date: date):
    # get current portfolio stocks
    portfolio_stocks = dp.get_portfolio_stocks(transactions)

    # fetch latest stock price
    latest_stock_price_df = fetch_stocks_price(
        portfolio_stocks.index.unique(), as_on_date
    )

    return 50000


def _get_query_date(year: int) -> date:
    if year == date.today().year:
        return date.today()
    return date(year, 12, 31)


if __name__ == "__main__":
    latest_value = 456800.0
    ledger_data = dm.read_ledger_data()
    portfolio_xirr = calculate_portfolio_xirr_from_ledger(ledger_data, latest_value)

    print(portfolio_xirr)
