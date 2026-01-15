from pathlib import Path

import panel as pn


class BoldTitleWidget(pn.widgets.Widget):
    # Custom base class for widgets with bold titles
    def __init__(self, *args, **kwargs):
        # Automatically add the CSS class for bold titles
        css_style = {
            "font-weight": "bold  !important",
        }
        styles = kwargs.pop("styles", {})
        styles.update(css_style)
        super().__init__(*args, styles=styles, **kwargs)


class CustomAutoCompleteInput(BoldTitleWidget, pn.widgets.AutocompleteInput):
    pass


class CustomDatePicker(BoldTitleWidget, pn.widgets.DatePicker):
    pass


class CustomFloatInput(BoldTitleWidget, pn.widgets.FloatInput):
    pass


class CustomTextInput(BoldTitleWidget, pn.widgets.TextInput):
    pass
