import panel as pn
import param


class WizardStepHeader(pn.viewable.Viewer):
    """
    A custom Wizard Step Header component that displays steps with chevron/arrow shapes.
    Highlighting the active step with primary colors, and previous steps with a faded color.
    """

    steps = param.List(default=[])
    active_step = param.Integer(default=0)

    def __init__(self, **params):
        super().__init__(**params)
        self._layout = pn.pane.HTML(self._get_html(), sizing_mode="stretch_width")

    @param.depends("steps", "active_step", watch=True)
    def _update_layout(self):
        self._layout.object = self._get_html()

    def _get_html(self):
        if not self.steps:
            return ""

        html = [
            "<div style='display: flex; width: 100%; border-radius: 8px; "
            "overflow: hidden; background-color: var(--neutral-fill-card-rest); "
            "border: 1px solid var(--neutral-stroke-divider-rest);'>"
        ]

        n_steps = len(self.steps)
        for i, step in enumerate(self.steps):
            is_active = i == self.active_step
            is_past = i < self.active_step

            # CSS Variable mapping for themes
            bg_color = (
                "var(--accent-fill-rest)"
                if is_active
                else ("var(--neutral-fill-hover)" if is_past else "transparent")
            )
            text_color = (
                "white"
                if is_active
                else (
                    "var(--neutral-foreground-rest)"
                    if is_past
                    else "var(--neutral-foreground-hint)"
                )
            )
            font_weight = "bold" if is_active else "normal"

            # Chevron shapes
            if n_steps == 1:
                clip_path = "none"
                padding = "10px 20px"
                margin_left = "0"
            elif i == 0:
                clip_path = "polygon(0 0, calc(100% - 15px) 0, 100% 50%, calc(100% - 15px) 100%, 0 100%)"
                padding = "10px 20px 10px 20px"
                margin_left = "0"
            elif i == n_steps - 1:
                clip_path = "polygon(0 0, 100% 0, 100% 100%, 0 100%, 15px 50%)"
                padding = "10px 20px 10px 35px"
                margin_left = "-15px"
            else:
                clip_path = "polygon(0 0, calc(100% - 15px) 0, 100% 50%, calc(100% - 15px) 100%, 0 100%, 15px 50%)"
                padding = "10px 35px 10px 35px"
                margin_left = "-15px"

            # Ensure proper z-index for overlapping shapes
            z_index = (n_steps - i) if not is_active else 10

            step_html = f"""
            <div style='
                flex: 1;
                text-align: center;
                padding: {padding};
                background-color: {bg_color};
                color: {text_color};
                font-weight: {font_weight};
                clip-path: {clip_path};
                margin-left: {margin_left};
                position: relative;
                z-index: {z_index};
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
            '>
                {step}
            </div>
            """
            html.append(step_html)

        html.append("</div>")
        return "".join(html)

    def __panel__(self):
        return self._layout
