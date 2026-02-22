import os
from datetime import datetime
from pathlib import Path

import panel as pn
import param

import mFinix.constants.columns as col
import mFinix.constants.constants as const
from mFinix.util import log
from mFinix.webapp.components.progress_logger import ProgressLogger
from mFinix.webapp.components.wizard_step_header import WizardStepHeader
from mFinix.webapp.tab_stocks.utility import (
    prepare_stocks_tab_data_progressive,
    run_once,
)


class ManualDataFetchManager:
    def __init__(self, tab_data: dict, tab_widgets: dict, refresh_cb: callable):
        self.tab_data = tab_data
        self.tab_widgets = tab_widgets
        self.refresh_cb = refresh_cb

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
            sizing_mode="stretch_width",
            min_width=600,
            min_height=400,
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
            content.append(
                pn.pane.HTML(
                    f"<div style='margin-bottom: 10px;'><b>Last Uploaded:</b> <span style='color: var(--neutral-foreground-hint);'>{self._get_file_timestamp('Holdings')}</span></div>"
                )
            )
            content.append(self.file_inputs[0])

        elif self.current_step == 1:
            content.append(pn.pane.Markdown("### Step 2: Ledger Data"))
            content.append(
                pn.pane.Markdown(
                    "1. Go to **Zerodha Console** > **Funds** > **Statement**.\n2. Select the date range and click **Download CSV**.\n3. Upload the downloaded file here."
                )
            )
            content.append(
                pn.pane.HTML(
                    f"<div style='margin-bottom: 10px;'><b>Last Uploaded:</b> <span style='color: var(--neutral-foreground-hint);'>{self._get_file_timestamp('Ledger')}</span></div>"
                )
            )
            content.append(self.file_inputs[1])

        elif self.current_step == 2:
            content.append(pn.pane.Markdown("### Step 3: Tradebook Data"))
            content.append(
                pn.pane.Markdown(
                    "1. Go to **Zerodha Console** > **Reports** > **Tradebook**.\n2. Select the date range and click **Download CSV**.\n3. Upload the downloaded file here."
                )
            )
            content.append(
                pn.pane.HTML(
                    f"<div style='margin-bottom: 10px;'><b>Last Uploaded:</b> <span style='color: var(--neutral-foreground-hint);'>{self._get_file_timestamp('Tradebook')}</span></div>"
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

    def _save_file(self, step_idx):
        file_input = self.file_inputs[step_idx]
        if file_input.value is not None:
            docs_path = const.DOCS_PATH
            docs_path.mkdir(parents=True, exist_ok=True)

            if step_idx == 0:
                filename = const.HOLDING_EXCEL_ZERODHA
            elif step_idx == 1:
                filename = f"{const.LEDGER_ID_ZERODHA}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
            elif step_idx == 2:
                filename = f"{const.TRADEBOOK_ID_ZERODHA}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"

            file_path = docs_path / filename
            file_input.save(str(file_path))
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
