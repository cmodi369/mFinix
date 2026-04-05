import re
import shutil
from datetime import date, datetime
from functools import reduce
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.core.nse_webscraping import extract_all_corporate_actions
from mFinix.core.yfinance_query import extract_corporate_actions
from mFinix.util import log


def add_corporate_actions_in_tradebook(trade_data: pd.DataFrame):
    # read/initialize required datasets
    (
        dividend_data,
        splits_data,
        ipo_data,
        merger_data,
        demerger_data,
        bonus_data,
        buyback_data,
        last_date,
    ) = _read_local_corporate_actions_data()

    # add trade type
    dividend_data[col.TRADE_TYPE] = const.DIVIDEND
    ipo_data[col.TRADE_TYPE] = const.BUY
    splits_data[col.TRADE_TYPE] = const.STOCK_SPLIT
    splits_data[col.TRANSACTION_AMOUNT] = 0
    merger_data[col.TRADE_TYPE] = const.MERGER
    merger_data[col.TRANSACTION_AMOUNT] = 0
    demerger_data[col.TRADE_TYPE] = const.DEMERGER
    demerger_data[col.TRANSACTION_AMOUNT] = 0
    bonus_data[col.TRADE_TYPE] = const.BONUS
    bonus_data[col.TRANSACTION_AMOUNT] = 0
    buyback_data[col.TRADE_TYPE] = const.BUYBACK
    buyback_data[col.TRANSACTION_AMOUNT] = 0
    if not buyback_data.empty:
        # Ensure buyback quantity is negative so it reduces total holdings
        buyback_data[col.QUANTITY] = -buyback_data[col.QUANTITY].abs()

    # Handle mergers/demergers where we need to close parent positions
    # (specifically mergers where the old stock is replaced)
    if not merger_data.empty and col.PARENT_SYMBOL in merger_data.columns:
        merger_offsets = []
        for _, row in merger_data.iterrows():
            parent_sym = row.get(col.PARENT_SYMBOL)
            parent_qty = row.get(col.PARENT_QUANTITY)
            if pd.notna(parent_sym) and pd.notna(parent_qty) and parent_qty != 0:
                merger_offsets.append(
                    {
                        col.SYMBOL: parent_sym,
                        col.TRADE_DATE: row[col.TRADE_DATE],
                        col.QUANTITY: -float(parent_qty),
                        col.TRADE_TYPE: const.MERGER,
                        col.TRANSACTION_AMOUNT: 0,
                    }
                )
        if merger_offsets:
            merger_data = pd.concat([merger_data, pd.DataFrame(merger_offsets)])

    # Combine all quantity-affecting transactions
    ret_data = pd.concat(
        [
            trade_data,
            splits_data,
            ipo_data,
            merger_data,
            demerger_data,
            bonus_data,
            buyback_data,
        ]
    )
    ret_data = ret_data.sort_values(by=[col.TRADE_DATE, col.TRADE_TYPE]).reset_index(
        drop=True
    )

    # adjust total quantity column
    ret_data[col.QUANTITY] = pd.to_numeric(
        ret_data[col.QUANTITY], errors="coerce"
    ).fillna(0)
    ret_data[col.TOTAL_QUANTITY] = ret_data.groupby(col.SYMBOL)[col.QUANTITY].cumsum()

    # add dividend data (doesn't affect quantity but needed for XIRR)
    ret_data = pd.concat([ret_data, dividend_data])
    ret_data = ret_data.sort_values(by=[col.TRADE_DATE, col.TRADE_TYPE]).reset_index(
        drop=True
    )

    return ret_data


