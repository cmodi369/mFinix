"""
Buy/Sell Analysis Panel.

Renders a premium dashboard panel showing buy/sell sentiment analysis
with KPI cards, Alpha vs Opportunity bar chart, 1-Year Reality Check
scatter plot, and a detailed graded table.

Embedded as a sub-tab inside the main Stocks tab layout.
"""

import math
from typing import Any

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.core.benchmark_data import fy_label_to_dates, get_all_fy_labels
from mFinix.core.buy_sell_analysis import compute_buy_sell_analysis
from mFinix.util import log
from mFinix.webapp.webapp_constants import UIStyles


class BuySellAnalysisPanel:
    """Inline panel: Buy/Sell sentiment analysis dashboard.

    Parameters
    ----------
    tab_data : dict
        Must contain ``transactions_data`` (DataFrame) and
        ``stocks_xirr_data`` (DataFrame).
    """

    def __init__(self, tab_data: dict[str, Any]) -> None:
        self.tab_data = tab_data
        self._analysis: dict | None = None
        self._current_fy = "All"
        self.layout = pn.Column(sizing_mode="stretch_width")
        self._build_layout()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Reset cached analysis and rebuild layout."""
        self._analysis = None
        self._build_layout()

    # ------------------------------------------------------------------
    # Private – data
    # ------------------------------------------------------------------

    def _get_analysis(self) -> dict:
        if self._analysis is None:
            try:
                self._analysis = compute_buy_sell_analysis(
                    self.tab_data.get("transactions_data", pd.DataFrame()),
                    self.tab_data.get("stocks_xirr_data", pd.DataFrame()),
                )
            except Exception as exc:
                log.error("Buy/Sell analysis failed: %s", exc)
                self._analysis = {
                    "kpis": {
                        "total_alpha": 0.0,
                        "buy_win_rate": 0.0,
                        "sell_win_rate": 0.0,
                        "sentiment_lag": 0.0,
                    },
                    "details_df": pd.DataFrame(),
                }
        return self._analysis

    def _get_available_fys(self) -> list[str]:
        """Get all FY labels found in transactions."""
        txns = self.tab_data.get("transactions_data", pd.DataFrame())
        if txns.empty:
            return ["All"]
        start_date = txns[col.TRADE_DATE].min()
        if pd.isna(start_date):
            return ["All"]
        labels = get_all_fy_labels(pd.Timestamp(start_date).date())
        return ["All"] + list(reversed(labels))

    def _get_filtered_analysis(self, fy_label: str) -> dict:
        """Return analysis calculated specifically for an FY."""
        if fy_label == "All":
            return self._get_analysis()

        start, end = fy_label_to_dates(fy_label)

        # Filter transactions for the core engine calculation
        txns = self.tab_data.get("transactions_data", pd.DataFrame())
        txns_copy = txns.copy()
        txns_copy["_dt"] = pd.to_datetime(txns_copy[col.TRADE_DATE]).dt.date
        filtered_txns = txns_copy[
            (txns_copy["_dt"] >= start) & (txns_copy["_dt"] <= end)
        ].copy()

        # Run analysis specifically on this slice of transactions
        try:
            return compute_buy_sell_analysis(
                filtered_txns, self.tab_data.get("stocks_xirr_data", pd.DataFrame())
            )
        except Exception as exc:
            log.error("Filtered Buy/Sell analysis failed for %s: %s", fy_label, exc)
            return {
                "kpis": {
                    "total_alpha": 0.0,
                    "buy_win_rate": 0.0,
                    "sell_win_rate": 0.0,
                    "sentiment_lag": 0.0,
                },
                "details_df": pd.DataFrame(),
            }

    # ------------------------------------------------------------------
    # Private – KPI Cards
    # ------------------------------------------------------------------

    def _build_kpi_cards(self, kpis: dict) -> pn.Row:
        """Build the 4 top-level KPI summary cards."""
        alpha = kpis["total_alpha"]
        alpha_color = (
            "var(--success-text-color, #16a34a)"
            if alpha >= 0
            else "var(--danger-text-color, #dc2626)"
        )
        alpha_sign = "+" if alpha >= 0 else ""

        cards_data = [
            {
                "label": "TOTAL ALPHA",
                "value": f"{alpha_sign}{alpha:.2f}%",
                "color": alpha_color,
            },
            {
                "label": "BUY WIN RATE",
                "value": f"{kpis['buy_win_rate']:.1f}%",
                "color": "var(--neutral-foreground-rest, #022c22)",
            },
            {
                "label": "SELL WIN RATE",
                "value": f"{kpis['sell_win_rate']:.1f}%",
                "color": "var(--neutral-foreground-rest, #022c22)",
            },
            {
                "label": "SENTIMENT LAG",
                "value": f"{kpis['sentiment_lag']:.1f} Mo",
                "color": "var(--neutral-foreground-rest, #022c22)",
            },
        ]

        card_panes = []
        for card in cards_data:
            html = f"""
            <div class="summary-label">{card['label']}</div>
            <div class="summary-value-container">
                <div class="summary-value" style="color: {card['color']};">{card['value']}</div>
            </div>
            """
            card_panes.append(
                pn.Column(
                    pn.pane.HTML(html, sizing_mode="stretch_width"),
                    css_classes=["summary-card"],
                    sizing_mode="stretch_width",
                    min_height=110,
                )
            )

        return pn.Row(
            *card_panes,
            sizing_mode="stretch_width",
            styles={"gap": "20px"},
        )

    # ------------------------------------------------------------------
    # Private – Alpha vs Opportunity Chart
    # ------------------------------------------------------------------

    def _build_alpha_chart(self, details_df: pd.DataFrame) -> pn.Column:
        """Build a vertical bar chart of relative impact per ticker."""
        if details_df.empty:
            return pn.Column(
                pn.pane.HTML(
                    '<div style="padding: 40px; color: var(--neutral-foreground-hint);">'
                    "No data available.</div>"
                ),
                sizing_mode="stretch_width",
            )

        # Aggregate by symbol – sum relative impacts
        agg = (
            details_df.groupby("symbol")["relative_impact"]
            .sum()
            .sort_values(ascending=False)
        )

        max_abs = max(abs(agg.max()), abs(agg.min()), 1.0)
        # round up to a nice number
        if max_abs <= 5:
            axis_max = 5
        elif max_abs <= 10:
            axis_max = 10
        elif max_abs <= 15:
            axis_max = 15
        else:
            axis_max = math.ceil(max_abs / 5) * 5

        # Build bars HTML
        bar_width = max(60, min(80, 600 // max(len(agg), 1)))
        bars_html_parts = []

        for symbol, impact in agg.items():
            height_pct = min(abs(impact) / axis_max * 100, 100)
            is_positive = impact >= 0
            bar_color = "#16a34a" if is_positive else "#ef4444"

            if is_positive:
                bar_style = (
                    f"position: absolute; bottom: 50%; left: 50%; transform: translateX(-50%); "
                    f"width: {bar_width - 10}px; height: {height_pct / 2:.1f}%; "
                    f"background: {bar_color}; border-radius: 4px 4px 0 0; "
                    f"transition: height 0.4s ease;"
                )
            else:
                bar_style = (
                    f"position: absolute; top: 50%; left: 50%; transform: translateX(-50%); "
                    f"width: {bar_width - 10}px; height: {height_pct / 2:.1f}%; "
                    f"background: {bar_color}; border-radius: 0 0 4px 4px; "
                    f"transition: height 0.4s ease;"
                )

            bars_html_parts.append(
                f"""
                <div style="position: relative; width: {bar_width}px; height: 100%; display: flex; flex-direction: column; align-items: center;">
                    <div style="{bar_style}"></div>
                    <div style="position: absolute; bottom: -22px; font-size: 0.68rem; font-weight: 600; color: var(--neutral-foreground-hint); white-space: nowrap; text-align: center;">{symbol}</div>
                </div>
            """
            )

        bars_html = "".join(bars_html_parts)

        chart_html = f"""
        <div style="position: relative; width: 100%; height: 220px; overflow-x: auto;">
            <div style="position: absolute; left: 0; right: 0; top: 50%; height: 1px; background: var(--neutral-stroke-divider-rest, #e5e7eb);"></div>
            <div style="position: absolute; left: 0; top: 5px; font-size: 0.68rem; color: var(--neutral-foreground-hint);">{axis_max}</div>
            <div style="position: absolute; left: 0; top: 50%; transform: translateY(-50%); font-size: 0.68rem; color: var(--neutral-foreground-hint);">0</div>
            <div style="position: absolute; left: 0; bottom: 25px; font-size: 0.68rem; color: var(--neutral-foreground-hint);">-{axis_max}</div>
            <div style="display: flex; align-items: stretch; height: 100%; padding: 0 25px; gap: 4px; padding-bottom: 25px;">
                {bars_html}
            </div>
        </div>
        """

        return pn.Column(
            pn.pane.HTML(
                f"""
                <div style="font-size: 0.95rem; font-weight: 700; color: var(--neutral-foreground-rest, #022c22); margin-bottom: 2px;">Alpha vs. Opportunity</div>
                <div style="font-size: 0.78rem; color: var(--neutral-foreground-hint, #64748b); margin-bottom: 12px;">
                    Relative % Impact by ticker. Measures individual contribution to total return.
                </div>
                """,
                sizing_mode="stretch_width",
            ),
            pn.pane.HTML(chart_html, sizing_mode="stretch_width", min_height=260),
            sizing_mode="stretch_width",
            styles={
                "background": "var(--neutral-fill-layer-rest, rgba(0,0,0,0.015))",
                "border": "1px solid var(--neutral-stroke-divider-rest, #e5e7eb)",
                "border-radius": "12px",
                "padding": "20px",
            },
        )

    # ------------------------------------------------------------------
    # Private – 1-Year Reality Check Scatter Plot
    # ------------------------------------------------------------------

    def _build_scatter_chart(self, details_df: pd.DataFrame) -> pn.Column:
        """Build a scatter plot: 1-yr move (x) vs current move (y)."""
        if details_df.empty:
            return pn.Column(
                pn.pane.HTML(
                    '<div style="padding: 40px; color: var(--neutral-foreground-hint);">'
                    "No data available.</div>"
                ),
                sizing_mode="stretch_width",
            )

        x_vals = details_df["one_yr_move"].values
        y_vals = details_df["current_move"].values
        symbols = details_df["symbol"].values

        # Determine axes
        all_vals = list(x_vals) + list(y_vals)
        max_abs = max(abs(min(all_vals, default=0)), abs(max(all_vals, default=0)), 10)
        step = 20 if max_abs <= 50 else 50 if max_abs <= 200 else 100
        axis_max = max(math.ceil(max_abs / step) * step, step)

        # Scale to SVG coordinates
        svg_w, svg_h = 500, 300
        margin = 50

        def scale_x(v):
            return margin + (v + axis_max) / (2 * axis_max) * (svg_w - 2 * margin)

        def scale_y(v):
            return (svg_h - margin) - (v + axis_max) / (2 * axis_max) * (
                svg_h - 2 * margin
            )

        # Build SVG dots
        dots = []
        for i, (x, y, sym) in enumerate(zip(x_vals, y_vals, symbols)):
            cx, cy = scale_x(x), scale_y(y)
            dots.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="#1e293b" opacity="0.8">'
                f"<title>{sym}: 1yr={x:.1f}%, cur={y:.1f}%</title></circle>"
            )

        dots_svg = "\n".join(dots)

        # Axis tick marks
        tick_count = 5
        x_ticks = ""
        y_ticks = ""
        for i in range(tick_count + 1):
            val = -axis_max + (2 * axis_max) * i / tick_count
            tx = scale_x(val)
            ty = scale_y(val)
            x_ticks += f'<text x="{tx:.1f}" y="{svg_h - 8}" text-anchor="middle" font-size="10" fill="var(--neutral-foreground-hint, #64748b)">{val:g}</text>'
            y_ticks += f'<text x="{margin - 8}" y="{ty + 3:.1f}" text-anchor="end" font-size="10" fill="var(--neutral-foreground-hint, #64748b)">{val:g}</text>'

        # Grid lines
        grid_lines = ""
        for i in range(tick_count + 1):
            val = -axis_max + (2 * axis_max) * i / tick_count
            tx = scale_x(val)
            ty = scale_y(val)
            grid_lines += f'<line x1="{tx:.1f}" y1="{margin}" x2="{tx:.1f}" y2="{svg_h - margin}" stroke="var(--neutral-stroke-divider-rest, #e5e7eb)" stroke-width="0.5"/>'
            grid_lines += f'<line x1="{margin}" y1="{ty:.1f}" x2="{svg_w - margin}" y2="{ty:.1f}" stroke="var(--neutral-stroke-divider-rest, #e5e7eb)" stroke-width="0.5"/>'

        svg = f"""
        <svg viewBox="0 0 {svg_w} {svg_h}" width="100%" height="100%" style="max-height: 280px;">
            {grid_lines}
            <line x1="{margin}" y1="{scale_y(0):.1f}" x2="{svg_w - margin}" y2="{scale_y(0):.1f}" stroke="var(--neutral-stroke-rest, #94a3b8)" stroke-width="1"/>
            <line x1="{scale_x(0):.1f}" y1="{margin}" x2="{scale_x(0):.1f}" y2="{svg_h - margin}" stroke="var(--neutral-stroke-rest, #94a3b8)" stroke-width="1"/>
            {dots_svg}
            {x_ticks}
            {y_ticks}
        </svg>
        """

        return pn.Column(
            pn.pane.HTML(
                """
                <div style="font-size: 0.95rem; font-weight: 700; color: var(--neutral-foreground-rest, #022c22); margin-bottom: 2px;">1-Year Reality Check</div>
                <div style="font-size: 0.78rem; color: var(--neutral-foreground-hint, #64748b); margin-bottom: 12px;">
                    Mapping 1-Year Performance vs Current Performance to assess trend persistence.
                </div>
                """,
                sizing_mode="stretch_width",
            ),
            pn.pane.HTML(svg, sizing_mode="stretch_width", min_height=260),
            sizing_mode="stretch_width",
            styles={
                "background": "var(--neutral-fill-layer-rest, rgba(0,0,0,0.015))",
                "border": "1px solid var(--neutral-stroke-divider-rest, #e5e7eb)",
                "border-radius": "12px",
                "padding": "20px",
            },
        )

    # ------------------------------------------------------------------
    # Private – Details Table
    # ------------------------------------------------------------------

    def _build_details_table(self, details_df: pd.DataFrame) -> pn.Column:
        """Build the Accuracy & Impact Details table with filter."""
        if details_df.empty:
            return pn.Column(
                pn.pane.HTML(
                    '<div style="padding: 40px; color: var(--neutral-foreground-hint);">'
                    "No data available.</div>"
                ),
                sizing_mode="stretch_width",
            )

        # Prepare display DataFrame
        display_df = details_df.copy()
        display_df["call_date"] = pd.to_datetime(display_df["call_date"])

        # Format columns for HTML display
        def _fmt_type(val):
            color = "#16a34a" if val == "BUY" else "#dc2626"
            return f'<span style="font-weight: 700; color: {color};">{val}</span>'

        def _fmt_move(val):
            color = "#16a34a" if val >= 0 else "#dc2626"
            sign = "+" if val >= 0 else ""
            return f'<span style="font-weight: 600; color: {color};">{sign}{val:.2f}%</span>'

        def _fmt_impact(val):
            color = "#16a34a" if val >= 0 else "#dc2626"
            sign = "+" if val >= 0 else ""
            return f'<span style="font-weight: 700; color: {color};">{sign}{val:.2f}%</span>'

        def _fmt_grade(val):
            grade_colors = {
                "A": "#16a34a",
                "B": "#65a30d",
                "C": "#ca8a04",
                "D": "#9ca3af",
                "E": "#ea580c",
                "F": "#dc2626",
            }
            color = grade_colors.get(val, "#6b7280")
            return (
                f'<div style="display: inline-flex; align-items: center; justify-content: center; '
                f"width: 32px; height: 32px; border-radius: 50%; "
                f"font-weight: 700; font-size: 0.85rem; color: {color}; "
                f'border: 2px solid {color};">{val}</div>'
            )

        def _fmt_date(val):
            if pd.isna(val):
                return ""
            return pd.Timestamp(val).strftime("%b-%y")

        def _fmt_price(val):
            return f"{val:,.2f}"

        display_df["call_type"] = display_df["call_type"].apply(_fmt_type)
        display_df["one_yr_move"] = display_df["one_yr_move"].apply(_fmt_move)
        display_df["current_move"] = display_df["current_move"].apply(_fmt_move)
        display_df["relative_impact"] = display_df["relative_impact"].apply(_fmt_impact)
        display_df["grade"] = display_df["grade"].apply(_fmt_grade)
        display_df["call_date"] = display_df["call_date"].apply(_fmt_date)
        display_df["adj_call_price"] = display_df["adj_call_price"].apply(_fmt_price)
        display_df["current_price"] = display_df["current_price"].apply(_fmt_price)
        display_df["portfolio_weight"] = display_df["portfolio_weight"].apply(
            lambda v: f"{v:.1f}%"
        )

        # Select and rename columns for display
        table_cols = [
            "symbol",
            "call_type",
            "call_date",
            "adj_call_price",
            "current_price",
            "one_yr_move",
            "current_move",
            "portfolio_weight",
            "relative_impact",
            "grade",
        ]
        table_df = display_df[table_cols].copy()

        col_titles = {
            "symbol": "Ticker",
            "call_type": "Type",
            "call_date": "Date",
            "adj_call_price": "Entry Price*",
            "current_price": "Current Price",
            "one_yr_move": "1-Yr Move",
            "current_move": "Current Move",
            "portfolio_weight": "Portfolio Weight",
            "relative_impact": "Relative Impact",
            "grade": "Grade",
        }

        table = pn.widgets.Tabulator(
            table_df,
            layout="fit_data",
            pagination="local",
            page_size=15,
            formatters={c: "html" for c in table_df.columns},
            titles=col_titles,
            disabled=True,
            theme=UIStyles.TABLE_THEME,
            css_classes=["holdings-table"],
            show_index=False,
            sizing_mode="stretch_width",
            row_height=55,
            text_align={
                "adj_call_price": "right",
                "current_price": "right",
                "one_yr_move": "right",
                "current_move": "right",
                "portfolio_weight": "right",
                "relative_impact": "right",
                "grade": "center",
            },
        )

        # Filter dropdown
        filter_select = pn.widgets.Select(
            name="",
            options=["All Calls", "BUY Only", "SELL Only"],
            value="All Calls",
            width=130,
            stylesheets=[
                """
                .bk-input {
                    border: 1px solid #86868b !important;
                    border-radius: 6px !important;
                }
                """
            ],
        )

        def on_filter_change(event):
            analysis = self._get_analysis()
            df = analysis["details_df"]
            if event.new == "BUY Only":
                df = df[df["call_type"] == "BUY"]
            elif event.new == "SELL Only":
                df = df[df["call_type"] == "SELL"]

            # Rebuild the formatted table
            filtered_display = df.copy()
            filtered_display["call_date"] = pd.to_datetime(
                filtered_display["call_date"]
            )
            filtered_display["call_type"] = filtered_display["call_type"].apply(
                _fmt_type
            )
            filtered_display["one_yr_move"] = filtered_display["one_yr_move"].apply(
                _fmt_move
            )
            filtered_display["current_move"] = filtered_display["current_move"].apply(
                _fmt_move
            )
            filtered_display["relative_impact"] = filtered_display[
                "relative_impact"
            ].apply(_fmt_impact)
            filtered_display["grade"] = filtered_display["grade"].apply(_fmt_grade)
            filtered_display["call_date"] = filtered_display["call_date"].apply(
                _fmt_date
            )
            filtered_display["adj_call_price"] = filtered_display[
                "adj_call_price"
            ].apply(_fmt_price)
            filtered_display["current_price"] = filtered_display["current_price"].apply(
                _fmt_price
            )
            filtered_display["portfolio_weight"] = filtered_display[
                "portfolio_weight"
            ].apply(lambda v: f"{v:.1f}%")
            table.value = filtered_display[table_cols]

        filter_select.param.watch(on_filter_change, "value")

        header_row = pn.Row(
            pn.pane.HTML(
                """
                <div style="font-size: 0.95rem; font-weight: 700; color: var(--neutral-foreground-rest, #022c22);">Accuracy & Impact Details</div>
                <div style="font-size: 0.78rem; color: var(--neutral-foreground-hint, #64748b);">
                    Detailed logs including sentiment grades and relative impact calculations.
                </div>
                """,
                sizing_mode="stretch_width",
            ),
            pn.Spacer(sizing_mode="stretch_width"),
            filter_select,
            align="center",
            sizing_mode="stretch_width",
        )

        return pn.Column(
            header_row,
            table,
            sizing_mode="stretch_width",
            styles={
                "background": "var(--neutral-fill-layer-rest, rgba(0,0,0,0.015))",
                "border": "1px solid var(--neutral-stroke-divider-rest, #e5e7eb)",
                "border-radius": "12px",
                "padding": "20px",
            },
        )

    # ------------------------------------------------------------------
    # Private – layout assembly
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Build the full Buy/Sell Analysis panel layout."""
        available_fys = self._get_available_fys()
        fy_selector = pn.widgets.Select(
            name="",
            options=available_fys,
            value=self._current_fy,
            width=140,
            stylesheets=[
                """
                .bk-input {
                    border: 1px solid #86868b !important;
                    border-radius: 6px !important;
                }
                """
            ],
        )

        controls_row = pn.Row(
            pn.pane.HTML(
                '<span style="font-size:0.82rem;font-weight:600;'
                'color:var(--neutral-foreground-hint);letter-spacing:0.06em;">'
                "FILTER BY FY</span>",
                margin=(10, 0, 10, 5),
            ),
            fy_selector,
            align="center",
            sizing_mode="stretch_width",
        )

        content_area = pn.Column(sizing_mode="stretch_width")

        def _update_content(fy_label):
            filtered = self._get_filtered_analysis(fy_label)
            kpis = filtered["kpis"]
            details_df = filtered["details_df"]

            # Section header
            section_header = pn.pane.HTML(
                f"""
                <div style="font-size: 1.1rem; font-weight: 700; color: var(--neutral-foreground-rest);">
                    Top-Level Performance KPIs ({fy_label})
                </div>
                <div style="font-size: 0.82rem; color: var(--neutral-foreground-hint); margin-bottom: 4px;">
                    A snapshot of your portfolio attribution and timing accuracy for the selected period.
                </div>
                """,
                sizing_mode="stretch_width",
            )

            kpi_row = self._build_kpi_cards(kpis)
            charts_row = pn.Row(
                self._build_alpha_chart(details_df),
                self._build_scatter_chart(details_df),
                sizing_mode="stretch_width",
                styles={"gap": "20px"},
            )
            details_section = self._build_details_table(details_df)

            # Footer note
            footer_note = pn.pane.HTML(
                """
                <div style="font-size: 0.72rem; color: var(--neutral-foreground-hint); margin-top: -10px; margin-left: 20px;">
                    * Entry Price is adjusted for all stock splits and bonus issues occurring after the call date.
                </div>
                """,
                sizing_mode="stretch_width",
            )

            content_area.objects = [
                section_header,
                kpi_row,
                pn.Spacer(height=10),
                charts_row,
                pn.Spacer(height=10),
                details_section,
                footer_note,
            ]

        # FY selector callback
        def on_fy_change(event):
            self._current_fy = event.new
            _update_content(self._current_fy)

        fy_selector.param.watch(on_fy_change, "value")

        # Initial Load
        _update_content(self._current_fy)

        self.layout.objects = [
            pn.Column(
                controls_row,
                pn.layout.Divider(),
                content_area,
                sizing_mode="stretch_width",
                styles={"gap": "12px"},
            )
        ]
