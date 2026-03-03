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
PARTICULARS: str = "particulars"
DEBIT: str = "debit"
CREDIT: str = "credit"
NET_BALANCE: str = "net_balance"

# column names used by yf stock actions
DIVIDEND: str = "Dividends"
STOCK_SPLITS: str = "Stock Splits"

# column names used in local files
DIVIDEND_COL: str = DIVIDEND.lower().replace(" ", "_")
STOCK_SPLITS_COL: str = STOCK_SPLITS.lower().replace(" ", "_")

# column names used in the project
CURRENT_PRICE: str = "current_price"
TOTAL_QUANTITY: str = "balanced_quantity"
XIRR: str = "xirr"
AVG_BUY_PRICE: str = "avg_buy_price"
BUY_VALUE: str = "buy_value"
PRESENT_VALUE: str = "present_value"
PNL: str = "pnl"
PNL_PERCENTAGE: str = "pnl_percentage"
HOLDING_QUANTITY: str = "holding_quantity"
IS_DISCREPANCY: str = "is_discrepancy"
STATUS_ICON: str = "status_icon"

# demerger specific columns
PARENT_SYMBOL: str = "parent_symbol"
PARENT_QUANTITY: str = "parent_quantity"
RATIO: str = "ratio"
