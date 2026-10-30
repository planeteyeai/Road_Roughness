#!/usr/bin/env python3
"""
road_roughness_app.py  —  Road Roughness Platform (single backend)
=====================================================================
Merges the three scripts into one FastAPI service + web page:

  STEP 1  Lane KMLs        (was: Full Road Pipeline / KML creation script)
          Draw the median line on the satellite map in the web page (or upload
          a KML / KMZ) -> 5 m chainage, Median_LHS / Median_RHS
          offsets, lane edges LHS/RHS L1..L3, 100 m bin KMLs, merge KMLs and
          the Excels (LHS_L1.xlsx, LHS_L2.xlsx, RHS_L1.xlsx, RHS_L2.xlsx ...).

  STEP 2  Sentinel-2 NDWI  (was: Roughness_image_process.py, Stages 1-6)
          Cloud cover < 40 %. Date check against the Sentinel-2 archive (shows the nearest
          captures when the chosen range has none), NDWI JPG per lane bin
          KML, rotation / alignment. Both down_to_up_images and
          up_to_down_images are stored, so the direction is picked in step 3.

  STEP 3  RI / IRI report  (was: Roughness_ri_calc.py, Stage 7)
          100 m rows AND 10 m sub-blocks (no weather), from the latest NDWI
          image set. From/To lat-long come from the Step-1 lane Excels.
          Output: Excel + PDF for each resolution.

Everything is stored under  ./storage/projects/<project_id>/

Run
---
    pip install -r requirements.txt
    earthengine authenticate              # once per machine
    python road_roughness_app.py          # then open http://127.0.0.1:8000
                                          # API docs: http://127.0.0.1:8000/docs

Environment overrides: GEE_PROJECT, RR_STORAGE, NDWI_WORKERS, RR_HOST, RR_PORT
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import threading
import time
import traceback
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.dom import minidom

import cv2
import ee
import numpy as np
import pandas as pd
import requests
import simplekml
from geopy import Point
from geopy.distance import geodesic
from PIL import Image
from pyproj import Geod
from shapely.geometry import Polygon
from shapely.ops import unary_union

from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


# ============================================================
# CONFIG
# ============================================================
BASE_DIR     = Path(__file__).resolve().parent
STORAGE_ROOT = Path(os.environ.get("RR_STORAGE", str(BASE_DIR / "storage")))
PROJECTS_DIR = STORAGE_ROOT / "projects"
STATIC_DIR   = BASE_DIR / "static"

APP_VERSION         = "1.5"     # the web page checks this to spot an old backend still running
GEE_PROJECT         = os.environ.get("GEE_PROJECT", "arctic-hybrid-462806-c9")

# Google satellite imagery for the web map (optional). Google only allows its
# imagery through the Map Tiles API: create an API key in Google Cloud with the
# "Map Tiles API" enabled and paste it here (or set GOOGLE_MAPS_API_KEY).
# Without a key the map uses Esri imagery.
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

KEEP_ONLY_LATEST_PROJECT = True   # saving a new project deletes the previous ones
S2_COLLECTION       = "COPERNICUS/S2_SR_HARMONIZED"
DEFAULT_CLOUD_PCT   = 40      # Sentinel-2 CLOUDY_PIXEL_PERCENTAGE < 40
NEAREST_SEARCH_DAYS = 90        # how far either side to look for the nearest capture
NDWI_WORKERS        = int(os.environ.get("NDWI_WORKERS", "4"))   # parallel GEE downloads
OUTPUT_WIDTH        = 1200      # NDWI JPG width (px)

CHAINAGE_DECIMALS = 3

# Defaults shown in the web form (same values as the original script)
DEFAULT_LANE_PARAMS = {
    "chainage_start_km": 0.000,
    "interval_m":        1.0,
    "median_offset_m":   1.0,
    "lane_count":        4,
    "lane_width_m":      3.40,
    "bin_km":            0.100,     # KML_MERGE_OFFSET_KM
}

# RI constants (from Roughness_ri_calc.py)
RI_SAMPLE_POINTS = 41           # 0, 2.5, 5 ... 100 m for a 100 m bin
BLOCK_SIZE_M     = 10.0         # 10 m sub-blocks inside each 100 m image
BLOCK_OFFSETS    = np.arange(0, BLOCK_SIZE_M + 0.25, 0.25)   # 41 points: 0, 0.25 ... 10 m
GRAY_THRESHOLD   = 200
LINE_SPACING_M   = 0.10

IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp")

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
GEOD = Geod(ellps="WGS84")


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# ============================================================
# PART 1 — LANE KML PIPELINE   (was: Full Road Pipeline)
# ============================================================
@dataclass
class LaneParams:
    chainage_start_km: float
    interval_m: float
    median_offset_m: float
    lane_count: int
    lane_width_m: float
    bin_km: float


def layer_count(lane_count: int) -> int:
    """2 -> L1 only, 4 -> L1+L2, 6 -> L1+L2+L3 (per side)."""
    if lane_count < 2:
        return 0
    return 1 + (lane_count >= 4) + (lane_count >= 6)


def _node_text(node) -> str:
    return "".join(c.nodeValue for c in node.childNodes
                   if c.nodeType in (c.TEXT_NODE, c.CDATA_SECTION_NODE)).strip()


def read_linestring_from_kml(kml_path: Path):
    """First LineString in the KML (falls back to the first <coordinates>)."""
    doc = minidom.parse(str(kml_path))
    nodes = []
    for ls in doc.getElementsByTagName("LineString"):
        nodes.extend(ls.getElementsByTagName("coordinates"))
    if not nodes:
        nodes = list(doc.getElementsByTagName("coordinates"))
    if not nodes:
        raise ValueError("No <coordinates> found in the KML.")
    out = []
    for tok in _node_text(nodes[0]).split():
        parts = tok.split(",")
        if len(parts) >= 2:
            out.append((float(parts[0]), float(parts[1])))
    if len(out) < 2:
        raise ValueError("The median line needs at least 2 points.")
    return out


def interpolate_geodesic_points(line_coords, interval_m):
    """Point every interval_m along the line (same method as the original;
    the segment index is clamped so the last point can't overrun the list)."""
    cum = [0.0]
    for (lon1, lat1), (lon2, lat2) in zip(line_coords[:-1], line_coords[1:]):
        cum.append(cum[-1] + GEOD.line_length([lon1, lon2], [lat1, lat2]))
    total_len = cum[-1]
    if total_len <= 0:
        return [], 0.0
    pts, cur, i = [], 0.0, 0
    last_seg = len(line_coords) - 2
    while cur <= total_len + 1e-6:
        while i < last_seg and cum[i + 1] < cur - 1e-9:
            i += 1
        s, e = cum[i], cum[i + 1]
        frac = 0.0 if e == s else min(1.0, max(0.0, (cur - s) / (e - s)))
        lon1, lat1 = line_coords[i]
        lon2, lat2 = line_coords[i + 1]
        pts.append((lon1 + frac * (lon2 - lon1), lat1 + frac * (lat2 - lat1)))
        cur += interval_m
    return pts, total_len


def make_chainages(start_km, n_points, step_m):
    step_km = step_m / 1000.0
    return [round(start_km + i * step_km, CHAINAGE_DECIMALS) for i in range(n_points)]


def calculate_bearing(A: Point, B: Point):
    lat1, lon1 = math.radians(A.latitude), math.radians(A.longitude)
    lat2, lon2 = math.radians(B.latitude), math.radians(B.longitude)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def offset_point(lat, lon, offset_meters, side, prev_pt=None, next_pt=None):
    current = Point(latitude=lat, longitude=lon)
    if prev_pt and next_pt:
        b1 = calculate_bearing(prev_pt, current)
        b2 = calculate_bearing(current, next_pt)
        x = math.cos(math.radians(b1)) + math.cos(math.radians(b2))
        y = math.sin(math.radians(b1)) + math.sin(math.radians(b2))
        bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    elif next_pt:
        bearing = calculate_bearing(current, next_pt)
    elif prev_pt:
        bearing = calculate_bearing(prev_pt, current)
    else:
        bearing = 0.0
    b = (bearing - 90) % 360 if side == "left" else (bearing + 90) % 360
    dest = geodesic(meters=offset_meters).destination((lat, lon), b)
    return dest.latitude, dest.longitude


def offset_line(points_lonlat, offset_m, side):
    """Offset every point of a line sideways (prev/next taken from the same line)."""
    pts = [Point(latitude=lat, longitude=lon) for lon, lat in points_lonlat]
    out = []
    for i, p in enumerate(pts):
        prev_pt = pts[i - 1] if i > 0 else None
        next_pt = pts[i + 1] if i < len(pts) - 1 else None
        lat, lon = offset_point(p.latitude, p.longitude, offset_m, side, prev_pt, next_pt)
        out.append((lon, lat))
    return out


def edge_frame(chainages, pts_lonlat, step_km):
    return pd.DataFrame({
        "Chainage Start": [round(c, CHAINAGE_DECIMALS) for c in chainages],
        "Chainage End":   [round(c + step_km, CHAINAGE_DECIMALS) for c in chainages],
        "Latitude":       [lat for lon, lat in pts_lonlat],
        "Longitude":      [lon for lon, lat in pts_lonlat],
    })


def strip_polygons(inner, outer, chainages, step_km):
    """5 m polygons between two edge lines: (chainage_start, chainage_end, coords)."""
    polys = []
    for i in range(len(inner) - 1):
        cs = chainages[i]
        ce = round(cs + step_km, CHAINAGE_DECIMALS)
        polys.append((cs, ce, [inner[i], inner[i + 1], outer[i + 1], outer[i], inner[i]]))
    return polys


def _outline_style():
    st = simplekml.Style()
    st.polystyle.fill = 0
    return st


def write_bin_kmls(polys, folder: Path, tag: str, p: LaneParams):
    """Group the 5 m polygons into bin_km bins -> one KML per bin."""
    folder.mkdir(parents=True, exist_ok=True)
    bin_m = round(p.bin_km * 1000.0, 6)
    bins = {}
    for cs, ce, coords in polys:
        rel_m = round((cs - p.chainage_start_km) * 1000.0, 3)
        bins.setdefault(int(math.floor(rel_m / bin_m + 1e-9)), []).append((cs, ce, coords))
    style = _outline_style()
    paths = []
    for b, items in sorted(bins.items()):
        s = p.chainage_start_km + b * p.bin_km
        e = s + p.bin_km
        kml = simplekml.Kml()
        for cs, ce, coords in items:
            pol = kml.newpolygon(name=f"Chainage_{cs:.{CHAINAGE_DECIMALS}f}_to_{ce:.{CHAINAGE_DECIMALS}f}_{tag}",
                                 outerboundaryis=coords)
            pol.style = style
        out = folder / f"Chainage_{s:.{CHAINAGE_DECIMALS}f}_to_{e:.{CHAINAGE_DECIMALS}f}_{tag}.kml"
        kml.save(str(out))
        paths.append(out)
    return paths


def write_merged_kml(named_polys, path: Path):
    kml = simplekml.Kml()
    style = _outline_style()
    for name, coords in named_polys:
        pol = kml.newpolygon(name=name, outerboundaryis=coords)
        pol.style = style
    kml.save(str(path))


def write_chainage_line_kml(chainages, pts, path: Path):
    kml = simplekml.Kml()
    line_style = simplekml.Style()
    line_style.linestyle.width = 3
    line_style.linestyle.color = simplekml.Color.white
    pt_style = simplekml.Style()
    pt_style.iconstyle.scale = 0.8
    pt_style.iconstyle.color = simplekml.Color.yellow
    for i in range(len(pts) - 1):
        s, e = chainages[i], chainages[i + 1]
        ln = kml.newlinestring(name=f"Chainage_{s:.{CHAINAGE_DECIMALS}f}_to_{e:.{CHAINAGE_DECIMALS}f}",
                               coords=[pts[i], pts[i + 1]])
        ln.style = line_style
        pt = kml.newpoint(name=f"CH {s:.{CHAINAGE_DECIMALS}f}", coords=[pts[i]])
        pt.style = pt_style
    pt = kml.newpoint(name=f"CH {chainages[-1]:.{CHAINAGE_DECIMALS}f}", coords=[pts[-1]])
    pt.style = pt_style
    kml.save(str(path))


def _downsample(seq, max_n):
    if len(seq) <= max_n:
        return list(seq)
    step = math.ceil(len(seq) / max_n)
    out = list(seq[::step])
    if out[-1] != seq[-1]:
        out.append(seq[-1])
    return out


def run_lane_pipeline(proj_dir: Path, kml_path: Path, p: LaneParams, log=print):
    out = proj_dir / "kml_output"
    if out.exists():
        shutil.rmtree(out)
    lhs_dir, rhs_dir = out / "LHS_KMLs", out / "RHS_KMLs"
    med_dir, xl_dir, merge_dir = out / "Median_KMLs", out / "Excels", out / "Merge_KMLs"
    for d in (lhs_dir, rhs_dir, med_dir, xl_dir, merge_dir):
        d.mkdir(parents=True, exist_ok=True)

    log("1) Reading median line & interpolating ...")
    line = read_linestring_from_kml(kml_path)
    centre, total_len = interpolate_geodesic_points(line, p.interval_m)
    if len(centre) < 2:
        raise ValueError("The median line is shorter than one interpolation interval.")
    chain = make_chainages(p.chainage_start_km, len(centre), p.interval_m)
    step_km = p.interval_m / 1000.0

    edge_frame(chain, centre, step_km).to_excel(xl_dir / "line_polygons_chainage.xlsx", index=False)
    write_chainage_line_kml(chain, centre, merge_dir / "line_polygons_chainage.kml")

    log(f"2) Median offsets ({p.median_offset_m} m each side) ...")
    edges = {("LHS", 0): offset_line(centre, p.median_offset_m, "left"),
             ("RHS", 0): offset_line(centre, p.median_offset_m, "right")}
    edge_frame(chain, edges[("LHS", 0)], step_km).to_excel(xl_dir / "Median_LHS.xlsx", index=False)
    edge_frame(chain, edges[("RHS", 0)], step_km).to_excel(xl_dir / "Median_RHS.xlsx", index=False)

    n_layers = layer_count(p.lane_count)
    log(f"3) Lane edges for {p.lane_count}-lane road ({n_layers} per side, {p.lane_width_m} m) ...")
    for side, sname in (("LHS", "left"), ("RHS", "right")):
        prev = edges[(side, 0)]
        for L in range(1, n_layers + 1):
            cur = offset_line(prev, p.lane_width_m, sname)
            edges[(side, L)] = cur
            edge_frame(chain, cur, step_km).to_excel(xl_dir / f"{side}_L{L}.xlsx", index=False)
            prev = cur

    log("4) Lane / combined / median bin KMLs ...")
    merged = {"LHS": [], "RHS": [], "Median": []}
    lane_tags, bins_per_lane = [], 0
    for side, side_dir in (("LHS", lhs_dir), ("RHS", rhs_dir)):
        for L in range(1, n_layers + 1):
            tag = f"{side}_L{L}"
            polys = strip_polygons(edges[(side, L - 1)], edges[(side, L)], chain, step_km)
            paths = write_bin_kmls(polys, side_dir / tag, tag, p)
            bins_per_lane = max(bins_per_lane, len(paths))
            lane_tags.append(tag)
            merged[side] += [(f"Chainage_{cs:.3f}_to_{ce:.3f}_{tag}", c) for cs, ce, c in polys]
        if n_layers >= 2:
            tag = f"{side}_L1_L2" if n_layers == 2 else f"{side}_L1_to_L{n_layers}"
            polys = strip_polygons(edges[(side, 0)], edges[(side, n_layers)], chain, step_km)
            write_bin_kmls(polys, side_dir / tag, tag, p)
            merged[side] += [(f"Chainage_{cs:.3f}_to_{ce:.3f}_{tag}", c) for cs, ce, c in polys]

    polys = strip_polygons(edges[("LHS", 0)], edges[("RHS", 0)], chain, step_km)
    write_bin_kmls(polys, med_dir / "Median", "Median", p)
    merged["Median"] = [(f"Chainage_{cs:.3f}_to_{ce:.3f}_Median", c) for cs, ce, c in polys]

    log("5) Merge KMLs ...")
    write_merged_kml(merged["LHS"], merge_dir / "LHS_merge.kml")
    write_merged_kml(merged["RHS"], merge_dir / "RHS_merge.kml")
    write_merged_kml(merged["Median"], merge_dir / "Median_merge.kml")

    # GeoJSON preview for the web map
    feats = [{"type": "Feature", "properties": {"name": "Centre line", "kind": "centre"},
              "geometry": {"type": "LineString", "coordinates": _downsample(centre, 1500)}}]
    for (side, L), pts in sorted(edges.items()):
        name = f"Median_{side}" if L == 0 else f"{side}_L{L}"
        feats.append({"type": "Feature",
                      "properties": {"name": name, "kind": "median" if L == 0 else side.lower()},
                      "geometry": {"type": "LineString", "coordinates": _downsample(pts, 1500)}})
    write_json(out / "preview.geojson", {"type": "FeatureCollection", "features": feats})

    return {
        "length_m": round(total_len, 1),
        "points": len(centre),
        "chainage_start_km": chain[0],
        "chainage_end_km": chain[-1],
        "layers_per_side": n_layers,
        "lane_tags": lane_tags,
        "bins_per_lane": bins_per_lane,
        "orientation": road_orientation(centre[0], centre[-1]),
        "aoi_line": [[round(x, 7), round(y, 7)] for x, y in _downsample(centre, 250)],
    }


# ============================================================
# PART 2 — SENTINEL-2 NDWI PIPELINE   (was: Roughness_image_process.py)
# ============================================================
_EE_LOCK = threading.Lock()
_EE_READY = False


def ee_init():
    global _EE_READY
    with _EE_LOCK:
        if _EE_READY:
            return
        
        # Check for service account key (for Vercel/serverless deployment)
        service_account_key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY")
        
        try:
            if service_account_key:
                # Parse service account JSON from environment variable
                import tempfile
                key_data = json.loads(service_account_key)
                
                # Write to temporary file for ee.Initialize
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(key_data, f)
                    key_file = f.name
                
                # Initialize with service account
                credentials = ee.ServiceAccountCredentials(
                    email=key_data['client_email'],
                    key_file=key_file
                )
                ee.Initialize(credentials=credentials, project=GEE_PROJECT)
                
                # Clean up temp file
                try:
                    os.unlink(key_file)
                except:
                    pass
            else:
                # Use default authentication (local development)
                ee.Initialize(project=GEE_PROJECT)
        except Exception as e:
            raise RuntimeError(
                f"Google Earth Engine could not start ({e}). "
                f"For local: Run `earthengine authenticate` once. "
                f"For Vercel: Set GEE_SERVICE_ACCOUNT_KEY environment variable with service account JSON. "
                f"Check that GEE_PROJECT='{GEE_PROJECT}' is registered for Earth Engine.") from e
        _EE_READY = True


def s2_collection(aoi, start_iso, end_excl_iso, cloud):
    return (ee.ImageCollection(S2_COLLECTION)
            .filterBounds(aoi).filterDate(start_iso, end_excl_iso)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud)))


