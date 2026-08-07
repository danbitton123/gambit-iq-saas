from __future__ import annotations

"""Pre-flight validation for a Widget configuration. Used both by the property panel (immediate
inline feedback while editing) and by the renderer (a last line of defense) so an incomplete
configuration always reads as guidance, never as a crash."""

from dashboard_builder.models import Widget


def validate_widget(widget: Widget) -> str | None:
    """Returns a human-readable reason the widget can't render yet, or None if it's ready."""
    if widget.type == "text":
        return None if widget.text_content.strip() else "Add some text to display this widget."
    if not widget.dataset:
        return "Select a data domain to start."
    if widget.type == "kpi":
        return None if widget.measures else "Select a measure to create this KPI."
    if widget.type == "scatter":
        if len(widget.measures) < 2:
            return "Select two measures to create this scatter plot."
        return None
    if widget.type == "pie":
        if not widget.dimension:
            return "Select a dimension and a measure to create this chart."
        if len(widget.measures) != 1:
            return "A pie chart needs exactly one measure."
        return None
    if widget.type in ("line", "bar"):
        if not widget.dimension:
            return "Select a dimension and a measure to create this chart."
        if not widget.measures:
            return "Select a dimension and a measure to create this chart."
        return None
    if widget.type == "table":
        return None if widget.measures else "Select at least one measure to populate this table."
    return None
