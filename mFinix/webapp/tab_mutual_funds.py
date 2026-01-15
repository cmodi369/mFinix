import panel as pn


class TabMutualFunds:
    NAME: str = "Mutual Funds"

    ICON: str = "clipboard-data"

    def __init__(self, data):
        self.layout = pn.Column("## Mutual Funds", height=400, width=500)
