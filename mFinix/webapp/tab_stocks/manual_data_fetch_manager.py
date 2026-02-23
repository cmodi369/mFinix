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
        """Get formatting timestamp for the appropriate file type."""
        docs_path = const.DOCS_PATH
        if file_type == "Holdings":
            p = docs_path / const.HOLDING_EXCEL_ZERODHA
            if p.exists():
                return datetime.fromtimestamp(p.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
        elif file_type == "Ledger":
            files = list(docs_path.glob(f"{const.LEDGER_ID_ZERODHA}*.csv"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                return datetime.fromtimestamp(latest.stat().st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
        elif file_type == "Tradebook":
            files = list(docs_path.glob(f"{const.TRADEBOOK_ID_ZERODHA}*.csv"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                return datetime.fromtimestamp(latest.stat().st_mtime).strftime(
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
                width=1150,
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

    def _merge_and_save_data(
        self, temp_file_path: Path, data_type: str, timestamp_str: str
    ) -> Path:
        """Merge newly uploaded CSV with existing CSVs, remove duplicates, and archive old files."""
        docs_path = const.DOCS_PATH
        archive_path = docs_path / "archive"
        archive_path.mkdir(exist_ok=True)

        if data_type == "Ledger":
            file_prefix = const.LEDGER_ID_ZERODHA
            subset_cols = [
                "particulars",
                "posting_date",
                "cost_center",
                "voucher_type",
                "debit",
                "credit",
                "net_balance",
            ]
            date_col = "posting_date"
        elif data_type == "Tradebook":
            file_prefix = const.TRADEBOOK_ID_ZERODHA
            subset_cols = ["trade_id", "order_id", "order_execution_time"]
            date_col = "trade_date"

        new_filename = f"{file_prefix}_{timestamp_str}.csv"
        final_file_path = docs_path / new_filename

        try:
            # Load new data
            df_new = pd.read_csv(temp_file_path)

            # Find existing files
            existing_files = list(docs_path.glob(f"{file_prefix}*.csv"))
            dfs_to_concat = [df_new]

            for f in existing_files:
                # Need to read and concatenate
                try:
                    df_existing = pd.read_csv(f)
                    dfs_to_concat.append(df_existing)
                except Exception as e:
                    log.error(f"Failed to read existing file for merge {f}: {e}")

            if len(dfs_to_concat) > 1:
                # Combine and deduplicate
                df_combined = pd.concat(dfs_to_concat, ignore_index=True)
                # For safety, ensure date column is somewhat parsable for sorting if we want to sort,
                # but drop_duplicates will keep the first occurrence usually.
                # Let's drop duplicates cleanly
                df_combined = df_combined.drop_duplicates(
                    subset=subset_cols, keep="last"
                )

                # Try sorting by date if exists
                if date_col in df_combined.columns:
                    try:
                        df_combined[date_col] = pd.to_datetime(
                            df_combined[date_col], format="mixed", dayfirst=False
                        )
                        df_combined = df_combined.sort_values(by=date_col)
                        # We might need to keep it as string if the original was string, read_csv will handle it
                    except Exception as e:
                        log.warning(f"Could not sort merged data by date: {e}")

                # Save merged data
                df_combined.to_csv(final_file_path, index=False)
            else:
                # Just rename the temp file to final destination if no existing files
                shutil.copy(temp_file_path, final_file_path)

            # Move all existing matched files to archive
            for f in existing_files:
                archive_file_path = archive_path / f.name
                # Avoid moving the file we just created if glob picked it up (shouldn't if temp is named differently, but still)
                if f != final_file_path and f != temp_file_path:
                    try:
                        os.rename(f, archive_file_path)
                    except Exception as e:
                        log.error(f"Failed to archive old file {f}: {e}")

            return final_file_path

        except Exception as e:
            log.error(f"Data merge pipeline failed: {traceback.format_exc()}")
            # Fallback: Just save the new file
            return final_file_path

    def _save_file(self, step_idx):
        file_input = self.file_inputs[step_idx]
        if file_input.value is not None:
            docs_path = const.DOCS_PATH
            docs_path.mkdir(parents=True, exist_ok=True)
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")

            if step_idx == 0:
                filename = const.HOLDING_EXCEL_ZERODHA
                file_path = docs_path / filename
                file_input.save(str(file_path))
            elif step_idx == 1:
                # Ledger
                temp_filename = f"temp_ledger_{timestamp_str}.csv"
                temp_file_path = docs_path / "archive" / temp_filename
                (docs_path / "archive").mkdir(exist_ok=True)
                file_input.save(str(temp_file_path))

                # Run Merge Pipeline
                self._merge_and_save_data(temp_file_path, "Ledger", timestamp_str)

            elif step_idx == 2:
                # Tradebook
                temp_filename = f"temp_tradebook_{timestamp_str}.csv"
                temp_file_path = docs_path / "archive" / temp_filename
                (docs_path / "archive").mkdir(exist_ok=True)
                file_input.save(str(temp_file_path))

                # Run Merge Pipeline
                self._merge_and_save_data(temp_file_path, "Tradebook", timestamp_str)

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
