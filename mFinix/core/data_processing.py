from typing import List

import pandas as pd

import mFinix.constants.constants as const
from mFinix.constants.columns import ISIN, QUANTITY, SYMBOL, TOTAL_QUANTITY, TRADE_TYPE
from mFinix.core.corporate_actions import (
    add_corporate_actions_in_tradebook,
    automatic_update_corporate_actions_data,
)
from mFinix.core.read_kite_data import read_tradebook_data


def get_portfolio_stocks(trade_data: pd.DataFrame) -> pd.DataFrame:
    # find latest row with quantity for each stock
    last_rows = (
        trade_data[trade_data[TRADE_TYPE].isin([const.BUY, const.SELL])]
        .groupby(SYMBOL)
        .last()
    )

    # filter stocks with total quantity not equal to 0
    portfolio_data = last_rows[last_rows[TOTAL_QUANTITY].ne(0)]

    return portfolio_data


def prepare_transactions_data():
    tradebook_df = read_tradebook_data()
    updated_trade_data = add_corporate_actions_in_tradebook(tradebook_df)

    return updated_trade_data
