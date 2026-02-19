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
    # check if local corporate actions data is available
    dividend_file = Path(const.LOCAL_DATA_PATH / const.DIVIDEND_CSV)
    if dividend_file.exists():
        log.info("Reading local corporate actions data.")
        dividend_data = pd.read_csv(dividend_file)
        dividend_data[col.TRADE_DATE] = pd.to_datetime(
            dividend_data[col.TRADE_DATE], format="mixed"
        ).dt.date
        log.info("Dividends data is pulled for %s entries", len(dividend_data))

        splits_data = pd.read_csv(Path(const.LOCAL_DATA_PATH / const.SPLIT_ACTIONS_CSV))
        splits_data[col.TRADE_DATE] = pd.to_datetime(
            splits_data[col.TRADE_DATE], format="mixed"
        ).dt.date
        log.info("Stock splits data is pulled for %s entries", len(splits_data))

        ipo_data = pd.read_csv(Path(const.LOCAL_DATA_PATH / const.IPO_CSV))
        ipo_data[col.TRADE_DATE] = pd.to_datetime(
            ipo_data[col.TRADE_DATE], format="mixed"
        ).dt.date
        log.info("IPO data is pulled for %s entries", len(ipo_data))

        merger_file = Path(const.LOCAL_DATA_PATH / const.MERGER_CSV)
        if merger_file.exists():
            merger_data = pd.read_csv(merger_file)
            merger_data[col.TRADE_DATE] = pd.to_datetime(
                merger_data[col.TRADE_DATE], format="mixed"
            ).dt.date
            log.info("Merger data is pulled for %s entries", len(merger_data))
        else:
            merger_data = pd.DataFrame(
                columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY]
            )

        demerger_file = Path(const.LOCAL_DATA_PATH / const.DEMERGER_CSV)
        if demerger_file.exists():
            demerger_data = pd.read_csv(demerger_file)
            demerger_data[col.TRADE_DATE] = pd.to_datetime(
                demerger_data[col.TRADE_DATE], format="mixed"
            ).dt.date
            log.info("Demerger data is pulled for %s entries", len(demerger_data))
        else:
            demerger_data = pd.DataFrame(
                columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY]
            )

        bonus_file = Path(const.LOCAL_DATA_PATH / const.BONUS_CSV)
        if bonus_file.exists():
            bonus_data = pd.read_csv(bonus_file)
            bonus_data[col.TRADE_DATE] = pd.to_datetime(
                bonus_data[col.TRADE_DATE], format="mixed"
            ).dt.date
            log.info("Bonus data is pulled for %s entries", len(bonus_data))
        else:
            bonus_data = pd.DataFrame(
                columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY]
            )

        buyback_file = Path(const.LOCAL_DATA_PATH / const.BUYBACK_CSV)
        if buyback_file.exists():
            buyback_data = pd.read_csv(buyback_file)
            buyback_data[col.TRADE_DATE] = pd.to_datetime(
                buyback_data[col.TRADE_DATE], format="mixed"
            ).dt.date
            log.info("Buyback data is pulled for %s entries", len(buyback_data))
        else:
            buyback_data = pd.DataFrame(
                columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY]
            )

        last_date = pd.to_datetime(
            Path(const.LOCAL_DATA_PATH / const.LAST_DATE_TXT).read_text()
        ).date()

        log.info("Last corporate data was updated on: %s", last_date)

    else:
        log.info("Local corporate actions data is not available.")
        const.LOCAL_DATA_PATH.mkdir(parents=True, exist_ok=True)
        dividend_data = pd.DataFrame(
            columns=[
                col.SYMBOL,
                col.ISIN,
                col.TRADE_DATE,
                col.QUANTITY,
                col.DIVIDEND_COL,
                col.TRANSACTION_AMOUNT,
            ]
        )
        ipo_data = pd.DataFrame(
            columns=[
                col.SYMBOL,
                col.ISIN,
                col.TRADE_DATE,
                col.QUANTITY,
                col.PRICE,
            ]
        )
        splits_data = pd.DataFrame(
            columns=[
                col.SYMBOL,
                col.ISIN,
                col.TRADE_DATE,
                col.STOCK_SPLITS_COL,
                col.QUANTITY,
            ]
        )
        merger_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        demerger_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        bonus_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        buyback_data = pd.DataFrame(columns=[col.SYMBOL, col.TRADE_DATE, col.QUANTITY])
        last_date = const.DEFAULT_LAST_DATE

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