def s2_capture_days(aoi, start_iso, end_excl_iso, cloud):
    """Sentinel-2 capture days touching the AOI: [{date, cloud, scenes}]."""
    col = s2_collection(aoi, start_iso, end_excl_iso, cloud)
    info = ee.Dictionary({"t": col.aggregate_array("system:time_start"),
                          "c": col.aggregate_array("CLOUDY_PIXEL_PERCENTAGE")}).getInfo()
    days = {}
    for t, c in zip(info.get("t") or [], info.get("c") or []):
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc).date().isoformat()
        e = days.setdefault(d, {"date": d, "cloud": float(c), "scenes": 0})
        e["scenes"] += 1
        e["cloud"] = min(e["cloud"], float(c))
    for e in days.values():
        e["cloud"] = round(e["cloud"], 1)
    return sorted(days.values(), key=lambda x: x["date"])


def check_s2_dates(aoi_line, start: date, end: date, cloud: int):
    ee_init()
    aoi = ee.Geometry.LineString(aoi_line)
    end_excl = end + timedelta(days=1)                     # end date is inclusive
    inside = s2_capture_days(aoi, start.isoformat(), end_excl.isoformat(), cloud)
    res = {"start": start.isoformat(), "end": end.isoformat(), "cloud": cloud,
           "available": bool(inside), "captures": inside,
           "nearest_before": [], "nearest_after": [], "search_days": NEAREST_SEARCH_DAYS}
    if not inside:
        around = s2_capture_days(aoi, (start - timedelta(days=NEAREST_SEARCH_DAYS)).isoformat(),
                                 (end_excl + timedelta(days=NEAREST_SEARCH_DAYS)).isoformat(), cloud)
        before = [d for d in around if d["date"] < start.isoformat()][-3:][::-1]
        after = [d for d in around if d["date"] > end.isoformat()][:3]
        for d in before:
            d["days_away"] = (start - date.fromisoformat(d["date"])).days
        for d in after:
            d["days_away"] = (date.fromisoformat(d["date"]) - end).days
        res["nearest_before"], res["nearest_after"] = before, after
    return res


