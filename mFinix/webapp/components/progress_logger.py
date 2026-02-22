import panel as pn
import param


class ProgressLogger(pn.viewable.Viewer):
    """
    A real-time progress logger component for operations with multiple steps.
    """

    def __init__(self, **params):
        super().__init__(**params)
        self._logs = []
        self._layout = pn.pane.HTML(
            self._get_html(),
            sizing_mode="stretch_width",
            styles={
                "background-color": "var(--neutral-fill-input-rest, #1e1e1e)",
                "border": "1px solid var(--neutral-stroke-rest, #333)",
                "border-radius": "8px",
                "padding": "15px",
                "box-shadow": "inset 0 2px 4px rgba(0,0,0,0.5)",
                "min-height": "100px",
                "max-height": "250px",
                "overflow-y": "auto",
                "font-family": "Consolas, monospace",
                "font-size": "13px",
            },
        )

    def _get_html(self):
        if not self._logs:
            return "<div style='color: var(--neutral-foreground-hint); font-style: italic;'>Waiting to start...</div>"

        formatted_logs = []
        for i, log in enumerate(self._logs):
            msg = log["msg"]
            status = log["status"]

            # Icons based on status
            if status == "success":
                prefix = "✔️ "
            elif status == "warning":
                prefix = "⚠️ "
            elif status == "error":
                prefix = "❌ "
            else:
                # If it's the last one and not success/error, it's loading
                prefix = "⏳ " if i == len(self._logs) - 1 else "✔️ "

            is_last = i == len(self._logs) - 1

            # Colors based on state
            if is_last:
                if status == "success":
                    color = "#2ecc71"  # Bright green
                elif status == "warning":
                    color = "#f39c12"  # Bright orange
                elif status == "error":
                    color = "#e74c3c"  # Bright red
                else:
                    color = "#3498db"  # Bright blue for loading
                font_weight = "bold"
            else:
                if status in ["success", "info"] or (
                    status == "info" and prefix == "✔️ "
                ):
                    color = "#27ae60"  # Dimmer green
                elif status == "warning":
                    color = "#d68910"  # Dimmer orange
                elif status == "error":
                    color = "#c0392b"  # Dimmer red
                else:
                    color = "#888888"  # Gray for old info
                font_weight = "normal"

            formatted_logs.append(
                f"<div style='color: {color}; font-weight: {font_weight}; margin-bottom: 6px;'>"
                f"{prefix}{msg}"
                f"</div>"
            )

        return "".join(formatted_logs)

    def log(self, message: str, status: str = "info"):
        self._logs.append({"msg": message, "status": status})
        self._layout.object = self._get_html()

    def complete(self, message: str = "Completed successfully!"):
        if self._logs and self._logs[-1]["status"] == "info":
            self._logs[-1]["status"] = "success"
        self._logs.append({"msg": message, "status": "success"})
        self._layout.object = self._get_html()

    def error(self, message: str):
        if self._logs and self._logs[-1]["status"] == "info":
            self._logs[-1]["status"] = "error"
        self._logs.append({"msg": message, "status": "error"})
        self._layout.object = self._get_html()

    def clear(self):
        self._logs = []
        self._layout.object = self._get_html()

    def __panel__(self):
        return self._layout
