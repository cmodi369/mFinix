# standard imports
from datetime import date
from typing import Optional

import pandas as pd
from pyxirr import xirr

import mFinix.constants.columns as col

# module specific constants
import mFinix.core.data_management as dm
import mFinix.core.data_processing as dp
from mFinix.core.historical_price_cache import (
    get_cached_fy_value,
    update_cached_fy_value,
)
from mFinix.core.yfinance_query import fetch_stocks_price
from mFinix.util import log


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


def calculate_portfolio_value(stocks_xirr_df: pd.DataFrame) -> float:
    """Calculate total current value of the portfolio.

    Parameters
    ----------
    stocks_xirr_df : pd.DataFrame
        Per-stock XIRR dataframe containing TOTAL_QUANTITY and CURRENT_PRICE columns.

    Returns
    -------
    float
        Total portfolio value.
    """
    return (
        stocks_xirr_df[col.TOTAL_QUANTITY] * stocks_xirr_df[col.CURRENT_PRICE]
    ).sum()


def calculate_portfolio_xirr_from_transactions(
    transactions_data: pd.DataFrame, portfolio_stocks: pd.DataFrame
) -> float:
    """
    Calculate portfolio XIRR from zerodha tradebook transactions.

    Combines all buy/sell transaction amounts with current portfolio value
    to compute the overall portfolio XIRR.
    """
    full_xirr_data = pd.concat([transactions_data, portfolio_stocks])

    return (
        xirr(
            full_xirr_data[col.TRADE_DATE].tolist(),
            full_xirr_data[col.TRANSACTION_AMOUNT].tolist(),
        )
        * 100
    )


def calculate_stock_xirr_from_transactions(transactions_data: pd.DataFrame) -> dict:
    """
    Calculate XIRR from zerodha tradebook
    """
    ret_data_dict = {}

    # get current portfolio stocks
    portfolio_stocks = dp.get_portfolio_stocks(transactions_data).reset_index()

    # fetch latest stock price
    # Create identifier -> Symbol mapping for fallback logic in fetch_stocks_price
    # If ISIN is empty, use Symbol as identifier
    portfolio_stocks["price_identifier"] = portfolio_stocks.apply(
        lambda row: (
            row[col.ISIN]
            if pd.notna(row[col.ISIN]) and row[col.ISIN] != ""
            else row[col.SYMBOL]
        ),
        axis=1,
    )

    isin_symbol_map = dict(
        zip(portfolio_stocks["price_identifier"], portfolio_stocks[col.SYMBOL])
    )

    latest_stock_price_data = fetch_stocks_price(isin_symbol_map)
    latest_stock_price_data.name = col.CURRENT_PRICE

    # add latest price in portfolio and transactions data
    portfolio_stocks = portfolio_stocks.merge(
        latest_stock_price_data,
        left_on="price_identifier",
        right_index=True,
        how="left",
    ).drop(columns=["price_identifier"])
    portfolio_stocks = portfolio_stocks.dropna(subset=col.CURRENT_PRICE)
    portfolio_stocks[col.TRADE_DATE] = date.today()
    portfolio_stocks[col.TRANSACTION_AMOUNT] = (
        -portfolio_stocks[col.TOTAL_QUANTITY] * portfolio_stocks[col.CURRENT_PRICE]
    )
    full_xirr_data = pd.concat([transactions_data, portfolio_stocks])

    # calculate individual stocks XIRR
    stocks_xirr_df = (
        full_xirr_data.groupby(col.SYMBOL, as_index=False)
        .apply(
            lambda group: (
                xirr(
                    group[col.TRADE_DATE].tolist(),
                    group[col.TRANSACTION_AMOUNT].tolist(),
                )
                if (
                    group[col.TRANSACTION_AMOUNT].gt(0).any()
                    and group[col.TRANSACTION_AMOUNT].lt(0).any()
                )
                else None
            )
        )
        .rename(columns={None: col.XIRR})
    )

    # calculate stocks XIRR
    stocks_xirr_df = (
        portfolio_stocks.merge(stocks_xirr_df, how="inner", on=col.SYMBOL)
        .sort_values(by=col.SYMBOL)
        .reset_index(drop=True)
    )

    # update stocks_xirr_df with average buy price, P&L and P&L % for each stock
    dm.calculate_and_add_avg_buy_for_all_stocks(transactions_data, stocks_xirr_df)
    dm.calculate_and_add_current_total_value_for_all_stocks(stocks_xirr_df)
    dm.calculate_and_add_pnl_for_all_stocks(stocks_xirr_df)

    ret_data_dict["stocks_xirr_data"] = stocks_xirr_df

    return ret_data_dict


