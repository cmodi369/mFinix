from datetime import date, datetime

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.core.data_processing import prepare_transactions_data
from mFinix.core.read_kite_data import read_holding_data, read_ledger_data
from mFinix.core.xirr_calculation import (
    calculate_portfolio_value,
    calculate_portfolio_xirr_from_ledger,
    calculate_stock_xirr_from_transactions,
)


def run_once(method):
    """Decorator to ensure a method can only be executed once per instance."""

    def wrapper(self, *args, **kwargs):
        # Use an instance-specific attribute to track if the method has run
        attr_name = f"_has_run_{method.__name__}"
        if getattr(self, attr_name, False):
            return
        setattr(self, attr_name, True)
        return method(self, *args, **kwargs)

    return wrapper


def get_status_icon(row):
    """Generate HTML status icon with tooltip for a row."""
    is_discrepancy = row[col.IS_DISCREPANCY]
    if is_discrepancy:
        expected = row.get(col.TOTAL_QUANTITY, 0)
        actual = row.get(col.HOLDING_QUANTITY, 0)
        title = f"Discrepancy: Expected {expected} but broker says {actual}"
        color = "#e74c3c"
        bg = "rgba(231, 76, 60, 0.1)"
        icon = "exclamation"
    else:
        title = "Quantity matches broker holdings"
        color = "#2ecc71"
        bg = "rgba(46, 204, 113, 0.1)"
        icon = "check"

    return f'<div class="status-icon" style="background-color: {bg}; color: {color};" title="{title}"><i class="fa-solid fa-{icon}"></i></div>'


