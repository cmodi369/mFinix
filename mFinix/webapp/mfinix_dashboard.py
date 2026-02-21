import panel as pn

from mFinix.util import log

# import tabs and sidebar layout
from mFinix.webapp.sidebar_layout import SideBar
from mFinix.webapp.tab_mutual_funds import TabMutualFunds
from mFinix.webapp.tab_portfolio_summary import TabPortfolioSummary
from mFinix.webapp.tab_stocks import TabStocks
from mFinix.webapp.webapp_constants import SidebarStyles, UIStyles


class Mfinix:
    def __init__(self):
        pn.extension(
            "tabulator",
            notifications=True,
            css_files=[
                "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"
            ],
            raw_css=[UIStyles.CUSTOM_CSS, SidebarStyles.CUSTOM_CSS],
        )

        log.info("Instantiate mFinix.")

        # initialize dictionary to store all relevant data
        self.data = {}
        self.widgets = {}

        self.dashboard = pn.template.FastListTemplate(
            title="Multi Asset Finance Explorer",
            header_background="#2F4F4F",
            accent_base_color="#DAA520",
            site="mFinix",
            sidebar_width=250,
            busy_indicator=None,
            main_max_width="95%",
        )

        # initialize tabs (after dashboard so TabStocks can access the modal)
        self.tabs = [
            TabPortfolioSummary(self.data),
            TabStocks(self.data, self.widgets, self.dashboard),
            TabMutualFunds(self.data),
        ]

        self._create_layout()

        # Serve the Panel app
        self.dashboard.servable()

        log.info("mFinix initialized.")

    def _create_layout(self) -> None:
        """Create layout for sidebar and main"""
        # initialize sidebar
        self.sidebar = SideBar(self.tabs, self.dashboard)

        # initial main layout
        main = pn.Column(self.tabs[0].layout, styles={"width": "100%"})
        self.dashboard.main.append(main)