def _get_fy_end_portfolio_value(
    transactions_up_to_fy_end: pd.DataFrame,
    fy_end_date: date,
    fy_label: str,
    force_refresh: bool = False,
) -> Optional[float]:
    """Return (cached) portfolio value at the end of a given FY.

    For completed FYs the value is cached on disk after first calculation.
    """
    if not force_refresh:
        cached = get_cached_fy_value(fy_label)
        if cached is not None:
            log.info("Using cached portfolio value for %s: %.2f", fy_label, cached)
            return cached

    portfolio = dp.get_portfolio_stocks(transactions_up_to_fy_end).reset_index()
    if portfolio.empty:
        return None

    # Build identifier map (ISIN preferred, fallback Symbol)
    portfolio["_price_id"] = portfolio.apply(
        lambda r: r[col.ISIN]
        if pd.notna(r.get(col.ISIN, "")) and r[col.ISIN] != ""
        else r[col.SYMBOL],
        axis=1,
    )
    isin_symbol_map = dict(zip(portfolio["_price_id"], portfolio[col.SYMBOL]))

    prices = fetch_stocks_price(isin_symbol_map, on_date=fy_end_date)
    prices.name = col.CURRENT_PRICE

    portfolio = portfolio.merge(
        prices, left_on="_price_id", right_index=True, how="left"
    ).drop(columns=["_price_id"])
    portfolio = portfolio.dropna(subset=[col.CURRENT_PRICE])

    value = float((portfolio[col.TOTAL_QUANTITY] * portfolio[col.CURRENT_PRICE]).sum())

    # Cache only for completed FYs
    if fy_end_date < date.today():
        update_cached_fy_value(fy_label, value)
        log.info("Cached portfolio value for %s: %.2f", fy_label, value)

    return value


def calculate_fy_xirr_series(
    transactions_data: pd.DataFrame,
    current_portfolio_value: float,
) -> dict:
    """Calculate XIRR for each Financial Year (Apr-Mar).

    Uses cached FY-end portfolio values to avoid repeated yfinance calls.
    The current (incomplete) FY uses the live portfolio value.

    Parameters
    ----------
    transactions_data : pd.DataFrame
        Full transactions DataFrame with TRADE_DATE and TRANSACTION_AMOUNT columns.
    current_portfolio_value : float
        Live portfolio value in INR (used for the current FY).

    Returns
    -------
    dict
        Mapping of FY label (e.g. "FY2024-25") -> XIRR as a percentage.
        Returns None for FYs where XIRR cannot be computed.
    """
    from mFinix.core.benchmark_data import (
        fy_label_to_dates,
        get_all_fy_labels,
        is_fy_complete,
    )

    if transactions_data.empty:
        return {}

    transactions_data = transactions_data.copy()
    transactions_data[col.TRADE_DATE] = pd.to_datetime(
        transactions_data[col.TRADE_DATE]
    )

    earliest_date = transactions_data[col.TRADE_DATE].min().date()
    all_fy_labels = get_all_fy_labels(earliest_date)

    result = {}

    for fy_label in all_fy_labels:
        fy_start, fy_end = fy_label_to_dates(fy_label)
        fy_complete = is_fy_complete(fy_label)

        clean_label = fy_label.split(" ")[0]
        start_year = int(clean_label[2:6])
        prev_start_year = start_year - 1
        prev_fy_label = f"FY{prev_start_year}-{str(start_year)[2:]}"
        prev_fy_end = date(start_year, 3, 31)

        # Transactions up to previous FY end (for starting portfolio value)
        tx_up_to_prev_fy = transactions_data[
            transactions_data[col.TRADE_DATE] <= pd.Timestamp(prev_fy_end)
        ]

        # Transactions up to FY-end (to calculate FY-end value if needed)
        tx_up_to_fy = transactions_data[
            transactions_data[col.TRADE_DATE] <= pd.Timestamp(fy_end)
        ]

        # Transactions within the FY only
        tx_in_fy = transactions_data[
            (transactions_data[col.TRADE_DATE] >= pd.Timestamp(fy_start))
            & (transactions_data[col.TRADE_DATE] <= pd.Timestamp(fy_end))
        ]

        fy_start_value = 0.0
        if not tx_up_to_prev_fy.empty:
            val = _get_fy_end_portfolio_value(
                tx_up_to_prev_fy, prev_fy_end, prev_fy_label
            )
            if val is not None:
                fy_start_value = val

        # Determine portfolio value at FY-end
        if fy_complete:
            fy_end_value = _get_fy_end_portfolio_value(tx_up_to_fy, fy_end, fy_label)
        else:
            # Current FY - use live value
            fy_end_value = current_portfolio_value

        if fy_end_value is None:
            fy_end_value = 0.0

        if fy_start_value <= 0 and fy_end_value <= 0 and tx_in_fy.empty:
            log.warning("No portfolio value available for %s, skipping XIRR.", fy_label)
            result[fy_label] = None
            continue

        # Build XIRR cash flows:
        dates_list = []
        amounts_list = []

        # 1. Starting portfolio value (simulated investment/inflow into the period)
        if fy_start_value > 0:
            dates_list.append(prev_fy_end)
            amounts_list.append(fy_start_value)

        # 2. Transactions during the FY
        if not tx_in_fy.empty:
            dates_list.extend(tx_in_fy[col.TRADE_DATE].dt.date.tolist())
            amounts_list.extend(tx_in_fy[col.TRANSACTION_AMOUNT].tolist())

        # 3. Ending portfolio value (simulated withdrawal/outflow from the period)
        end_date = fy_end if fy_complete else date.today()
        if fy_end_value > 0:
            dates_list.append(end_date)
            amounts_list.append(-fy_end_value)

        # Need at least one positive and one negative cash flow
        if not (any(a > 0 for a in amounts_list) and any(a < 0 for a in amounts_list)):
            result[fy_label] = None
            continue

        try:
            fy_xirr_value = xirr(dates_list, amounts_list) * 100
            result[fy_label] = round(float(fy_xirr_value), 2)
            log.info("FY XIRR %s: %.2f%%", fy_label, result[fy_label])
        except Exception as exc:
            log.warning("XIRR computation failed for %s: %s", fy_label, exc)
            result[fy_label] = None

    return result