def automatic_update_buyback_from_ledger(trade_data: pd.DataFrame) -> pd.DataFrame:
    """Detect buyback entries from ledger data and fetch prices dynamically.

    Parameters
    ----------
    trade_data : pd.DataFrame
        Trade data to check holdings during the buyback period.

    Returns
    -------
    pd.DataFrame
        Buyback transactions detected from the ledger.
    """
    from mFinix.core.nse_webscraping import extract_buyback_data
    from mFinix.core.read_kite_data import read_ledger_data

    try:
        ledger_df = read_ledger_data()
    except Exception as e:
        log.warning("Could not read ledger data: %s", e)
        return pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])

    # Look for "Buyback amount credit"
    credits = ledger_df[
        ledger_df[col.PARTICULARS].str.contains(
            "Buyback amount credit", case=False, na=False
        )
    ].copy()

    buybacks = []

    for _, row in credits.iterrows():
        particulars = row[col.PARTICULARS]
        posting_date = row[col.POSTING_DATE].date()

        # Extract symbol
        symbol_match = re.search(r"for\s+([A-Z\s]+?)\s+Limited", particulars, re.I)
        if symbol_match:
            raw_name = symbol_match.group(1).strip().upper()
            # Map common names to symbols
            symbol_map = {
                "TANLA PLATFORMS": "TANLA",
                "WIPRO": "WIPRO",
            }
            symbol = symbol_map.get(raw_name, raw_name)

            # Check if stock was part of holdings during the day of transaction
            applicable_trade_data = trade_data[
                (trade_data[col.SYMBOL] == symbol)
                & (trade_data[col.TRADE_DATE] < posting_date)
            ]

            if (
                not applicable_trade_data.empty
                and applicable_trade_data[col.TOTAL_QUANTITY].iloc[-1] > 0
            ):
                # Fetch buyback price dynamically
                buyback_info = extract_buyback_data(symbol)

                if not buyback_info.empty:
                    # Find the nearest buyback date before posting_date
                    valid_buybacks = buyback_info[
                        buyback_info.index.date <= posting_date
                    ]
                    if not valid_buybacks.empty:
                        # Get the most recent one
                        price = valid_buybacks.iloc[-1]["buyback_price"]
                        credit_amount = row[col.CREDIT]
                        qty = -round(credit_amount / price)
                        buybacks.append(
                            {
                                col.SYMBOL: symbol,
                                col.TRADE_DATE: posting_date,
                                col.QUANTITY: float(qty),
                            }
                        )
                        log.info(
                            "Detected buyback for %s: Date=%s, Price=%.2f, Qty=%.2f",
                            symbol,
                            posting_date,
                            price,
                            qty,
                        )
                else:
                    log.warning(
                        "No buyback data found for %s near %s", symbol, posting_date
                    )
            else:
                log.info(
                    "Skipping buyback for %s on %s as it was not in holdings",
                    symbol,
                    posting_date,
                )

    return pd.DataFrame(buybacks)


def _read_local_corporate_actions_data():
    """Read local corporate actions data from CSV files.

    Handles missing files by returning empty DataFrames with correct columns.
    """
    # ensure directory exists
    if not const.LOCAL_DATA_PATH.exists():
        const.LOCAL_DATA_PATH.mkdir(parents=True, exist_ok=True)

    def load_csv_safe(filename, default_cols):
        path = const.LOCAL_DATA_PATH / filename
        if path.exists():
            try:
                df = pd.read_csv(path)
                if not df.empty and col.TRADE_DATE in df.columns:
                    df[col.TRADE_DATE] = pd.to_datetime(
                        df[col.TRADE_DATE], format="mixed"
                    ).dt.date
                log.info(
                    "%s data is pulled for %d entries",
                    filename.capitalize().replace(".csv", ""),
                    len(df),
                )
                return df
            except Exception as e:
                log.warning("Could not read %s: %s", filename, e)

        return pd.DataFrame(columns=default_cols)

    dividend_data = load_csv_safe(
        const.DIVIDEND_CSV,
        [
            col.SYMBOL,
            col.ISIN,
            col.TRADE_DATE,
            col.QUANTITY,
            col.DIVIDEND_COL,
            col.TRANSACTION_AMOUNT,
        ],
    )
    splits_data = load_csv_safe(
        const.SPLIT_ACTIONS_CSV,
        [col.SYMBOL, col.ISIN, col.TRADE_DATE, col.STOCK_SPLITS_COL, col.QUANTITY],
    )
    ipo_data = load_csv_safe(
        const.IPO_CSV, [col.SYMBOL, col.ISIN, col.TRADE_DATE, col.QUANTITY, col.PRICE]
    )
    merger_data = load_csv_safe(
        const.MERGER_CSV,
        [
            col.SYMBOL,
            col.TRADE_DATE,
            col.QUANTITY,
            col.PARENT_SYMBOL,
            col.PARENT_QUANTITY,
            col.RATIO,
        ],
    )
    demerger_data = load_csv_safe(
        const.DEMERGER_CSV,
        [
            col.SYMBOL,
            col.TRADE_DATE,
            col.QUANTITY,
            col.PARENT_SYMBOL,
            col.PARENT_QUANTITY,
            col.RATIO,
        ],
    )
    bonus_data = load_csv_safe(
        const.BONUS_CSV, [col.SYMBOL, col.TRADE_DATE, col.QUANTITY]
    )
    buyback_data = load_csv_safe(
        const.BUYBACK_CSV, [col.SYMBOL, col.TRADE_DATE, col.QUANTITY]
    )

    # Handle last_date.txt
    last_date_file = const.LOCAL_DATA_PATH / const.LAST_DATE_TXT
    last_date = const.DEFAULT_LAST_DATE
    if last_date_file.exists():
        try:
            last_date = pd.to_datetime(last_date_file.read_text().strip()).date()
            log.info("Last corporate data was updated on: %s", last_date)
        except Exception as e:
            log.warning("Could not parse %s: %s", const.LAST_DATE_TXT, e)

    return (
        dividend_data,
        splits_data,
        ipo_data,
        merger_data,
        demerger_data,
        bonus_data,
        buyback_data,
        last_date,
    )


