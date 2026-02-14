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
        font-weight: 600 !important;
        color: #2c3e50 !important;
        border-bottom: 2px solid #e0e0e0 !important;
        text-transform: uppercase;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
    }
    .tabulator-row {
        border-bottom: 1px solid #f0f0f0 !important;
        transition: background-color 0.2s ease;
    }
    .tabulator-row-odd {
        background-color: #ffffff !important;
    }
    .tabulator-row-even {
        background-color: #fafbfc !important;
    }
    .tabulator-row:hover {
        background-color: #f1f4f8 !important;
        cursor: pointer;
    }
    .pn-indicator-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        border: 1px solid #eef0f3;
    }
    .pn-indicator-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.12);
    }
    .metric-label {
        color: #7f8c8d;
        font-size: 0.9rem;
        font-weight: 500;
        margin-bottom: 4px;
    }
    .metric-value {
        color: #2c3e50;
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

    # Color palette
    PRIMARY_COLOR = "#3498db"  # Peter River Blue
    PRIMARY_DARK = "#2980b9"  # Darker shade for hover
    BG_COLOR = "#ffffff"  # White background
    TEXT_COLOR = "#2c3e50"  # Midnight Blue
    TEXT_SECONDARY = "#7f8c8d"  # Gray for secondary text
    BORDER_COLOR = "#e0e0e0"  # Light gray for borders
    ACTIVE_BG = "#ecf0f6"  # Light blue for active state background
    ACTIVE_BORDER = "#3498db"  # Blue for left border

    # Button styling
    BUTTON_STYLES = {
        "width": "100%",
        "text-align": "left",
        "font-weight": "500",
        "font-size": "14px",
        "color": TEXT_COLOR,
        "background-color": BG_COLOR,
        "border": "1px solid transparent",
        "border-left": f"4px solid transparent",
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
        "box-shadow": "inset 2px 0 0 0 " + ACTIVE_BORDER,  # Subtle inner shadow
    }

    # Sidebar container styling
    SIDEBAR_CONTAINER_STYLES = {
        "width": "100%",
        "padding": "15px",
        "background-color": BG_COLOR,
        "display": "flex",
        "flex-direction": "column",
        "gap": "10px",
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

    # Card styling for content sections
    CARD_STYLE = {
        "background-color": BG_COLOR,
        "border": f"1px solid {BORDER_COLOR}",
        "border-radius": "12px",
        "box_shadow": "0 4px 6px rgba(0, 0, 0, 0.05)",
        "padding": "24px",
        "margin_bottom": "24px",
        "display": "flex",
        "flex_direction": "column",
        "gap": "16px",
    }

    CUSTOM_CSS = """
            /* Sidebar styling */
        .pn-sidebar {
            background-color: #ffffff;
            border-right: 1px solid #e0e0e0;
            padding: 0;
        }

        /* Navigation buttons improved styling */
        .pn-btn {
            border-radius: 0px 4px 4px 0px;
            transition: all 0.2s ease-in-out;
        }

        .pn-btn:hover {
            background-color: #ecf0f6 !important;
            transform: translateX(2px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        .pn-btn-light {
            color: #2c3e50;
            border: 1px solid transparent;
            border-left: 4px solid transparent;
        }

        .pn-btn-light:active {
            background-color: #ecf0f6 !important;
            border-left: 4px solid #3498db;
            color: #3498db;
        }

        /* Main content area improvements */
        .pn-main {
            padding: 20px;
            background-color: #f8f9fa;
        }

        /* Typography improvements */
        h1, h2, h3 {
            color: #2c3e50;
            font-weight: 600;
        }

        /* Focus states for accessibility */
        .pn-btn:focus {
            outline: 2px solid #3498db;
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
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            padding: 16px;
            margin-bottom: 16px;
        }"""