def prepare_stocks_tab_data() -> dict:
    """Prepare all data required for the Stocks tab.

    Returns
    -------
    dict
        Dictionary containing:
        - transactions_data: processed tradebook transactions
        - stocks_xirr_data: per-stock XIRR with P&L metrics
        - portfolio_xirr: overall portfolio XIRR (ledger-based)
        - equity_holdings: equity holdings data
        - mf_holdings: mutual fund holdings data
    """
    # load and process tradebook transactions
    transactions_data = prepare_transactions_data()

    # compute per-stock XIRR, P&L, and portfolio metrics
    stocks_data = calculate_stock_xirr_from_transactions(transactions_data)

    # load holdings data
    equity_holdings, mf_holdings = read_holding_data()

    # compute portfolio XIRR from ledger cash flows
    ledger_df = read_ledger_data()
    portfolio_value = calculate_portfolio_value(stocks_data["stocks_xirr_data"])
    portfolio_xirr = calculate_portfolio_xirr_from_ledger(ledger_df, portfolio_value)

    # Merge holding quantity and identify discrepancies
    stocks_xirr_df = stocks_data["stocks_xirr_data"]
    if not equity_holdings.empty:
        # Aggregate holdings by ISIN and Symbol to prevent row duplication on merge
        isin_agg = (
            equity_holdings.groupby(col.ISIN)[col.HOLDING_QUANTITY].sum().to_dict()
        )
        symbol_agg = (
            equity_holdings.groupby(col.SYMBOL)[col.HOLDING_QUANTITY].sum().to_dict()
        )

        # First match by ISIN
        stocks_xirr_df[col.HOLDING_QUANTITY] = (
            stocks_xirr_df[col.ISIN].map(isin_agg).fillna(0)
        )

        # Fallback to Symbol if ISIN match failed (quantity is 0)
        # This handles cases where ISIN has changed due to corporate actions
        mask = stocks_xirr_df[col.HOLDING_QUANTITY] == 0
        stocks_xirr_df.loc[mask, col.HOLDING_QUANTITY] = (
            stocks_xirr_df.loc[mask, col.SYMBOL].map(symbol_agg).fillna(0)
        )

        # Flag discrepancies
        stocks_xirr_df[col.IS_DISCREPANCY] = (
            stocks_xirr_df[col.TOTAL_QUANTITY] != stocks_xirr_df[col.HOLDING_QUANTITY]
        )

        # Fallback to broker's Average Price for 0-cost holdings (e.g., demerger cost apportioning)
        if "Average Price" in equity_holdings.columns:
            avg_price_symbol_agg = (
                equity_holdings.groupby(col.SYMBOL)["Average Price"].first().to_dict()
            )
            avg_price_isin_agg = (
                equity_holdings.groupby(col.ISIN)["Average Price"].first().to_dict()
            )

            # Identify where we hold shares but our calculated cost is exactly 0
            zero_cost_mask = (stocks_xirr_df[col.AVG_BUY_PRICE] == 0) & (
                stocks_xirr_df[col.TOTAL_QUANTITY] > 0
            )

            if zero_cost_mask.any():
                broker_prices = stocks_xirr_df.loc[zero_cost_mask, col.ISIN].map(
                    avg_price_isin_agg
                )
                broker_prices = broker_prices.fillna(
                    stocks_xirr_df.loc[zero_cost_mask, col.SYMBOL].map(
                        avg_price_symbol_agg
                    )
                )

                # Apply broker prices where available
                valid_prices_mask = broker_prices.notna() & (broker_prices > 0)
                indices_to_update = broker_prices[valid_prices_mask].index

                stocks_xirr_df.loc[indices_to_update, col.AVG_BUY_PRICE] = (
                    broker_prices[valid_prices_mask]
                )
                stocks_xirr_df.loc[indices_to_update, col.BUY_VALUE] = (
                    stocks_xirr_df.loc[indices_to_update, col.TOTAL_QUANTITY]
                    * stocks_xirr_df.loc[indices_to_update, col.AVG_BUY_PRICE]
                )

                # Recalculate P&L for these updated rows
                stocks_xirr_df.loc[indices_to_update, col.PNL] = (
                    stocks_xirr_df.loc[indices_to_update, col.PRESENT_VALUE]
                    - stocks_xirr_df.loc[indices_to_update, col.BUY_VALUE]
                )
                stocks_xirr_df.loc[indices_to_update, col.PNL_PERCENTAGE] = (
                    stocks_xirr_df.loc[indices_to_update, col.PNL]
                    / stocks_xirr_df.loc[indices_to_update, col.BUY_VALUE]
                )
    else:
        stocks_xirr_df[col.HOLDING_QUANTITY] = 0
        stocks_xirr_df[col.IS_DISCREPANCY] = stocks_xirr_df[col.TOTAL_QUANTITY] != 0

    # Add HTML icons for advanced visualization
    stocks_xirr_df[col.STATUS_ICON] = stocks_xirr_df.apply(get_status_icon, axis=1)

    stocks_data["stocks_xirr_data"] = stocks_xirr_df

    return {
        "transactions_data": transactions_data,
        "equity_holdings": equity_holdings,
        "mf_holdings": mf_holdings,
        "portfolio_xirr": portfolio_xirr,
        "portfolio_value": portfolio_value,
        **stocks_data,
    }