def get_last_corporate_actions_update_date() -> date:
    """Read the last corporate actions update date from the local file.

    Returns
    -------
    date
        The last update date, or DEFAULT_LAST_DATE if the file doesn't exist.
    """
    last_date_file = const.LOCAL_DATA_PATH / const.LAST_DATE_TXT
    if last_date_file.exists():
        try:
            return pd.to_datetime(last_date_file.read_text().strip()).date()
        except Exception as e:
            log.warning("Could not parse last_date.txt: %s", e)

    return const.DEFAULT_LAST_DATE


# Function to apply mergers
def _apply_mergers(transactions, holdings, old_stock, new_stock, ratio):
    # Adjust holdings
    if old_stock in holdings["Stock"].values:
        old_quantity = holdings.loc[
            holdings["Stock"] == old_stock, "Total_Quantity"
        ].values[0]
        old_cost = holdings.loc[holdings["Stock"] == old_stock, "Avg_Cost"].values[0]

        # Calculate new holdings
        new_quantity = old_quantity * ratio
        new_cost = old_cost / ratio

        # Remove old stock and add new stock to holdings
        holdings = holdings[holdings["Stock"] != old_stock]
        holdings = holdings.append(
            {"Stock": new_stock, "Total_Quantity": new_quantity, "Avg_Cost": new_cost},
            ignore_index=True,
        )

    # Adjust transactions
    transactions.loc[transactions["Stock"] == old_stock, "Stock"] = new_stock
    transactions.loc[transactions["Stock"] == new_stock, "Quantity"] *= ratio
    transactions.loc[transactions["Stock"] == new_stock, "Price"] /= ratio

    return transactions, holdings


class _PendingActionsRegistry:
    """Central deduplication registry for pending corporate actions.

    Tracks (stock, date) per action_type to prevent duplicates from
    multiple data sources (YFinance, NSE, Ledger).
    """

    def __init__(self):
        self._actions: List[Dict] = []
        # {action_type: {(stock, date_str), ...}} for O(1) lookup
        self._seen: Dict[str, set] = {}

    @property
    def actions(self) -> List[Dict]:
        return self._actions

    @staticmethod
    def _to_date(dt) -> date:
        return dt.date() if hasattr(dt, "date") else dt

    def _key(self, stock: str, dt) -> tuple:
        return (stock, str(self._to_date(dt)))

    def has(self, action_type: str, stock: str, dt) -> bool:
        """Check if an action already exists for (stock, date, action_type)."""
        return self._key(stock, dt) in self._seen.get(action_type, set())

    def add(self, action: Dict) -> bool:
        """Add action if not a duplicate. Returns True if added."""
        atype = action["action_type"]
        key = self._key(action["stock"], action["date"])
        if key in self._seen.get(atype, set()):
            log.debug("Skipping duplicate %s for %s", atype, key)
            return False
        self._seen.setdefault(atype, set()).add(key)
        self._actions.append(action)
        return True

    def reclassify_or_skip(
        self, new_action: Dict, from_type: str, to_type: str
    ) -> bool:
        """If an action of *from_type* exists at the same (stock, date),
        reclassify it to *to_type* using *new_action*'s details.
        Otherwise add *new_action* normally.
        Returns True if reclassified or added.
        """
        stock = new_action["stock"]
        dt = new_action["date"]
        key = self._key(stock, dt)

        if key in self._seen.get(from_type, set()):
            # Reclassify the existing entry
            for existing in self._actions:
                if (
                    existing["action_type"] == from_type
                    and self._key(existing["stock"], existing["date"]) == key
                ):
                    existing["action_type"] = to_type
                    existing["details"] = new_action.get("details", existing["details"])
                    log.info(
                        "Reclassified %s -> %s for %s on %s",
                        from_type,
                        to_type,
                        stock,
                        self._to_date(dt),
                    )
                    # Update seen sets
                    self._seen[from_type].discard(key)
                    self._seen.setdefault(to_type, set()).add(key)
                    return True
        # Not a reclassification — add normally
        return self.add(new_action)


