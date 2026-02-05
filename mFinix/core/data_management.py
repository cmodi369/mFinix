"""
Data management utilities for stock portfolio calculations.
"""

import numpy as np
import pandas as pd

import mFinix.constants.columns as col
from mFinix.constants.constants import BUY


def _calculate_weighted_avg_price_for_isin(
    isin: str,
    quantity: float,
    transactions_data: pd.DataFrame,
) -> float:
    """Calculate weighted average buy price for a single ISIN.

    Calculates the average buy price by taking the latest buy transactions

    Parameters
    ----------
    isin : str
        The ISIN identifier for the stock.
    quantity : float
        The total quantity to calculate average price for.
    transactions_data : pd.DataFrame
        DataFrame containing all buy transactions with columns: ISIN, TRADE_TYPE,
        TRADE_DATE, QUANTITY, PRICE.

    Returns
    -------
    float
        The weighted average buy price for the given quantity.
        Returns 0 if quantity is zero or no transactions are found.
    """
    if quantity <= 0:
        return 0.0

    # Filter and sort buy transactions in reverse chronological order
    buy_transactions = transactions_data[
        (transactions_data[col.ISIN] == isin)
        & (transactions_data[col.TRADE_TYPE] == BUY)
    ].sort_values(by=col.TRADE_DATE, ascending=False)

    if buy_transactions.empty:
        return 0.0

    total_price = 0.0
    remaining_quantity = quantity

    for _, transaction in buy_transactions.iterrows():
        if remaining_quantity <= 0:
            break

        transaction_quantity = transaction[col.QUANTITY]
        transaction_price = transaction[col.PRICE]
        quantity_to_use = min(transaction_quantity, remaining_quantity)

        total_price += quantity_to_use * transaction_price
        remaining_quantity -= quantity_to_use

    return total_price / quantity


def calculate_and_add_avg_buy_for_all_stocks(
    transactions_data: pd.DataFrame,
    xirr_df: pd.DataFrame,
) -> None:
    """Calculate and add average buy prices to portfolio dataframe.

    Computes the weighted average buy price for each stock in the portfolio
    and the corresponding total buy value. Uses the latest buy transactions
    in reverse chronological order.

    Parameters
    ----------
    transactions_data : pd.DataFrame
        DataFrame containing all transactions with columns: ISIN, TRADE_TYPE,
        TRADE_DATE, QUANTITY, PRICE.
    xirr_df : pd.DataFrame
        DataFrame containing portfolio data with columns: ISIN, TOTAL_QUANTITY.
        Modified in-place to add AVG_BUY_PRICE and BUY_VALUE columns.

    Returns
    -------
    None
        Modifies xirr_df in-place by adding two new columns.
    """
    # Calculate average buy prices for each ISIN
    avg_buy_prices = [
        _calculate_weighted_avg_price_for_isin(
            row[col.ISIN],
            row[col.TOTAL_QUANTITY],
            transactions_data,
        )
        for _, row in xirr_df.iterrows()
    ]

    # Vectorized operations for adding calculated columns
    xirr_df[col.AVG_BUY_PRICE] = avg_buy_prices
    xirr_df[col.BUY_VALUE] = xirr_df[col.TOTAL_QUANTITY] * xirr_df[col.AVG_BUY_PRICE]


def calculate_and_add_current_total_value_for_all_stocks(
    xirr_df: pd.DataFrame,
) -> None:
    """Calculate and add current total value for all stocks to dataframe.

    Computes the present value for each stock by multiplying total quantity
    by current price using vectorized operations.

    Parameters
    ----------
    xirr_df : pd.DataFrame
        DataFrame containing portfolio data with columns: TOTAL_QUANTITY,
        CURRENT_PRICE. Modified in-place to add PRESENT_VALUE column.

    Returns
    -------
    None
        Modifies xirr_df in-place by adding PRESENT_VALUE column.
    """
    xirr_df[col.PRESENT_VALUE] = (
        xirr_df[col.TOTAL_QUANTITY] * xirr_df[col.CURRENT_PRICE]
    )


def calculate_and_add_pnl_for_all_stocks(xirr_df: pd.DataFrame) -> None:
    """Calculate and add profit/loss metrics to portfolio dataframe.

    Computes absolute and percentage profit/loss for each stock by comparing
    present value against buy value using vectorized operations.

    Parameters
    ----------
    xirr_df : pd.DataFrame
        DataFrame containing portfolio data with columns: PRESENT_VALUE,
        BUY_VALUE. Modified in-place to add PNL and PNL_PERCENTAGE columns.

    Returns
    -------
    None
        Modifies xirr_df in-place by adding PNL and PNL_PERCENTAGE columns.

    """
    xirr_df[col.PNL] = xirr_df[col.PRESENT_VALUE] - xirr_df[col.BUY_VALUE]
    xirr_df[col.PNL_PERCENTAGE] = xirr_df[col.PNL] / xirr_df[col.BUY_VALUE]
