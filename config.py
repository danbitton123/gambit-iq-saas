from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

APP_NAME = "GAMBIT IQ"
APP_TAGLINE = "Revenue, Risk & Player Intelligence"
OPERATOR = os.getenv("GAMBIT_OPERATOR", "Gambit Demo Casino")
CURRENCY = os.getenv("GAMBIT_CURRENCY", "USD")
DB_PATH = ROOT / "data" / "gambit_iq.db"

COLORS = {
    "bg": "#050f1c",
    "panel": "#071c24",
    "panel_2": "#0a2730",
    "green": "#27d17f",
    "emerald": "#0e7d54",
    "gold": "#d9a72e",
    "cyan": "#26c6e5",
    "red": "#ff5b57",
    "orange": "#f59e42",
    "text": "#f4f7fb",
    "muted": "#8da3b4",
    "grid": "rgba(141,163,180,.14)",
}
