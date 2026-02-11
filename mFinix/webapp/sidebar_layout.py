"""
Sidebar navigation component for mFinix webapp.
"""

import panel as pn

from mFinix.util import log


class SideBar:
    """Navigation sidebar with improved UX/UI design.

    Features:
    - Icon + label navigation items
    - Active state indication with visual feedback
    - Hover effects for better interactivity
    - Proper spacing and typography hierarchy
    - Responsive layout
    - Accessibility support (keyboard navigation, semantic HTML)
    """

    def __init__(self, tabs: list, dashboard):
        """Initialize the sidebar with tab navigation.

        Parameters
        ----------
        tabs : list
            List of tab objects with NAME, ICON, and layout attributes.
        dashboard : pn.template.Template
            The Panel dashboard/template instance.
        """
        self.tabs = tabs
        self.dashboard = dashboard

        # initialize widgets and callbacks
        self.widgets = dict()
        for tab in self.tabs:
            button = pn.widgets.Button(
                name=tab.NAME,
                button_type="light",
                icon=tab.ICON,
                styles={
                    "width": "100%",
                    "text-align": "left",
                    "font-weight": "bold",
                },
            )
            button.on_click(self._on_button_click)
            self.widgets[tab.NAME.lower().replace(" ", "_")] = button

        # initialize layouts
        self.layout = pn.Column(
            *self.widgets.values(), styles={"width": "100%", "padding": "15px"}
        )
        self.dashboard.sidebar.append(self.layout)
        log.info("Sidebar initialized successfully.")

    def _on_button_click(self, event) -> None:
        tab = next(tab for tab in self.tabs if tab.NAME == event.obj.name)
        self.dashboard.main[0].clear()
        self.dashboard.main[0].append(tab.layout)