# ---- Stage 1 helpers (verbatim logic) ----
def clean_image(arr, dot_threshold=60, bg_threshold=15):
    arr = arr.copy()
    h, w = arr.shape[:2]
    black_bg = ((arr[:, :, 0] < bg_threshold) &
                (arr[:, :, 1] < bg_threshold) &
                (arr[:, :, 2] < bg_threshold))
    arr[black_bg] = [255, 255, 255]
    brightness = arr[:, :, 0].astype(int) + arr[:, :, 1].astype(int) + arr[:, :, 2].astype(int)
    dark_coords = np.argwhere(brightness < dot_threshold * 3)
    for y, x in dark_coords:
        nb = arr[max(0, y - 3):min(h, y + 4), max(0, x - 3):min(w, x + 4)]
        nb_br = nb[:, :, 0].astype(int) + nb[:, :, 1].astype(int) + nb[:, :, 2].astype(int)
        good = nb_br >= dot_threshold * 3
        arr[y, x] = ([int(np.median(nb[:, :, 0][good])),
                      int(np.median(nb[:, :, 1][good])),
                      int(np.median(nb[:, :, 2][good]))]
                     if good.any() else [255, 255, 255])
    return arr


def tight_crop(arr, thr=240, margin=10):
    content = ~((arr[:, :, 0] > thr) & (arr[:, :, 1] > thr) & (arr[:, :, 2] > thr))
    rows = np.any(content, axis=1)
    cols = np.any(content, axis=0)
    if not rows.any() or not cols.any():
        return arr
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    h, w = arr.shape[:2]
    return arr[max(0, rmin - margin):min(h - 1, rmax + margin) + 1,
               max(0, cmin - margin):min(w - 1, cmax + margin) + 1]


def shapely_to_ee(geom):
    if geom.geom_type == "Polygon":
        return ee.Geometry.Polygon([[[c[0], c[1]] for c in geom.exterior.coords]])
    if geom.geom_type == "MultiPolygon":
        # one extra nesting level per polygon (GeoJSON MultiPolygon depth)
        return ee.Geometry.MultiPolygon([[[[c[0], c[1]] for c in p.exterior.coords]] for p in geom.geoms])
    raise ValueError(f"Unsupported geometry: {geom.geom_type}")


def read_kml_polygons(path: Path):
    doc = minidom.parse(str(path))
    polys = []
    for pg in doc.getElementsByTagName("Polygon"):
        cn = pg.getElementsByTagName("coordinates")
        if not cn:
            continue
        coords = []
        for tok in _node_text(cn[0]).split():
            parts = tok.split(",")
            if len(parts) >= 2:
                coords.append((float(parts[0]), float(parts[1])))
        if len(coords) >= 4:
            polys.append(Polygon(coords))
    return polys


def ndwi_for_bin(kml_path: Path, out_jpg: Path, start_iso, end_excl_iso, cloud):
    """Stage 1 for one bin KML. Returns a status string."""
    polys = [g for g in read_kml_polygons(kml_path) if g.is_valid and not g.is_empty]
    if not polys:
        return "skipped: empty geometry"
    merged = unary_union(polys)
    minx, miny, maxx, maxy = merged.bounds
    scale = max(0.05, max((maxx - minx) * 111320 * 0.9, (maxy - miny) * 111320) / 800)
    ee_aoi = shapely_to_ee(merged)

    last_err = None
    for attempt in range(3):
        try:
            image = s2_collection(ee_aoi, start_iso, end_excl_iso, cloud).median().clip(ee_aoi)
            b03 = image.select("B3").toFloat()
            b08 = image.select("B8").toFloat()
            ndwi_vis = (b03.subtract(b08).divide(b03.add(b08)).rename("NDWI")
                        .visualize(min=-0.8, max=0.8, palette=["008000", "FFFFFF", "0000CC"]))
            url = ndwi_vis.getDownloadURL({"scale": scale, "region": ee_aoi,
                                           "format": "jpg", "crs": "EPSG:4326"})
            resp = requests.get(url, timeout=180)
            resp.raise_for_status()
            break
        except Exception as e:
            if "did not match any bands" in str(e):
                return "skipped: no Sentinel-2 pixels for this bin in the date range"
            last_err = e
            time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"GEE download failed after 3 attempts: {last_err}")

    arr = tight_crop(clean_image(np.array(Image.open(io.BytesIO(resp.content)).convert("RGB"),
                                          dtype=np.uint8)))
    final_h = max(100, int(OUTPUT_WIDTH / (arr.shape[1] / arr.shape[0])))
    Image.fromarray(arr).resize((OUTPUT_WIDTH, final_h), Image.LANCZOS).save(
        str(out_jpg), "JPEG", quality=95)
    return f"saved {OUTPUT_WIDTH}x{final_h}px"


