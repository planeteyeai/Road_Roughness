"""Step 1: median line KML -> chainage points, median/lane edges, bin KMLs, merge KMLs, Excels.
(was: Full Road Pipeline script)"""

import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from xml.dom import minidom

import pandas as pd
import simplekml
from geopy import Point
from geopy.distance import geodesic

from .classification import road_orientation
from .config import CHAINAGE_DECIMALS, GEOD
from .utils import write_json


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
