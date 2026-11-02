"""FastAPI application: all /api routes, CORS, and (optionally) the frontend files."""

import io
import shutil
import threading
import time
import traceback
import uuid
import zipfile
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .classification import MODES, SURFACES, project_orientation
from .config import (
    APP_VERSION,
    CORS_ORIGINS,
    DEFAULT_CLOUD_PCT,
    DEFAULT_LANE_PARAMS,
    FRONTEND_DIR,
    GEE_PROJECT,
    GOOGLE_MAPS_API_KEY,
    KEEP_ONLY_LATEST_PROJECT,
    NEAREST_SEARCH_DAYS,
    PROJECTS_DIR,
    SERVE_FRONTEND,
)
from .lanes import LaneParams, run_lane_pipeline
from .ndwi import check_s2_dates, ndwi_run_id, ndwi_task
from .roughness import compute_roughness_report
from .storage import _RUN_RE, delete_other_projects, list_runs, project_dir, zip_folder_response
from .tasks import EXECUTOR, TASKS
from .utils import now_iso, read_json, write_json


app = FastAPI(title="Road Roughness Platform", version=APP_VERSION)


@app.middleware("http")
async def json_errors(request, call_next):
    """Unexpected errors come back as JSON (with CORS headers, because the CORS
    middleware below wraps this one) instead of a bare 500 the browser hides
    behind "Failed to fetch"."""
    try:
        return await call_next(request)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"detail": f"Server error: {e}"}, status_code=500)


# The page may also be opened as a file or from another local port and still
# call http://127.0.0.1:8000, so allow cross-origin requests (local tool).
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class NdwiRequest(BaseModel):
    start: str
    end: str
    cloud: int = DEFAULT_CLOUD_PCT


class RoughnessRequest(BaseModel):
    run_id: Optional[str] = None       # empty -> latest finished NDWI image set
    mode: str = "up_to_down"
    surface: str = "Bituminous"


def _parse_range(start: str, end: str, cloud: int):
    try:
        s, e = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise HTTPException(400, "Dates must be in YYYY-MM-DD format.")
    if e < s:
        raise HTTPException(400, "End date is before the start date.")
    if s < date(2017, 3, 28):
        raise HTTPException(400, "Sentinel-2 surface reflectance starts on 2017-03-28.")
    if e > date.today():
        raise HTTPException(400, "End date is in the future.")
    if not 1 <= cloud <= 100:
        raise HTTPException(400, "Cloud limit must be between 1 and 100 %.")
    return s, e


_TILE_SESSIONS = {}


_TILE_LOCK = threading.Lock()


def google_tile_session(kind: str):
    """Session token for Google's Map Tiles API (2D satellite tiles), cached until
    an hour before it expires. kind: "satellite" or "hybrid" (with road labels)."""
    with _TILE_LOCK:
        cached = _TILE_SESSIONS.get(kind)
        if cached and cached["expiry"] - time.time() > 3600:
            return cached
        body = {"mapType": "satellite", "language": "en-US", "region": "IN"}
        if kind == "hybrid":
            body["layerTypes"] = ["layerRoadmap"]
        r = requests.post("https://tile.googleapis.com/v1/createSession",
                          params={"key": GOOGLE_MAPS_API_KEY}, json=body, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code} {r.text[:200]}")
        js = r.json()
        sess = {"session": js["session"], "expiry": float(js.get("expiry") or time.time() + 86400)}
        _TILE_SESSIONS[kind] = sess
        return sess


@app.get("/api/map-tiles")
def map_tiles():
    if not GOOGLE_MAPS_API_KEY:
        return {"provider": "esri", "reason": "no_key"}
    try:
        layers = {}
        for kind in ("satellite", "hybrid"):
            sess = google_tile_session(kind)["session"]
            layers[kind] = {"session": sess,
                            "url": f"https://tile.googleapis.com/v1/2dtiles/{{z}}/{{x}}/{{y}}"
                                   f"?session={sess}&key={GOOGLE_MAPS_API_KEY}"}
        return {"provider": "google", "key": GOOGLE_MAPS_API_KEY, "layers": layers}
    except Exception as e:
        print(f"   Google Map Tiles session failed: {e}", flush=True)
        return {"provider": "esri", "reason": f"Google Map Tiles API session failed ({e})."}


