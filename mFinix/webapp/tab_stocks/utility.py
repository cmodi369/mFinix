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
        # Aggregate holdings by ISIN to prevent row duplication on merge
        holding_agg = equity_holdings.groupby(col.ISIN, as_index=False)[
            col.HOLDING_QUANTITY
        ].sum()

        # Merge by ISIN
        stocks_xirr_df = stocks_xirr_df.merge(
            holding_agg, on=col.ISIN, how="left"
        ).fillna({col.HOLDING_QUANTITY: 0})

        # Flag discrepancies
        stocks_xirr_df[col.IS_DISCREPANCY] = (
            stocks_xirr_df[col.TOTAL_QUANTITY] != stocks_xirr_df[col.HOLDING_QUANTITY]
        )
    else:
        stocks_xirr_df[col.HOLDING_QUANTITY] = 0
        stocks_xirr_df[col.IS_DISCREPANCY] = stocks_xirr_df[col.TOTAL_QUANTITY] != 0

    # Add HTML icons for advanced visualization
    def get_status_icon(row):
        if row[col.IS_DISCREPANCY]:
            return f'<i class="fa fa-exclamation-triangle" style="color: #e74c3c;" title="Discrepancy: Expected {row[col.TOTAL_QUANTITY]} but broker says {row[col.HOLDING_QUANTITY]}"></i>'
        return '<i class="fa fa-check-circle" style="color: #2ecc71;" title="Quantity matches broker holdings"></i>'

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
        # Aggregate holdings by ISIN to prevent row duplication on merge
        holding_agg = equity_holdings.groupby(col.ISIN, as_index=False)[
            col.HOLDING_QUANTITY
        ].sum()

        # Merge by ISIN
        stocks_xirr_df = stocks_xirr_df.merge(
            holding_agg, on=col.ISIN, how="left"
        ).fillna({col.HOLDING_QUANTITY: 0})

        # Flag discrepancies
        stocks_xirr_df[col.IS_DISCREPANCY] = (
            stocks_xirr_df[col.TOTAL_QUANTITY] != stocks_xirr_df[col.HOLDING_QUANTITY]
        )
    else:
        stocks_xirr_df[col.HOLDING_QUANTITY] = 0
        stocks_xirr_df[col.IS_DISCREPANCY] = stocks_xirr_df[col.TOTAL_QUANTITY] != 0

    def get_status_icon(row):
        if row[col.IS_DISCREPANCY]:
            return f'<i class="fa fa-exclamation-triangle" style="color: #e74c3c;" title="Discrepancy: Expected {row[col.TOTAL_QUANTITY]} but broker says {row[col.HOLDING_QUANTITY]}"></i>'
        return '<i class="fa fa-check-circle" style="color: #2ecc71;" title="Quantity matches broker holdings"></i>'

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
    """Check if the Zerodha data files were modified today."""
    today = date.today()
    files_to_check = [
        const.DOCS_PATH / const.HOLDING_EXCEL_ZERODHA,
    ]

    # Tradebook
    tb_files = list(const.DOCS_PATH.glob(f"{const.TRADEBOOK_ID_ZERODHA}*"))
    if tb_files:
        latest_tb = max(tb_files, key=lambda f: f.stat().st_mtime)
        files_to_check.append(latest_tb)
    else:
        return False

    # Ledger
    ld_files = list(const.DOCS_PATH.glob(f"{const.LEDGER_ID_ZERODHA}*.csv"))
    if ld_files:
        latest_ld = max(ld_files, key=lambda f: f.stat().st_mtime)
        files_to_check.append(latest_ld)
    else:
        return False

    for file_path in files_to_check:
        if not file_path.exists():
            return False
        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime).date()
        if mod_time < today:
            return False

    return True
