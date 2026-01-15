import panel as pn

from mFinix.util import log


class SideBar:
    def __init__(self, tabs: list, dashboard):
        self.tabs = tabs
        self.dashboard = dashboard

        # initialize widgets and callbacks
        self.widgets = dict()
        for tab in self.tabs:
            button = pn.widgets.Button(
                name=tab.NAME,
                button_type="warning",
                icon=tab.ICON,
                styles={"width": "100%"},
            )
            button.on_click(self._on_button_click)
            self.widgets[tab.NAME.lower().replace(" ", "_")] = button

        # initialize layouts
        self.layout = pn.Column(
            pn.pane.Markdown("## Pages"),
            *self.widgets.values(),
            styles={"width": "100%", "padding": "15px"}
        )
        self.dashboard.sidebar.append(self.layout)
        log.info("Sidebar initialized successfully.")

    def _on_button_click(self, event) -> None:
        tab = next(tab for tab in self.tabs if tab.NAME == event.obj.name)
        self.dashboard.main[0].clear()
        self.dashboard.main[0].append(tab.layout)
