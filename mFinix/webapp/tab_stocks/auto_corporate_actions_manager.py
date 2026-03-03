"""
Auto Corporate Actions Manager for the Stocks tab.
"""

from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd
import panel as pn

import mFinix.constants.columns as col
import mFinix.constants.constants as const
import mFinix.webapp.webapp_constants as webapp_const
from mFinix.core.corporate_actions import (
    delete_all_corporate_actions_data,
    fetch_pending_corporate_actions_progressive,
    get_last_corporate_actions_update_date,
    save_approved_action,
)
from mFinix.util import log
from mFinix.webapp.components.progress_logger import ProgressLogger
from mFinix.webapp.components.wizard_step_header import WizardStepHeader
from mFinix.webapp.tab_stocks.corporate_events_manager.demerger_inputs_manager import (
    DemergerInputsManager,
)
from mFinix.webapp.tab_stocks.utility import run_once

# ---------------------------------------------------------------------------
# Action-type display metadata
# ---------------------------------------------------------------------------

_ACTION_TABS: List[Dict] = [
    {"key": const.DEMERGER, "label": "Demerger", "color": "#f39c12"},
    {"key": const.MERGER, "label": "Merger", "color": "#8e44ad"},
    {"key": const.STOCK_SPLIT, "label": "Split", "color": "#2980b9"},
    {"key": const.BONUS, "label": "Bonus", "color": "#27ae60"},
    {"key": const.DIVIDEND, "label": "Dividend", "color": "#16a085"},
    {"key": const.BUYBACK, "label": "Buyback", "color": "#c0392b"},
]

# Columns shown in each per-type Tabulator
_TABLE_COLUMNS = ["Stock", "Type", "Date", "Details", "Quantity"]