def _rotate_bound(img, angle, center=None):
    h, w = img.shape[:2]
    if center is None:
        center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += (nw - w) / 2
    M[1, 2] += (nh - h) / 2
    return cv2.warpAffine(img, M, (nw, nh), borderValue=(255, 255, 255))


def _images_in(folder: Path, exts=IMG_EXT):
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(exts))


def stage2_rotation(src: Path, dst: Path, log):
    """Rectangle rotation. Images without a detectable rectangle are kept as-is
    (same net result as the original no_rectangle_detected merge)."""
    dst.mkdir(parents=True, exist_ok=True)
    no_rect = 0
    for fname in _images_in(src):
        img = cv2.imread(str(src / fname))
        if img is None:
            log(f"   cannot read {fname}")
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([40, 40, 40]), np.array([80, 255, 255]))
        if np.sum(mask) == 0:
            _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        k = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k), cv2.MORPH_OPEN, k)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            contours, _ = cv2.findContours(cv2.Canny(gray, 50, 150),
                                           cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            cv2.imwrite(str(dst / fname), img)
            no_rect += 1
            continue
        _, (wr, hr), angle = cv2.minAreaRect(max(contours, key=cv2.contourArea))
        ra = angle + 90 if wr < hr else angle
        while ra > 45:
            ra -= 90
        while ra < -45:
            ra += 90
        cv2.imwrite(str(dst / fname), _rotate_bound(img, ra))
    log(f"   stage 2: rotated, {no_rect} without rectangle kept as-is")


def stage3_hori_rota(src: Path, dst: Path, log):
    dst.mkdir(parents=True, exist_ok=True)
    turned = 0
    for fname in _images_in(src):
        img = cv2.imread(str(src / fname))
        if img is None:
            continue
        h, w = img.shape[:2]
        if h > w:
            img = _rotate_bound(img, -90)
            turned += 1
        cv2.imwrite(str(dst / fname), img)
    log(f"   stage 3: {turned} portrait images turned horizontal")


def stage4_classify(src: Path, base: Path, log):
    dirs = {k: base / k for k in ("STRAIGHT", "SLANTED", "NONE_IMG")}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    def get_angle(path):
        img = cv2.imread(str(path))
        if img is None:
            return None
        lines = cv2.HoughLines(cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 30, 200),
                               1, np.pi / 180, 80)
        if lines is None:
            return None
        a = np.degrees(lines[0][0][1])
        return a - 180 if a > 90 else a

    counts = {"STRAIGHT": 0, "SLANTED": 0, "NONE_IMG": 0}
    for fname in _images_in(src):
        angle = get_angle(src / fname)
        if angle is None:
            lbl = "NONE_IMG"
        elif -10 <= angle <= 10 or 80 <= abs(angle) <= 100:
            lbl = "STRAIGHT"
        else:
            lbl = "SLANTED"
        counts[lbl] += 1
        shutil.copy(src / fname, dirs[lbl] / fname)
    log(f"   stage 4: STRAIGHT {counts['STRAIGHT']}, SLANTED {counts['SLANTED']}, NONE {counts['NONE_IMG']}")


