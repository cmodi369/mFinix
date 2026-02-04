"""
Data management utilities for stock price fetching and general data operations.

This module provides utilities for fetching historical stock prices and
data transformation operations. For reading trading data from the Kite
platform, use the read_kite_data module.

"""

from datetime import date
from typing import Iterator, List, Union

import pandas as pd

from mFinix.core.yfinance_query import fetch_stocks_price  # noqa: F401

# Preserve backward compatibility by re-exporting public function
__all__ = ["fetch_stocks_price"]