class AutoCorporateActionsManager:
    """Manager for the Auto Corporate Actions review workflow.

    Fetches pending corporate actions progressively and presents them in a
    wizard interface (WizardStepHeader). Allows per-row and bulk approval/rejection.
    """

    def __init__(self, data_dict: dict, widgets: dict, panel_modal=None) -> None:
        self.data_dict = data_dict
        self.transactions_data = self.data_dict["transactions_data"]
        self.widgets = widgets.get("auto_corp_wids", {})
        widgets["auto_corp_wids"] = self.widgets
        self.panel_modal = panel_modal

        # Internal state
        self._pending_actions: List[Dict] = []
        self._current_step = 0
        self._steps = []

        # Components
        self.wizard_header = WizardStepHeader(steps=[], active_step=0)
        self.progress_logger = ProgressLogger()
        self.progress_logger_pane = pn.Column(
            pn.pane.Markdown("### 🔍 Fetching Corporate Actions..."),
            self.progress_logger,
            visible=False,
            sizing_mode="stretch_width",
        )

        # UI Layout areas
        self._content_area = pn.Column(sizing_mode="stretch_width")
        self._nav_area = pn.Row(sizing_mode="stretch_width")

        self._layout = pn.Column(
            self.wizard_header,
            self.progress_logger_pane,
            self._content_area,
            pn.layout.Divider(),
            self._nav_area,
            sizing_mode="stretch_width",
        )

    @run_once
    def initialize(self) -> None:
        """Initialize all widgets and callbacks (called once)."""
        self._create_widgets()
        self._add_callbacks()
        log.info("AutoCorporateActionsManager initialized")

    def _add_callbacks(self) -> None:
        """Connect all widget callbacks."""
        self.widgets["fetch_button"].on_click(self._on_fetch_click)
        self.widgets["source_radio"].param.watch(self._on_source_change, "value")

    def _create_widgets(self) -> None:
        """Create all UI widgets for the auto corporate actions flow."""

        # --- Source selection ---
        self.widgets["source_radio"] = pn.widgets.RadioButtonGroup(
            name="Fetch Mode",
            options=["From Last Date", "From Selected Date"],
            value="From Last Date",
            button_type="primary",
            button_style="outline",
        )

        self.widgets["custom_date_picker"] = pn.widgets.DatePicker(
            name="Select Date",
            value=date.today(),
            end=date.today(),
            visible=False,
            styles={"font-weight": "bold !important"},
        )

        last_update = get_last_corporate_actions_update_date()
        self.widgets["last_update_text"] = pn.pane.Markdown(
            f"*Last Updated: {last_update.strftime('%d-%b-%Y')}*",
            styles={"color": "#7f8c8d", "font-size": "0.85rem"},
        )

        self.widgets["fetch_button"] = pn.widgets.Button(
            name="Fetch Actions",
            button_type="primary",
            width=140,
            styles={"font-weight": "bold"},
        )

        self.widgets["status_text"] = pn.pane.Markdown(
            "", sizing_mode="stretch_width", margin=(10, 0)
        )

    @property
    def layout(self) -> list:
        """Return the main layout container."""
        self._fetch_row = pn.Row(
            pn.Column(
                self.widgets["source_radio"],
                self.widgets["last_update_text"],
                self.widgets["custom_date_picker"],
                margin=(0, 20, 0, 0),
            ),
            pn.Column(
                pn.Spacer(height=20),
                self.widgets["fetch_button"],
            ),
            sizing_mode="stretch_width",
            styles={"align-items": "flex-end"},
            name="fetch_row",
        )
        return [
            pn.Column(
                # Fetch controls container
                self._fetch_row,
                pn.layout.Divider(),
                self.widgets["status_text"],
                self._layout,
                sizing_mode="stretch_width",
            )
        ]

    # =========================================================================
    # Callbacks
    # =========================================================================

    def _on_source_change(self, event) -> None:
        """Show/hide the custom date picker based on selection."""
        self.widgets["custom_date_picker"].visible = event.new == "From Selected Date"

    def _on_fetch_click(self, event) -> None:
        """Execute progressive fetch and update the UI logger."""
        self.widgets["fetch_button"].disabled = True
        self.widgets["status_text"].object = ""

        # Hide the fetch row during processing
        fetch_row = self._fetch_row
        fetch_row.visible = False

        self.progress_logger_pane.visible = True
        self.progress_logger.clear()
        self.progress_logger.log("🔍 Initializing fetch...", "info")

        from_date = None
        if self.widgets["source_radio"].value == "From Selected Date":
            from_date = self.widgets["custom_date_picker"].value
            delete_all_corporate_actions_data()

        generator = fetch_pending_corporate_actions_progressive(
            self.transactions_data, from_date
        )

        def _fetch_step():
            try:
                update = next(generator)
                if "data" in update:
                    self._pending_actions = update["data"]
                    self.progress_logger.complete("Fetching complete!")

                    if not self._pending_actions:
                        self.widgets["status_text"].object = (
                            "**No pending actions found.**"
                        )
                        self.progress_logger_pane.visible = False
                        fetch_row.visible = True
                        self.widgets["fetch_button"].disabled = False
                    else:
                        pn.state.add_periodic_callback(
                            self._start_wizard, period=500, count=1
                        )
                else:
                    self.progress_logger.log(update["status"], "info")
                    pn.state.add_periodic_callback(_fetch_step, period=50, count=1)
            except StopIteration:
                pass
            except Exception as e:
                log.error("Fetch failed: %s", e)
                self.progress_logger.error(f"Error: {str(e)}")
                self.widgets["fetch_button"].disabled = False
                fetch_row.visible = True

        pn.state.add_periodic_callback(_fetch_step, period=50, count=1)

    def _start_wizard(self) -> None:
        """Analyze results and initialize wizard steps."""
        self.progress_logger_pane.visible = False

        by_type = {}
        for a in self._pending_actions:
            by_type.setdefault(a["action_type"], []).append(a)

        self._steps = [meta for meta in _ACTION_TABS if meta["key"] in by_type]

        if not self._steps:
            self.widgets["status_text"].object = "**No actions to review.**"
            return

        self.wizard_header.steps = [s["label"] for s in self._steps]
        self.wizard_header.visible = True
        self._current_step = 0
        self._render_step()

    def _render_step(self) -> None:
        """Render the current step based on _current_step index."""
        self.wizard_header.active_step = self._current_step
        step_meta = self._steps[self._current_step]
        action_type = step_meta["key"]

        actions = [a for a in self._pending_actions if a["action_type"] == action_type]

        df_rows = []
        for action in actions:
            dt = action["date"]
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            df_rows.append(
                {
                    "Stock": action["stock"],
                    "Type": action["action_type"].capitalize(),
                    "Date": date_str,
                    "Details": str(action.get("details", "")).replace("₹", "Rs."),
                    "Quantity": action.get("quantity", 0),
                }
            )

        is_demerger = action_type == const.DEMERGER
        if is_demerger:
            table_buttons = {"add": "➕"}
        else:
            table_buttons = {"approve": "✅", "reject": "❌"}

        table = pn.widgets.Tabulator(
            pd.DataFrame(df_rows),
            show_index=False,
            layout="fit_data",
            disabled=True,
            sizing_mode="stretch_width",
            buttons=table_buttons,
            theme=webapp_const.UIStyles.TABLE_THEME,
            row_height=webapp_const.UIStyles.TABLE_ROW_HEIGHT,
            page_size=20,
            pagination="local",
        )
        table.on_click(self._make_table_click_cb(action_type, actions))

        approve_all_btn = pn.widgets.Button(
            name="✅ Approve All", button_type="success", width=140
        )
        reject_all_btn = pn.widgets.Button(
            name="❌ Reject All", button_type="danger", width=140
        )

        approve_all_btn.on_click(self._make_approve_all_cb(action_type, actions))
        reject_all_btn.on_click(self._make_reject_all_cb(action_type, actions))

        self._content_area.objects = [
            pn.pane.Markdown(f"### {step_meta['label']}"),
            table,
            pn.Row(
                approve_all_btn,
                reject_all_btn,
                sizing_mode="stretch_width",
                visible=not is_demerger,
                styles={
                    "justify-content": "flex-end",
                    "gap": "10px",
                    "margin-top": "10px",
                },
            ),
        ]

        # Navigation
        nav_buttons = []
        if self._current_step > 0:
            prev_btn = pn.widgets.Button(name="Back", button_type="default", width=100)
            prev_btn.on_click(self._prev_step)
            nav_buttons.append(prev_btn)

        nav_buttons.append(pn.Spacer(sizing_mode="stretch_width"))

        if self._current_step < len(self._steps) - 1:
            next_btn = pn.widgets.Button(name="Next", button_type="primary", width=100)
            next_btn.on_click(self._next_step)
            nav_buttons.append(next_btn)
        else:
            finish_btn = pn.widgets.Button(
                name="Finish", button_type="success", width=100
            )
            finish_btn.on_click(self._on_finish)
            nav_buttons.append(finish_btn)

        self._nav_area.objects = nav_buttons

    def _next_step(self, _) -> None:
        self._current_step += 1
        self._render_step()

    def _prev_step(self, _) -> None:
        self._current_step -= 1
        self._render_step()

    def _on_finish(self, _) -> None:
        if self.panel_modal:
            self.panel_modal.close()
        pn.state.notifications.success("Corporate actions review completed.")

    # =========================================================================
    # Interaction Logic
    # =========================================================================

    def _make_table_click_cb(self, action_type: str, actions: List[Dict]):
        def _cb(event):
            if event.row >= len(actions):
                return
            action = actions[event.row]
            if event.column == "add" and action_type == const.DEMERGER:
                self._open_demerger_modal(action)
            elif event.column == "approve":
                self._approve_single(action)
            elif event.column == "reject":
                self._reject_single(action)

        return _cb

    def _open_demerger_modal(self, action: Dict):
        """Transition to the Add Demerger Details sub-modal."""
        if self.panel_modal is None:
            return

        # Fresh widget dict for this modal instance to avoid callback accumulation
        event_widgets = {}
        event_widgets["submit_button"] = pn.widgets.Button(
            name="✅ Submit", button_type="success", width=140
        )

        # Layout container for the manager to inject into
        temp_layout = pn.Column(sizing_mode="stretch_width")

        mgr = DemergerInputsManager(
            transactions_data=self.transactions_data,
            holdings_data=self.data_dict["equity_holdings"],
            widgets=event_widgets,
            layout=temp_layout,
        )

        # Pre-fill available values from the pending action
        stock = action.get("stock")
        if stock:
            mgr.widgets["stock_select"].value = stock

        action_date = action.get("date")
        if action_date is not None:
            # Handle Timestamp objects from pandas
            if hasattr(action_date, "date"):
                action_date = action_date.date()
            mgr.widgets["transactions_date_select"].value = action_date

        # Render the demerger form
        mgr.show_layout()

        # Wire submit: save demerger data then remove from pending list
        def _on_submit(_):
            mgr.process_submission()
            self._on_demerger_submitted(action)

        event_widgets["submit_button"].on_click(_on_submit)

        self.panel_modal.open(
            content=[temp_layout],
            title="Add Demerger Details",
            back_cb=self._reopen_self,
        )

    def _reopen_self(self) -> None:
        """Used as back callback from sub-modals."""
        if self.panel_modal:
            self._render_step()
            self.panel_modal.open(self.layout, "⚡ Auto Corporate Actions")

    def _on_demerger_submitted(self, action: Dict) -> None:
        """Remove demerger from list and refresh."""
        if action in self._pending_actions:
            self._pending_actions.remove(action)
        self._render_step()
        self._refresh_last_update_date()

    def _make_approve_all_cb(self, action_type: str, actions: List[Dict]):
        def _cb(_):
            count = 0
            for action in list(actions):
                try:
                    save_approved_action(action)
                    self._pending_actions.remove(action)
                    count += 1
                except Exception as e:
                    log.error("Failed to approve %s: %s", action_type, e)
            self._render_step()
            self._refresh_last_update_date()
            pn.state.notifications.success(f"Approved {count} {action_type} action(s).")

        return _cb

    def _make_reject_all_cb(self, action_type: str, actions: List[Dict]):
        def _cb(_):
            count = 0
            for action in list(actions):
                if action in self._pending_actions:
                    self._pending_actions.remove(action)
                    count += 1
            self._render_step()
            pn.state.notifications.warning(f"Rejected {count} {action_type} action(s).")

        return _cb

    def _approve_single(self, action: Dict) -> None:
        try:
            save_approved_action(action)
            if action in self._pending_actions:
                self._pending_actions.remove(action)
            self._render_step()
            self._refresh_last_update_date()
            pn.state.notifications.success(
                f"Approved {action['action_type']} for {action['stock']}"
            )
        except Exception as e:
            log.error("Approval failed: %s", e)
            pn.state.notifications.error(f"Approval failed: {e}")

    def _reject_single(self, action: Dict) -> None:
        if action in self._pending_actions:
            self._pending_actions.remove(action)
        self._render_step()
        pn.state.notifications.warning(
            f"Rejected {action['action_type']} for {action['stock']}"
        )

    def _refresh_last_update_date(self) -> None:
        """Update the label from disk."""
        last_update = get_last_corporate_actions_update_date()
        self.widgets["last_update_text"].object = (
            f"*Last Updated: {last_update.strftime('%d-%b-%Y')}*"
        )
