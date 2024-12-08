from datetime import date
from pathlib import Path

DOCS_PATH: Path = Path(Path(__file__).parents[1], "docs")

# files identifier for zerodha file names
LEDGER_ID_ZERODHA: str = "ledger"
TRADEBOOK_ID_ZERODHA: str = "tradebook"

# local corporate_actions data file name
LOCAL_DATA_PATH: Path = Path(Path(__file__).parents[1], ".data")
DIVIDEND_CSV: str = "dividends.csv"
SPLIT_ACTIONS_CSV: str = "splits.csv"
MERGER_CSV: str = "merger.csv"
DEMERGER_CSV: str = "demerger.csv"
LAST_DATE_TXT: str = "last_date.txt"

# buy and sell transactions
BUY: str = "buy"
SELL: str = "sell"

DEFAULT_LAST_DATE: date = date(2015, 1, 1)
