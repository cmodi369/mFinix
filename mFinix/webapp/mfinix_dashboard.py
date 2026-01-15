import panel as pn

from mFinix.util import log

# import tabs and sidebar layout
from mFinix.webapp.sidebar_layout import SideBar
from mFinix.webapp.tab_mutual_funds import TabMutualFunds
from mFinix.webapp.tab_portfolio_summary import TabPortfolioSummary
from mFinix.webapp.tab_stocks import TabStocks


class Mfinix:
    def __init__(self):
        pn.extension(
            "tabulator",
            notifications=True,
            css_files=[
                "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css"
            ],
        )

        log.info("Instantiate mFinix.")

        # initialize dictionary to store all relevant data
        self.data = {}
        self.widgets = {}

        # initialize tabs
        self.tabs = [
            TabPortfolioSummary(self.data),
            TabStocks(self.data, self.widgets),
            TabMutualFunds(self.data),
        ]

        self.dashboard = pn.template.FastListTemplate(
            title="Multi Asset Finance Explorer",
            header_background="black",
            site="mFinix",
            sidebar_width=250,  ## Default is 330
            busy_indicator=None,
        )

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
