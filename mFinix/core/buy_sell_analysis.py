"""
Buy/Sell Analysis Engine.

Analyses the quality and timing of buy/sell sentiment switches in the portfolio.
Computes per-call metrics (current move, 1-year move, relative impact) and
aggregate KPIs (total alpha, win rates, sentiment lag, grades).

All data is derived from existing transactions and portfolio XIRR data—no new
external API calls are made.
"""

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.util import log

# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------


def _assign_grade(relative_impact: float) -> str:
    """Assign a letter grade based on relative impact value.

    Parameters
    ----------
    relative_impact : float
        The weighted contribution of this call to the portfolio.

    Returns
    -------
    str
        A letter grade from A to F.
    """
    abs_val = abs(relative_impact)
    if relative_impact >= 0:
        if abs_val >= 5.0:
            return "A"
        if abs_val >= 2.0:
            return "B"
        if abs_val >= 0.5:
            return "C"
        return "D"
    else:
        if abs_val >= 2.0:
            return "F"
        if abs_val >= 0.5:
            return "E"
        return "D"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_price_adjustment_factor(
    symbol: str, call_date: Any, transactions_data: pd.DataFrame
) -> float:
    """Calculate the cumulative multiplier for splits and bonuses after call_date.

    Parameters
    ----------
    symbol : str
        Stock ticker symbol.
    call_date : date
        The date of the sentiment switch.
    transactions_data : pd.DataFrame
        Full transactions history.

    Returns
    -------
    float
        The cumulative multiplier (e.g., 2.0 for a 1:1 bonus).
    """
    # Filter for corporate actions of this stock after the call date
    actions = transactions_data[
        (transactions_data[col.SYMBOL] == symbol)
        & (transactions_data[col.TRADE_DATE] > call_date)
        & (transactions_data[col.TRADE_TYPE].isin([const.STOCK_SPLIT, const.BONUS]))
    ]
    if actions.empty:
        return 1.0

    # Sort full history and keep ONLY quantity-bearing transactions for tracking
    full_history = transactions_data[
        transactions_data[col.SYMBOL] == symbol
    ].sort_values([col.TRADE_DATE, col.TRADE_TYPE])
    # Filter out rows like DIVIDENDS that don't have TOTAL_QUANTITY
    inventory_history = full_history[
        full_history[col.TOTAL_QUANTITY].notna()
    ].reset_index(drop=True)

    multiplier = 1.0
    for _, row in actions.iterrows():
        # Find this action's position in the inventory history
        match = inventory_history[
            (inventory_history[col.TRADE_DATE] == row[col.TRADE_DATE])
            & (inventory_history[col.TRADE_TYPE] == row[col.TRADE_TYPE])
            & (inventory_history[col.QUANTITY] == row[col.QUANTITY])
        ]
        if match.empty:
            continue

        idx = match.index[0]
        if idx == 0:
            continue

        # Get the quantity from the immediately preceding inventory-bearing row
        qty_before = inventory_history.iloc[idx - 1][col.TOTAL_QUANTITY]
        event_qty = row[col.QUANTITY]

        if qty_before > 0:
            multiplier *= (qty_before + event_qty) / qty_before

    return multiplier


def _identify_sentiment_calls(transactions_data: pd.DataFrame) -> pd.DataFrame:
    """Identify the first BUY and last SELL for each stock.

    For each symbol we extract:
      - The earliest BUY transaction (the initial accumulation call).
      - The latest SELL transaction (the exit/trim call), if any.

    Parameters
    ----------
    transactions_data : pd.DataFrame
        Processed transactions with columns: SYMBOL, TRADE_TYPE, TRADE_DATE,
        PRICE, ISIN.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: symbol, call_type, call_date, call_price, isin
    """
    calls = []

    for symbol, group in transactions_data.groupby(col.SYMBOL):
        isin = group[col.ISIN].iloc[0]

        # --- First BUY ---
        buys = group[group[col.TRADE_TYPE] == const.BUY]
        if not buys.empty:
            first_buy = buys.sort_values(col.TRADE_DATE).iloc[0]
            calls.append(
                {
                    "symbol": symbol,
                    "call_type": "BUY",
                    "call_date": first_buy[col.TRADE_DATE],
                    "call_price": first_buy[col.PRICE],
                    "isin": isin,
                }
            )

        # --- Last SELL ---
        sells = group[group[col.TRADE_TYPE] == const.SELL]
        if not sells.empty:
            last_sell = sells.sort_values(col.TRADE_DATE).iloc[-1]
            calls.append(
                {
                    "symbol": symbol,
                    "call_type": "SELL",
                    "call_date": last_sell[col.TRADE_DATE],
                    "call_price": abs(last_sell[col.PRICE]),
                    "isin": isin,
                }
            )

    return pd.DataFrame(calls)