@app.get("/api/config")
def get_config():
    return {"version": APP_VERSION, "defaults": DEFAULT_LANE_PARAMS, "cloud": DEFAULT_CLOUD_PCT,
            "surfaces": list(SURFACES), "modes": {k: v[1] for k, v in MODES.items()},
            "gee_project": GEE_PROJECT, "nearest_search_days": NEAREST_SEARCH_DAYS}


@app.get("/api/projects")
def list_projects():
    out = []
    for d in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        f = d / "project.json"
        if f.exists():
            p = read_json(f)
            out.append({"id": p["id"], "name": p["name"], "created": p["created"],
                        "length_m": p["summary"]["length_m"],
                        "chainage_start_km": p["summary"]["chainage_start_km"]})
    return out


@app.post("/api/projects")
def create_project(
    kml: UploadFile = File(...),
    name: str = Form(""),
    chainage_start_km: float = Form(...),
    median_offset_m: float = Form(...),
    lane_count: int = Form(...),
    lane_width_m: float = Form(DEFAULT_LANE_PARAMS["lane_width_m"]),
    bin_km: float = Form(DEFAULT_LANE_PARAMS["bin_km"]),
    interval_m: float = Form(DEFAULT_LANE_PARAMS["interval_m"]),
):
    if lane_count not in (2, 4, 6):
        raise HTTPException(400, "Lanes must be 2, 4 or 6.")
    if not 0.5 <= interval_m <= 50:
        raise HTTPException(400, "Interval must be between 0.5 and 50 m.")
    if median_offset_m < 0 or not 0 < lane_width_m <= 10:
        raise HTTPException(400, "Median offset must be >= 0 and lane width between 0 and 10 m.")
    bin_m = bin_km * 1000.0
    if bin_m < interval_m or abs(bin_m / interval_m - round(bin_m / interval_m)) > 1e-6:
        raise HTTPException(400, "Bin length must be a whole multiple of the interval "
                                 "(e.g. 0.100 km with 5 m).")

    raw = kml.file.read()
    fname = kml.filename or "median_line.kml"
    if fname.lower().endswith(".kmz"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                members = [m for m in zf.namelist() if m.lower().endswith(".kml")]
                if not members:
                    raise ValueError
                raw = zf.read("doc.kml" if "doc.kml" in members else members[0])
        except Exception:
            raise HTTPException(400, "The KMZ does not contain a KML file.")
    elif not fname.lower().endswith(".kml"):
        raise HTTPException(400, "Upload a .kml or .kmz file.")
    if KEEP_ONLY_LATEST_PROJECT and TASKS.any_active("ndwi"):
        raise HTTPException(409, "NDWI images are still being generated for the current project. "
                                 "Wait until they finish, then save the new project.")

    pid = uuid.uuid4().hex[:10]
    pdir = PROJECTS_DIR / pid
    (pdir / "input").mkdir(parents=True)
    kml_path = pdir / "input" / "median_line.kml"
    kml_path.write_bytes(raw)

    params = LaneParams(chainage_start_km=chainage_start_km, interval_m=interval_m,
                        median_offset_m=median_offset_m, lane_count=lane_count,
                        lane_width_m=lane_width_m, bin_km=bin_km)
    try:
        summary = run_lane_pipeline(pdir, kml_path, params)
    except Exception as e:
        shutil.rmtree(pdir, ignore_errors=True)
        traceback.print_exc()
        raise HTTPException(400, f"Could not process the KML: {e}")

    aoi = summary.pop("aoi_line")
    proj = {"id": pid, "name": name.strip() or Path(fname).stem, "source_file": fname,
            "created": now_iso(), "params": asdict(params), "summary": summary,
            "lane_tags": summary["lane_tags"], "aoi_line": aoi}
    write_json(pdir / "project.json", proj)
    if KEEP_ONLY_LATEST_PROJECT:
        delete_other_projects(pid)
    return get_project(pid)


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    pdir = project_dir(pid)
    proj = read_json(pdir / "project.json")
    proj.pop("aoi_line", None)
    proj["summary"]["orientation"] = project_orientation(pdir, proj)
    reports = []
    rdir = pdir / "reports"
    if rdir.is_dir():
        for f in sorted(rdir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            reports.append({"name": f.name, "url": f"/api/projects/{pid}/files/reports/{f.name}"})
    active = TASKS.active(pid, "ndwi")
    return {"project": proj, "runs": list_runs(pid, pdir), "reports": reports,
            "active_task": active["id"] if active else None,
            "kml_zip_url": f"/api/projects/{pid}/kml-zip"}


@app.get("/api/projects/{pid}/geojson")
def get_geojson(pid: str):
    return read_json(project_dir(pid) / "kml_output" / "preview.geojson")


@app.get("/api/projects/{pid}/kml-zip")
def get_kml_zip(pid: str):
    pdir = project_dir(pid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(pdir / "input" / "median_line.kml", "KML_output/median_line.kml")
        for path in sorted((pdir / "kml_output").rglob("*")):
            if path.is_file() and path.suffix != ".geojson":
                zf.write(path, f"KML_output/{path.relative_to(pdir / 'kml_output').as_posix()}")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="KML_output_{pid}.zip"'})


@app.get("/api/projects/{pid}/s2-dates")
def get_s2_dates(pid: str, start: str, end: str, cloud: int = DEFAULT_CLOUD_PCT):
    pdir = project_dir(pid)
    s, e = _parse_range(start, end, cloud)
    try:
        return check_s2_dates(read_json(pdir / "project.json")["aoi_line"], s, e, cloud)
    except RuntimeError as ex:
        raise HTTPException(503, str(ex))
    except Exception as ex:
        traceback.print_exc()
        raise HTTPException(502, f"Sentinel-2 date check failed: {ex}")


@app.post("/api/projects/{pid}/ndwi")
def start_ndwi(pid: str, req: NdwiRequest):
    project_dir(pid)
    _parse_range(req.start, req.end, req.cloud)
    if TASKS.active(pid, "ndwi"):
        raise HTTPException(409, "NDWI images are already being generated for this project.")
    run_id = ndwi_run_id(req.start, req.end, req.cloud)
    tid = TASKS.create("ndwi", pid, {"run_id": run_id})
    EXECUTOR.submit(ndwi_task, tid, pid, req.start, req.end, req.cloud)
    return {"task_id": tid, "run_id": run_id}


@app.get("/api/tasks/{tid}")
def get_task(tid: str):
    t = TASKS.get(tid)
    if not t:
        raise HTTPException(404, "Unknown task (the server may have restarted).")
    return t


@app.get("/api/projects/{pid}/ndwi/{run_id}/zip")
def get_ndwi_zip(pid: str, run_id: str):
    pdir = project_dir(pid)
    run_dir = pdir / "ndwi" / run_id
    if not _RUN_RE.match(run_id) or not run_dir.is_dir():
        raise HTTPException(404, "Unknown NDWI image set.")
    return zip_folder_response(run_dir, f"NDWI_{run_id}", f"NDWI_{run_id}.zip",
                               only={"images", "down_to_up_images", "up_to_down_images"})


@app.post("/api/projects/{pid}/roughness")
def post_roughness(pid: str, req: RoughnessRequest):
    return compute_roughness_report(pid, req.run_id, req.mode, req.surface)


@app.get("/api/projects/{pid}/files/{rel:path}")
def get_file(pid: str, rel: str):
    base = project_dir(pid).resolve()
    target = (base / rel).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(404, "File not found.")
    return FileResponse(target, filename=target.name)


# ---- frontend (optional): serve ../frontend at "/" so one server is enough ----
if SERVE_FRONTEND and FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