def fetch_pending_corporate_actions_progressive(
    trade_data: pd.DataFrame,
    from_date: date = None,
    to_date: date = None,
    stock_symbol: str = None,
):
    """
    Progressive generator version of fetch_pending_corporate_actions.
    Yields dicts with 'status' (str) and 'progress' (int 0-100).
    Final yield contains 'data' (list[dict]).
    """
    (
        dividend_data,
        splits_data,
        ipo_data,
        merger_data,
        demerger_data,
        bonus_data,
        buyback_data,
        last_date,
    ) = _read_local_corporate_actions_data()

    effective_date = from_date if from_date is not None else last_date
    registry = _PendingActionsRegistry()

    if stock_symbol:
        unique_isins = (
            trade_data[trade_data[col.SYMBOL] == stock_symbol][col.ISIN]
            .unique()
            .tolist()
        )
    else:
        unique_isins = [
            isin for isin in trade_data[col.ISIN].unique() if not pd.isna(isin)
        ]
        # Filter trades without ISIN too
        if trade_data[col.ISIN].isna().any():
            unique_isins.append(None)

    total_stocks = len(unique_isins)

    for i, stock_id in enumerate(unique_isins):
        if stock_id is None:
            stock_trade_data = trade_data[trade_data[col.ISIN].isna()]
            display_name = "Stocks without ISIN"
        else:
            stock_trade_data = trade_data[trade_data[col.ISIN].eq(stock_id)]
            display_name = (
                stock_trade_data[col.SYMBOL].iloc[0]
                if not stock_trade_data.empty
                else str(stock_id)
            )

        progress = int((i / total_stocks) * 100) if total_stocks > 0 else 0
        yield {"status": f"Checking {display_name}...", "progress": progress}

        if stock_trade_data.empty:
            continue

        # Check if stock was in portfolio during [effective_date, to_date]
        _check_end_date = to_date if to_date else date.today()
        applicable_trades_end = stock_trade_data[
            stock_trade_data[col.TRADE_DATE] <= _check_end_date
        ]
        if applicable_trades_end.empty:
            continue

        applicable_trades_start = stock_trade_data[
            stock_trade_data[col.TRADE_DATE] < effective_date
        ]
        qty_at_start = (
            applicable_trades_start[col.TOTAL_QUANTITY].iloc[-1]
            if not applicable_trades_start.empty
            else 0
        )

        trades_during = stock_trade_data[
            (stock_trade_data[col.TRADE_DATE] >= effective_date)
            & (stock_trade_data[col.TRADE_DATE] <= _check_end_date)
        ]

        if qty_at_start <= 0 and trades_during.empty:
            continue

        # 1. Fetch from YFinance
        symbol = stock_trade_data[col.SYMBOL].iloc[0]
        try:
            actions_data_obj = extract_corporate_actions(
                stock_id if stock_id else symbol, symbol=symbol
            )
            actions_data = actions_data_obj.actions
            stock_name = actions_data_obj.get_ticker_name()
        except Exception as e:
            log.warning("YFinance fetch failed for %s: %s", display_name, e)
            actions_data = pd.DataFrame()
            stock_name = display_name

        if not actions_data.empty:
            date_mask = actions_data.index.date >= effective_date
            if to_date:
                date_mask = date_mask & (actions_data.index.date <= to_date)
            for dt, row in actions_data[date_mask].iterrows():
                applicable = stock_trade_data[
                    stock_trade_data[col.TRADE_DATE].lt(dt.date())
                ]
                if (
                    not applicable.empty
                    and (qty := applicable[col.TOTAL_QUANTITY].iloc[-1]) > 0
                ):
                    if row[col.DIVIDEND] > 0:
                        registry.add(
                            {
                                "action_type": const.DIVIDEND,
                                "stock": stock_name,
                                "isin": stock_id,
                                "date": dt,
                                "details": f"₹{row[col.DIVIDEND]:.2f}/share",
                                "quantity": qty,
                                "raw_data": {
                                    col.SYMBOL: stock_name,
                                    col.ISIN: stock_id,
                                    col.TRADE_DATE: dt,
                                    col.QUANTITY: qty,
                                    col.DIVIDEND_COL: row[col.DIVIDEND],
                                    col.TRANSACTION_AMOUNT: qty * row[col.DIVIDEND],
                                },
                            }
                        )

                    if row[col.STOCK_SPLITS] > 0:
                        new_qty = qty * (row[col.STOCK_SPLITS] - 1)
                        registry.add(
                            {
                                "action_type": const.STOCK_SPLIT,
                                "stock": stock_name,
                                "isin": stock_id,
                                "date": dt,
                                "details": f"Ratio {row[col.STOCK_SPLITS]}:1",
                                "quantity": new_qty,
                                "raw_data": {
                                    col.SYMBOL: stock_name,
                                    col.ISIN: stock_id,
                                    col.TRADE_DATE: dt,
                                    col.STOCK_SPLITS_COL: row[col.STOCK_SPLITS],
                                    col.QUANTITY: new_qty,
                                },
                            }
                        )
                        # update total quantity for internal logic within this loop if needed
                        stock_trade_data.loc[
                            stock_trade_data[col.TRADE_DATE].gt(dt.date()),
                            col.TOTAL_QUANTITY,
                        ] = (
                            stock_trade_data[col.TOTAL_QUANTITY] + new_qty
                        )

        # 2. Fetch from NSE Webscraping (Supplementary)
        if const.USE_WEBSCRAPPING:
            try:
                all_actions = extract_all_corporate_actions(stock_name)
            except Exception as e:
                log.warning("NSE scraping failed for %s: %s", stock_name, e)
                all_actions = {}

            # Dividends from NSE (registry auto-skips duplicates from YFinance)
            div_df = all_actions.get(const.DIVIDEND, pd.DataFrame())
            if not div_df.empty:
                date_mask = div_df.index.date >= effective_date
                if to_date:
                    date_mask = date_mask & (div_df.index.date <= to_date)
                for dt, row in div_df[date_mask].iterrows():
                    applicable = stock_trade_data[
                        stock_trade_data[col.TRADE_DATE].lt(dt.date())
                    ]
                    if (
                        not applicable.empty
                        and (qty := applicable[col.TOTAL_QUANTITY].iloc[-1]) > 0
                    ):
                        registry.add(
                            {
                                "action_type": const.DIVIDEND,
                                "stock": stock_name,
                                "isin": stock_id,
                                "date": dt,
                                "details": f"₹{row[col.DIVIDEND]:.2f}/share",
                                "quantity": qty,
                                "raw_data": {
                                    col.SYMBOL: stock_name,
                                    col.ISIN: stock_id,
                                    col.TRADE_DATE: dt,
                                    col.QUANTITY: qty,
                                    col.DIVIDEND_COL: row[col.DIVIDEND],
                                    col.TRANSACTION_AMOUNT: qty * row[col.DIVIDEND],
                                },
                            }
                        )

            # Bonus, Merger / Demerger
            for key in (const.BONUS, const.MERGER, const.DEMERGER):
                act_df = all_actions.get(key, pd.DataFrame())
                if not act_df.empty:
                    date_mask = act_df.index.date >= effective_date
                    if to_date:
                        date_mask = date_mask & (act_df.index.date <= to_date)
                    for dt, row in act_df[date_mask].iterrows():
                        applicable = stock_trade_data[
                            stock_trade_data[col.TRADE_DATE].lt(dt.date())
                        ]
                        if (
                            not applicable.empty
                            and (qty := applicable[col.TOTAL_QUANTITY].iloc[-1]) > 0
                        ):
                            subject = row.get("subject", key.capitalize())
                            action = {
                                "action_type": key,
                                "stock": stock_name,
                                "isin": stock_id,
                                "date": dt,
                                "details": str(subject),
                                "quantity": (
                                    qty if key != const.DEMERGER else 0
                                ),  # Demerger starts with 0 for incomplete
                                "raw_data": {
                                    col.SYMBOL: stock_name,
                                    col.TRADE_DATE: dt,
                                    col.QUANTITY: 0,
                                },
                            }
                            if key == const.BONUS:
                                # If YFinance recorded a split on this
                                # date, reclassify it as bonus (NSE has
                                # the more accurate action type).
                                registry.reclassify_or_skip(
                                    action,
                                    from_type=const.STOCK_SPLIT,
                                    to_type=const.BONUS,
                                )
                            else:
                                registry.add(action)

    # 3. Buyback detection from ledger
    yield {"status": "Checking for Buybacks in Ledger...", "progress": 95}
    try:
        new_buybacks = automatic_update_buyback_from_ledger(trade_data)
        for _, bb_row in new_buybacks.iterrows():
            registry.add(
                {
                    "action_type": const.BUYBACK,
                    "stock": bb_row[col.SYMBOL],
                    "isin": "",
                    "date": bb_row[col.TRADE_DATE],
                    "details": f"Qty: {bb_row[col.QUANTITY]}",
                    "quantity": bb_row[col.QUANTITY],
                    "raw_data": {
                        col.SYMBOL: bb_row[col.SYMBOL],
                        col.TRADE_DATE: bb_row[col.TRADE_DATE],
                        col.QUANTITY: bb_row[col.QUANTITY],
                    },
                }
            )
    except Exception as e:
        log.warning("Buyback detection failed: %s", e)

    yield {"status": "Complete", "progress": 100, "data": registry.actions}


