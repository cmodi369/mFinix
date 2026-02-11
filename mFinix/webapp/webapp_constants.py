import mFinix.constants.columns as col


class EventOptions:
    ADD_TRANSACTION: str = "Add Transaction"
    ADD_SPLIT: str = "Add Split"
    ADD_BONUS: str = "Add Bonus"
    ADD_MERGER: str = "Add Merger"
    ADD_DEMERGER: str = "Add Demerger"
    ADD_IPO: str = "Add IPO"
    ADD_BUYBACK: str = "Add Buyback"
    ADD_DIVIDEND: str = "Add Dividend"

    @classmethod
    def all_options(cls):
        return [
            value
            for name, value in vars(cls).items()
            if isinstance(value, str) and not name.startswith("__")
        ]


class StockMenuOptions:
    SHOW_PORTFOLIO: str = "Show Portfolio"
    SHOW_TRANSACTIONS: str = "Show All Transactions"
    AUTO_CORP_ACTIONS: str = "Auto Corporate Actions"
    ADD_MANUAL_EVENTS: str = "Add Manual Events"

    @classmethod
    def all_options(cls):
        return [
            value
            for name, value in vars(cls).items()
            if isinstance(value, str) and not name.startswith("__")
        ]


EVENTS_OPTIONS = EventOptions.all_options()

STOCK_MENU_OPTIONS = StockMenuOptions.all_options()

COL_NAME_MAPPING: dict[str, str] = {
    col.SYMBOL: "Stock Name",
    col.TRADE_DATE: "Trade Date",
    col.TRADE_TYPE: "Trade Type",
    col.QUANTITY: "Quantity",
    col.PRICE: "Price",
    col.TRANSACTION_AMOUNT: "Transaction Amount",
    col.TOTAL_QUANTITY: "Total Quantity",
}


class UIStyles:
    # Color constants
    POSITIVE_COLOR = "#2ecc71"  # Emerald Green
    NEGATIVE_COLOR = "#e74c3c"  # Cinnabar Red
    NEUTRAL_COLOR = "#95a5a6"  # Asbestos Gray
    INDICATOR_BG_COLOR = "#f8f9fa"  # Light background for indicators
    HEADER_COLOR = "#2c3e50"  # Midnight Blue
    ACCENT_COLOR = "#3498db"  # Peter River Blue

    # Table styles
    TABLE_THEME = "fast"
    TABLE_HEADER_BG = "#f2f2f2"
    TABLE_ROW_HEIGHT = 35

    # Text styles
    INDICATOR_TITLE_SIZE = "14pt"
    INDICATOR_VALUE_SIZE = "24pt"

    # Custom CSS
    CUSTOM_CSS = """
    .tabulator-header {
        background-color: #f8f9fa !important;
        font-weight: bold !important;
        color: #2c3e50 !important;
    }
    .tabulator-row-odd {
        background-color: #ffffff !important;
    }
    .tabulator-row-even {
        background-color: #fdfdfd !important;
    }
    .tabulator-row:hover {
        background-color: #eef2f7 !important;
    }
    .pn-indicator-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    """
