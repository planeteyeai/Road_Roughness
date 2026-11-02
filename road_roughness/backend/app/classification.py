"""RI / IRI bands, pavement tables, report columns and road-direction helpers."""

from pathlib import Path

from .config import GEOD
from .utils import read_json


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
