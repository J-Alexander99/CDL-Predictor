"""
Configuration settings for CDL Predictor
"""
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Scraping settings
HEADLESS_BROWSER = True
PAGE_LOAD_TIMEOUT = 10
REQUEST_DELAY = 2  # seconds between requests to be polite

# CDL URLs
CDL_BASE_URL = "https://www.breakingpoint.gg"
CDL_MATCHES_URL = f"{CDL_BASE_URL}/matches"

# Database
DB_PATH = DATA_DIR / "cdl_data.db"
