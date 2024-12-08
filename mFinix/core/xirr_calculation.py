# standard imports
import data_management as dm
import data_processing as dp
import pandas as pd
from corporate_actions import (
    add_corporate_actions_in_tradebook,
    update_corporate_actions_data,
)
from pyxirr import xirr

# module specific constants
import mFinix.constants.constants as const


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


def calculate_stock_xirr_from_tradebook(tradebook_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate XIRR from zerodha tradebook
    """
    # get all years from data
    years = tradebook_df["trade_date"].dt.year.unique().tolist()

    ret_data = pd.DataFrame(columns=["Stock Name"] + years + ["All Time"])

    # TODO: Adjust stocks for corporate actions
    update_corporate_actions_data(tradebook_df)
    updated_trade_data = add_corporate_actions_in_tradebook(tradebook_df)

    # get current portfolio stocks
    portfolio_stocks = dp.get_latest_portfolio_stocks(updated_trade_data)

    # TODO: pull latest stock price for portfolio stocks

    # TODO: calculate XIRR for all stocks, add latest value for portfolio stocks

    return ret_data


if __name__ == "__main__":
    latest_value = 477000.0
    ledger_data = dm.read_ledger_data()
    portfolio_xirr = calculate_portfolio_xirr_from_ledger(ledger_data, latest_value)

    tradebook_data = dm.read_tradebook_data()
    calculate_stock_xirr_from_tradebook(tradebook_data)
    print(portfolio_xirr)
