"""Static audit: every KPI card rendered by pages/*.py must be traceable to a SQL query.

GAMBIT IQ's stated architecture (README.md) is "every dashboard KPI ... is
calculated in SQL". This module walks the AST of each page module and checks
that every value shown in a `kpis([...])` / `_executive_kpis([...])` card
depends — directly, or through simple arithmetic/attribute access/merges on
already-SQL-sourced data — on a call to one of the SQLContext/SQLRepository
query methods (`ctx.query`, `ctx.scalar`, `ctx.previous_query`,
`ctx.previous_scalar`, or the equivalent `ctx.repo.*`).

It is a heuristic, not a type-checker: it tracks simple `name = expr`
assignments inside `render()` and inside any other module-level function
`render()` calls, and treats a name as SQL-derived once it is built (directly
or by propagation through arithmetic, subscripting, attribute access, merges,
etc.) from a SQL call or from another already SQL-derived name. Formatting
helpers (`money`, `pct`, `number`, `period_delta`, `int`, `str`, `float`,
`round`, `len`) never count as data sources on their own.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

SQL_METHOD_NAMES = {"query", "scalar", "previous_query", "previous_scalar"}
KPI_CALL_NAMES = {"kpis", "_executive_kpis"}
FORMATTING_NAMES = {"money", "pct", "number", "period_delta", "int", "str", "float", "round", "len", "f"}


@dataclass(frozen=True)
class Violation:
    file: str
    label: str
    detail: str


def _is_sql_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in SQL_METHOD_NAMES


def _calls_function(node: ast.AST, names: set[str]) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in names:
            return True
    return False


def _passes_ctx(call: ast.Call) -> bool:
    """`SomeCollaborator(ctx)` / `SomeCollaborator(ctx=ctx)` — a helper object built from the
    page's SQLContext, whose own methods are assumed to query SQL (verified per-module by audit)."""
    args = list(call.args) + [kw.value for kw in call.keywords]
    return any(isinstance(a, ast.Name) and a.id == "ctx" for a in args)


def _touches_sql(node: ast.AST, sql_derived: set[str], sql_functions: set[str]) -> bool:
    for sub in ast.walk(node):
        if _is_sql_call(sub):
            return True
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in sql_functions:
            return True
        if isinstance(sub, ast.Call) and _passes_ctx(sub):
            return True
        if isinstance(sub, ast.Name) and sub.id in sql_derived:
            return True
    return False


def _assign_targets(node: ast.AST) -> list[str]:
    names = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            names.append(sub.id)
    return names


def _sql_touching_functions(module: ast.Module) -> set[str]:
    """Module-level functions whose body directly issues a SQL query (e.g. helpers like _prepare_players)."""
    found = set()
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if _is_sql_call(sub):
                    found.add(node.name)
                    break
    return found


def _kpi_items(call: ast.Call) -> list[tuple[ast.AST, ast.AST]]:
    """Extract (label_node, value_node) pairs from a kpis([...])/_executive_kpis([...]) call."""
    if not call.args or not isinstance(call.args[0], ast.List):
        return []
    items = []
    for element in call.args[0].elts:
        if isinstance(element, ast.Tuple) and len(element.elts) >= 2:
            items.append((element.elts[0], element.elts[1]))
        elif isinstance(element, ast.Dict):
            pairs = dict(zip(element.keys, element.values))
            label = next((v for k, v in pairs.items() if isinstance(k, ast.Constant) and k.value == "label"), None)
            value = next((v for k, v in pairs.items() if isinstance(k, ast.Constant) and k.value == "value"), None)
            if label is not None and value is not None:
                items.append((label, value))
    return items


def _names_in(node: ast.AST) -> set[str]:
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name)}


def _iter_statements_in_order(stmts: list[ast.stmt]):
    """Yield every statement in program order, recursing into compound-statement bodies."""
    for stmt in stmts:
        yield stmt
        for field in ("body", "orelse", "finalbody"):
            nested = getattr(stmt, field, None)
            if nested:
                yield from _iter_statements_in_order(nested)
        for handler in getattr(stmt, "handlers", []):
            yield from _iter_statements_in_order(handler.body)


def _process_function(func: ast.FunctionDef, sql_functions: set[str], path: Path) -> list[Violation]:
    violations: list[Violation] = []
    sql_derived: set[str] = set()
    for stmt in _iter_statements_in_order(func.body):
        if isinstance(stmt, ast.Assign):
            if _touches_sql(stmt.value, sql_derived, sql_functions):
                sql_derived.update(_assign_targets(stmt))
        elif isinstance(stmt, ast.For):
            # `for col, item in zip(cols, items):` — propagate SQL-derivedness onto loop targets.
            if _touches_sql(stmt.iter, sql_derived, sql_functions):
                sql_derived.update(_assign_targets(stmt.target))
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Name) and call.func.id in KPI_CALL_NAMES:
                for label_node, value_node in _kpi_items(call):
                    if not (isinstance(label_node, ast.Constant) and isinstance(label_node.value, str)):
                        continue
                    label = label_node.value
                    if not _touches_sql(value_node, sql_derived, sql_functions):
                        names = sorted(_names_in(value_node) - FORMATTING_NAMES)
                        detail = f"value expression has no SQL-derived name(s) — found {names or 'a plain literal'}"
                        violations.append(Violation(file=str(path), label=label, detail=detail))
    return violations


def audit_module(path: Path) -> list[Violation]:
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(path))
    sql_functions = _sql_touching_functions(module)
    violations: list[Violation] = []
    for func in [n for n in module.body if isinstance(n, ast.FunctionDef)]:
        violations += _process_function(func, sql_functions, path)
    return violations


def audit_pages(pages_dir: Path, allowlist: set[str]) -> list[Violation]:
    violations = []
    for path in sorted(pages_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        for violation in audit_module(path):
            if violation.label in allowlist:
                continue
            violations.append(violation)
    return violations
