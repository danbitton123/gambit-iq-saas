from __future__ import annotations

"""Grid layout helpers. Widgets keep the x/y/w/h shape described in query_engine.py's module
docstring (compatible with a future real drag-and-drop canvas or an AI-generated dashboard),
but this MVP interprets them as an explicit row/order model rather than free pixel coordinates:
`y` is a row index, `x` is order-within-row, `w`/`h` are grid-unit spans (12-column grid). Moving
a widget reorders/renumbers rows so two widgets can never overlap by construction — no bin-
packing or collision detection needed, which is the more fragile approach for a first version.
"""

from dashboard_builder.models import GRID_COLUMNS, Widget

MIN_W, MAX_W = 2, GRID_COLUMNS
MIN_H, MAX_H = 2, 10


def pack_rows(widgets: list[Widget]) -> list[list[Widget]]:
    """Group widgets into visual rows: same `y` first, then split further whenever a row's
    cumulative width would exceed 12 columns (e.g. after a resize)."""
    ordered = sorted(widgets, key=lambda widget: (widget.y, widget.x))
    rows: list[list[Widget]] = []
    for widget in ordered:
        if rows and rows[-1] and rows[-1][0].y == widget.y and sum(w.w for w in rows[-1]) + widget.w <= GRID_COLUMNS:
            rows[-1].append(widget)
        else:
            rows.append([widget])
    return rows


def _renumber(widgets: list[Widget]) -> None:
    """Reassign y/x from the current row packing so values stay small and contiguous."""
    for row_index, row in enumerate(pack_rows(widgets)):
        for order, widget in enumerate(row):
            widget.y, widget.x = row_index, order


def move_widget(widgets: list[Widget], widget_id: str, direction: str) -> None:
    _renumber(widgets)
    rows = pack_rows(widgets)
    position = next(((r, i) for r, row in enumerate(rows) for i, w in enumerate(row) if w.id == widget_id), None)
    if position is None:
        return
    row_index, order = position
    if direction == "left" and order > 0:
        rows[row_index][order], rows[row_index][order - 1] = rows[row_index][order - 1], rows[row_index][order]
    elif direction == "right" and order < len(rows[row_index]) - 1:
        rows[row_index][order], rows[row_index][order + 1] = rows[row_index][order + 1], rows[row_index][order]
    elif direction == "up" and row_index > 0:
        widget = rows[row_index].pop(order)
        rows[row_index - 1].append(widget)
    elif direction == "down":
        widget = rows[row_index].pop(order)
        if row_index + 1 < len(rows):
            rows[row_index + 1].append(widget)
        else:
            rows.append([widget])
    rows = [row for row in rows if row]
    for new_row_index, row in enumerate(rows):
        for new_order, widget in enumerate(row):
            widget.y, widget.x = new_row_index, new_order


def resize_widget(widget: Widget, delta_w: int = 0, delta_h: int = 0) -> None:
    widget.w = max(MIN_W, min(MAX_W, widget.w + delta_w))
    widget.h = max(MIN_H, min(MAX_H, widget.h + delta_h))


def next_position(widgets: list[Widget], width: int) -> tuple[int, int]:
    """Where a newly-added widget should land: end of the last row if it fits, else a new row."""
    rows = pack_rows(widgets)
    if not rows:
        return 0, 0
    last_row = rows[-1]
    if sum(w.w for w in last_row) + width <= GRID_COLUMNS:
        return last_row[0].y, len(last_row)
    return last_row[0].y + 1, 0
