from datetime import date
from pathlib import Path

DOCS_PATH: Path = Path(Path(__file__).parents[1], "docs")

# files identifier for zerodha file names
LEDGER_ID_ZERODHA: str = "ledger"
TRADEBOOK_ID_ZERODHA: str = "tradebook"
HOLDING_EXCEL_ZERODHA: str = "holdings-RY9229.xlsx"

# NSE web scrapping specific constants
USE_WEBSCRAPPING: bool = True

HEADERS: dict = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/87.0.4280.88 Safari/537.36 "
}

NSE_URL: str = "https://www.nseindia.com"
NSE_STOCK_URL: str = "https://www.nseindia.com/get-quotes/equity?symbol={stock_name}"
NSE_CORP_ACTIONS_URL: str = (
    "https://www.nseindia.com/api/corp-info?symbol={stock_name}&corpType=corpactions&market=equities"
)
NSE_PAST_IPO_URL: str = (
    "https://www.nseindia.com/api/public-past-issues?symbol={stock_name}&security_type=all"
)

# local corporate_actions data file name
LOCAL_DATA_PATH: Path = Path(Path(__file__).parents[1], ".data")
DIVIDEND_CSV: str = "dividends.csv"
SPLIT_ACTIONS_CSV: str = "splits.csv"
MERGER_CSV: str = "merger.csv"
DEMERGER_CSV: str = "demerger.csv"
IPO_CSV: str = "ipo.csv"
LAST_DATE_TXT: str = "last_date.txt"

# buy and sell transactions
BUY: str = "buy"
SELL: str = "sell"
DIVIDEND: str = "dividend"
STOCK_SPLIT: str = "split"

DEFAULT_LAST_DATE: date = date(2015, 1, 1)
