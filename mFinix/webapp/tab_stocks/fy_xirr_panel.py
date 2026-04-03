"""
FY XIRR Panel.

Renders a panel horizontal bar chart comparing portfolio XIRR vs
benchmark index returns for a user-selected Financial Year.
Embedded directly in the main Stocks tab layout (no modal).
"""

import math
from typing import Any, Optional

import pandas as pd
import panel as pn

from mFinix.core.benchmark_data import (
    BENCHMARK_INDICES,
    fetch_benchmark_fy_returns,
    get_current_fy_label,
)
from mFinix.core.xirr_calculation import calculate_fy_xirr_series
from mFinix.util import log


class FYXirrPanel:
    """Inline panel: FY selector + benchmark bar chart.

    Parameters
    ----------
    tab_data : dict
        Must contain ``transactions_data`` (DataFrame) and
        ``portfolio_value`` (float).
    """

    def __init__(self, tab_data: dict[str, Any]) -> None:
        self.tab_data = tab_data
        self._fy_xirr_series: dict = {}
        self._current_fy = get_current_fy_label()
        self.layout = pn.Column(sizing_mode="stretch_width")
        self._build_layout()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Reset cached data and rebuild layout."""
        self._fy_xirr_series = {}
        self._build_layout()

    # ------------------------------------------------------------------
    # Private – data
    # ------------------------------------------------------------------

    def _get_fy_xirr_series(self) -> dict:
        if not self._fy_xirr_series:
            try:
                self._fy_xirr_series = calculate_fy_xirr_series(
                    self.tab_data.get("transactions_data", pd.DataFrame()),
                    self.tab_data.get("portfolio_value", 0.0),
                )
            except Exception as exc:
                log.error("FY XIRR computation failed: %s", exc)
                self._fy_xirr_series = {}
        return self._fy_xirr_series

    def _get_available_fy_labels(self) -> list[str]:
        return list(reversed(list(self._get_fy_xirr_series().keys())))

    # ------------------------------------------------------------------
    # Private – bar chart objects
    # ------------------------------------------------------------------

    def _build_chart_column(self, fy_label: str) -> pn.Column:
        fy_data: dict = self._get_fy_xirr_series().get(fy_label, {})
        portfolio_xirr: Optional[float] = fy_data.get("xirr")

        try:
            bench_returns = fetch_benchmark_fy_returns(fy_label)
        except Exception as exc:
            log.error("Benchmark fetch failed for %s: %s", fy_label, exc)
            bench_returns = {name: None for name in BENCHMARK_INDICES}

        # Build rows: My XIRR first, then benchmarks sorted by return desc
        rows: list[dict] = [
            {"label": "My XIRR", "value": portfolio_xirr, "is_xirr": True}
        ]
        bench = [
            {"label": name, "value": bench_returns.get(name), "is_xirr": False}
            for name in BENCHMARK_INDICES
        ]
        bench.sort(key=lambda r: (r["value"] is None, -(r["value"] or 0)))
        rows.extend(bench)

        # Max absolute value drives proportional widths.
        vals = [r["value"] for r in rows if r["value"] is not None]
        max_abs = max((abs(v) for v in vals), default=1.0)

        if max_abs <= 10:
            step = 2
        elif max_abs <= 25:
            step = 5
        elif max_abs <= 50:
            step = 10
        elif max_abs <= 100:
            step = 20
        else:
            step = 50

        axis_max = max(math.ceil(max_abs / step) * step, step)

        # Title pane to match the summary boxes
        title_pane = pn.pane.HTML(
            f"""
            <div style="font-size: 0.95rem; font-weight: 700; color: var(--neutral-foreground-rest, #022c22); margin-bottom: 2px;">My XIRR vs Index Return</div>
            <div style="font-size: 0.78rem; font-weight: 600; color: var(--neutral-foreground-hint, #64748b); margin-bottom: 10px; text-transform: uppercase;">{fy_label}</div>
            """
        )

        # Container for all rows
        chart_column = pn.Column(
            title_pane,
            sizing_mode="stretch_width",
            styles={
                "gap": "5px",
                "padding": "5px",
                "background": "var(--neutral-fill-layer-rest, rgba(0,0,0,0.015))",
                "border": "1px solid var(--neutral-stroke-divider-rest, #e5e7eb)",
                "border-radius": "12px",
            },
        )

        for row in rows:
            v = row["value"]
            label = row["label"]
            is_xirr = row["is_xirr"]

            if v is not None:
                width_pct = min((abs(v) / axis_max * 50), 50)
                is_pos = v >= 0
                arrow = "↑" if is_pos else "↓"
                badge_bg = "#16a34a" if is_pos else "#dc2626"
                badge_txt = f"{arrow} {abs(v):.1f}%"
            else:
                width_pct = 0
                is_pos = True
                badge_bg = "#6b7280"
                badge_txt = "N/A"

            # 1. Row Label (Standard Panel HTML Pane with inline styles)
            label_styles = {
                "min-width": "130px",
                "max-width": "130px",
                "font-size": "0.88rem",
                "color": "var(--neutral-foreground-rest)",
                "text-align": "right",
                "line-height": "1.3",
            }
            if is_xirr:
                label_styles["font-weight"] = "700"

            label_pane = pn.pane.HTML(label, styles=label_styles)

            # 2. Row Bar Track (Standard Panel HTML Pane since it requires complex overlapping absolute positioning)
            bar_bg = (
                "linear-gradient(90deg, #14532d 0%, #166534 100%)"
                if is_xirr
                else "linear-gradient(90deg, #5eead4 0%, #99f6e4 100%)"
            )

            bar_pos_styles = (
                f"left: 50%; border-radius: 0 6px 6px 0;"
                if is_pos
                else f"right: 50%; border-radius: 6px 0 0 6px;"
            )
            badge_pos_styles = (
                f"left: 100%; margin-left: 8px;"
                if is_pos
                else f"right: 100%; margin-right: 8px;"
            )

            track_html = f"""
            <div style="position: relative; width: calc(100% - 120px); min-height: 36px; margin: 0 60px;">
                <div style="position: absolute; left: 50%; top: -4px; bottom: -4px; width: 1px; background-color: var(--neutral-stroke-divider-rest); z-index: 1;"></div>
                <div style="height: 34px; position: absolute; top: 1px; width: {width_pct:.1f}%; {bar_pos_styles} background: {bar_bg}; z-index: 2; transition: width 0.4s ease; min-width: 2px;">
                    <span style="position: absolute; top: 50%; transform: translateY(-50%); white-space: nowrap; font-size: 0.78rem; font-weight: 700; padding: 3px 8px; border-radius: 6px; color: #fff; min-width: 60px; text-align: center; background-color: {badge_bg}; {badge_pos_styles}">{badge_txt}</span>
                </div>
            </div>
            """
            track_pane = pn.pane.HTML(track_html, sizing_mode="stretch_width")

            # Combine into a Standard Panel Row
            row_layout = pn.Row(
                label_pane,
                track_pane,
                align="center",
                sizing_mode="stretch_width",
            )
            chart_column.append(row_layout)

        # 3. Add X-axis row at the bottom
        axis_html = f"""
        <div style="position: relative; width: calc(100% - 120px); min-height: 24px; margin: 0 60px; border-top: 1px solid var(--neutral-stroke-divider-rest);">
            <div style="position: absolute; top: 6px; transform: translateX(-50%); font-size: 0.72rem; color: var(--neutral-foreground-hint); left: 0%;">-{axis_max}%</div>
            <div style="position: absolute; top: 6px; transform: translateX(-50%); font-size: 0.72rem; color: var(--neutral-foreground-hint); left: 25%;">-{axis_max/2:g}%</div>
            <div style="position: absolute; top: 6px; transform: translateX(-50%); font-size: 0.72rem; color: var(--neutral-foreground-hint); left: 50%;">0%</div>
            <div style="position: absolute; top: 6px; transform: translateX(-50%); font-size: 0.72rem; color: var(--neutral-foreground-hint); left: 75%;">{axis_max/2:g}%</div>
            <div style="position: absolute; top: 6px; transform: translateX(-50%); font-size: 0.72rem; color: var(--neutral-foreground-hint); left: 100%;">{axis_max}%</div>
        </div>
        """

        # Standard Panel spacer to offset the 130px label width on the left
        axis_row = pn.Row(
            pn.Spacer(width=130),
            pn.pane.HTML(axis_html, sizing_mode="stretch_width"),
            align="center",
            styles={"gap": "5px", "margin-top": "2px"},
            sizing_mode="stretch_width",
        )
        chart_column.append(axis_row)

        return chart_column

    def _build_summary_boxes(self, fy_data: dict) -> pn.Column:
        total_buy = fy_data.get("total_buy", 0.0)
        total_sell = fy_data.get("total_sell", 0.0)
        start_val = fy_data.get("start_value", 0.0)
        end_val = fy_data.get("end_value", 0.0)

        def _fmt(v):
            if v >= 10000000:
                return f"₹ {v/10000000:.2f} Cr"
            elif v >= 100000:
                return f"₹ {v/100000:.1f}L"
            else:
                return f"₹ {v:,.0f}"

        max_tx = max(total_buy, total_sell) if max(total_buy, total_sell) > 0 else 1.0
        buy_pct = min((total_buy / max_tx) * 100, 100)
        sell_pct = min((total_sell / max_tx) * 100, 100)

        net_flow = total_buy - total_sell
        net_color = "#16a34a" if net_flow >= 0 else "#dc2626"
        net_sign = "+" if net_flow >= 0 else "-"
        net_label = "Net Investment" if net_flow >= 0 else "Net Withdrawal"

        tx_html = f"""
        <div style="background: var(--neutral-fill-layer-rest, rgba(0,0,0,0.015)); border: 1px solid var(--neutral-stroke-divider-rest, #e5e7eb); border-radius: 12px; padding: 20px; width: 100%; box-sizing: border-box; height: 100%; font-family: 'Inter', sans-serif; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.72rem; font-weight: 700; color: var(--neutral-foreground-hint, #64748b); margin-bottom: 6px; text-transform: uppercase;">
                    <span>Total Buy Value</span>
                    <span style="color: var(--neutral-foreground-rest, #022c22); font-weight: 800;">{_fmt(total_buy)}</span>
                </div>
                <div style="height: 10px; background: var(--neutral-stroke-divider-rest, #f1f5f9); border-radius: 5px; margin-bottom: 18px; overflow: hidden;">
                    <div style="height: 100%; width: {buy_pct}%; background: #064e3b; border-radius: 5px; transition: width 0.5s ease;"></div>
                </div>
                
                <div style="display: flex; justify-content: space-between; font-size: 0.72rem; font-weight: 700; color: var(--neutral-foreground-hint, #64748b); margin-bottom: 6px; text-transform: uppercase;">
                    <span>Total Sell Value</span>
                    <span style="color: var(--neutral-foreground-rest, #334155); font-weight: 800;">{_fmt(total_sell)}</span>
                </div>
                <div style="height: 10px; background: var(--neutral-stroke-divider-rest, #f1f5f9); border-radius: 5px; margin-bottom: 12px; overflow: hidden;">
                    <div style="height: 100%; width: {sell_pct}%; background: #64748b; border-radius: 5px; transition: width 0.5s ease;"></div>
                </div>
            </div>
            
            <div style="display: flex; align-items: baseline; gap: 8px; margin-top: 12px;">
                <span style="color: {net_color}; font-size: 1.15rem; font-weight: 800;">{net_sign}{_fmt(abs(net_flow))}</span>
                <span style="color: var(--neutral-foreground-hint, #64748b); font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">{net_label}</span>
            </div>
        </div>
        """

        max_port = max(start_val, end_val) if max(start_val, end_val) > 0 else 1.0
        start_pct = min((start_val / max_port) * 100, 100)
        end_pct = min((end_val / max_port) * 100, 100)

        abs_gain = end_val - start_val

        gain_color = "#16a34a" if abs_gain >= 0 else "#dc2626"
        gain_sign = "+" if abs_gain >= 0 else "-"

        port_html = f"""
        <div style="background: var(--neutral-fill-layer-rest, rgba(0,0,0,0.015)); border: 1px solid var(--neutral-stroke-divider-rest, #e5e7eb); border-radius: 12px; padding: 20px; width: 100%; box-sizing: border-box; height: 100%; font-family: 'Inter', sans-serif; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.72rem; font-weight: 700; color: var(--neutral-foreground-hint, #64748b); margin-bottom: 6px; text-transform: uppercase;">
                    <span>Start Value</span>
                    <span style="color: var(--neutral-foreground-rest, #334155); font-weight: 800;">{_fmt(start_val)}</span>
                </div>
                <div style="height: 10px; background: var(--neutral-stroke-divider-rest, #f1f5f9); border-radius: 5px; margin-bottom: 18px; overflow: hidden;">
                    <div style="height: 100%; width: {start_pct}%; background: #94a3b8; border-radius: 5px; transition: width 0.5s ease;"></div>
                </div>
                
                <div style="display: flex; justify-content: space-between; font-size: 0.72rem; font-weight: 700; color: var(--neutral-foreground-hint, #64748b); margin-bottom: 6px; text-transform: uppercase;">
                    <span>End Value</span>
                    <span style="color: var(--neutral-foreground-rest, #022c22); font-weight: 800;">{_fmt(end_val)}</span>
                </div>
                <div style="height: 10px; background: var(--neutral-stroke-divider-rest, #f1f5f9); border-radius: 5px; margin-bottom: 12px; overflow: hidden;">
                    <div style="height: 100%; width: {end_pct}%; background: #064e3b; border-radius: 5px; transition: width 0.5s ease;"></div>
                </div>
            </div>

            <div style="display: flex; align-items: baseline; gap: 8px; margin-top: 12px;">
                <span style="color: {gain_color}; font-size: 1.15rem; font-weight: 800;">{gain_sign}{_fmt(abs(abs_gain))}</span>
                <span style="color: var(--neutral-foreground-hint, #64748b); font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">Absolute Gain</span>
            </div>
        </div>
        """

        return pn.Column(
            pn.pane.HTML(tx_html, sizing_mode="stretch_width", margin=(0, 0, 16, 0)),
            pn.pane.HTML(port_html, sizing_mode="stretch_width", margin=0),
            sizing_mode="fixed",
            width=280,
        )

    # ------------------------------------------------------------------
    # Private – layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        available_fys = self._get_available_fy_labels()
        if not available_fys:
            self.layout.objects = [
                pn.pane.HTML(
                    '<div style="padding:24px 0;color:var(--neutral-foreground-hint);">'
                    "No FY data. Please ensure transactions data is loaded.</div>"
                )
            ]
            return

        default_fy = available_fys[0]

        # ---- FY selector in a compact right-aligned row ----
        fy_selector = pn.widgets.Select(
            name="",
            options=available_fys,
            value=default_fy,
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
                "SELECT FY</span>",
                margin=(10, 0, 10, 5),
            ),
            fy_selector,
            align="center",
            styles={"justify-content": "flex-start"},
            sizing_mode="stretch_width",
        )

        # ---- Chart and Summary Area ----
        default_fy_data = self._get_fy_xirr_series().get(default_fy, {})
        chart_area = pn.Row(
            pn.Column(
                self._build_chart_column(default_fy),
                sizing_mode="stretch_width",
                min_width=400,
            ),
            self._build_summary_boxes(default_fy_data),
            sizing_mode="stretch_width",
            styles={
                "gap": "24px",
                "align-items": "stretch",
                "flex-wrap": "wrap",
                "margin-top": "8px",
            },
        )

        # ---- FY selector callback ----
        def on_fy_change(event):
            fy = event.new
            fy_data = self._get_fy_xirr_series().get(fy, {})
            chart_area.objects = [
                pn.Column(
                    self._build_chart_column(fy),
                    sizing_mode="stretch_width",
                    min_width=400,
                ),
                self._build_summary_boxes(fy_data),
            ]

        fy_selector.param.watch(on_fy_change, "value")

        # ---- Assemble natively using a standard Panel Column ----
        self.layout.objects = [
            pn.Column(
                controls_row,
                chart_area,
                styles={"padding": "4px 0"},
                sizing_mode="stretch_width",
            )
        ]
