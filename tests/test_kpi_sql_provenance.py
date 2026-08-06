from __future__ import annotations

from pathlib import Path

from tools.kpi_sql_audit import audit_pages, KPI_CALL_NAMES
from ui.kpi_governance import KPI_REGISTRY

ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "pages"

# Disclosed, non-computed placeholders — already labelled "Estimated"/"unavailable"
# in KPI_REGISTRY and in their own on-page caption. Not real KPI calculations.
ALLOWED_NON_SQL_KPIS = {"Estimated Uplift Assumption", "Observed Bonus Efficiency"}


def test_every_kpi_card_value_is_sql_derived():
    violations = audit_pages(PAGES_DIR, ALLOWED_NON_SQL_KPIS)
    assert not violations, "\n".join(f"{v.file}: {v.label!r} — {v.detail}" for v in violations)


def test_allowlist_entries_are_still_referenced():
    """Keep the allowlist honest: every entry must exist as a real, still-present KPI label."""
    for label in ALLOWED_NON_SQL_KPIS:
        assert label in KPI_REGISTRY, f"{label!r} is allowlisted but no longer in KPI_REGISTRY — remove it"


def test_every_page_kpi_label_is_registered():
    """Every KPI card shown on a page must resolve through ui.kpi_governance.kpi_help (no KeyError at runtime)."""
    import ast

    missing = []
    for path in sorted(PAGES_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in KPI_CALL_NAMES:
                if not node.args or not isinstance(node.args[0], ast.List):
                    continue
                for element in node.args[0].elts:
                    label_node = None
                    if isinstance(element, ast.Tuple) and element.elts:
                        label_node = element.elts[0]
                    elif isinstance(element, ast.Dict):
                        label_node = next((v for k, v in zip(element.keys, element.values) if isinstance(k, ast.Constant) and k.value == "label"), None)
                    if isinstance(label_node, ast.Constant) and isinstance(label_node.value, str) and label_node.value not in KPI_REGISTRY:
                        missing.append(f"{path.name}: {label_node.value!r}")
    assert not missing, "KPI card labels missing from KPI_REGISTRY (would raise KeyError at runtime):\n" + "\n".join(missing)