def fetch_pending_corporate_actions(
    trade_data: pd.DataFrame,
    from_date: date = None,
    to_date: date = None,
    stock_symbol: str = None,
) -> List[Dict]:
    """
    Synchronous wrapper for fetch_pending_corporate_actions_progressive.
    """
    generator = fetch_pending_corporate_actions_progressive(
        trade_data, from_date, to_date, stock_symbol
    )
    result = []
    for update in generator:
        if "data" in update:
            result = update["data"]
    return result


def delete_all_corporate_actions_data(stock_symbol: str = None) -> Path:
    """Delete all corporate actions CSV files after creating a backup.

    If `stock_symbol` is provided, filters the CSVs to delete only records for that stock
    instead of deleting the entire file.

    Returns
    -------
    Path
        Path to the backup directory created.
    """
    backup_dir = (
        const.LOCAL_DATA_PATH
        / "backups"
        / f"full_reset_{stock_symbol if stock_symbol else 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    csv_files = [
        const.DIVIDEND_CSV,
        const.SPLIT_ACTIONS_CSV,
        const.BONUS_CSV,
        const.BUYBACK_CSV,
        const.MERGER_CSV,
        const.DEMERGER_CSV,
        const.LAST_DATE_TXT,
    ]

    for fname in csv_files:
        src = const.LOCAL_DATA_PATH / fname
        if src.exists():
            shutil.copy2(src, backup_dir / fname)

            if stock_symbol:
                try:
                    df = pd.read_csv(src)
                    if not df.empty and col.SYMBOL in df.columns:
                        filtered_df = df[df[col.SYMBOL] != stock_symbol]
                        filtered_df.to_csv(src, index=False)
                        log.info("Filtered out %s records from %s", stock_symbol, fname)
                except Exception as e:
                    log.warning(
                        "Could not filter %s for %s reset: %s", fname, stock_symbol, e
                    )
            else:
                src.unlink()
                log.info("Backed up and deleted %s", fname)

    log.info(
        "Corporate actions data for %s backed up to %s and deleted/filtered",
        stock_symbol or "all",
        backup_dir,
    )
    return backup_dir