def _compute_per_call_metrics(
    calls_df: pd.DataFrame,
    stocks_xirr_data: pd.DataFrame,
    transactions_data: pd.DataFrame,
) -> pd.DataFrame:
    """Compute per-call metrics: current_move, 1yr_move, portfolio_weight,
    relative_impact, and grade.

    Parameters
    ----------
    calls_df : pd.DataFrame
        Output of ``_identify_sentiment_calls``.
    stocks_xirr_data : pd.DataFrame
        Per-stock XIRR data with CURRENT_PRICE, PRESENT_VALUE, etc.
    transactions_data : pd.DataFrame
        Full processed transactions.

    Returns
    -------
    pd.DataFrame
        Enriched calls DataFrame.
    """
    if calls_df.empty:
        return calls_df

    # Build a current-price lookup keyed on symbol
    price_lookup = dict(
        zip(stocks_xirr_data[col.SYMBOL], stocks_xirr_data[col.CURRENT_PRICE])
    )

    # Total portfolio value for weight calculation
    total_portfolio_value = stocks_xirr_data[col.PRESENT_VALUE].sum()
    if total_portfolio_value == 0:
        total_portfolio_value = 1.0  # avoid division by zero

    # Portfolio weight lookup (present_value / total)
    weight_lookup = dict(
        zip(
            stocks_xirr_data[col.SYMBOL],
            stocks_xirr_data[col.PRESENT_VALUE] / total_portfolio_value * 100,
        )
    )

    # --- Approximate 1-year price from transactions ---
    # For each stock we find the transaction closest to (call_date + 1 year)
    # to approximate price about 1 year after the call.
    def _find_price_near_date(symbol: str, target_date) -> float | None:
        """Return a price from transactions nearest to target_date."""
        stock_txns = transactions_data[
            (transactions_data[col.SYMBOL] == symbol)
            & (transactions_data[col.TRADE_TYPE].isin([const.BUY, const.SELL]))
        ].copy()
        if stock_txns.empty:
            return None
        stock_txns["_delta"] = (
            pd.to_datetime(stock_txns[col.TRADE_DATE]) - pd.Timestamp(target_date)
        ).abs()
        nearest = stock_txns.sort_values("_delta").iloc[0]
        return abs(nearest[col.PRICE])

    today = date.today()

    current_moves = []
    one_yr_moves = []
    portfolio_weights = []
    relative_impacts = []
    current_prices = []
    adjusted_call_prices = []
    grades = []

    for _, row in calls_df.iterrows():
        symbol = row["symbol"]
        call_price = row["call_price"]
        call_date = row["call_date"]
        call_type = row["call_type"]

        # Current price (from portfolio data if available, else call_price)
        current_price = price_lookup.get(symbol, call_price)

        # --- Price Adjustment for Corporate Actions ---
        adj_factor = _get_price_adjustment_factor(symbol, call_date, transactions_data)
        adj_call_price = call_price / adj_factor if adj_factor > 0 else call_price

        # --- Current Move ---
        if adj_call_price and adj_call_price != 0:
            if call_type == "BUY":
                current_move = ((current_price - adj_call_price) / adj_call_price) * 100
            else:
                # For SELL, positive move means stock went DOWN after sell (good)
                current_move = ((adj_call_price - current_price) / adj_call_price) * 100
        else:
            current_move = 0.0

        # --- 1-Year Move ---
        call_date_dt = pd.Timestamp(call_date)
        target_date = call_date_dt + pd.DateOffset(years=1)

        if target_date.date() <= today:
            # The 1-year window has passed – try to find a price near that date
            price_1yr = _find_price_near_date(symbol, target_date)
            if price_1yr and adj_call_price and adj_call_price != 0:
                one_yr_move = ((price_1yr - adj_call_price) / adj_call_price) * 100
            else:
                one_yr_move = current_move  # fallback
        else:
            # Less than 1 year – use current move as proxy
            one_yr_move = current_move

        # --- Portfolio Weight ---
        weight = weight_lookup.get(symbol, 0.0)

        # --- Relative Impact ---
        relative_impact = current_move * weight / 100.0

        # --- Grade ---
        grade = _assign_grade(relative_impact)

        current_moves.append(round(current_move, 2))
        one_yr_moves.append(round(one_yr_move, 2))
        portfolio_weights.append(round(weight, 1))
        relative_impacts.append(round(relative_impact, 2))
        current_prices.append(round(current_price, 2))
        adjusted_call_prices.append(round(adj_call_price, 2))
        grades.append(grade)

    calls_df = calls_df.copy()
    calls_df["current_move"] = current_moves
    calls_df["one_yr_move"] = one_yr_moves
    calls_df["portfolio_weight"] = portfolio_weights
    calls_df["relative_impact"] = relative_impacts
    calls_df["current_price"] = current_prices
    calls_df["adj_call_price"] = adjusted_call_prices
    calls_df["grade"] = grades

    return calls_df


