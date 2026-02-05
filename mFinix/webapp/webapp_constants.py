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
