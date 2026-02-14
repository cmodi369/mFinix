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
    POSITIVE_COLOR = "var(--success-foreground-rest)"  # Adapts to theme (Green)
    NEGATIVE_COLOR = "var(--danger-foreground-rest)"  # Adapts to theme (Red)
    NEUTRAL_COLOR = "var(--neutral-foreground-rest)"  # Adapts to theme (Gray)
    INDICATOR_BG_COLOR = "#fbbf24"  # Input background for distinction
    HEADER_COLOR = "var(--neutral-foreground-rest)"
    ACCENT_COLOR = "var(--accent-foreground-rest)"
    BORDER_STYLE = "3px solid #7c6464"

    # Table styles
    TABLE_THEME = "fast"  # Fast theme supports variables better usually, or we override
    TABLE_HEADER_BG = "var(--neutral-fill-hover)"
    TABLE_ROW_HEIGHT = 35

    # Text styles
    INDICATOR_TITLE_SIZE = "14pt"
    INDICATOR_VALUE_SIZE = "24pt"

    # Card styles
    CARD_BACKGROUND = "var(--neutral-fill-card-rest)"
    CARD_STYLE = {
        "background-color": CARD_BACKGROUND,
        "border": BORDER_STYLE,
        "border-radius": "12px",
        "box_shadow": "var(--elevation-shadow-3)",
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
        color: var(--neutral-foreground-rest) !important;
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
    """


class SidebarStyles:
    """Modern sidebar styling constants following standard UI guidelines.

    Features:
    - Clean color scheme matching dashboard
    - Proper spacing and typography
    - Active state with visual indicators
    - Hover effects for better interactivity
    - Accessible color contrasts
    """

    # Color palette - CSS Variables
    PRIMARY_COLOR = "var(--accent-foreground-rest)"
    PRIMARY_DARK = "var(--accent-foreground-active)"
    BG_COLOR = "var(--neutral-fill-card-rest)"
    TEXT_COLOR = "var(--neutral-foreground-rest)"
    TEXT_SECONDARY = "var(--neutral-foreground-hint)"
    BORDER_COLOR = "var(--neutral-stroke-divider-rest)"
    ACTIVE_BG = "var(--neutral-fill-hover)"
    ACTIVE_BORDER = "var(--accent-foreground-rest)"

    # Button styling
    BUTTON_STYLES = {
        "width": "100%",
        "text-align": "left",
        "font-weight": "500",
        "font-size": "14px",
        "color": TEXT_COLOR,
        "background-color": "transparent",
        "border": "1px solid transparent",
        "border-left": "4px solid transparent",
        "cursor": "pointer",
        "display": "flex",
        "align-items": "center",
        "margin": "0px",
        "justify-content": "flex-start",
        "padding": "5px 15px",
        "transition": "all 0.2s ease-in-out",
    }

    # Active button styling
    BUTTON_ACTIVE_STYLES = {
        "background-color": ACTIVE_BG,
        "border-left": f"4px solid {ACTIVE_BORDER}",
        "color": PRIMARY_COLOR,
        "font-weight": "600",
        # "box-shadow": "inset 2px 0 0 0 " + ACTIVE_BORDER, # Can sometimes conflict with border-left
    }

    # Sidebar container styling
    SIDEBAR_CONTAINER_STYLES = {
        "width": "100%",
        "padding": "15px",
        "background-color": BG_COLOR,
        "display": "flex",
        "flex-direction": "column",
        "gap": "10px",
        "height": "100vh",  # Ensure full height for background
    }

    # Header styles
    HEADER_STYLES = {
        "padding": "15px 0",
        "border-bottom": f"1px solid {BORDER_COLOR}",
        "margin-bottom": "10px",
        "color": TEXT_COLOR,
        "font-weight": "600",
    }

    # Footer styles
    FOOTER_STYLES = {
        "margin-top": "auto",
        "padding-top": "15px",
        "border-top": f"1px solid {BORDER_COLOR}",
        "color": TEXT_SECONDARY,
        "font-size": "11px",
        "line-height": "1.5",
    }

    CUSTOM_CSS = """
            /* Sidebar styling */
        .pn-sidebar {
            background-color: var(--neutral-fill-card-rest);
            border-right: 1px solid var(--neutral-stroke-divider-rest);
            padding: 0;
        }

        /* Navigation buttons improved styling */
        .pn-btn {
            border-radius: 0px 4px 4px 0px;
            transition: all 0.2s ease-in-out;
            color: var(--neutral-foreground-rest);
        }

        .pn-btn:hover {
            background-color: var(--neutral-fill-hover) !important;
            transform: translateX(2px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        .pn-btn-light {
            color: var(--neutral-foreground-rest);
            border: 1px solid transparent;
            border-left: 4px solid transparent;
            background-color: transparent;
        }

        .pn-btn-light:active {
            background-color: var(--neutral-fill-active) !important;
            border-left: 4px solid var(--accent-foreground-rest);
            color: var(--accent-foreground-rest);
        }

        /* Main content area improvements */
        .pn-main {
            padding: 20px;
            background-color: var(--neutral-fill-bg);
        }

        /* Typography improvements */
        h1, h2, h3 {
            color: var(--neutral-foreground-rest);
            font-weight: 600;
        }

        /* Focus states for accessibility */
        .pn-btn:focus {
            outline: 2px solid var(--accent-foreground-rest);
            outline-offset: 2px;
        }

        /* Smooth transitions */
        * {
            transition-property: background-color, color, border-color;
            transition-duration: 0.2s;
            transition-timing-function: ease-in-out;
        }

        /* Card styling for content sections */
        .pn-card {
            background-color: var(--neutral-fill-card-rest);
            border: 1px solid var(--neutral-stroke-card-rest);
            border-radius: 8px;
            box-shadow: var(--elevation-shadow-1);
            padding: 16px;
            margin-bottom: 16px;
        }"""
