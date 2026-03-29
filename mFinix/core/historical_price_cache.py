"""
Historical Portfolio Value Cache.

Stores end-of-FY portfolio values to avoid re-fetching historical prices
on every load. Only completed FYs are cached permanently; the current FY
is always recomputed.

Cache file: LOCAL_DATA_PATH / fy_portfolio_cache.json
Format: { "FY2022-23": 1500000.0, "FY2023-24": 1850000.0, ... }
"""

import json
from pathlib import Path
from typing import Optional

from mFinix.constants.constants import FY_PORTFOLIO_CACHE, LOCAL_DATA_PATH
from mFinix.util import log

_CACHE_PATH: Path = LOCAL_DATA_PATH / FY_PORTFOLIO_CACHE


def get_cached_fy_portfolio_values() -> dict[str, float]:
    """Load cached FY portfolio values from disk.

    Returns
    -------
    dict[str, float]
        Dictionary mapping FY label (e.g. "FY2022-23") to portfolio value in INR.
        Returns empty dict if cache does not exist or is corrupt.
    """
    if not _CACHE_PATH.exists():
        return {}

    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to read FY portfolio cache: %s. Starting fresh.", exc)
        return {}


def save_fy_portfolio_values(data: dict[str, float]) -> None:
    """Persist FY portfolio values to disk.

    Parameters
    ----------
    data : dict[str, float]
        Dictionary mapping FY label to portfolio value in INR.
    """
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log.info("Saved FY portfolio cache (%d entries).", len(data))
    except OSError as exc:
        log.error("Failed to save FY portfolio cache: %s", exc)


def update_cached_fy_value(fy_label: str, portfolio_value: float) -> None:
    """Update a single FY entry in the cache (load → update → save).

    Parameters
    ----------
    fy_label : str
        FY label, e.g. "FY2022-23".
    portfolio_value : float
        Portfolio value in INR at FY-end.
    """
    cache = get_cached_fy_portfolio_values()
    cache[fy_label] = portfolio_value
    save_fy_portfolio_values(cache)


def get_cached_fy_value(fy_label: str) -> Optional[float]:
    """Retrieve a single FY value from cache.

    Parameters
    ----------
    fy_label : str
        FY label, e.g. "FY2022-23".

    Returns
    -------
    Optional[float]
        Cached portfolio value or None if not cached.
    """
    cache = get_cached_fy_portfolio_values()
    return cache.get(fy_label)