def delete_corporate_actions_range(
    start_date: date, end_date: date, stock_symbol: str = None
) -> Path:
    """Delete corporate actions between start_date and end_date.

    If `stock_symbol` is provided, filters the CSVs to delete only range records specifically for that stock
    instead of replacing the range universally.

    Returns
    -------
    Path
        Path to the backup directory created.
    """
    backup_dir = (
        const.LOCAL_DATA_PATH
        / "backups"
        / f"replace_range_{stock_symbol if stock_symbol else 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    csv_files = [
        const.DIVIDEND_CSV,
        const.SPLIT_ACTIONS_CSV,
        const.BONUS_CSV,
        const.BUYBACK_CSV,
        const.MERGER_CSV,
        const.DEMERGER_CSV,
    ]

    for fname in csv_files:
        src = const.LOCAL_DATA_PATH / fname
        if src.exists():
            shutil.copy2(src, backup_dir / fname)

            try:
                df = pd.read_csv(src)
                if not df.empty and col.TRADE_DATE in df.columns:
                    df_dates = pd.to_datetime(
                        df[col.TRADE_DATE], format="mixed"
                    ).dt.date

                    if stock_symbol and col.SYMBOL in df.columns:
                        mask_outside = (
                            (df_dates < start_date)
                            | (df_dates > end_date)
                            | (df[col.SYMBOL] != stock_symbol)
                        )
                    else:
                        mask_outside = (df_dates < start_date) | (df_dates > end_date)

                    filtered_df = df[mask_outside]
                    filtered_df.to_csv(src, index=False)
                    log.info(
                        "Filtered %d rows from %s (between %s and %s for %s)",
                        len(df) - len(filtered_df),
                        fname,
                        start_date,
                        end_date,
                        stock_symbol or "all",
                    )
            except Exception as e:
                log.warning("Could not filter %s for range deletion: %s", fname, e)

    log.info(
        "Corporate actions between %s and %s for %s backed up to %s and removed",
        start_date,
        end_date,
        stock_symbol or "all",
        backup_dir,
    )
    return backup_dir


