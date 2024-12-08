# tradebook data column names
ISIN: str = "isin"
SYMBOL: str = "symbol"
TRADE_TYPE: str = "trade_type"
TRADE_DATE: str = "trade_date"
QUANTITY: str = "quantity"
PRICE: str = "price"
TRANSACTION_AMOUNT: str = "transaction_amount"

# ledger data column names
POSTING_DATE: str = "posting_date"

# column names used by yf stock actions
DIVIDEND: str = "Dividends"
STOCK_SPLITS: str = "Stock Splits"

# column names used in local files
DIVIDEND_COL: str = DIVIDEND.lower().replace(" ", "_")
STOCK_SPLITS_COL: str = STOCK_SPLITS.lower().replace(" ", "_")

TOTAL_QUANTITY: str = "total_quantity"
