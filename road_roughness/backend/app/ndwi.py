"""Step 2: Sentinel-2 NDWI images per lane bin KML, then Stages 2-6 (rotation / alignment).
(was: Roughness_image_process.py)"""

import io
import os
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.dom import minidom

import cv2
import ee
import numpy as np
import requests
from PIL import Image
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .config import GEE_PROJECT, IMG_EXT, NDWI_WORKERS, NEAREST_SEARCH_DAYS, OUTPUT_WIDTH, S2_COLLECTION
from .gee_auth import initialize_earth_engine
from .lanes import _node_text
from .storage import project_dir
from .tasks import TASKS
from .utils import now_iso, read_json, write_json


_EE_LOCK = threading.Lock()


_EE_READY = False


def ee_init():
    global _EE_READY
    with _EE_LOCK:
        if _EE_READY:
            return
        try:
            initialize_earth_engine(GEE_PROJECT)
        except Exception as e:
            raise RuntimeError(
                f"Google Earth Engine could not start ({e}). "
                f"For cloud deployment, set GEE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS. "
                f"For local development, run `earthengine authenticate` once and check that "
                f"GEE_PROJECT='{GEE_PROJECT}' is registered for Earth Engine.") from e
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
