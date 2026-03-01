"""Sidebar navigation component for mFinix webapp."""

import panel as pn

from mFinix.util import log
from mFinix.webapp.webapp_constants import SidebarStyles


class SideBar:
    """Navigation sidebar for dashboard tab switching."""

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
        self.active_tab_key = None
        self.widgets = {}
        self.button_objects = {}

        # Create navigation buttons
        self._create_buttons()

        # Set first tab as active
        if self.tabs:
            self.active_tab_key = self.tabs[0].NAME.lower().replace(" ", "_")
            self._update_active_state(self.tabs[0].NAME)

        # Create sidebar layout
        self.layout = pn.Column(
            self._create_nav_section(),
            styles=SidebarStyles.SIDEBAR_CONTAINER_STYLES,
        )
        self.dashboard.sidebar.append(self.layout)
        log.info("Sidebar initialized.")

    def _create_buttons(self) -> None:
        """Create navigation buttons for each tab."""
        for tab in self.tabs:
            tab_key = tab.NAME.lower().replace(" ", "_")
            button = pn.widgets.Button(
                name=tab.NAME,
                icon=tab.ICON,
                sizing_mode="stretch_width",
                stylesheets=[SidebarStyles.BUTTON_CSS],
                css_classes=["sidebar-nav-btn"],
            )
            button.on_click(self._on_button_click)
            self.widgets[tab_key] = button
            self.button_objects[tab.NAME] = button

    def _create_nav_section(self) -> pn.Column:
        """Create main navigation section with buttons.

        Returns
        -------
        pn.Column
            Column containing all navigation buttons.
        """
        return pn.Column(
            *self.widgets.values(),
            sizing_mode="stretch_width",
        )

    def _update_active_state(self, active_tab_name: str) -> None:
        """Update visual styling for active tab.

        Parameters
        ----------
        active_tab_name : str
            Name of the tab that should be marked as active.
        """
        for btn in self.button_objects.values():
            if active_tab_name == btn.name:
                btn.css_classes = ["nav-button", "nav-active"]
                log.debug(f"Active tab set to: {active_tab_name}")
            else:
                btn.css_classes = ["nav-button"]

    def _on_button_click(self, event) -> None:
        """Handle navigation button click events.

        Parameters
        ----------
        event : pn.events.Event
            The click event from the button.
        """
        tab = next(tab for tab in self.tabs if tab.NAME == event.obj.name)
        self.active_tab_key = tab.NAME.lower().replace(" ", "_")

        # Update active state styling
        self._update_active_state(event.obj.name)

        # Update main content
        self.dashboard.main[0].clear()
        self.dashboard.main[0].append(tab.layout)

        log.info(f"Navigated to tab: {event.obj.name}")
