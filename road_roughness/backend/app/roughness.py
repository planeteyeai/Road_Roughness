"""Step 3: RI / IRI per 100 m image and per 10 m block, lat/long, report assembly.
(was: Roughness_ri_calc.py, Stage 7)"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pandas as pd
from fastapi import HTTPException

from .classification import (
    MODES,
    REPORT_COLUMNS,
    SURFACES,
    classify_condition,
    classify_ri_bands,
    mode_descending,
    mode_heading,
    project_orientation,
    road_orientation,
)
from .config import BLOCK_OFFSETS, BLOCK_SIZE_M, GRAY_THRESHOLD, LINE_SPACING_M, RI_SAMPLE_POINTS
from .ndwi import _images_in
from .reports import write_excel_report, write_pdf_report
from .storage import _RUN_RE, list_runs, project_dir
from .utils import read_json


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
        sections = json.loads(df.to_json(orient="records", double_precision=10))
        records = [dict(rec, _image=img) for rec, img in zip(sections, images)]
        out[key] = {
            "rows": records, "summary": summary, "meta": meta,
            # Clean RI / IRI JSON shown (and copyable) on the page: same columns as the Excel.
            "ri_json": {
                "project": proj["name"],
                "section_length_m": int(round(sec_m)),
                "imagery_direction": meta["Road direction"],
                "pavement": carriage,
                "survey_dates": {"start": run["start"], "end": run["end"]},
                "sections": sections,
            },
            "excel_url": f"/api/projects/{pid}/files/reports/{xlsx_path.name}",
            "pdf_url": f"/api/projects/{pid}/files/reports/{pdf_path.name}",
        }
    return {"mode": mode, "heading": heading, "descending": descending, "orientation": orient, "run": {"id": run_id, "start": run["start"], "end": run["end"], "cloud": run["cloud"],
                    "n_images": run.get("n_images")},
            "skipped": skipped, "lane_tags": proj["lane_tags"], "reports": out}
