"""
Reusable Panel Modal helper for mFinix webapp.

Wraps the FastListTemplate's built-in modal area to provide a standardized
modal overlay that can be used by any tab or manager.
"""

import panel as pn

from mFinix.util import log
from mFinix.webapp.webapp_constants import UIStyles


class PanelModal:
    """Reusable modal dialog backed by FastListTemplate's built-in modal.

    Parameters
    ----------
    dashboard : pn.template.FastListTemplate
        The Panel dashboard/template instance whose modal area will be used.
    """

    # Styling for the modal content wrapper
    MODAL_HEADER_STYLES = {
        "display": "flex",
        "justify-content": "space-between",
        "align-items": "center",
        "border-bottom": "1px solid var(--neutral-stroke-divider-rest)",
        "padding-bottom": "10px",
        "margin-bottom": "10px",
    }

    MODAL_CONTAINER_STYLES = {
        "background-color": UIStyles.CARD_BACKGROUND,
        "border-radius": "12px",
        "padding": "20px",
        "min-width": "600px",
        "max-width": "1200px",
        "min-height": "400px",
        "max-height": "900px",
        "overflow": "auto",
        "box-shadow": "var(--elevation-shadow-2)",
    }

    def __init__(self, dashboard) -> None:
        self.dashboard = dashboard
        self._title_markdown = pn.pane.Markdown(
            "",
            styles={
                "font-size": "1.2rem",
                "font-weight": "600",
                "color": UIStyles.HEADER_COLOR,
                "margin": "0",
            },
        )

        self._back_cb = None
        self._back_btn = pn.widgets.Button(
            name="Back",
            icon="arrow-left",
            button_type="primary",
            button_style="outline",
            width=100,
            height=40,
            margin=(0, 10, 0, 0),
            visible=False,
        )
        self._back_btn.on_click(self._handle_back_click)

        self._header = pn.Row(
            self._back_btn,
            self._title_markdown,
            styles=self.MODAL_HEADER_STYLES,
            sizing_mode="stretch_width",
        )

        self._content_column = pn.Column(sizing_mode="stretch_both")

        self._modal_body = pn.Column(
            self._header,
            self._content_column,
            styles=self.MODAL_CONTAINER_STYLES,
            sizing_mode="stretch_both",
            css_classes=["pn-modal-content"],
        )

        # Pre-attach the modal body to the dashboard
        self.dashboard.modal[:] = [self._modal_body]

    def open(self, content: list, title: str = "", back_cb: callable = None) -> None:
        """Open the modal with the given content.

        Parameters
        ----------
        content : list
            List of Panel components to display inside the modal.
        title : str
            Title text shown in the modal header.
        back_cb : callable, optional
            A callback function to execute when the back button is clicked.
            If provided, the back button will be visible.
        """
        if not content:
            log.warning("Attempted to open modal with empty content.")
            return

        # Update title and content
        self._title_markdown.object = f"### {title}"
        self._content_column[:] = list(content)

        # Update back button
        self._back_cb = back_cb
        if back_cb:
            log.info("Showing back button")
            self._back_btn.visible = True
        else:
            self._back_btn.visible = False

        # Open the modal
        self.dashboard.open_modal()
        log.info("Opened modal: %s (back=%s)", title, bool(back_cb))

    def _handle_back_click(self, event):
        """Handle back button click."""
        if self._back_cb:
            self._back_cb()