def save_approved_action(action: Dict) -> None:
    """Save a single approved corporate action to its CSV file.

    Parameters
    ----------
    action : dict
        Action dict from fetch_pending_corporate_actions with 'action_type' and 'raw_data'.
    """
    raw = action["raw_data"]
    action_type = action["action_type"]

    file_mapping = {
        const.DIVIDEND: const.DIVIDEND_CSV,
        const.STOCK_SPLIT: const.SPLIT_ACTIONS_CSV,
        const.BONUS: const.BONUS_CSV,
        const.BUYBACK: const.BUYBACK_CSV,
        const.MERGER: const.MERGER_CSV,
        const.DEMERGER: const.DEMERGER_CSV,
    }

    csv_name = file_mapping.get(action_type)
    if csv_name is None:
        log.warning("Unknown action type: %s", action_type)
        return

    file_path = const.LOCAL_DATA_PATH / csv_name
    file_exists = file_path.exists()

    # Read existing data or create empty DataFrame
    if file_exists:
        existing_df = pd.read_csv(file_path)
    else:
        const.LOCAL_DATA_PATH.mkdir(parents=True, exist_ok=True)
        existing_df = pd.DataFrame(columns=list(raw.keys()))

    # Guard: skip if identical (symbol, date) already exists in CSV
    if not existing_df.empty and col.TRADE_DATE in existing_df.columns:
        dup_mask = existing_df[col.SYMBOL].eq(raw.get(col.SYMBOL)) & existing_df[
            col.TRADE_DATE
        ].astype(str).eq(str(raw.get(col.TRADE_DATE)))
        if dup_mask.any():
            log.warning(
                "Duplicate %s for %s on %s skipped in CSV",
                action_type,
                raw.get(col.SYMBOL),
                raw.get(col.TRADE_DATE),
            )
            return

    # Append the new row
    new_row_df = pd.DataFrame([raw])
    updated_df = pd.concat([existing_df, new_row_df], ignore_index=True)
    updated_df.to_csv(file_path, index=False)

    # Update last_date.txt
    last_date_file = const.LOCAL_DATA_PATH / const.LAST_DATE_TXT
    with last_date_file.open("w") as f:
        f.write(str(datetime.now()))

    log.info(
        "Saved approved %s action for %s", action_type, action.get("stock", "unknown")
    )