def fetch_pending_corporate_actions(
    trade_data: pd.DataFrame, from_date: date = None
) -> List[Dict]:
    """Fetch corporate actions for preview without saving.

    Mirrors automatic_update_corporate_actions_data but returns a list of
    action dicts for the user to approve/reject before persisting.

    Parameters
    ----------
    trade_data : pd.DataFrame
        Trade data with columns: isin, symbol, trade_date, balanced_quantity.
    from_date : date, optional
        Start date for fetching actions. If None, uses the last saved date.

    Returns
    -------
    list[dict]
        Each dict has: action_type, stock, isin, date, details, quantity, raw_data.
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
    log.info("Fetching pending corporate actions from %s", effective_date)

    pending_actions: List[Dict] = []

    for stock_id in trade_data[col.ISIN].unique():
        if pd.isna(stock_id):
            stock_trade_data = trade_data[trade_data[col.ISIN].isna()]
        else:
            stock_trade_data = trade_data[trade_data[col.ISIN].eq(stock_id)]

        if stock_trade_data.empty:
            continue

        symbol = stock_trade_data[col.SYMBOL].iloc[0]
        actions_data_obj = extract_corporate_actions(stock_id, symbol=symbol)
        actions_data = actions_data_obj.actions
        stock_name = actions_data_obj.get_ticker_name()

        if actions_data.empty:
            if const.USE_WEBSCRAPPING:
                try:
                    all_actions = extract_all_corporate_actions(stock_name)
                except Exception as e:
                    log.warning("NSE scraping failed for %s: %s", stock_name, e)
                    continue

                # Dividends from NSE
                div_df = all_actions.get(const.DIVIDEND, pd.DataFrame())
                if not div_df.empty:
                    for dt, row in div_df[
                        div_df.index.date >= effective_date
                    ].iterrows():
                        applicable = stock_trade_data[
                            stock_trade_data[col.TRADE_DATE].lt(dt.date())
                        ]
                        if (
                            not applicable.empty
                            and (qty := applicable[col.TOTAL_QUANTITY].iloc[-1]) > 0
                        ):
                            pending_actions.append(
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

                # Bonus from NSE
                bonus_df = all_actions.get(const.BONUS, pd.DataFrame())
                if not bonus_df.empty:
                    for dt, row in bonus_df[
                        bonus_df.index.date >= effective_date
                    ].iterrows():
                        applicable = stock_trade_data[
                            stock_trade_data[col.TRADE_DATE].lt(dt.date())
                        ]
                        if (
                            not applicable.empty
                            and (qty := applicable[col.TOTAL_QUANTITY].iloc[-1]) > 0
                        ):
                            subject = row.get("subject", "Bonus")
                            pending_actions.append(
                                {
                                    "action_type": const.BONUS,
                                    "stock": stock_name,
                                    "isin": stock_id,
                                    "date": dt,
                                    "details": str(subject),
                                    "quantity": qty,
                                    "raw_data": {
                                        col.SYMBOL: stock_name,
                                        col.TRADE_DATE: dt,
                                        col.QUANTITY: 0,
                                    },
                                }
                            )

                # Merger / Demerger from NSE
                for key in (const.MERGER, const.DEMERGER):
                    act_df = all_actions.get(key, pd.DataFrame())
                    if not act_df.empty:
                        for dt, row in act_df[
                            act_df.index.date >= effective_date
                        ].iterrows():
                            applicable = stock_trade_data[
                                stock_trade_data[col.TRADE_DATE].lt(dt.date())
                            ]
                            if (
                                not applicable.empty
                                and (qty := applicable[col.TOTAL_QUANTITY].iloc[-1]) > 0
                            ):
                                subject = row.get("subject", key.capitalize())
                                pending_actions.append(
                                    {
                                        "action_type": key,
                                        "stock": stock_name,
                                        "isin": stock_id,
                                        "date": dt,
                                        "details": str(subject),
                                        "quantity": qty,
                                        "raw_data": {
                                            col.SYMBOL: stock_name,
                                            col.TRADE_DATE: dt,
                                            col.QUANTITY: 0,
                                        },
                                    }
                                )
            continue

        # yfinance-based actions
        for dt, row in actions_data[
            actions_data.index.date >= effective_date
        ].iterrows():
            applicable = stock_trade_data[
                stock_trade_data[col.TRADE_DATE].lt(dt.date())
            ]
            if (
                len(applicable) > 0
                and (qty := applicable[col.TOTAL_QUANTITY].iloc[-1]) > 0
            ):
                if row[col.DIVIDEND] > 0:
                    pending_actions.append(
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
                    pending_actions.append(
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
                    # update total quantity in stock trade data after split update
                    stock_trade_data.loc[
                        stock_trade_data[col.TRADE_DATE].gt(dt.date()),
                        col.TOTAL_QUANTITY,
                    ] = (
                        stock_trade_data[col.TOTAL_QUANTITY] + new_qty
                    )

    # Buyback detection from ledger
    try:
        new_buybacks = automatic_update_buyback_from_ledger(trade_data)
        for _, bb_row in new_buybacks.iterrows():
            pending_actions.append(
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

    log.info("Found %d pending corporate actions", len(pending_actions))
    return pending_actions


def delete_all_corporate_actions_data() -> Path:
    """Delete all corporate actions CSV files after creating a backup.

    Creates a timestamped backup directory under .data/backups/ before
    removing the original files.

    Returns
    -------
    Path
        Path to the backup directory created.
    """
    backup_dir = (
        const.LOCAL_DATA_PATH / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
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
            src.unlink()
            log.info("Backed up and deleted %s", fname)

    log.info("All corporate actions data backed up to %s and deleted", backup_dir)
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
