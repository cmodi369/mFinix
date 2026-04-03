import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import panel as pn
import param

import mFinix.constants.columns as col
import mFinix.constants.constants as const
import mFinix.core.read_kite_data as rkd
from mFinix.core.master_source_data_manager import MasterSourceDataManager
from mFinix.util import log
from mFinix.webapp.components.progress_logger import ProgressLogger
from mFinix.webapp.components.wizard_step_header import WizardStepHeader
from mFinix.webapp.tab_stocks.utility import (
    prepare_stocks_tab_data_progressive,
    run_once,
)


class ManualDataFetchManager:
    def __init__(
        self, tab_data: dict, tab_widgets: dict, refresh_cb: callable, panel_modal=None
    ):
        self.tab_data = tab_data
        self.tab_widgets = tab_widgets
        self.refresh_cb = refresh_cb
        self.panel_modal = panel_modal

        # Components
        self.data_manager = MasterSourceDataManager()
        self.wizard_header = WizardStepHeader(
            steps=["Holdings", "Ledger", "Tradebook"], active_step=0
        )
        self.progress_logger = ProgressLogger()
        self.progress_logger_pane = pn.Column(
            pn.pane.Markdown("### Processing Data"),
            self.progress_logger,
            visible=False,
            sizing_mode="stretch_width",
        )

        self.step_content = pn.Column(sizing_mode="stretch_width")
        self.navigation_row = pn.Row(sizing_mode="stretch_width")

        # UI State
        self.current_step = 0

        # File Inputs
        self.file_inputs = {
            0: pn.widgets.FileInput(accept=".xlsx", name="Upload Holdings File"),
            1: pn.widgets.FileInput(accept=".csv", name="Upload Ledger File"),
            2: pn.widgets.FileInput(accept=".csv", name="Upload Tradebook File"),
        }

        self._layout = pn.Column(
            self.wizard_header,
            pn.layout.Divider(),
            self.step_content,
            pn.layout.Divider(),
            self.navigation_row,
            self.progress_logger_pane,
            sizing_mode="stretch_both",
        )

    @run_once
    def initialize(self):
        self._render_step()
        log.info("Initialized Manual Data Fetch Manager")

    @property
    def layout(self):
        return [self._layout]

    def _get_file_timestamp(self, file_type: str) -> str:
        """Get formatting timestamp for the appropriate file type from Master records."""
        master_path = const.DOCS_MASTER_PATH

        mapping = {
            "Holdings": const.HOLDINGS_MASTER,
            "Ledger": const.LEDGER_MASTER,
            "Tradebook": const.TRADEBOOK_MASTER,
        }

        if file_type in mapping:
            p = master_path / mapping[file_type]
            if p.exists():
                return datetime.fromtimestamp(p.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        return "Not Found"

    def _show_data_modal(self, data_type: str):
        """Show processed data in a modal dialog."""
        if not self.panel_modal:
            log.warning("Panel modal not available")
            return

        self.panel_modal.open(
            [pn.pane.Markdown(f"### Loading {data_type} Data...")],
            f"Loading {data_type}...",
        )

        try:
            reader = rkd.KiteDataReader()
            if data_type == "Holdings":
                equity_df, mf_df = reader.read_holdings()
                df = equity_df
            elif data_type == "Ledger":
                df = reader.read_ledger()
            elif data_type == "Tradebook":
                df = reader.read_tradebook()
            else:
                raise ValueError(f"Unknown data type: {data_type}")

            if df.empty:
                self.panel_modal.open(
                    [pn.pane.Markdown(f"No {data_type} data found.")],
                    f"{data_type} Data",
                )
                return

            table = pn.widgets.Tabulator(
                df,
                pagination="remote",
                page_size=20,
                sizing_mode="stretch_both",
                theme="bootstrap4",
                formatters={
                    "price": {"type": "money"},
                    "transaction_amount": {"type": "money"},
                    "debit": {"type": "money"},
                    "credit": {"type": "money"},
                    "net_balance": {"type": "money"},
                },
                header_filters=True,
                width=900,
                height=600,
            )

            back_cb = lambda: self.panel_modal.open(
                self.layout, "📥 Update Data from Zerodha"
            )

            self.panel_modal.open(
                [
                    pn.pane.Markdown(
                        f"### {data_type} Data Context (Total Rows: {len(df)})"
                    ),
                    table,
                ],
                f"{data_type} Data View",
                back_cb=back_cb,
            )

        except FileNotFoundError:
            self.panel_modal.open(
                [pn.pane.Markdown(f"No {data_type} data recorded yet.")],
                f"{data_type} Data",
            )
        except Exception as e:
            log.error(
                f"Error loading {data_type} data for modal: {traceback.format_exc()}"
            )
            self.panel_modal.open(
                [pn.pane.Alert(f"Error loading data: {e}", alert_type="danger")],
                "Error",
            )

    def _render_step(self):
        self.wizard_header.active_step = self.current_step

        content = []
        if self.current_step == 0:
            content.append(pn.pane.Markdown("### Step 1: Holdings Data"))
            content.append(
                pn.pane.Markdown(
                    "1. Go to **Zerodha Console** > **Portfolio** > **Holdings**.\n2. Click on the **Download** (Excel) button.\n3. Upload the downloaded file here."
                )
            )

            view_btn = pn.widgets.Button(
                name="View Current Data",
                button_type="primary",
                button_style="outline",
                width=150,
            )
            view_btn.on_click(lambda e: self._show_data_modal("Holdings"))

            content.append(
                pn.Row(
                    pn.pane.HTML(
                        f"<div><b>Last Uploaded:</b> <span style='color: var(--neutral-foreground-hint);'>{self._get_file_timestamp('Holdings')}</span></div>",
                        align="center",
                    ),
                    pn.Spacer(width=20),
                    view_btn,
                    margin=(0, 0, 10, 0),
                )
            )
            content.append(self.file_inputs[0])

        elif self.current_step == 1:
            content.append(pn.pane.Markdown("### Step 2: Ledger Data"))
            content.append(
                pn.pane.Markdown(
                    "1. Go to **Zerodha Console** > **Funds** > **Statement**.\n"
                    "2. **Select a date range from your last update to today.** *(It's safe to overlap dates; duplicates are automatically removed!)*\n"
                    "3. Click **Download CSV** and upload it here.\n\n"
                    "> **Note:** Your new upload will be seamlessly merged with your historical data to ensure no duplicate or missing entries."
                )
            )

            view_btn = pn.widgets.Button(
                name="View Current Data",
                button_type="primary",
                button_style="outline",
                width=150,
            )
            view_btn.on_click(lambda e: self._show_data_modal("Ledger"))

            content.append(
                pn.Row(
                    pn.pane.HTML(
                        f"<div><b>Last Uploaded:</b> <span style='color: var(--neutral-foreground-hint);'>{self._get_file_timestamp('Ledger')}</span></div>",
                        align="center",
                    ),
                    pn.Spacer(width=20),
                    view_btn,
                    margin=(0, 0, 10, 0),
                )
            )
            content.append(self.file_inputs[1])

        elif self.current_step == 2:
            content.append(pn.pane.Markdown("### Step 3: Tradebook Data"))
            content.append(
                pn.pane.Markdown(
                    "1. Go to **Zerodha Console** > **Reports** > **Tradebook**.\n"
                    "2. **Select a date range from your last update to today.** *(It's safe to overlap dates; duplicates are automatically removed!)*\n"
                    "3. Click **Download CSV** and upload it here.\n\n"
                    "> **Note:** Your new upload will be seamlessly merged with your historical data to ensure no duplicate or missing entries."
                )
            )

            view_btn = pn.widgets.Button(
                name="View Current Data",
                button_type="primary",
                button_style="outline",
                width=150,
            )
            view_btn.on_click(lambda e: self._show_data_modal("Tradebook"))

            content.append(
                pn.Row(
                    pn.pane.HTML(
                        f"<div><b>Last Uploaded:</b> <span style='color: var(--neutral-foreground-hint);'>{self._get_file_timestamp('Tradebook')}</span></div>",
                        align="center",
                    ),
                    pn.Spacer(width=20),
                    view_btn,
                    margin=(0, 0, 10, 0),
                )
            )
            content.append(self.file_inputs[2])

        self.step_content.objects = content

        # Navigation buttons
        nav_buttons = []
        if self.current_step > 0:
            prev_btn = pn.widgets.Button(name="Back", button_type="default", width=100)
            prev_btn.on_click(self._prev_step)
            nav_buttons.append(prev_btn)

        nav_buttons.append(pn.Spacer(sizing_mode="stretch_width"))

        if self.current_step < 2:
            next_btn = pn.widgets.Button(name="Next", button_type="primary", width=100)
            next_btn.on_click(self._next_step)
            nav_buttons.append(next_btn)
        else:
            submit_btn = pn.widgets.Button(
                name="Submit & Recalculate", button_type="success", width=180
            )
            submit_btn.on_click(self._submit)
            nav_buttons.append(submit_btn)

        self.navigation_row.objects = nav_buttons

    # Removed _merge_and_save_data as it is now handled by MasterSourceDataManager

    def _save_file(self, step_idx):
        file_input = self.file_inputs[step_idx]
        if file_input.value is not None:
            source = "zerodha"

            if step_idx == 0:
                # Holdings - Source specific Excel
                raw_path = self.data_manager.save_raw_file(
                    file_input.value, source, const.HOLDING_EXCEL_ZERODHA
                )

                # Archive current master before replacement
                self.data_manager.archive_master(const.HOLDINGS_MASTER)

                # Process raw file to get "Cleaned" data
                try:
                    # Zerodha usually has these two sheets
                    sheets = pd.read_excel(
                        raw_path, sheet_name=["Equity", "Mutual Funds"], header=None
                    )
                    cleaned_data = {
                        "Equity": rkd._HoldingProcessor.process(sheets["Equity"]),
                        "Mutual Funds": rkd._HoldingProcessor.process(
                            sheets["Mutual Funds"]
                        ),
                    }

                    # Save as the new master file (replacing the old one)
                    self.data_manager.save_dataframes_to_excel(
                        cleaned_data, const.HOLDINGS_MASTER
                    )
                except Exception as e:
                    log.error(f"Failed to process and replace holdings master: {e}")
                    raise
            elif step_idx == 1:
                # Ledger
                raw_path = self.data_manager.save_raw_file(
                    file_input.value, source, "ledger.csv"
                )
                subset_cols = [
                    "particulars",
                    "posting_date",
                    "cost_center",
                    "voucher_type",
                    "debit",
                    "credit",
                    "net_balance",
                ]
                self.data_manager.merge_and_update_master(
                    raw_path,
                    const.LEDGER_MASTER,
                    subset_cols=subset_cols,
                    date_col="posting_date",
                )

            elif step_idx == 2:
                # Tradebook
                raw_path = self.data_manager.save_raw_file(
                    file_input.value, source, "tradebook.csv"
                )
                subset_cols = ["trade_id", "order_id", "order_execution_time"]
                self.data_manager.merge_and_update_master(
                    raw_path,
                    const.TRADEBOOK_MASTER,
                    subset_cols=subset_cols,
                    date_col="trade_date",
                )

            # Reset file input to prevent re-saving
            file_input.value = None

    def _next_step(self, event):
        self._save_file(self.current_step)
        self.current_step += 1
        self._render_step()

    def _prev_step(self, event):
        self.current_step -= 1
        self._render_step()

    def _submit(self, event):
        self._save_file(2)  # Save tradebook if uploaded

        event.obj.disabled = True
        event.obj.loading = True

        # Disable Back button
        for obj in self.navigation_row.objects:
            if isinstance(obj, pn.widgets.Button):
                obj.disabled = True

        self.progress_logger_pane.visible = True
        self.progress_logger.clear()
        self.progress_logger.log("Starting data recalculation...", "info")

        try:
            generator = prepare_stocks_tab_data_progressive()

            def process_next_step():
                try:
                    update_data = next(generator)
                    if "data" in update_data:
                        # Final step completed
                        self.progress_logger.log(
                            "Recalculation logic finished", "success"
                        )

                        # Update Tab Data
                        new_data = update_data["data"]
                        self.tab_data.update(new_data)

                        self.progress_logger.complete(
                            "All data recalculated successfully!"
                        )

                        # Trigger refresh
                        if self.refresh_cb:
                            self.refresh_cb()

                        event.obj.disabled = False
                        event.obj.loading = False

                        # Re-enable navigation
                        for obj in self.navigation_row.objects:
                            if hasattr(obj, "disabled"):
                                obj.disabled = False
                    else:
                        self.progress_logger.log(update_data["status"], "info")
                        # Schedule next tick
                        pn.state.add_periodic_callback(
                            process_next_step, period=50, count=1
                        )
                except StopIteration:
                    pass
                except Exception as e:
                    self.progress_logger.error(f"Error occurred: {str(e)}")
                    log.error(f"Error during recalculation: {str(e)}")
                    event.obj.disabled = False
                    event.obj.loading = False

            # Start processor
            pn.state.add_periodic_callback(process_next_step, period=50, count=1)

        except Exception as e:
            self.progress_logger.error(f"Failed to initialize recalculation: {str(e)}")
            event.obj.disabled = False
            event.obj.loading = False