def stage5_down_to_up(sorted_base: Path, out_dir: Path, log):
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for root, _dirs, files in sorted(os.walk(sorted_base)):
        for fname in sorted(files):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            img = cv2.imread(os.path.join(root, fname))
            if img is None:
                log(f"   cannot read {fname}")
                continue
            h, w = img.shape[:2]
            if h > w:                                           # portrait -> landscape first
                img = _rotate_bound(img, -90)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)        # PCA rotation
            _, thresh = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                log(f"   no contour: {fname}")
                continue
            pts = np.squeeze(max(contours, key=cv2.contourArea)).astype(np.float32)
            if pts.ndim < 2:
                log(f"   not enough points: {fname}")
                continue
            _, ev = cv2.PCACompute(pts, mean=None)
            angle = np.degrees(np.arctan2(ev[0, 1], ev[0, 0]))
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC)

            gr2 = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)     # crop to content
            _, th2 = cv2.threshold(gr2, 10, 255, cv2.THRESH_BINARY)
            cr2, _ = cv2.findContours(th2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cr2:
                log(f"   no contour after PCA: {fname}")
                continue
            x, y, cw, ch = cv2.boundingRect(max(cr2, key=cv2.contourArea))
            cropped = rotated[y:y + ch, x:x + cw]

            if cropped.shape[0] > cropped.shape[1]:             # landscape after crop
                cropped = _rotate_bound(cropped, -90,
                                        center=(cropped.shape[1] // 2, cropped.shape[0] // 2))

            if ev[0, 0] < 0:                                    # road runs left -> right
                cropped = cv2.flip(cropped, 1)

            cv2.imwrite(str(out_dir / fname), cropped)
            saved += 1
    log(f"   stage 5: {saved} images -> down_to_up_images")
    return saved


def stage6_up_to_down(src: Path, dst: Path, log):
    dst.mkdir(parents=True, exist_ok=True)
    saved = 0
    for fname in _images_in(src, (".jpg", ".jpeg", ".png")):
        img = cv2.imread(str(src / fname))
        if img is None:
            continue
        h, w = img.shape[:2]
        if h > w:
            img = _rotate_bound(img, -90)
        cv2.imwrite(str(dst / fname), cv2.flip(img, 1))
        saved += 1
    log(f"   stage 6: {saved} images -> up_to_down_images")


def ndwi_dirs(run_dir: Path):
    return {
        "raw":        run_dir / "images",
        "all2":       run_dir / "IMAGES_ALL_2",
        "all3":       run_dir / "IMAGES_ALL_3",
        "sorted":     run_dir / "IMAGES_ALL_4_SORTED",
        "down_to_up": run_dir / "down_to_up_images",
        "up_to_down": run_dir / "up_to_down_images",
    }


def lane_bin_kmls(proj_dir: Path, lane_tags):
    """Only single-lane folders (LHS_L1, LHS_L2, RHS_L1 ...) go to NDWI —
    combined (LHS_L1_L2) and median KMLs are skipped."""
    out = []
    for tag in lane_tags:
        side = tag.split("_")[0]
        folder = proj_dir / "kml_output" / f"{side}_KMLs" / tag
        if folder.is_dir():
            out += sorted(folder.glob("*.kml"))
    return out


def ndwi_run_id(start: str, end: str, cloud: int):
    return f"{start}_to_{end}_cc{int(cloud)}"


# ============================================================
# PART 3 — RI / IRI REPORT   (was: Roughness_ri_calc.py, Stage 7)
# ============================================================
SURFACE_THRESHOLDS = {
    "Bituminous": {
        "RI":  [(1800, "<1800", "Good"), (2400, "1800-2400", "Fair"), (float("inf"), ">2400", "Poor")],
        "IRI": [(2.55, "<2.55", "Good"), (3.30, "2.55-3.30", "Fair"), (float("inf"), ">3.30", "Poor")],
    },
    "Cemented": {
        "RI":  [(2000, "<2000", "Good"), (2400, "2000-2400", "Fair"), (float("inf"), ">2400", "Poor")],
        "IRI": [(2.81, "<2.81", "Good"), (3.30, "2.81-3.30", "Fair"), (float("inf"), ">3.30", "Poor")],
    },
}
_CONDITION_ORDER = {"Good": 0, "Fair": 1, "Poor": 2}

RI_PCS_TABLE = {
    "Bituminous": [
        (900,          "100-90", "Off carriageway maintenance",                                  "T3 (Low)"),
        (1800,         "89-70",  "Off carriageway maintenance",                                  "T3 (Low)"),
        (2100,         "69-50",  "Distress repair and off carriageway maintenance",              "T2 (Moderate)"),
        (2400,         "49-30",  "Distress repair and off carriageway maintenance",              "T2 (Moderate)"),
        (float("inf"), "29-0",   "Distress repair + Thin Overlay / Strengthening Thick Overlay", "T1 (High)"),
    ],
    "Cemented": [
        (1000,         "100-90", "Off carriageway maintenance",                                  "T3 (Low)"),
        (2000,         "89-70",  "Off carriageway maintenance",                                  "T3 (Low)"),
        (2200,         "69-50",  "Distress repair and off carriageway maintenance",              "T2 (Moderate)"),
        (2400,         "49-30",  "Distress repair and off carriageway maintenance",              "T2 (Moderate)"),
        (float("inf"), "29-0",   "Distress repair + Thin Overlay / Strengthening Thick Overlay", "T1 (High)"),
    ],
}

# Dropdown value -> (threshold table key, "Carriage Type" text in the report)
SURFACES = {"Bituminous": ("Bituminous", "Bituminous"),
            "Concrete":   ("Cemented",   "Concrete")}
MODES = {"up_to_down": ("up_to_down_images", "North to south / East to west"),
         "down_to_up": ("down_to_up_images", "South to north / West to east")}

# Direction of the image folders, checked by running bins at 20 headings through
# Stages 2-5: in down_to_up images the road reads south -> north (roads within 45 deg
# of north-south) or west -> east (the rest); up_to_down images are the reverse.
COMPASS8 = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


def road_orientation(start_lonlat, end_lonlat):
    """Heading from the chainage-start point to the end point."""
    az, _, _ = GEOD.inv(start_lonlat[0], start_lonlat[1], end_lonlat[0], end_lonlat[1])
    bearing = az % 360.0
    towards = ("N" if bearing >= 315 or bearing < 45 else "E" if bearing < 135
               else "S" if bearing < 225 else "W")
    idx = int(((bearing + 22.5) % 360) // 45)
    return {"bearing": round(bearing, 1),
            "axis": "NS" if towards in "NS" else "EW",
            "increases_towards": towards,                  # chainage grows towards this side
            "from": COMPASS8[(idx + 4) % 8], "to": COMPASS8[idx]}


def mode_heading(mode, axis):
    if mode == "up_to_down":
        return "North to south" if axis == "NS" else "East to west"
    return "South to north" if axis == "NS" else "West to east"


def mode_descending(mode, orientation):
    """True when the chosen heading runs against increasing chainage."""
    return (mode == "up_to_down") == (orientation["increases_towards"] in ("N", "E"))


def project_orientation(pdir: Path, proj: dict):
    o = proj.get("summary", {}).get("orientation")
    if o:
        return o
    gj = read_json(pdir / "kml_output" / "preview.geojson")
    centre = next(f for f in gj["features"] if f["properties"]["kind"] == "centre")
    pts = centre["geometry"]["coordinates"]
    return road_orientation(pts[0], pts[-1])

REPORT_COLUMNS = [
    "Chainage_Start", "Chainage_End", "Direction", "Lane", "RI", "IRI",
    "IRI_Index", "RI_Index", "Drainage Condition:", "Carriage Type ",
    "Survey_Date_Start", "Survey_Date_End",
    "From Latitude", "From Longitude", "To Latitude", "To Longitude",
    "Roughness_Status",
]


def classify_ri_bands(ri_value, table_key):
    table = RI_PCS_TABLE.get(table_key, RI_PCS_TABLE["Bituminous"])
    for limit, pcs_band, status, cvd_class in table:
        if ri_value <= limit:
            return pcs_band, status, cvd_class
    return table[-1][1], table[-1][2], table[-1][3]


def classify_condition(ri_value, iri_value, table_key):
    table = SURFACE_THRESHOLDS.get(table_key, SURFACE_THRESHOLDS["Bituminous"])
    ri_band, ri_status = table["RI"][-1][1], table["RI"][-1][2]
    for limit, band, status in table["RI"]:
        if ri_value <= limit:
            ri_band, ri_status = band, status
            break
    iri_band, iri_status = table["IRI"][-1][1], table["IRI"][-1][2]
    for limit, band, status in table["IRI"]:
        if iri_value <= limit:
            iri_band, iri_status = band, status
            break
    overall = ri_status if _CONDITION_ORDER[ri_status] >= _CONDITION_ORDER[iri_status] else iri_status
    return ri_band, iri_band, overall


def parse_image_name(fn):
    ch = re.search(r'(\d+\.\d+)_to_(\d+\.\d+)', fn)
    cs = float(ch.group(1)) if ch else 0.0
    ce = float(ch.group(2)) if ch else 0.0
    dm = re.search(r'_(LHS|RHS)(?:[_.]|$)', fn, re.IGNORECASE)
    dr = dm.group(1).upper() if dm else "UNKNOWN"
    lm = re.search(r'_(L\d+)\.\w+$', fn, re.IGNORECASE)
    lane = lm.group(1).upper() if lm else "UNKNOWN"
    return cs, ce, dr, lane


def gray_profile(path: Path, known_distance_m: float):
    """Average gray value along one bin image (same maths as Stage 7).
    Returns (distance_m, average_gray), or None if the image can't be read."""
    img_gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img_gray is None:
        return None
    if img_gray.shape[0] > img_gray.shape[1]:
        img_gray = cv2.rotate(img_gray, cv2.ROTATE_90_CLOCKWISE)
    img_gray = cv2.normalize(img_gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    scale_mpp = known_distance_m / img_gray.shape[1]
    pixel_gap = max(1, int(round(LINE_SPACING_M / scale_mpp)))
    line_pos = list(range(0, img_gray.shape[0], pixel_gap))
    if line_pos[-1] != img_gray.shape[0] - 1:
        line_pos.append(img_gray.shape[0] - 1)

    profiles = img_gray[line_pos, :].astype(float)       # one row per scan line
    profiles[profiles > GRAY_THRESHOLD] = 0               # suppress background whites
    cnt = (profiles > 0).sum(axis=0)
    average_gray = np.where(cnt > 0, profiles.sum(axis=0) / np.maximum(cnt, 1), 0.0)
    distance = np.arange(img_gray.shape[1]) * scale_mpp
    return distance, average_gray


def ri_iri(distance, average_gray, offsets):
    """Sample the profile at `offsets`, sum, /2  ->  RI;  IRI = (RI/630)^(1/1.12)."""
    interp = np.interp(offsets, distance, average_gray)
    ri = float(np.sum(interp)) / 2.0
    iri = float((ri / 630) ** (1 / 1.12)) if ri > 0 else 0.0
    return ri, iri


def bin_ri_iri(distance, average_gray, known_distance_m):
    """100 m value: 41 samples over the bin (= np.arange(0, 102.5, 2.5) for 100 m)."""
    return ri_iri(distance, average_gray, np.linspace(0.0, known_distance_m, RI_SAMPLE_POINTS))


def block_ri_iri(distance, average_gray, known_distance_m):
    """10 m values: the same formula re-applied inside each 10 m block at
    0.25 m spacing (41 points per block), as in the original 10 m calc."""
    n_blocks = int(round(known_distance_m / BLOCK_SIZE_M))
    return [ri_iri(distance, average_gray, BLOCK_OFFSETS + b * BLOCK_SIZE_M) for b in range(n_blocks)]


def ri_iri_from_image(path: Path, known_distance_m: float):
    prof = gray_profile(path, known_distance_m)
    return None if prof is None else bin_ri_iri(*prof, known_distance_m)


class LaneLookup:
    """Chainage -> (lat, lon) from a Step-1 lane Excel (e.g. LHS_L1.xlsx)."""

    def __init__(self, path: Path):
        self.table = {}
        if path.exists():
            df = pd.read_excel(path)
            df.columns = df.columns.str.strip()
            for cs, lat, lon in zip(df["Chainage Start"], df["Latitude"], df["Longitude"]):
                self.table.setdefault(int(round(float(cs) * 1000)), (float(lat), float(lon)))
        self.last = max(self.table) if self.table else None

    def at(self, chainage_km):
        k = int(round(chainage_km * 1000))
        if k in self.table:
            return self.table[k]
        if self.last is not None and k > self.last:      # last bin runs past the road end
            return self.table[self.last]
        return None, None


def lane_summary(df: pd.DataFrame):
    rows = []
    groups = list(df.groupby(["Direction", "Lane"], sort=True)) + [(("All", "All"), df)]
    for (d, l), g in groups:
        vc = g["Drainage Condition:"].value_counts()
        rows.append({"Direction": d, "Lane": l, "Segments": int(len(g)),
                     "Avg RI": round(float(g["RI"].mean()), 2),
                     "Avg IRI": round(float(g["IRI"].mean()), 3),
                     "Good": int(vc.get("Good", 0)), "Fair": int(vc.get("Fair", 0)),
                     "Poor": int(vc.get("Poor", 0))})
    return rows


# ---------------- Excel report ----------------
def write_excel_report(df: pd.DataFrame, summary, meta: dict, table_key: str, path: Path, sheet: str):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    font = Font(name="Arial", size=10)
    bold = Font(name="Arial", size=10, bold=True)
    head_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1C2124")
    thin = Side(style="thin", color="C7CDC9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    cond_style = {"Good": ("C6EFCE", "006100"), "Fair": ("FFEB9C", "9C5700"), "Poor": ("FFC7CE", "9C0006")}

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name=sheet, index=False)
        wb = xw.book
        ws = xw.sheets[sheet]

        widths = [14, 14, 10, 7, 11, 9, 12, 12, 18, 14, 17, 17, 15, 15, 15, 15, 58]
        formats = {1: "0.000", 2: "0.000", 5: "0.00", 6: "0.000",
                   13: "0.00000000", 14: "0.00000000", 15: "0.00000000", 16: "0.00000000"}
        cond_col = REPORT_COLUMNS.index("Drainage Condition:") + 1
        for c in range(1, len(REPORT_COLUMNS) + 1):
            ws.column_dimensions[get_column_letter(c)].width = widths[c - 1]
            h = ws.cell(row=1, column=c)
            h.font, h.fill, h.border = head_font, head_fill, border
            h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 30
        for r in range(2, ws.max_row + 1):
            for c in range(1, len(REPORT_COLUMNS) + 1):
                cell = ws.cell(row=r, column=c)
                cell.font, cell.border = font, border
                if c in formats:
                    cell.number_format = formats[c]
            cv = ws.cell(row=r, column=cond_col)
            if cv.value in cond_style:
                bg, fg = cond_style[cv.value]
                cv.fill = PatternFill("solid", fgColor=bg)
                cv.font = Font(name="Arial", size=10, bold=True, color=fg)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        # ---- Summary sheet (live formulas over the data sheet) ----
        sm = wb.create_sheet("Summary")
        sm["A1"] = "Road roughness report — summary"
        sm["A1"].font = Font(name="Arial", size=14, bold=True)
        r = 3
        for k, v in meta.items():
            sm.cell(row=r, column=1, value=k).font = bold
            sm.cell(row=r, column=2, value=v).font = font
            r += 1
        r += 1
        hdr = ["Direction", "Lane", "Segments", "Avg RI", "Avg IRI", "Good", "Fair", "Poor"]
        for c, t in enumerate(hdr, 1):
            cell = sm.cell(row=r, column=c, value=t)
            cell.font, cell.fill, cell.border = head_font, head_fill, border
            cell.alignment = Alignment(horizontal="center")
        q = f"'{sheet}'!"
        rng = lambda col: f"{q}${col}:${col}"
        for row in summary:
            r += 1
            d, l = row["Direction"], row["Lane"]
            sm.cell(row=r, column=1, value=d)
            sm.cell(row=r, column=2, value=l)
            if d == "All":
                sm.cell(row=r, column=3, value=f"=COUNTA({rng('A')})-1")
                sm.cell(row=r, column=4, value=f"=IFERROR(AVERAGE({rng('E')}),\"-\")")
                sm.cell(row=r, column=5, value=f"=IFERROR(AVERAGE({rng('F')}),\"-\")")
                for c, cond in ((6, "Good"), (7, "Fair"), (8, "Poor")):
                    sm.cell(row=r, column=c, value=f"=COUNTIF({rng('I')},\"{cond}\")")
            else:
                crit = f"{rng('C')},$A{r},{rng('D')},$B{r}"
                sm.cell(row=r, column=3, value=f"=COUNTIFS({crit})")
                sm.cell(row=r, column=4, value=f"=IFERROR(AVERAGEIFS({rng('E')},{crit}),\"-\")")
                sm.cell(row=r, column=5, value=f"=IFERROR(AVERAGEIFS({rng('F')},{crit}),\"-\")")
                for c, cond in ((6, "Good"), (7, "Fair"), (8, "Poor")):
                    sm.cell(row=r, column=c, value=f"=COUNTIFS({crit},{rng('I')},\"{cond}\")")
            for c in range(1, 9):
                cell = sm.cell(row=r, column=c)
                cell.border = border
                cell.font = bold if d == "All" else font
            sm.cell(row=r, column=4).number_format = "0.00"
            sm.cell(row=r, column=5).number_format = "0.000"
        r += 1
        sm.cell(row=r, column=1,
                value=f"Counts and averages are formulas over the {sheet} sheet.").font = \
            Font(name="Arial", size=9, italic=True, color="56616A")

        r += 2
        sm.cell(row=r, column=1, value=f"Classification used ({meta['Pavement']})").font = bold
        r += 1
        for c, t in enumerate(["Condition", "RI band", "IRI band"], 1):
            cell = sm.cell(row=r, column=c, value=t)
            cell.font, cell.fill, cell.border = head_font, head_fill, border
        th = SURFACE_THRESHOLDS[table_key]
        for (_, rb, cond), (_, ib, _) in zip(th["RI"], th["IRI"]):
            r += 1
            for c, v in enumerate([cond, rb, ib], 1):
                cell = sm.cell(row=r, column=c, value=v)
                cell.font, cell.border = font, border
        for col, w in zip("ABCDEFGH", [24, 44, 11, 11, 11, 9, 9, 9]):
            sm.column_dimensions[col].width = w
        wb.calculation.fullCalcOnLoad = True


# ---------------- PDF report ----------------
def write_pdf_report(df: pd.DataFrame, summary, meta: dict, table_key: str, path: Path, title: str):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    asphalt = colors.HexColor("#1C2124")
    rule = colors.HexColor("#C7CDC9")
    zebra = colors.HexColor("#F3F4F2")
    cond_bg = {"Good": colors.HexColor("#C6EFCE"), "Fair": colors.HexColor("#FFEB9C"),
               "Poor": colors.HexColor("#FFC7CE")}

    page = landscape(A3)
    margin = 12 * mm
    doc = SimpleDocTemplate(str(path), pagesize=page, leftMargin=margin, rightMargin=margin,
                            topMargin=14 * mm, bottomMargin=14 * mm, title=title,
                            author="Road Roughness Platform")
    s_title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=17, leading=21)
    s_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceAfter=4)
    s_meta = ParagraphStyle("m", fontName="Helvetica", fontSize=8.5, leading=11)
    s_cell = ParagraphStyle("c", fontName="Helvetica", fontSize=6.8, leading=8.2)
    s_head = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=6.8, leading=8.2,
                            textColor=colors.white, alignment=TA_CENTER)

    story = [Paragraph(title, s_title), Spacer(1, 6)]

    items = list(meta.items())
    half = math.ceil(len(items) / 2)
    left, right = items[:half], items[half:] + [("", "")] * (half - len(items[half:]))
    meta_rows = [[Paragraph(f"<b>{a}</b>", s_meta), Paragraph(str(b), s_meta),
                  Paragraph(f"<b>{c}</b>", s_meta), Paragraph(str(d), s_meta)]
                 for (a, b), (c, d) in zip(left, right)]
    mt = Table(meta_rows, colWidths=[110, 330, 110, 330], hAlign="LEFT")
    mt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("LINEBELOW", (0, -1), (-1, -1), 0.6, asphalt)]))
    story += [mt, Spacer(1, 10)]

    # summary + legend side by side
    s_hdr = ["Direction", "Lane", "Segments", "Avg RI", "Avg IRI", "Good", "Fair", "Poor"]
    s_rows = [s_hdr] + [[r["Direction"], r["Lane"], r["Segments"], f"{r['Avg RI']:.2f}",
                         f"{r['Avg IRI']:.3f}", r["Good"], r["Fair"], r["Poor"]] for r in summary]
    st = Table(s_rows, colWidths=[52, 40, 52, 56, 52, 40, 40, 40], hAlign="LEFT")
    st_style = [("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                ("BACKGROUND", (0, 0), (-1, 0), asphalt), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, rule), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 7.5),
                ("BACKGROUND", (5, 1), (5, -1), cond_bg["Good"]),
                ("BACKGROUND", (6, 1), (6, -1), cond_bg["Fair"]),
                ("BACKGROUND", (7, 1), (7, -1), cond_bg["Poor"])]
    st.setStyle(TableStyle(st_style))

    th = SURFACE_THRESHOLDS[table_key]
    lg_rows = [["Condition", "RI band", "IRI band"]] + \
              [[cond, rb, ib] for (_, rb, cond), (_, ib, _) in zip(th["RI"], th["IRI"])]
    lg = Table(lg_rows, colWidths=[56, 64, 64], hAlign="LEFT")
    lg.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                            ("BACKGROUND", (0, 0), (-1, 0), asphalt),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.3, rule),
                            ("BACKGROUND", (0, 1), (0, 1), cond_bg["Good"]),
                            ("BACKGROUND", (0, 2), (0, 2), cond_bg["Fair"]),
                            ("BACKGROUND", (0, 3), (0, 3), cond_bg["Poor"])]))
    pair = Table([[Paragraph("Summary by lane", s_h2), "",
                   Paragraph(f"Classification ({meta['Pavement']})", s_h2)],
                  [st, "", lg]], colWidths=[400, 30, 200], hAlign="LEFT")
    pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [pair, Spacer(1, 12), Paragraph(f"{meta['Section length']} roughness", s_h2)]

    def fmt(v, nd):
        return "-" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{float(v):.{nd}f}"

    header = [Paragraph(c.replace("_", " ").strip(), s_head) for c in REPORT_COLUMNS]
    data = [header]
    for rec in df.to_dict("records"):
        data.append([
            fmt(rec["Chainage_Start"], 3), fmt(rec["Chainage_End"], 3), rec["Direction"], rec["Lane"],
            fmt(rec["RI"], 2), fmt(rec["IRI"], 3), rec["IRI_Index"], rec["RI_Index"],
            rec["Drainage Condition:"], rec["Carriage Type "],
            rec["Survey_Date_Start"], rec["Survey_Date_End"],
            fmt(rec["From Latitude"], 8), fmt(rec["From Longitude"], 8),
            fmt(rec["To Latitude"], 8), fmt(rec["To Longitude"], 8),
            Paragraph(str(rec["Roughness_Status"]), s_cell),
        ])
    base_w = [44, 44, 42, 28, 44, 36, 50, 54, 54, 52, 54, 54, 58, 58, 58, 58, 192]
    avail = page[0] - 2 * margin
    col_w = [w * avail / sum(base_w) for w in base_w]
    t = Table(data, colWidths=col_w, repeatRows=1)
    ts = [("FONT", (0, 1), (-1, -1), "Helvetica", 6.8),
          ("BACKGROUND", (0, 0), (-1, 0), asphalt),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("GRID", (0, 0), (-1, -1), 0.25, rule),
          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, zebra]),
          ("ALIGN", (0, 1), (1, -1), "RIGHT"), ("ALIGN", (4, 1), (5, -1), "RIGHT"),
          ("ALIGN", (12, 1), (15, -1), "RIGHT"),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    ci = REPORT_COLUMNS.index("Drainage Condition:")
    for i, rec in enumerate(df.to_dict("records"), start=1):
        bg = cond_bg.get(rec["Drainage Condition:"])
        if bg is not None:
            ts += [("BACKGROUND", (ci, i), (ci, i), bg), ("FONT", (ci, i), (ci, i), "Helvetica-Bold", 6.8)]
    t.setStyle(TableStyle(ts))
    story.append(t)

    footer_left = f"{meta['Project']}  |  {meta['Pavement']}  |  {meta['Road direction']}"

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#56616A"))
        canvas.drawString(margin, 8 * mm, footer_left)
        canvas.drawRightString(page[0] - margin, 8 * mm, f"Page {doc_.page}  |  Generated {meta['Generated']}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def latest_done_run(pid: str, pdir: Path):
    done = [r for r in list_runs(pid, pdir) if r.get("status") == "done"]
    return max(done, key=lambda r: r.get("finished") or r.get("created") or "") if done else None


def compute_roughness_report(pid: str, run_id: Optional[str], mode: str, surface: str):
    pdir = project_dir(pid)
    proj = read_json(pdir / "project.json")
    if not run_id:                                   # default: latest finished NDWI image set
        latest = latest_done_run(pid, pdir)
        if latest is None:
            raise HTTPException(409, "No finished NDWI images yet. Generate them in step 2.")
        run_id = latest["id"]
    run_dir = pdir / "ndwi" / run_id
    if not _RUN_RE.match(run_id) or not (run_dir / "run.json").exists():
        raise HTTPException(404, "Unknown NDWI image set.")
    run = read_json(run_dir / "run.json")
    if run.get("status") != "done":
        raise HTTPException(409, "This NDWI image set is not finished yet.")
    if mode not in MODES:
        raise HTTPException(400, f"Direction must be one of {list(MODES)}.")
    surface = "Concrete" if surface == "Cemented" else surface
    if surface not in SURFACES:
        raise HTTPException(400, f"Pavement must be one of {list(SURFACES)}.")

    table_key, carriage = SURFACES[surface]
    folder = MODES[mode][0]
    orient = project_orientation(pdir, proj)
    heading = mode_heading(mode, orient["axis"])
    descending = mode_descending(mode, orient)
    src = run_dir / folder
    if not src.is_dir():
        raise HTTPException(404, f"{folder} is missing for this image set.")
    bin_m = float(proj["params"]["bin_km"]) * 1000.0
    block_km = BLOCK_SIZE_M / 1000.0
    xl_dir = pdir / "kml_output" / "Excels"

    def make_row(cs, ce, dr, lane, ri, iri, lookup, image):
        ri_band, iri_band, condition = classify_condition(ri, iri, table_key)
        _pcs, status, _cvd = classify_ri_bands(ri, table_key)
        flat, flon = lookup.at(cs)
        tlat, tlon = lookup.at(ce)
        return {
            "Chainage_Start": round(cs, 3), "Chainage_End": round(ce, 3),
            "Direction": dr, "Lane": lane,
            "RI": round(ri, 2), "IRI": round(iri, 3),
            "IRI_Index": iri_band, "RI_Index": ri_band,
            "Drainage Condition:": condition, "Carriage Type ": carriage,
            "Survey_Date_Start": run["start"], "Survey_Date_End": run["end"],
            "From Latitude": flat, "From Longitude": flon,
            "To Latitude": tlat, "To Longitude": tlon,
            "Roughness_Status": status,
            "_image": image,
        }

    lookups, rows_bin, rows_block, skipped = {}, [], [], []
    for name in _images_in(src, (".jpg", ".jpeg", ".png", ".tif")):
        cs, ce, dr, lane = parse_image_name(name)
        if dr == "UNKNOWN" or lane == "UNKNOWN":
            skipped.append(name)
            continue
        prof = gray_profile(src / name, bin_m)
        if prof is None:
            skipped.append(name)
            continue
        if (dr, lane) not in lookups:
            lookups[(dr, lane)] = LaneLookup(xl_dir / f"{dr}_{lane}.xlsx")
        lk = lookups[(dr, lane)]
        image = f"/api/projects/{pid}/files/ndwi/{run_id}/{folder}/{name}"

        ri, iri = bin_ri_iri(*prof, bin_m)
        rows_bin.append(make_row(cs, ce, dr, lane, ri, iri, lk, image))

        # 10 m blocks are read left -> right across the image. Which end of this bin
        # is on the left depends on the image folder (N->S / E->W or S->N / W->E) and
        # on which way chainage runs in this bin.
        p0, p1 = lk.at(cs), lk.at(ce)
        bin_or = (road_orientation((p0[1], p0[0]), (p1[1], p1[0]))
                  if None not in p0 + p1 and p0 != p1 else orient)
        left_is_high = mode_descending(mode, bin_or)
        blocks = block_ri_iri(*prof, bin_m)
        for b, (ri_b, iri_b) in enumerate(blocks):
            k = len(blocks) - 1 - b if left_is_high else b      # block index from the low-chainage end
            rows_block.append(make_row(round(cs + k * block_km, 3), round(cs + (k + 1) * block_km, 3),
                                       dr, lane, ri_b, iri_b, lk, image))
    if not rows_bin:
        raise HTTPException(422, "No usable images found in this image set.")

    reports_dir = pdir / "reports"
    reports_dir.mkdir(exist_ok=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = {}
    for key, rows, sec_m in (("100m", rows_bin, bin_m), ("10m", rows_block, BLOCK_SIZE_M)):
        df = pd.DataFrame(rows)
        if descending:
            # The chosen heading runs against chainage (e.g. 10 -> 0): each section
            # reads from its higher chainage to its lower one, From lat/long at the higher end.
            df = df.rename(columns={"Chainage_Start": "Chainage_End", "Chainage_End": "Chainage_Start",
                                    "From Latitude": "To Latitude", "To Latitude": "From Latitude",
                                    "From Longitude": "To Longitude", "To Longitude": "From Longitude"})
        df = (df.sort_values(["Chainage_Start", "Direction", "Lane"], ascending=[not descending, True, True],
                             kind="stable").reset_index(drop=True))
        images = df.pop("_image").tolist()
        df = df[REPORT_COLUMNS]
        summary = lane_summary(df)
        sec_label = f"{int(round(sec_m))} m"
        meta = {
            "Project": proj["name"],
            "Median line KML": proj.get("source_file", ""),
            "Chainage": f"{df['Chainage_Start'].iloc[0]:.3f} to {df['Chainage_End'].iloc[-1]:.3f} km",
            "Pavement": carriage,
            "Road direction": f"{heading} ({df['Chainage_Start'].iloc[0]:.3f} to {df['Chainage_End'].iloc[-1]:.3f} km)",
            "Road alignment": f"Chainage runs {orient['from']} to {orient['to']}, bearing {orient['bearing']:.0f}°",
            "Survey dates": f"{run['start']} to {run['end']} (Sentinel-2, cloud < {run['cloud']}%)",
            "Section length": sec_label,
            "Segments": str(len(df)),
            "Generated": generated,
        }
        stem = f"Roughness_{int(round(sec_m))}m_{run_id}_{heading.replace(' ', '_')}_{carriage}"
        xlsx_path, pdf_path = reports_dir / f"{stem}.xlsx", reports_dir / f"{stem}.pdf"
        write_excel_report(df, summary, meta, table_key, xlsx_path, sheet=f"Roughness_{int(round(sec_m))}m")
        write_pdf_report(df, summary, meta, table_key, pdf_path,
                         title=f"Road roughness report (RI / IRI), {sec_label} sections")
        records = json.loads(df.to_json(orient="records", double_precision=10))
        for rec, img in zip(records, images):
            rec["_image"] = img
        out[key] = {
            "rows": records, "summary": summary, "meta": meta,
            "excel_url": f"/api/projects/{pid}/files/reports/{xlsx_path.name}",
            "pdf_url": f"/api/projects/{pid}/files/reports/{pdf_path.name}",
        }
    return {"mode": mode, "heading": heading, "descending": descending, "orientation": orient, "run": {"id": run_id, "start": run["start"], "end": run["end"], "cloud": run["cloud"],
                    "n_images": run.get("n_images")},
            "skipped": skipped, "lane_tags": proj["lane_tags"], "reports": out}


# ============================================================
# PROJECT STORAGE + BACKGROUND TASKS
# ============================================================
_PID_RE = re.compile(r"^[a-f0-9]{10}$")
_RUN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_to_\d{4}-\d{2}-\d{2}_cc\d{1,3}$")


def project_dir(pid: str) -> Path:
    if not _PID_RE.match(pid or ""):
        raise HTTPException(404, "Unknown project.")
    d = PROJECTS_DIR / pid
    if not (d / "project.json").exists():
        raise HTTPException(404, "Unknown project.")
    return d


class TaskStore:
    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()

    def create(self, kind, pid, extra=None):
        tid = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[tid] = {"id": tid, "kind": kind, "project": pid, "status": "queued",
                                "done": 0, "total": 0, "log": [], "error": None,
                                "result": None, "started": now_iso(), **(extra or {})}
        return tid

    def update(self, tid, **kw):
        with self._lock:
            self._tasks[tid].update(kw)

    def log(self, tid, msg):
        print(msg, flush=True)
        with self._lock:
            lg = self._tasks[tid]["log"]
            lg.append(msg)
            del lg[:-400]

    def get(self, tid):
        with self._lock:
            t = self._tasks.get(tid)
            return json.loads(json.dumps(t)) if t else None

    def any_active(self, kind):
        with self._lock:
            return any(t["kind"] == kind and t["status"] in ("queued", "running") for t in self._tasks.values())

    def active(self, pid, kind):
        with self._lock:
            for t in self._tasks.values():
                if t["project"] == pid and t["kind"] == kind and t["status"] in ("queued", "running"):
                    return dict(t)
        return None


TASKS = TaskStore()
EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rr-task")


def ndwi_task(tid, pid, start, end, cloud):
    log = lambda m: TASKS.log(tid, m)
    run_dir = None
    try:
        TASKS.update(tid, status="running")
        pdir = project_dir(pid)
        proj = read_json(pdir / "project.json")
        run_id = ndwi_run_id(start, end, cloud)
        run_dir = pdir / "ndwi" / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        dirs = ndwi_dirs(run_dir)
        dirs["raw"].mkdir(parents=True, exist_ok=True)
        run = {"id": run_id, "start": start, "end": end, "cloud": cloud, "status": "running",
               "created": now_iso(), "task": tid}
        write_json(run_dir / "run.json", run)

        log("Starting Google Earth Engine ...")
        ee_init()
        kmls = lane_bin_kmls(pdir, proj["lane_tags"])
        if not kmls:
            raise RuntimeError("No lane bin KMLs found. Generate lane KMLs first.")
        total = len(kmls) + 5
        TASKS.update(tid, total=total, done=0)
        end_excl = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        log(f"Stage 1: NDWI for {len(kmls)} bin KMLs ({start} to {end}, cloud < {cloud}%) ...")

        ok, failed = 0, []
        with ThreadPoolExecutor(max_workers=NDWI_WORKERS) as pool:
            futs = {pool.submit(ndwi_for_bin, k, dirs["raw"] / f"{k.stem}.jpg",
                                start, end_excl, cloud): k for k in kmls}
            for i, fut in enumerate(as_completed(futs), 1):
                k = futs[fut]
                try:
                    msg = fut.result()
                except Exception as e:
                    msg = f"error: {e}"
                if msg.startswith("saved"):
                    ok += 1
                else:
                    failed.append({"bin": k.stem, "reason": msg})
                log(f"   [{i}/{len(kmls)}] {k.stem}: {msg}")
                TASKS.update(tid, done=i)
        if ok == 0:
            raise RuntimeError("No NDWI images were produced. Check the date range and the log above.")

        steps = [
            ("Stage 2: rectangle rotation", lambda: stage2_rotation(dirs["raw"], dirs["all2"], log)),
            ("Stage 3: horizontal rotation", lambda: stage3_hori_rota(dirs["all2"], dirs["all3"], log)),
            ("Stage 4: classify", lambda: stage4_classify(dirs["all3"], dirs["sorted"], log)),
            ("Stage 5: PCA alignment (down to up)",
             lambda: stage5_down_to_up(dirs["sorted"], dirs["down_to_up"], log)),
            ("Stage 6: flip (up to down)",
             lambda: stage6_up_to_down(dirs["down_to_up"], dirs["up_to_down"], log)),
        ]
        for j, (label, fn) in enumerate(steps, 1):
            log(label + " ...")
            fn()
            TASKS.update(tid, done=len(kmls) + j)

        n_images = len(_images_in(dirs["down_to_up"]))
        run.update(status="done", finished=now_iso(), n_bins=len(kmls), n_images=n_images,
                   failed=failed)
        write_json(run_dir / "run.json", run)
        TASKS.update(tid, status="done", result={"run_id": run_id, "n_images": n_images,
                                                 "failed": len(failed)})
        log(f"Done: {n_images} images stored, {len(failed)} bins skipped.")
    except Exception as e:
        traceback.print_exc()
        TASKS.log(tid, f"ERROR: {e}")
        TASKS.update(tid, status="error", error=str(e))
        if run_dir is not None and (run_dir / "run.json").exists():
            run = read_json(run_dir / "run.json")
            run.update(status="error", error=str(e))
            write_json(run_dir / "run.json", run)


def list_runs(pid, pdir):
    out = []
    ndwi_root = pdir / "ndwi"
    if not ndwi_root.is_dir():
        return out
    for d in sorted(ndwi_root.iterdir()):
        f = d / "run.json"
        if not f.exists():
            continue
        run = read_json(f)
        if run.get("status") == "running":
            t = TASKS.get(run.get("task", ""))
            if not t or t["status"] not in ("queued", "running"):
                run["status"] = "interrupted"
        run["zip_url"] = f"/api/projects/{pid}/ndwi/{run['id']}/zip"
        out.append(run)
    return out


def zip_folder_response(folder: Path, arc_root: str, filename: str, only=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and (only is None or path.parent.name in only):
                zf.write(path, f"{arc_root}/{path.relative_to(folder).as_posix()}")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ============================================================
# API
# ============================================================
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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if (STATIC_DIR / "vendor").is_dir():          # Leaflet served locally (no CDN needed)
    app.mount("/vendor", StaticFiles(directory=str(STATIC_DIR / "vendor")), name="vendor")


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


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


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


def delete_other_projects(keep_pid: str):
    """Only the newest project is kept. project.json goes first so a folder that
    can't be fully removed (a report open in Excel, say) is no longer listed."""
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir() and d.name != keep_pid:
            try:
                (d / "project.json").unlink(missing_ok=True)
            except OSError:
                pass
            shutil.rmtree(d, ignore_errors=True)
            print(f"   deleted previous project {d.name}", flush=True)


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


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("RR_HOST", "127.0.0.1")
    port = int(os.environ.get("RR_PORT", "8000"))
    print(f"\n  Road Roughness Platform {APP_VERSION}"
          f"\n  Open http://{host}:{port}/ in your browser   (API docs: http://{host}:{port}/docs)\n", flush=True)
    uvicorn.run(app, host=host, port=port)