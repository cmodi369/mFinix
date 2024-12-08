from typing import List

import pandas as pd
from corporate_actions import add_corporate_actions_in_tradebook

import mFinix.constants.constants as const
from mFinix.constants.columns import ISIN, QUANTITY, SYMBOL, TRADE_TYPE


def get_latest_portfolio_stocks(trade_data: pd.DataFrame) -> List[str]:
    # TODO: Remove duplicates

    # find stocks where buy quantity is more than sell quantity
    data = trade_data.pivot_table(
        index=ISIN, columns=TRADE_TYPE, values=QUANTITY, aggfunc="sum", fill_value=0
    ).reset_index()

    return data[~data[const.BUY].eq(data[const.SELL])][SYMBOL].tolist()
