"""
Auto Corporate Actions Manager for the Stocks tab.
"""

from datetime import date

import pandas as pd
import panel as pn

import mFinix.webapp.webapp_constants as webapp_const
from mFinix.core.corporate_actions import (
    delete_all_corporate_actions_data,
    fetch_pending_corporate_actions,
    get_last_corporate_actions_update_date,
    save_approved_action,
)
from mFinix.util import log
from mFinix.webapp.tab_stocks.utility import run_once


class AutoCorporateActionsManager:
    """Manager for the Auto Corporate Actions review workflow.

    Fetches pending corporate actions for preview and allows the user
    to approve or reject each action before saving to disk.

    Parameters
    ----------
    data_dict : dict
        Shared data dictionary from the stocks tab (contains transactions_data).
    widgets : dict
        Shared widgets dictionary for the stocks tab.
    """

    # Column keys for the preview table
    _TABLE_COLUMNS = ["Stock", "Type", "Date", "Details", "Quantity"]

    def __init__(self, data_dict: dict, widgets: dict) -> None:
        self.data_dict = data_dict
        self.transactions_data = self.data_dict["transactions_data"]
        self.widgets = widgets.get("auto_corp_wids", {})
        widgets["auto_corp_wids"] = self.widgets

        # Internal state
        self._pending_actions: list[dict] = []
        self._layout = pn.Column(pn.Spacer(height=300))
        self._initialized = False

    @run_once
    def initialize(self) -> None:
        """Initialize all widgets and callbacks (called once)."""
        self._create_widgets()
        self._add_callbacks()
        log.info("AutoCorporateActionsManager initialized")

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
            styles={
                "color": "var(--neutral-foreground-hint)",
                "font-size": "0.8rem",
                "margin-top": "-5px",
            },
        )

        self.widgets["fetch_button"] = pn.widgets.Button(
            name="🔄 Fetch Actions",
            button_type="primary",
            width=200,
        )

        # --- Preview table ---
        self.widgets["preview_table"] = pn.widgets.Tabulator(
            pd.DataFrame(columns=self._TABLE_COLUMNS),
            show_index=False,
            layout="fit_data",
            disabled=True,
            sizing_mode="stretch_width",
            buttons={"approve": "✅", "reject": "❌"},
            theme=webapp_const.UIStyles.TABLE_THEME,
            row_height=webapp_const.UIStyles.TABLE_ROW_HEIGHT,
            page_size=20,
            pagination="local",
        )

        # --- Bulk action buttons ---
        self.widgets["approve_all_btn"] = pn.widgets.Button(
            name="✅ Approve All",
            button_type="success",
            width=150,
            visible=False,
        )
        self.widgets["reject_all_btn"] = pn.widgets.Button(
            name="❌ Reject All",
            button_type="danger",
            width=150,
            visible=False,
        )

        # --- Loading indicator ---
        self.widgets["loading_spinner"] = pn.indicators.LoadingSpinner(
            value=False,
            size=30,
            color="primary",
        )

        # --- Status text ---
        self.widgets["status_text"] = pn.pane.Markdown(
            "",
            styles={"color": "var(--neutral-foreground-hint)", "font-size": "0.9rem"},
        )

    def _add_callbacks(self) -> None:
        """Attach callbacks to widgets."""
        self.widgets["source_radio"].param.watch(self._on_source_change, "value")
        self.widgets["fetch_button"].on_click(self._on_fetch_click)
        self.widgets["preview_table"].on_click(self._on_table_click)
        self.widgets["approve_all_btn"].on_click(self._on_approve_all)
        self.widgets["reject_all_btn"].on_click(self._on_reject_all)

    @property
    def layout(self) -> list:
        """Return the layout components for the stocks tab."""
        return [
            pn.Column(
                pn.pane.Markdown(
                    "### ⚡ Auto Corporate Actions",
                    styles={
                        "font-size": "1.2rem",
                        "font-weight": "600",
                        "color": "#2c3e50",
                    },
                ),
                pn.pane.Markdown(
                    "Fetch and review corporate actions before applying them to your portfolio.",
                    styles={
                        "color": "var(--neutral-foreground-hint)",
                        "font-size": "0.9rem",
                        "margin-bottom": "10px",
                    },
                ),
                # Source selection
                pn.Row(
                    pn.Column(
                        pn.pane.Markdown(
                            "**Fetch Mode:**",
                            styles={"margin-bottom": "5px"},
                        ),
                        self.widgets["source_radio"],
                        self.widgets["last_update_text"],
                        self.widgets["custom_date_picker"],
                        margin=(0, 20, 0, 0),
                    ),
                    pn.Column(
                        pn.Spacer(height=20),
                        self.widgets["fetch_button"],
                        self.widgets["loading_spinner"],
                    ),
                    sizing_mode="stretch_width",
                    styles={"align-items": "flex-end"},
                ),
                pn.layout.Divider(),
                # Status and table
                self.widgets["status_text"],
                self.widgets["preview_table"],
                # Bulk actions
                pn.Row(
                    self.widgets["approve_all_btn"],
                    self.widgets["reject_all_btn"],
                    sizing_mode="stretch_width",
                    styles={
                        "justify-content": "flex-end",
                        "gap": "10px",
                        "margin-top": "10px",
                    },
                ),
                styles=webapp_const.UIStyles.CARD_STYLE,
            )
        ]

    # ========================================================================
    # Callbacks
    # ========================================================================

    def _on_source_change(self, event) -> None:
        """Show/hide the custom date picker based on radio selection."""
        self.widgets["custom_date_picker"].visible = event.new == "From Selected Date"

    def _on_fetch_click(self, _) -> None:
        """Fetch pending corporate actions and populate the preview table."""
        self.widgets["loading_spinner"].value = True
        self.widgets["fetch_button"].disabled = True
        self.widgets["status_text"].object = (
            "*Fetching corporate actions... This may take a moment.*"
        )

        try:
            # Determine from_date
            from_date = None
            if self.widgets["source_radio"].value == "From Selected Date":
                from_date = self.widgets["custom_date_picker"].value
                # Backup and delete existing data
                backup_path = delete_all_corporate_actions_data()
                pn.state.notifications.info(
                    f"Existing data backed up to {backup_path.name}"
                )

            # Fetch pending actions
            self._pending_actions = fetch_pending_corporate_actions(
                self.transactions_data, from_date
            )

            if not self._pending_actions:
                self.widgets["status_text"].object = (
                    "**No new corporate actions found.**"
                )
                self.widgets["preview_table"].value = pd.DataFrame(
                    columns=self._TABLE_COLUMNS
                )
                self._toggle_bulk_buttons(False)
                pn.state.notifications.info("No new corporate actions detected.")
            else:
                self._refresh_table()
                self.widgets["status_text"].object = (
                    f"**Found {len(self._pending_actions)} pending action(s).** "
                    "Click ✅ to approve or ❌ to reject each action."
                )
                self._toggle_bulk_buttons(True)
                pn.state.notifications.success(
                    f"Found {len(self._pending_actions)} pending corporate action(s)."
                )

        except Exception as e:
            log.error("Error fetching corporate actions: %s", e)
            self.widgets["status_text"].object = f"**Error:** {str(e)}"
            pn.state.notifications.error(f"Error fetching actions: {str(e)}")
        finally:
            self.widgets["loading_spinner"].value = False
            self.widgets["fetch_button"].disabled = False

    def _on_table_click(self, event) -> None:
        """Handle approve/reject button clicks in the preview table."""
        row_idx = event.row

        if row_idx >= len(self._pending_actions):
            return

        if event.column == "approve":
            self._approve_action(row_idx)
        elif event.column == "reject":
            self._reject_action(row_idx)

    def _on_approve_all(self, _) -> None:
        """Approve all remaining pending actions."""
        if not self._pending_actions:
            pn.state.notifications.info("No pending actions to approve.")
            return

        count = len(self._pending_actions)
        # Process in reverse to avoid index shifting
        for action in list(self._pending_actions):
            try:
                save_approved_action(action)
            except Exception as e:
                log.error(
                    "Failed to approve %s for %s: %s",
                    action["action_type"],
                    action["stock"],
                    e,
                )

        self._pending_actions.clear()
        self._refresh_table()
        self._refresh_last_update_date()
        self._toggle_bulk_buttons(False)
        self.widgets["status_text"].object = (
            f"**All {count} action(s) approved and saved.** ✅"
        )
        pn.state.notifications.success(f"All {count} action(s) approved and saved.")

    def _on_reject_all(self, _) -> None:
        """Reject all remaining pending actions."""
        count = len(self._pending_actions)
        self._pending_actions.clear()
        self._refresh_table()
        self._toggle_bulk_buttons(False)
        self.widgets["status_text"].object = f"**All {count} action(s) rejected.** ❌"
        pn.state.notifications.warning(f"All {count} action(s) rejected.")

    # ========================================================================
    # Private helpers
    # ========================================================================

    def _approve_action(self, idx: int) -> None:
        """Approve and save a single action by index."""
        action = self._pending_actions[idx]
        try:
            save_approved_action(action)
            stock = action["stock"]
            action_type = action["action_type"]
            self._pending_actions.pop(idx)
            self._refresh_table()
            self._refresh_last_update_date()
            self._update_bulk_visibility()
            pn.state.notifications.success(f"Approved {action_type} for {stock}")
            log.info("Approved %s for %s", action_type, stock)
        except Exception as e:
            log.error("Failed to save action: %s", e)
            pn.state.notifications.error(f"Failed to save: {str(e)}")

    def _reject_action(self, idx: int) -> None:
        """Reject (discard) a single action by index."""
        action = self._pending_actions[idx]
        stock = action["stock"]
        action_type = action["action_type"]
        self._pending_actions.pop(idx)
        self._refresh_table()
        self._update_bulk_visibility()
        pn.state.notifications.warning(f"Rejected {action_type} for {stock}")
        log.info("Rejected %s for %s", action_type, stock)

    def _refresh_table(self) -> None:
        """Rebuild the preview table from pending actions."""
        if not self._pending_actions:
            self.widgets["preview_table"].value = pd.DataFrame(
                columns=self._TABLE_COLUMNS
            )
            return

        rows = []
        for action in self._pending_actions:
            dt = action["date"]
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
            rows.append(
                {
                    "Stock": action["stock"],
                    "Type": action["action_type"].capitalize(),
                    "Date": date_str,
                    "Details": action["details"],
                    "Quantity": action["quantity"],
                }
            )

        self.widgets["preview_table"].value = pd.DataFrame(rows)

    def _refresh_last_update_date(self) -> None:
        """Update the 'Last Updated' label with the current value from disk."""
        last_update = get_last_corporate_actions_update_date()
        self.widgets["last_update_text"].object = (
            f"*Last Updated: {last_update.strftime('%d-%b-%Y')}*"
        )

    def _toggle_bulk_buttons(self, visible: bool) -> None:
        """Show or hide the bulk action buttons."""
        self.widgets["approve_all_btn"].visible = visible
        self.widgets["reject_all_btn"].visible = visible

    def _update_bulk_visibility(self) -> None:
        """Update bulk button visibility based on remaining actions."""
        has_actions = len(self._pending_actions) > 0
        self._toggle_bulk_buttons(has_actions)
        if not has_actions:
            self.widgets["status_text"].object = "**All actions processed.** ✅"
