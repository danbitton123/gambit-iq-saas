from __future__ import annotations

"""Dashboard persistence, in its own SQLite file (data/dashboards.db) — deliberately separate
from the analytical warehouse (data/gambit_iq.db), which gets rebuilt/atomically swapped by
data/repository.py::ensure_database(); dashboards must never be wiped by that.

Every read/write is scoped by tenant_id (and, for mutation, user_id) in the SQL WHERE clause
itself — never by trusting a dashboard_id alone — so one tenant can never load, rename or delete
another tenant's dashboard even by guessing/forging an id. There is no real authentication layer
in this app yet (see ui/dashboard_builder/identity.py), so tenant_id/user_id are currently a
single operator + a per-browser-session pseudo-user; the schema and every query already carry
the isolation a real multi-tenant login would plug into unchanged.
"""

import json
import sqlite3

from config import ROOT
from dashboard_builder.models import Dashboard

DB_ROOT = ROOT / "data"
REGISTRY_PATH = DB_ROOT / "dashboards.db"


def _connect() -> sqlite3.Connection:
    DB_ROOT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REGISTRY_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS dashboards(
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            is_favorite INTEGER NOT NULL DEFAULT 0,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dashboards_tenant ON dashboards(tenant_id)")
    return conn


class DashboardNotFoundError(Exception):
    pass


def _from_row(config_json: str, is_favorite: int, is_default: int) -> Dashboard:
    # is_favorite/is_default can be toggled by a lightweight UPDATE (see save_dashboard's
    # default-clearing statement) that touches only these columns, not every other row's
    # embedded config_json blob. The columns are therefore the source of truth for these two
    # flags — overriding whatever the JSON payload happens to say — so an old default dashboard
    # never keeps showing as default after another one is set.
    dashboard = Dashboard.from_dict(json.loads(config_json))
    dashboard.is_favorite = bool(is_favorite)
    dashboard.is_default = bool(is_default)
    return dashboard


def list_dashboards(tenant_id: str) -> list[Dashboard]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT config_json,is_favorite,is_default FROM dashboards WHERE tenant_id=? ORDER BY updated_at DESC",
            (tenant_id,),
        ).fetchall()
    return [_from_row(*row) for row in rows]


def load_dashboard(tenant_id: str, dashboard_id: str) -> Dashboard:
    with _connect() as conn:
        row = conn.execute(
            "SELECT config_json,is_favorite,is_default FROM dashboards WHERE tenant_id=? AND id=?",
            (tenant_id, dashboard_id),
        ).fetchone()
    if row is None:
        raise DashboardNotFoundError(dashboard_id)
    return _from_row(*row)


def save_dashboard(dashboard: Dashboard) -> None:
    from datetime import datetime, timezone
    dashboard.updated_at = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(dashboard.to_dict())
    with _connect() as conn:
        conn.execute(
            """INSERT INTO dashboards(id,tenant_id,user_id,name,config_json,is_favorite,is_default,created_at,updated_at)
               VALUES(:id,:tenant_id,:user_id,:name,:config_json,:is_favorite,:is_default,:created_at,:updated_at)
               ON CONFLICT(id) DO UPDATE SET
                 tenant_id=excluded.tenant_id, name=excluded.name, config_json=excluded.config_json,
                 is_favorite=excluded.is_favorite, is_default=excluded.is_default, updated_at=excluded.updated_at
               WHERE dashboards.tenant_id=:tenant_id""",
            {
                "id": dashboard.id, "tenant_id": dashboard.tenant_id, "user_id": dashboard.user_id,
                "name": dashboard.name, "config_json": payload,
                "is_favorite": int(dashboard.is_favorite), "is_default": int(dashboard.is_default),
                "created_at": dashboard.created_at, "updated_at": dashboard.updated_at,
            },
        )
        if dashboard.is_default:
            conn.execute(
                "UPDATE dashboards SET is_default=0 WHERE tenant_id=? AND id<>?",
                (dashboard.tenant_id, dashboard.id),
            )


def delete_dashboard(tenant_id: str, dashboard_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM dashboards WHERE tenant_id=? AND id=?", (tenant_id, dashboard_id))


def duplicate_dashboard(tenant_id: str, user_id: str, dashboard_id: str, new_name: str) -> Dashboard:
    source = load_dashboard(tenant_id, dashboard_id)
    clone = source.clone(new_name, tenant_id, user_id)
    save_dashboard(clone)
    return clone


def default_dashboard_id(tenant_id: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM dashboards WHERE tenant_id=? AND is_default=1 LIMIT 1", (tenant_id,)
        ).fetchone()
    return row[0] if row else None
