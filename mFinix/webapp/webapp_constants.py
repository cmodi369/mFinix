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
    POSITIVE_COLOR = "var(--success-text-color)"
    NEGATIVE_COLOR = "var(--danger-text-color)"
    NEUTRAL_COLOR = "var(--neutral-foreground-rest)"
    INDICATOR_BG_COLOR = "var(--neutral-fill-card-rest)"
    BORDER_STYLE = "1px solid var(--neutral-stroke-rest)"
    HEADER_COLOR = "var(--neutral-foreground-rest)"
    CARD_BACKGROUND = "var(--neutral-fill-card-rest)"

    # Table styles
    TABLE_THEME = "fast"

    # Text styles
    INDICATOR_TITLE_SIZE = "11pt"
    INDICATOR_VALUE_SIZE = "20pt"

    # Card styles
    CARD_STYLE = {
        "background-color": CARD_BACKGROUND,
        "border": BORDER_STYLE,
        "border-radius": "16px",
        "box-shadow": "var(--elevation-shadow-1)",
        "padding": "20px",
        "margin": "0px",
    }

    # Custom CSS for the premium overhaul - Modularized for maintainability
    MAIN_LAYOUT_CSS = """
    /* Main Layout */
    .main-container {
        background-color: var(--neutral-fill-focus);
        padding: 5px;
    }
    """

    SUMMARY_CARD_CSS = """
    /* Summary Cards */
    .summary-card {
        background: var(--neutral-fill-layer-rest, rgba(0,0,0,0.015));
        border: 1px solid var(--neutral-stroke-divider-rest, #e5e7eb);
        border-radius: 12px;
        padding: 20px;
        min-width: 280px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .summary-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--elevation-shadow-2);
    }
    .summary-label {
        color: var(--neutral-foreground-hint, #64748b);
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .summary-value-container {
        display: flex;
        align-items: baseline;
        gap: 8px;
    }
    .summary-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--neutral-foreground-rest, #022c22);
    }
    """

    HEADER_CONTROLS_CSS = """
    /* Header & Controls */
    .page-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--neutral-foreground-rest);
        margin: 0;
    }
    .action-button .bk-btn {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 8px 20px !important;
        transition: all 0.2s ease !important;
    }
    .search-input .bk-input {
        border-radius: 10px !important;
        border: 1px solid var(--neutral-stroke-rest) !important;
        padding: 8px 12px 8px 36px !important;
        background-color: var(--neutral-fill-input-rest) !important;
    }
    """

    TABULATOR_CSS = """
    /* Table Styling */
    .holdings-table .tabulator {
        border: none !important;
        background-color: transparent !important;
    }
    .holdings-table .tabulator-header {
        background-color: transparent !important;
        border-bottom: 2px solid var(--neutral-stroke-rest) !important;
    }
    .holdings-table .tabulator-col {
        background-color: transparent !important;
        border: none !important;
    }
    .holdings-table .tabulator-col-title {
        color: var(--neutral-foreground-hint) !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    .holdings-table .tabulator-row {
        border-bottom: 1px solid var(--neutral-stroke-divider-rest) !important;
        background-color: transparent !important;
        min-height: 70px !important;
        display: flex;
        align-items: center;
    }
    .holdings-table .tabulator-cell {
        border: none !important;
        padding: 12px 8px !important;
        display: flex !important;
        align-items: center !important;
    }
    """

    CELL_COMPONENTS_CSS = """
    /* Cell Components */
    .status-icon {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9rem;
    }
    .stock-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .stock-name {
        font-weight: 700;
        color: var(--neutral-foreground-rest);
        font-size: 0.95rem;
    }
    .stock-isin {
        color: var(--neutral-foreground-hint);
        font-size: 0.75rem;
        font-family: monospace;
    }
    .pnl-container {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 2px;
    }
    .pnl-value {
        font-weight: 700;
        font-size: 1rem;
    }
    .pnl-percent {
        font-size: 0.8rem;
        font-weight: 500;
    }

    .fix-now-btn .bk-btn {
        background: var(--danger-fill-rest, #fee2e2) !important;
        color: var(--danger-text-rest, #dc2626) !important;
        border: 1px solid var(--danger-stroke-rest, #f87171) !important;
        border-radius: 8px !important;
        padding: 6px 14px !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        font-family: 'Inter', sans-serif !important;
        text-decoration: none !important;
        cursor: pointer !important;
        min-height: unset !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .fix-now-btn .bk-btn:hover {
        background: var(--danger-fill-hover, #fecaca) !important;
        transform: translateY(-1px);
    }
    """

    CUSTOM_CSS = (
        MAIN_LAYOUT_CSS
        + SUMMARY_CARD_CSS
        + HEADER_CONTROLS_CSS
        + TABULATOR_CSS
        + CELL_COMPONENTS_CSS
    )


class SidebarStyles:
    """Modern sidebar styling with dark navy theme and active state."""

    # Color palette
    SIDEBAR_BG = "#0a1128"  # Dark navy background

    # Sidebar container styling
    SIDEBAR_CONTAINER_STYLES = {
        "width": "100%",
        "padding": "20px 8px",
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
            padding: 5px 0px 5px 0px  !important;
            overflow-y: hidden !important;
        }
        
        fast-card {
            padding: 0px !important;
        }

        .pn-sidebar-container {
            margin-top: 3px !important;
        }
    """
