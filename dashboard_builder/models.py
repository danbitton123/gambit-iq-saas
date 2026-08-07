from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from uuid import uuid4

GRID_COLUMNS = 12
DEFAULT_ROW_HEIGHT = 4  # widget "h" units; canvas renders in CSS grid rows of this height

WIDGET_TYPES = ("kpi", "line", "bar", "pie", "scatter", "table", "text")

WIDGET_TYPE_LABELS = {
    "kpi": "KPI Card", "line": "Line Chart", "bar": "Bar Chart", "pie": "Pie Chart",
    "scatter": "Scatter Plot", "table": "Table", "text": "Text",
}
WIDGET_TYPE_ICONS = {
    "kpi": "speed", "line": "show_chart", "bar": "bar_chart", "pie": "pie_chart",
    "scatter": "scatter_plot", "table": "table_rows", "text": "notes",
}

COMPARISON_OPTIONS = ("none", "previous_period")
SORT_DIRECTIONS = ("desc", "asc")
THEMES = ("casinoai_dark", "casinoai_light", "executive", "casino_neon", "minimal")

# Default widget footprints (w columns out of 12, h grid rows) per type — used both as the
# initial size when a widget is added and as the min/step for the size stepper.
DEFAULT_SIZE = {
    "kpi": (3, 3), "line": (6, 5), "bar": (6, 5), "pie": (4, 5),
    "scatter": (6, 5), "table": (12, 6), "text": (12, 2),
}


def new_id() -> str:
    return uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LocalFilter:
    dimension: str
    value: str

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "LocalFilter":
        return LocalFilter(dimension=data["dimension"], value=data["value"])


@dataclass
class Widget:
    """One visualization on the canvas. `dataset` keys into semantic_query.DATASETS;
    `dimension`/`measures` key into that dataset's own dimensions/metrics dicts."""

    id: str = field(default_factory=new_id)
    type: str = "kpi"
    title: str = "New widget"
    x: int = 0
    y: int = 0
    w: int = 3
    h: int = 3
    dataset: str | None = None
    dimension: str | None = None          # primary breakdown (x-axis / pie slice / group)
    dimension2: str | None = None         # secondary breakdown (scatter color, bar color)
    measures: list[str] = field(default_factory=list)
    sort_direction: str = "desc"
    top_n: int | None = 10
    comparison: str = "none"              # kpi only: "none" | "previous_period"
    filters: list[LocalFilter] = field(default_factory=list)
    text_content: str = ""                # text widgets only (markdown)
    accent_color: str | None = None       # None = use theme default palette
    show_title: bool = True
    compact_numbers: bool = True          # K/M/B notation vs full precision

    def to_dict(self) -> dict:
        data = asdict(self)
        data["filters"] = [f.to_dict() if isinstance(f, LocalFilter) else f for f in self.filters]
        return data

    @staticmethod
    def from_dict(data: dict) -> "Widget":
        payload = dict(data)
        payload["filters"] = [LocalFilter.from_dict(f) for f in payload.get("filters", [])]
        known = {f.name for f in Widget.__dataclass_fields__.values()}
        payload = {k: v for k, v in payload.items() if k in known}
        return Widget(**payload)


@dataclass
class GlobalFilter:
    dimension: str
    dataset: str
    values: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "GlobalFilter":
        return GlobalFilter(dimension=data["dimension"], dataset=data["dataset"], values=list(data["values"]))


@dataclass
class Dashboard:
    id: str = field(default_factory=new_id)
    tenant_id: str = ""
    user_id: str = ""
    name: str = "Untitled dashboard"
    theme: str = "casinoai_dark"
    widgets: list[Widget] = field(default_factory=list)
    global_filters: list[GlobalFilter] = field(default_factory=list)
    is_favorite: bool = False
    is_default: bool = False
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "tenant_id": self.tenant_id, "user_id": self.user_id, "name": self.name,
            "theme": self.theme, "widgets": [w.to_dict() for w in self.widgets],
            "global_filters": [f.to_dict() for f in self.global_filters],
            "is_favorite": self.is_favorite, "is_default": self.is_default,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "Dashboard":
        return Dashboard(
            id=data["id"], tenant_id=data["tenant_id"], user_id=data.get("user_id", ""),
            name=data["name"], theme=data.get("theme", "casinoai_dark"),
            widgets=[Widget.from_dict(w) for w in data.get("widgets", [])],
            global_filters=[GlobalFilter.from_dict(f) for f in data.get("global_filters", [])],
            is_favorite=data.get("is_favorite", False), is_default=data.get("is_default", False),
            created_at=data.get("created_at", _now()), updated_at=data.get("updated_at", _now()),
        )

    def clone(self, new_name: str, tenant_id: str, user_id: str) -> "Dashboard":
        cloned_widgets = [Widget.from_dict(w.to_dict()) for w in self.widgets]
        for widget in cloned_widgets:
            widget.id = new_id()
        return Dashboard(
            tenant_id=tenant_id, user_id=user_id, name=new_name, theme=self.theme,
            widgets=cloned_widgets, global_filters=[GlobalFilter.from_dict(f.to_dict()) for f in self.global_filters],
        )
