# Road Roughness Platform

Draw or upload a median line, generate lane KMLs, download Sentinel-2 NDWI images
for every 100 m bin, and produce RI / IRI results at 100 m and 10 m (Excel, PDF, JSON).

```
road_roughness/
├── backend/                  Python API (FastAPI)
│   ├── .env                  settings (edit this)  ·  .env.example = template
│   ├── requirements.txt
│   ├── setup_backend.bat     creates .venv and installs packages (once)
│   ├── run_backend.bat       starts the API
│   ├── main.py               entry point
│   ├── app/
│   │   ├── config.py         reads .env
│   │   ├── api.py            all /api routes, CORS, serves the frontend (optional)
│   │   ├── lanes.py          step 1: median line -> lane KMLs + Excels
│   │   ├── ndwi.py           step 2: Sentinel-2 NDWI images + image stages 2-6
│   │   ├── roughness.py      step 3: RI / IRI at 100 m and 10 m
│   │   ├── classification.py RI/IRI bands, pavement tables, road direction
│   │   ├── reports.py        Excel + PDF writers
│   │   ├── storage.py        project folders on disk
│   │   ├── tasks.py          background jobs
│   │   └── utils.py
│   └── storage/projects/     your projects (KMLs, NDWI images, reports)
└── frontend/                 web page (no build step)
    ├── index.html
    ├── css/styles.css
    ├── js/config.js          frontend settings: backend address (API_BASE)
    ├── js/app.js
    ├── vendor/leaflet/       map library (works offline)
    └── run_frontend.bat      serves the page on http://127.0.0.1:5500
```

## First-time setup (Windows)

1. Install Python 3.10 or newer (tick "Add python.exe to PATH").
2. Double-click `backend\setup_backend.bat`. It creates the virtual environment
   `backend\.venv`, installs `requirements.txt`, and creates `backend\.env` if missing.
3. Earth Engine login is stored per Windows user, so a PC that already ran the
   old version needs nothing more. On a new PC run once:
   `backend\.venv\Scripts\earthengine authenticate`

## Run

**One window (simplest):** double-click `backend\run_backend.bat`, then open
<http://127.0.0.1:8000/>. The backend serves the page too (`SERVE_FRONTEND=true`).

**Frontend and backend separately:** start `backend\run_backend.bat`, then
`frontend\run_frontend.bat`, and open <http://127.0.0.1:5500/>. The page calls the
backend address in `frontend\js\config.js`.

API documentation: <http://127.0.0.1:8000/docs>

## Settings

`backend\.env` (restart the backend after editing):

| Setting | Meaning |
|---|---|
| `RR_HOST`, `RR_PORT` | where the API listens (default 127.0.0.1:8000) |
| `CORS_ORIGINS` | web origins allowed to call the API (`*` = any) |
| `SERVE_FRONTEND`, `FRONTEND_DIR` | also serve the frontend folder at `/` |
| `RR_STORAGE` | data folder (default `storage`) |
| `KEEP_ONLY_LATEST_PROJECT` | saving a new project deletes the previous one |
| `GEE_PROJECT` | Google Earth Engine project ID |
| `DEFAULT_CLOUD_PCT` | Sentinel-2 cloud limit (%) |
| `NEAREST_SEARCH_DAYS` | how far to look for the nearest capture |
| `NDWI_WORKERS` | parallel Earth Engine downloads |
| `GOOGLE_MAPS_API_KEY` | optional Map Tiles API key |
| `DEFAULT_*` | defaults shown in the web form |

`frontend\js\config.js`: `API_BASE`, the backend address used when the page is not
served by the backend itself.

Company logo: put `logo.png` in the `frontend` folder (it appears top right).

If you change the backend's port or host, update `API_BASE` in `frontend\js\config.js` too.
