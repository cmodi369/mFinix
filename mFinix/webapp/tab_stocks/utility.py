import mFinix.constants.columns as col
from mFinix.core.data_processing import prepare_transactions_data
from mFinix.core.read_kite_data import read_holding_data, read_ledger_data
from mFinix.core.xirr_calculation import (
    calculate_portfolio_xirr,
    calculate_stock_xirr_from_transactions,
)


def run_once(method):
    """Decorator to ensure a method can only be executed once."""
    method._has_run = False

    def wrapper(self, *args, **kwargs):
        if method._has_run:
            return
        method._has_run = True
        return method(self, *args, **kwargs)

    return wrapper


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
    portfolio_xirr = calculate_portfolio_xirr(
        ledger_df, stocks_data["stocks_xirr_data"]
    )

    return {
        "transactions_data": transactions_data,
        "equity_holdings": equity_holdings,
        "mf_holdings": mf_holdings,
        "portfolio_xirr": portfolio_xirr,
        **stocks_data,
    }