def prepare_stocks_tab_data_progressive():
    """Generator to progressively prepare data and yield progress updates."""
    yield {"status": "Reading Tradebook Transactions..."}
    transactions_data = prepare_transactions_data()

    yield {"status": "Calculating Stock XIRR from Transactions..."}
    stocks_data = calculate_stock_xirr_from_transactions(transactions_data)

    yield {"status": "Reading Holdings Data..."}
    equity_holdings, mf_holdings = read_holding_data()

    yield {"status": "Reading Ledger Data and Calculating Portfolio XIRR..."}
    ledger_df = read_ledger_data()
    portfolio_value = calculate_portfolio_value(stocks_data["stocks_xirr_data"])
    portfolio_xirr = calculate_portfolio_xirr_from_ledger(ledger_df, portfolio_value)

    yield {"status": "Merging Holdings and Identifying Discrepancies..."}
    stocks_xirr_df = stocks_data["stocks_xirr_data"]
    if not equity_holdings.empty:
        # Aggregate holdings by ISIN and Symbol to prevent row duplication on merge
        isin_agg = (
            equity_holdings.groupby(col.ISIN)[col.HOLDING_QUANTITY].sum().to_dict()
        )
        symbol_agg = (
            equity_holdings.groupby(col.SYMBOL)[col.HOLDING_QUANTITY].sum().to_dict()
        )

        # First match by ISIN
        stocks_xirr_df[col.HOLDING_QUANTITY] = (
            stocks_xirr_df[col.ISIN].map(isin_agg).fillna(0)
        )

        # Fallback to Symbol if ISIN match failed (quantity is 0)
        # This handles cases where ISIN has changed due to corporate actions
        mask = stocks_xirr_df[col.HOLDING_QUANTITY] == 0
        stocks_xirr_df.loc[mask, col.HOLDING_QUANTITY] = (
            stocks_xirr_df.loc[mask, col.SYMBOL].map(symbol_agg).fillna(0)
        )

        # Flag discrepancies
        stocks_xirr_df[col.IS_DISCREPANCY] = (
            stocks_xirr_df[col.TOTAL_QUANTITY] != stocks_xirr_df[col.HOLDING_QUANTITY]
        )

        # Fallback to broker's Average Price for 0-cost holdings (e.g., demerger cost apportioning)
        if "Average Price" in equity_holdings.columns:
            avg_price_symbol_agg = (
                equity_holdings.groupby(col.SYMBOL)["Average Price"].first().to_dict()
            )
            avg_price_isin_agg = (
                equity_holdings.groupby(col.ISIN)["Average Price"].first().to_dict()
            )

            # Identify where we hold shares but our calculated cost is exactly 0
            zero_cost_mask = (stocks_xirr_df[col.AVG_BUY_PRICE] == 0) & (
                stocks_xirr_df[col.TOTAL_QUANTITY] > 0
            )

            if zero_cost_mask.any():
                broker_prices = stocks_xirr_df.loc[zero_cost_mask, col.ISIN].map(
                    avg_price_isin_agg
                )
                broker_prices = broker_prices.fillna(
                    stocks_xirr_df.loc[zero_cost_mask, col.SYMBOL].map(
                        avg_price_symbol_agg
                    )
                )

                # Apply broker prices where available
                valid_prices_mask = broker_prices.notna() & (broker_prices > 0)
                indices_to_update = broker_prices[valid_prices_mask].index

                stocks_xirr_df.loc[indices_to_update, col.AVG_BUY_PRICE] = (
                    broker_prices[valid_prices_mask]
                )
                stocks_xirr_df.loc[indices_to_update, col.BUY_VALUE] = (
                    stocks_xirr_df.loc[indices_to_update, col.TOTAL_QUANTITY]
                    * stocks_xirr_df.loc[indices_to_update, col.AVG_BUY_PRICE]
                )

                # Recalculate P&L for these updated rows
                stocks_xirr_df.loc[indices_to_update, col.PNL] = (
                    stocks_xirr_df.loc[indices_to_update, col.PRESENT_VALUE]
                    - stocks_xirr_df.loc[indices_to_update, col.BUY_VALUE]
                )
                stocks_xirr_df.loc[indices_to_update, col.PNL_PERCENTAGE] = (
                    stocks_xirr_df.loc[indices_to_update, col.PNL]
                    / stocks_xirr_df.loc[indices_to_update, col.BUY_VALUE]
                )
    else:
        stocks_xirr_df[col.HOLDING_QUANTITY] = 0
        stocks_xirr_df[col.IS_DISCREPANCY] = stocks_xirr_df[col.TOTAL_QUANTITY] != 0

    stocks_xirr_df[col.STATUS_ICON] = stocks_xirr_df.apply(get_status_icon, axis=1)
    stocks_data["stocks_xirr_data"] = stocks_xirr_df

    yield {
        "status": "Finalizing Data...",
        "data": {
            "transactions_data": transactions_data,
            "equity_holdings": equity_holdings,
            "mf_holdings": mf_holdings,
            "portfolio_xirr": portfolio_xirr,
            "portfolio_value": portfolio_value,
            **stocks_data,
        },
    }


def check_data_files_up_to_date() -> bool:
    """Check if the Zerodha master data files were modified today."""
    today = date.today()

    # Check Master Files primarily
    files_to_check = [
        const.DOCS_MASTER_PATH / const.HOLDINGS_MASTER,
        const.DOCS_MASTER_PATH / const.LEDGER_MASTER,
        const.DOCS_MASTER_PATH / const.TRADEBOOK_MASTER,
    ]

    for file_path in files_to_check:
        if not file_path.exists():
            # If a master file is missing, we are definitely NOT up to date
            return False

        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime).date()
        if mod_time < today:
            return False

    return True
