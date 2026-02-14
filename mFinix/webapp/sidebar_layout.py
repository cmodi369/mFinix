"""
Sidebar navigation component for mFinix webapp.
"""

import panel as pn

from mFinix.util import log
from mFinix.webapp.webapp_constants import SidebarStyles


class SideBar:
    """Navigation sidebar
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
        self.active_tab_key = None

        # initialize widgets and callbacks
        self.widgets = dict()
        self.button_objects = dict()

        for tab in self.tabs:
            tab_key = tab.NAME.lower().replace(" ", "_")
            button = pn.widgets.Button(
                name=tab.NAME,
                button_type="light",
                icon=tab.ICON,
                width=220,
                height=45,
                styles=SidebarStyles.BUTTON_STYLES,
            )
            button.on_click(self._on_button_click)
            self.widgets[tab_key] = button
            self.button_objects[tab.NAME] = button

        # Set first tab as active
        if self.tabs:
            self.active_tab_key = self.tabs[0].NAME.lower().replace(" ", "_")
            self._update_active_state(self.tabs[0].NAME)

        # initialize layouts with proper spacing
        self.layout = pn.Column(
            self._create_sidebar_header(),
            self._create_nav_section(),
            self._create_sidebar_footer(),
            styles=SidebarStyles.SIDEBAR_CONTAINER_STYLES,
        )
        self.dashboard.sidebar.append(self.layout)
        log.info("Sidebar initialized successfully with improved design.")

    def _create_sidebar_header(self) -> pn.pane.Markdown:
        """Create sidebar header with app branding."""
        return pn.pane.Markdown("### Navigation", styles=SidebarStyles.HEADER_STYLES)

    def _create_nav_section(self) -> pn.Column:
        """Create main navigation section with buttons."""
        return pn.Column(
            *self.widgets.values(),
            styles={
                "padding": "10px 0",
                "gap": "8px",  # Consistent gap between buttons
            },
        )

    def _create_sidebar_footer(self) -> pn.pane.Markdown:
        """Create sidebar footer with helpful info."""
        return pn.pane.Markdown(
            """
            **mFinix**<br>
            Multi Asset Finance Explorer
            """,
            styles=SidebarStyles.FOOTER_STYLES,
        )

    def _update_active_state(self, active_tab_name: str) -> None:
        """Update visual styling for active tab.

        Parameters
        ----------
        active_tab_name : str
            Name of the tab that should be marked as active.
        """
        # Reset all buttons to inactive state
        for button in self.button_objects.values():
            button.styles = SidebarStyles.BUTTON_STYLES

        # Set active button styling
        if active_tab_name in self.button_objects:
            active_button = self.button_objects[active_tab_name]
            active_styles = SidebarStyles.BUTTON_STYLES.copy()
            active_styles.update(SidebarStyles.BUTTON_ACTIVE_STYLES)
            active_button.styles = active_styles
            log.debug(f"Active tab set to: {active_tab_name}")

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
