import panel as pn


class TabPortfolioSummary:
    NAME: str = "Portfolio Summary"

    ICON: str = "chart-histogram"

    def __init__(self, data):
        self.layout = pn.Column("## Portfolio Summary Tab", height=400, width=500)
