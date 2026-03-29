"""
Benchmark Index Return Data.

Fetches and caches FY-scoped returns for major NSE benchmark indices
using yfinance. Results are stored in LOCAL_DATA_PATH / benchmark_cache.json
to avoid repeated API calls.

Cache file format:
{
  "FY2024-25": {
    "Nifty 50": 14.2,
    "Nifty Next 50": 18.1,
    ...
  },
  ...
}
"""

import json
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from mFinix.constants.constants import BENCHMARK_CACHE, LOCAL_DATA_PATH
from mFinix.util import log

# ---------------------------------------------------------------------------
# Benchmark Index Definitions
# ---------------------------------------------------------------------------

BENCHMARK_INDICES: dict[str, str] = {
    "Nifty 50": "^NSEI",
    "Nifty Next 50": "JUNIORBEES.NS",
    "Nifty Midcap 150": "NIFTYMIDCAP150.NS",
    "Nifty Smallcap 250 (ETF)": "HDFCSML250.NS",
}

_CACHE_PATH: Path = LOCAL_DATA_PATH / BENCHMARK_CACHE


# ---------------------------------------------------------------------------
# FY Date Helpers
# ---------------------------------------------------------------------------


def fy_label_to_dates(fy_label: str) -> tuple[date, date]:
    """Convert an FY label like 'FY2024-25' to (start_date, end_date).

    Indian FY: April 1 – March 31.

    Parameters
    ----------
    fy_label : str
        FY label, e.g. "FY2024-25".

    Returns
    -------
    tuple[date, date]
        (start_date, end_date) for the FY.
    """
    # Extract start year from "FY2024-25"
    clean = fy_label.lstrip("FY").split(" ")[0]  # handles "FY2024-25 (Current)"
    start_year = int(clean.split("-")[0])
    end_year = start_year + 1
    start_date = date(start_year, 4, 1)
    end_date = date(end_year, 3, 31)
    return start_date, end_date


def get_current_fy_label() -> str:
    """Get the FY label for the current fiscal year.

    Returns
    -------
    str
        E.g. "FY2024-25 (Current)".
    """
    today = date.today()
    if today.month >= 4:
        start_year = today.year
    else:
        start_year = today.year - 1
    end_year = start_year + 1
    return f"FY{start_year}-{str(end_year)[-2:]}"


def get_all_fy_labels(transactions_start_date: date) -> list[str]:
    """Get all FY labels from the start of transactions to the current FY.

    Parameters
    ----------
    transactions_start_date : date
        Earliest trade date in the tradebook.

    Returns
    -------
    list[str]
        List of FY labels in chronological order.
    """
    today = date.today()
    first_fy_start_year = (
        transactions_start_date.year
        if transactions_start_date.month >= 4
        else transactions_start_date.year - 1
    )
    current_fy_start_year = today.year if today.month >= 4 else today.year - 1

    labels = []
    for year in range(first_fy_start_year, current_fy_start_year + 1):
        end_year_short = str(year + 1)[-2:]
        labels.append(f"FY{year}-{end_year_short}")
    return labels


def is_fy_complete(fy_label: str) -> bool:
    """Check whether the FY has ended (i.e., is not the current FY).

    Parameters
    ----------
    fy_label : str
        FY label, e.g. "FY2023-24".

    Returns
    -------
    bool
        True if the FY's March 31 end date is in the past.
    """
    _, end_date = fy_label_to_dates(fy_label)
    return end_date < date.today()


# ---------------------------------------------------------------------------
# Cache Helpers
# ---------------------------------------------------------------------------


def _load_benchmark_cache() -> dict:
    if not _CACHE_PATH.exists():
        return {}
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to read benchmark cache: %s", exc)
        return {}


def _save_benchmark_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        log.info("Saved benchmark cache (%d FYs).", len(cache))
    except OSError as exc:
        log.error("Failed to save benchmark cache: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_benchmark_fy_returns(
    fy_label: str, force_refresh: bool = False
) -> dict[str, Optional[float]]:
    """Fetch FY returns for all benchmark indices.

    Uses cached returns for completed FYs unless force_refresh is True.
    The current FY is always fetched fresh.

    Parameters
    ----------
    fy_label : str
        FY label, e.g. "FY2024-25".
    force_refresh : bool
        If True, bypass cache and fetch fresh data.

    Returns
    -------
    dict[str, Optional[float]]
        Dictionary mapping index name → % return for the FY.
        e.g. {"Nifty 50": 14.2, "Nifty Next 50": 18.1, ...}
        Returns None for indices where data is unavailable.
    """
    cache = _load_benchmark_cache()
    fy_complete = is_fy_complete(fy_label)

    # Return cached data for completed FYs
    if not force_refresh and fy_complete and fy_label in cache:
        log.info("Using cached benchmark returns for %s.", fy_label)
        return cache[fy_label]

    start_date, end_date = fy_label_to_dates(fy_label)

    # Clamp end_date to today if FY hasn't ended yet
    if end_date > date.today():
        end_date = date.today()

    log.info(
        "Fetching benchmark returns for %s (%s to %s).", fy_label, start_date, end_date
    )

    returns: dict[str, Optional[float]] = {}

    tickers = list(BENCHMARK_INDICES.values())
    ticker_to_name = {v: k for k, v in BENCHMARK_INDICES.items()}

    try:
        # yfinance v1.0+ returns a (field, ticker) MultiIndex DataFrame for multi-ticker
        # downloads. Access via df["Close"][ticker].
        df = yf.download(
            tickers,
            start=start_date,
            end=end_date + pd.Timedelta(days=1),
            progress=False,
            auto_adjust=True,
        )

        # Normalise: yfinance always returns MultiIndex even for a single ticker in v1.0
        close_df = df["Close"] if "Close" in df.columns.get_level_values(0) else df

        for ticker, name in ticker_to_name.items():
            try:
                # Single-ticker download gives close_df with just that ticker as column
                if ticker in close_df.columns:
                    close_series = close_df[ticker].dropna()
                else:
                    log.warning("Ticker %s not found in downloaded data.", ticker)
                    returns[name] = None
                    continue

                if len(close_series) < 2:
                    log.warning("Insufficient data for %s (%s).", name, ticker)
                    returns[name] = None
                    continue

                start_price = close_series.iloc[0]
                end_price = close_series.iloc[-1]
                pct_return = (end_price - start_price) / start_price * 100
                returns[name] = round(float(pct_return), 2)
                log.info("  %s: %.2f%%", name, returns[name])

            except (KeyError, IndexError, ZeroDivisionError) as exc:
                log.warning("Failed to compute return for %s: %s", name, exc)
                returns[name] = None

    except Exception as exc:
        log.error("Failed to download benchmark data: %s", exc)
        # Return None for all indices on failure
        return {name: None for name in BENCHMARK_INDICES}

    # Cache results for completed FYs
    if fy_complete:
        cache[fy_label] = returns
        _save_benchmark_cache(cache)

    return returns
