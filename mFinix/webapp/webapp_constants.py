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
    # Color constants - Using Panel CSS variables for theme compatibility
    POSITIVE_COLOR = "var(--success-text-color)"  # Adapts to theme (Green)
    NEGATIVE_COLOR = "var(--danger-text-color)"  # Adapts to theme (Red)
    NEUTRAL_COLOR = "var(--neutral-text-color)"  # Adapts to theme (Gray)
    INDICATOR_BG_COLOR = "var(--neutral-fill-rest)"  # Neutral background
    HEADER_COLOR = "var(--neutral-foreground-rest)"
    ACCENT_COLOR = "var(--accent-foreground-rest)"
    BORDER_STYLE = "1px solid var(--neutral-stroke-rest)"

    # Table styles
    TABLE_THEME = "fast"
    TABLE_HEADER_BG = "var(--neutral-fill-hover)"
    TABLE_ROW_HEIGHT = 40

    # Text styles
    INDICATOR_TITLE_SIZE = "13pt"
    INDICATOR_VALUE_SIZE = "22pt"

    # Card styles
    CARD_BACKGROUND = "var(--neutral-fill-card-rest)"
    CARD_STYLE = {
        "background-color": CARD_BACKGROUND,
        "border": BORDER_STYLE,
        "border-radius": "16px",
        "box_shadow": "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        "margin_bottom": "24px",
        "display": "flex",
        "flex_direction": "column",
    }

    # Custom CSS
    CUSTOM_CSS = """
    .tabulator-header {
        background-color: var(--neutral-fill-hover) !important;
        font-weight: 600 !important;
        color: var(--neutral-foreground-rest) !important;
        border-bottom: 2px solid var(--neutral-stroke-rest) !important;
        text-transform: uppercase;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
    }
    .tabulator-row {
        border-bottom: 1px solid var(--neutral-stroke-divider-rest) !important;
        transition: background-color 0.2s ease;
        background-color: var(--neutral-fill-card-rest) !important;
        color: var(--neutral-foreground-rest);
    }
    .tabulator-row-odd {
        background-color: var(--neutral-fill-card-rest) !important;
    }
    .tabulator-row-even {
        background-color: var(--neutral-fill-card-rest) !important;
    }
    .tabulator-row:hover {
        background-color: var(--neutral-fill-hover) !important;
        cursor: pointer;
    }
    .metric-label {
        color: var(--neutral-foreground-hint);
        font-size: 0.9rem;
        font-weight: 500;
        margin-bottom: 4px;
    }
    .metric-value {
        color: var(--neutral-foreground-rest);
        font-size: 1.8rem;
        font-weight: 700;
    }
    .bk-root .bk-panel-models-layout-Column {
        width: 100% !important;
        max-width: none !important;
    }
    """


class SidebarStyles:
    """Modern sidebar styling with dark navy theme and active state."""

    # Color palette
    SIDEBAR_BG = "#0a1128"  # Dark navy background
    BUTTON_INACTIVE_COLOR = "#94a3b8"  # Slate gray for inactive buttons
    BUTTON_ACTIVE_BG = "#2563eb"  # Blue for active state
    BUTTON_HOVER_BG = "rgba(255, 255, 255, 0.05)"  # Subtle white overlay on hover

    # Sidebar container styling
    SIDEBAR_CONTAINER_STYLES = {
        "width": "100%",
        "padding": "20px 16px",
        "background-color": SIDEBAR_BG,
        "display": "flex",
        "flex-direction": "column",
        "height": "100vh",
        "border-radius": "0 24px 24px 0",  # Match rounded corners if visible
    }

    # Button styling
    BUTTON_CSS = """
        :host(.nav-button) .bk-btn {
            background-color: transparent !important;
            border: none !important;
            text-align: left !important;
            color: #94a3b8 !important;
            font-size: 15px !important;
            padding: 14px 18px !important;
            border-radius: 10px !important;
            width: 100% !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
        }

        :host(.nav-active) .bk-btn {
            background-color: #2563eb !important;
            color: white !important;
            font-weight: 500 !important;
        }

        :host(.nav-button:not(.nav-active)) .bk-btn:hover {
            background-color: rgba(255, 255, 255, 0.05) !important;
            color: white !important;
            cursor: pointer;
        }
        """

    CUSTOM_CSS = """
        #sidebar {
            padding: 5px 5px 5px 0px  !important;
            overflow-y: hidden !important;
        }

        .pn-sidebar-container {
            margin-top: 3px !important;
        }
    """