def _compute_sentiment_lag(transactions_data: pd.DataFrame) -> float:
    """Compute the average sentiment lag in months.

    Sentiment lag = average time between the first BUY and the first SELL
    for each stock that has both.

    Parameters
    ----------
    transactions_data : pd.DataFrame
        Processed transactions.

    Returns
    -------
    float
        Average sentiment lag in months. Returns 0.0 if no switches found.
    """
    lags = []
    for _, group in transactions_data.groupby(col.SYMBOL):
        buys = group[group[col.TRADE_TYPE] == const.BUY].sort_values(col.TRADE_DATE)
        sells = group[group[col.TRADE_TYPE] == const.SELL].sort_values(col.TRADE_DATE)

        if buys.empty or sells.empty:
            continue

        first_buy_date = pd.Timestamp(buys.iloc[0][col.TRADE_DATE])
        first_sell_date = pd.Timestamp(sells.iloc[0][col.TRADE_DATE])

        if first_sell_date > first_buy_date:
            delta_months = (first_sell_date - first_buy_date).days / 30.44
            lags.append(delta_months)

    return round(float(np.mean(lags)), 1) if lags else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_buy_sell_analysis(
    transactions_data: pd.DataFrame,
    stocks_xirr_data: pd.DataFrame,
) -> dict[str, Any]:
    """Compute full buy/sell analysis from existing data.

    Parameters
    ----------
    transactions_data : pd.DataFrame
        Processed tradebook transactions.
    stocks_xirr_data : pd.DataFrame
        Per-stock XIRR data with price, P&L, and value columns.

    Returns
    -------
    dict
        ``kpis`` : dict with total_alpha, buy_win_rate, sell_win_rate, sentiment_lag
        ``details_df`` : DataFrame with per-call details
    """
    log.info("Computing buy/sell analysis...")

    # 1. Identify sentiment calls
    calls_df = _identify_sentiment_calls(transactions_data)
    if calls_df.empty:
        log.warning("No sentiment calls found in transactions data.")
        return {
            "kpis": {
                "total_alpha": 0.0,
                "buy_win_rate": 0.0,
                "sell_win_rate": 0.0,
                "sentiment_lag": 0.0,
            },
            "details_df": pd.DataFrame(),
        }

    # 2. Compute per-call metrics
    details_df = _compute_per_call_metrics(
        calls_df, stocks_xirr_data, transactions_data
    )

    # 3. Aggregate KPIs
    total_alpha = round(details_df["relative_impact"].sum(), 2)

    buy_calls = details_df[details_df["call_type"] == "BUY"]
    sell_calls = details_df[details_df["call_type"] == "SELL"]

    buy_win_rate = 0.0
    if len(buy_calls) > 0:
        buy_wins = (buy_calls["current_move"] > 0).sum()
        buy_win_rate = round((buy_wins / len(buy_calls)) * 100, 1)

    sell_win_rate = 0.0
    if len(sell_calls) > 0:
        sell_wins = (sell_calls["current_move"] > 0).sum()
        sell_win_rate = round((sell_wins / len(sell_calls)) * 100, 1)

    sentiment_lag = _compute_sentiment_lag(transactions_data)

    # 4. Sort details by absolute relative impact descending
    details_df = details_df.sort_values(
        "relative_impact", key=abs, ascending=False
    ).reset_index(drop=True)

    log.info(
        "Buy/Sell analysis complete: alpha=%.2f%%, buy_wr=%.1f%%, sell_wr=%.1f%%",
        total_alpha,
        buy_win_rate,
        sell_win_rate,
    )

    return {
        "kpis": {
            "total_alpha": total_alpha,
            "buy_win_rate": buy_win_rate,
            "sell_win_rate": sell_win_rate,
            "sentiment_lag": sentiment_lag,
        },
        "details_df": details_df,
    }
