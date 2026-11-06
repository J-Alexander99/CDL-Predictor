"""Central configuration: paths, scraping etiquette and model parameters."""
from __future__ import annotations

import os
from pathlib import Path

# Project root: $CDL_ROOT, else the source checkout this package lives in. A non-editable install
# (site-packages) has no data/ next to it, so fall back to the working directory.
_PKG_ROOT = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ["CDL_ROOT"]) if os.environ.get("CDL_ROOT") else (
    _PKG_ROOT if (_PKG_ROOT / "pyproject.toml").exists() else Path.cwd()
)

# Committed state (git is the database of record)
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"  # one gzipped JSON per completed match
META_DIR = DATA_DIR / "meta"  # catalog of seasons/events/teams, event index
PREDICTIONS_DIR = DATA_DIR / "predictions"  # immutable prediction ledger

# Rebuilt every run (gitignored)
BUILD_DIR = ROOT / "build"
DB_PATH = BUILD_DIR / "cdl.db"
CACHE_DIR = BUILD_DIR / "http_cache"
SITE_DIR = ROOT / "site"
GRAPHICS_DIR = SITE_DIR / "graphics"

# Source site
BASE_URL = "https://breakingpoint.gg"
USER_AGENT = os.environ.get(
    "CDL_USER_AGENT",
    "Mozilla/5.0 (compatible; CDL-Predictor/3.0; +https://github.com/J-Alexander99/CDL-Predictor)",
)
REQUEST_INTERVAL_S = float(os.environ.get("CDL_REQUEST_INTERVAL", "1.0"))  # polite throttle
REQUEST_TIMEOUT_S = 30.0

# Breaking Point division id for the Call of Duty League (CDC/Challengers use other ids)
CDL_DIVISION_ID = 3
# Seasons we model. Earlier seasons exist on the site but are different games/rosters.
DEFAULT_SEASONS = (2024, 2025, 2026, 2027)

# Prediction policy
PREDICTION_HORIZON_H = 72  # predict matches starting within this many hours
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SITE_URL = os.environ.get("CDL_SITE_URL", "")


def ensure_dirs() -> None:
    for d in (RAW_DIR, META_DIR, PREDICTIONS_DIR, BUILD_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
