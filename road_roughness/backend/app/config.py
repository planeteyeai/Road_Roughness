"""Settings. Values come from backend/.env (see .env.example); real environment
variables with the same name win. Paths in .env are relative to the backend folder."""
import os
from pathlib import Path

import numpy as np
from pyproj import Geod

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path):
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


_load_env_file(BACKEND_DIR / ".env")


def _env(key, default):
    return os.environ.get(key, default)


def _env_bool(key, default):
    return str(_env(key, str(default))).strip().lower() in ("1", "true", "yes", "on")


def _env_path(key, default):
    p = Path(_env(key, default))
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


APP_VERSION = "1.6"          # the frontend checks this to spot an old backend still running

# ---- server ----
HOST = _env("RR_HOST", "127.0.0.1")
# Railway sets PORT env var, use it if available, otherwise use RR_PORT
PORT = int(_env("PORT", _env("RR_PORT", "8000")))
CORS_ORIGINS = [o.strip() for o in _env("CORS_ORIGINS", "*").split(",") if o.strip()]
SERVE_FRONTEND = _env_bool("SERVE_FRONTEND", True)          # also serve ../frontend at "/"
FRONTEND_DIR = _env_path("FRONTEND_DIR", "../frontend")

# ---- storage ----
STORAGE_ROOT = _env_path("RR_STORAGE", "storage")
PROJECTS_DIR = STORAGE_ROOT / "projects"
KEEP_ONLY_LATEST_PROJECT = _env_bool("KEEP_ONLY_LATEST_PROJECT", True)

# ---- Google Earth Engine / Sentinel-2 ----
GEE_PROJECT = _env("GEE_PROJECT", "arctic-hybrid-462806-c9")
S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
DEFAULT_CLOUD_PCT = int(_env("DEFAULT_CLOUD_PCT", "40"))     # CLOUDY_PIXEL_PERCENTAGE limit
NEAREST_SEARCH_DAYS = int(_env("NEAREST_SEARCH_DAYS", "90"))  # how far to look for the nearest capture
NDWI_WORKERS = int(_env("NDWI_WORKERS", "4"))                # parallel GEE downloads
OUTPUT_WIDTH = 1200                                          # NDWI JPG width (px)

# ---- optional Google Map Tiles API key (adds "(API key)" layers to the map) ----
GOOGLE_MAPS_API_KEY = _env("GOOGLE_MAPS_API_KEY", "")

# ---- defaults shown in the web form ----
DEFAULT_LANE_PARAMS = {
    "chainage_start_km": float(_env("DEFAULT_CHAINAGE_START_KM", "0.000")),
    "interval_m":        float(_env("DEFAULT_INTERVAL_M", "1.0")),
    "median_offset_m":   float(_env("DEFAULT_MEDIAN_OFFSET_M", "1.0")),
    "lane_count":        int(_env("DEFAULT_LANE_COUNT", "4")),
    "lane_width_m":      float(_env("DEFAULT_LANE_WIDTH_M", "3.40")),
    "bin_km":            float(_env("DEFAULT_BIN_KM", "0.100")),     # KML_MERGE_OFFSET_KM
}

# ---- fixed method constants (RI / IRI maths and chainage format; not settings) ----
CHAINAGE_DECIMALS = 3
RI_SAMPLE_POINTS = 41                                        # 0, 2.5, 5 ... 100 m for a 100 m bin
BLOCK_SIZE_M = 10.0                                          # 10 m sub-blocks inside each 100 m image
BLOCK_OFFSETS = np.arange(0, BLOCK_SIZE_M + 0.25, 0.25)      # 41 points: 0, 0.25 ... 10 m
GRAY_THRESHOLD = 200
LINE_SPACING_M = 0.10
IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp")
GEOD = Geod(ellps="WGS84")

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
