from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional, Union

import geopandas as gpd
import h3
from h3.api.basic_str import polygon_to_cells, LatLngPoly, cell_to_boundary
import numpy as np
import pandas as pd
import requests
from pyproj import Geod
from shapely.geometry import Polygon, MultiPolygon, Point, LineString, box, mapping
from shapely.ops import unary_union, split
from shapely.validation import make_valid
from shapely.errors import GEOSException
from skyfield.api import Loader, wgs84, EarthSatellite
from tqdm import tqdm


LOG = logging.getLogger(__name__)
GEOD = Geod(ellps="WGS84")
loader = Loader("~/.skyfield-data")
ts = loader.timescale()
eph = loader("de421.bsp")
SUN = eph["sun"]

# resolution choices, sampling, buffer, tolerance
SUBSAMPLES_PER_TIMESTEP = 3         # sample 3 subpoints per timestep (start, mid, end)
BUFFER_METERS = 75.0                # buffer swath before polyfill (meters) to avoid centroid-edge issues
COVERAGE_TOLERANCE = 0.995          # fraction of hex area to treat as full coverage
H3_BUFFER_SCALE_DEGREES = 0.0007    # small degree buffer (~75 m at mid lat) fallback for shapely.buffer when using lon/lat


# TODO: consider using Enums for sat names?
SATELLITES = [
    { "name": "Landsat-8",    "catalog_number": 39084, "half_swath_km": 92.5 },  # ~185 km total swath
    { "name": "Landsat-9",    "catalog_number": 49260, "half_swath_km": 92.5 },
    { "name": "Sentinel-1A",  "catalog_number": 39634, "half_swath_km": 125.0 },  # Sentinel-1 IW mode ~250 km total
    { "name": "Sentinel-1B",  "catalog_number": 41456, "half_swath_km": 125.0 },  # archival / deactivated
    { "name": "Sentinel-1C",  "catalog_number": 62261, "half_swath_km": 125.0 },  # launched Dec 2024
    { "name": "Sentinel-2A",  "catalog_number": 40697, "half_swath_km": 145.0 },  # ~290 km total swath
    { "name": "Sentinel-2B",  "catalog_number": 42063, "half_swath_km": 145.0 },  # twin of 2A
]

##########################################
# Utility helpers 

def get_satellite_params(satlist: List) -> Tuple[Dict[str, int], Dict[str, float]]:
    """Return dictionaries mapping satellite names to NORAD IDs and swath widths"""
    sats = {s["name"]: s["catalog_number"] for s in SATELLITES if s["name"] in satlist}
    swaths = {s["name"]: s["half_swath_km"] for s in SATELLITES if s["name"] in satlist}
    return sats, swaths


def fetch_archived_tles_spacetrack(norad_cat_id: int, start_dt: datetime, end_dt: datetime,
                                   username: Optional[str], password: Optional[str]) -> List[Tuple[str, str]]:
    """
    Fetch archived TLEs from Space-Track.org for a NORAD_CAT_ID.
    Returns list of (line1, line2) tuples. Raises HTTPError on failure.
    """
    if username is None or password is None:
        raise ValueError("Space-Track credentials required.")
    login_url = "https://www.space-track.org/ajaxauth/login"
    query_url = (
        f"https://www.space-track.org/basicspacedata/query/class/tle/"
        f"NORAD_CAT_ID/{norad_cat_id}/EPOCH/{start_dt:%Y-%m-%d}--{end_dt:%Y-%m-%d}/orderby/EPOCH asc/format/tle"
    )
    with requests.Session() as s:
        s.post(login_url, data={"identity": username, "password": password}).raise_for_status()
        r = s.get(query_url)
        r.raise_for_status()
        lines = [ln.strip() for ln in r.text.splitlines() if ln.strip()]
        tles = []
        i = 0
        while i < len(lines) - 1:
            l1, l2 = lines[i], lines[i+1]
            if l1.startswith("1 ") and l2.startswith("2 "):
                tles.append((l1, l2))
                i += 2
            elif not l1.startswith("1 ") and (i+2 < len(lines)) and lines[i+1].startswith("1 ") and lines[i+2].startswith("2 "):
                tles.append((lines[i+1], lines[i+2]))
                i += 3
            else:
                i += 1
        return tles


def build_earthsatellites_from_tles(tle_list: List[Tuple[str, str]], norad_label: str) -> List[EarthSatellite]:
    """
    Create Skyfield EarthSatellite objects from list of TLE pairs.
    """
    sats = []
    for idx, (l1, l2) in enumerate(tle_list):
        sats.append(EarthSatellite(l1, l2, f"{norad_label}_epoch_{idx}", ts))
    return sats


def pick_satellite_for_time(sat_list: List[EarthSatellite], sf_time) -> EarthSatellite:
    """
    Pick the EarthSatellite with the epoch closest to sf_time.
    Falls back to last element if epoch access not available.
    """
    # If single sat, return it
    if len(sat_list) == 1:
        return sat_list[0]
    # try to get epoch datetimes
    best = sat_list[-1]
    try:
        target_dt = sf_time.utc_datetime()
        best_dt = None
        best_delta = None
        for s in sat_list:
            try:
                # earthsatellite.epoch is a skyfield Time
                edt = s.epoch.utc_datetime()
            except Exception:
                # fallback: if not available, skip
                continue
            d = abs((edt - target_dt).total_seconds())
            if best_delta is None or d < best_delta:
                best_delta = d
                best = s
                best_dt = edt
    except Exception:
        # fallback - return last
        return sat_list[-1]
    return best


# ##########################################
#  Geometry utilities: dateline-safe operations 

def _lon_wrap_180(lon: float) -> float:
    """Wrap lon into [-180, 180)."""
    return ((lon + 180) % 360) - 180


def normalize_polygon_0_360(poly: Union[Polygon, MultiPolygon]) -> Union[Polygon, MultiPolygon]:
    """
    Convert polygon to 0..360 lon domain **only if** it crosses the dateline.
    If the polygon's longitude span is <= 180 degrees, return the polygon unchanged
    (except ensure coordinates are within [-180, 180) where reasonable).

    This avoids incorrectly moving western-hemisphere longitudes (e.g. -1°)
    to ~359°, which breaks intersections near the Prime Meridian.
    """
    if poly is None or poly.is_empty:
        return poly

    def lon_list_from_polygon(p: Polygon) -> List[float]:
        lons = []
        try:
            ext = list(p.exterior.coords)
            lons.extend([lon for lon, lat in ext])
            for ring in p.interiors:
                lons.extend([lon for lon, lat in ring.coords])
        except Exception:
            pass
        return lons

    # Work with a single polygon (or iterate multiparts)
    if isinstance(poly, Polygon):
        lons = lon_list_from_polygon(poly)
        if not lons:
            return poly
        min_lon = min(lons)
        max_lon = max(lons)
        span = max_lon - min_lon

        # If the polygon spans more than 180° in lon, assume it's crossing the dateline
        if span > 180.0:
            # shift negatives to 0..360 so geometry becomes continuous across 180E/W
            def shift_coords(coords):
                out = []
                for lon, lat in coords:
                    lon_s = lon if lon >= 0 else lon + 360.0
                    out.append((lon_s, lat))
                return out

            ext = shift_coords(poly.exterior.coords)
            ints = [shift_coords(r.coords) for r in poly.interiors]
            return Polygon(ext, ints)
        else:
            # no dateline crossing - return original polygon
            return poly

    else:
        # MultiPolygon: process each part individually
        parts = []
        for p in poly.geoms:
            parts.append(normalize_polygon_0_360(p))
        return MultiPolygon(parts)



def sanitize_swath_polygon(poly: Polygon) -> Union[Polygon, MultiPolygon]:
    """
    Try to make the polygon safe (valid) and handle dateline crossing robustly.
    Returns a valid Polygon or MultiPolygon where possible.
    """
    if poly is None or poly.is_empty:
        return poly

    # quick valid check
    if poly.is_valid:
        return poly

    # first attempt: shapely.make_valid
    try:
        cleaned = make_valid(poly)
        if not cleaned.is_empty and cleaned.is_valid:
            return cleaned
    except Exception:
        pass

    # fallback: buffer(0)
    try:
        buf = poly.buffer(0)
        if not buf.is_empty and buf.is_valid:
            return buf
    except Exception:
        pass

    # last resort: attempt splitting at dateline and normalizing pieces
    try:
        dateline = LineString([(180.0, -90.0), (180.0, 90.0)])
        parts = split(poly, dateline)
        pieces = []
        for g in parts.geoms if hasattr(parts, "geoms") else [parts]:
            if g.is_empty:
                continue
            # shift coords to be near centroid
            ref_lon = g.centroid.x if not g.centroid.is_empty else 180.0
            coords = []
            for lon, lat in g.exterior.coords:
                # bring lon close to ref_lon by shifting by multiples of 360
                d = lon - ref_lon
                shift = round(d / 360.0)
                lon_shifted = lon - shift * 360.0
                lon_shifted = _lon_wrap_180(lon_shifted)
                coords.append((lon_shifted, lat))
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            try:
                p = Polygon(coords)
                if not p.is_valid:
                    p = p.buffer(0)
                if not p.is_empty:
                    pieces.append(p)
            except Exception:
                continue
        if not pieces:
            return poly.buffer(0)
        combined = unary_union(pieces)
        if not combined.is_valid:
            combined = make_valid(combined)
        return combined
    except Exception:
        # if everything fails, return buffer(0)
        try:
            return poly.buffer(0)
        except Exception:
            return poly


def polygon_area_m2(poly: Polygon) -> float:
    """
    Compute approximate area of a lon/lat polygon in m^2 using pyproj.Geod.
    poly: shapely polygon in lon/lat order
    """
    if poly is None or poly.is_empty:
        return 0.0
    # exterior
    try:
        ext = list(poly.exterior.coords)
        lons, lats = zip(*ext)
        area, _ = GEOD.polygon_area_perimeter(lons, lats)
        area = abs(area)
    except Exception:
        area = 0.0
    # add interiors if present
    try:
        if poly.interiors:
            for ring in poly.interiors:
                lons, lats = zip(*list(ring.coords))
                a, _ = GEOD.polygon_area_perimeter(lons, lats)
                area -= abs(a)
    except Exception:
        pass
    return max(0.0, area)


##########################################
#  Swath building 

def offset_point(lat: float, lon: float, bearing_deg: float, distance_km: float) -> Tuple[float, float]:
    """
    Move a point by bearing and distance (on ellipsoid). Return (lat, lon).
    """
    lon2, lat2, _ = GEOD.fwd(lon, lat, bearing_deg, distance_km * 1000.0)
    return lat2, lon2


def heading_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return forward azimuth from point1 to point2 (degrees).
    """
    az12, _, _ = GEOD.inv(lon1, lat1, lon2, lat2)
    return az12


def swath_polygon_from_many_subpoints(subpoints: List[Tuple[float, float]], half_swath_km: float) -> Union[Polygon, MultiPolygon]:
    """
    Build a swath polygon from a sequence of sub-satellite points (lat, lon).
    This constructs left-edge points and right-edge points by offsetting each subpoint
    perpendicular to the track heading, then returns a stitched polygon.

    This approach reduces gaps that occur when using only two subpoints per timestep.
    """
    if len(subpoints) < 2:
        # fall back to trivial construction
        (lat0, lon0) = subpoints[0]
        latL, lonL = offset_point(lat0, lon0, 0.0, half_swath_km)
        latR, lonR = offset_point(lat0, lon0, 180.0, half_swath_km)
        return Polygon([(lonL, latL), (lonR, latR), (lonR, latR), (lonL, latL)])

    left_coords = []
    right_coords = []
    for i in range(len(subpoints) - 1):
        lat0, lon0 = subpoints[i]
        lat1, lon1 = subpoints[i+1]
        # normalize longitudes 
        lon0 = _lon_wrap_180(lon0)
        lon1 = _lon_wrap_180(lon1)
        h = heading_between(lat0, lon0, lat1, lon1)
        left_b = (h - 90.0) % 360.0
        right_b = (h + 90.0) % 360.0
        latL, lonL = offset_point(lat0, lon0, left_b, half_swath_km)
        latR, lonR = offset_point(lat0, lon0, right_b, half_swath_km)
        left_coords.append((_lon_wrap_180(lonL), latL))
        right_coords.append((_lon_wrap_180(lonR), latR))
    # add last subpoint offsets (use heading from last segment)
    lat_last, lon_last = subpoints[-1]
    if len(subpoints) >= 2:
        hlast = heading_between(subpoints[-2][0], subpoints[-2][1], subpoints[-1][0], subpoints[-1][1])
        left_b = (hlast - 90.0) % 360.0
        right_b = (hlast + 90.0) % 360.0
        latL, lonL = offset_point(lat_last, lon_last, left_b, half_swath_km)
        latR, lonR = offset_point(lat_last, lon_last, right_b, half_swath_km)
        left_coords.append((_lon_wrap_180(lonL), latL))
        right_coords.append((_lon_wrap_180(lonR), latR))

    # Build polygon ring: left edge (forward), right edge reversed (back to start)
    ring = left_coords + right_coords[::-1]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    raw = Polygon(ring)
    return sanitize_swath_polygon(raw)


##########################################
#  H3 helpers

def h3_hex_polygon(hexid: str) -> Polygon:
    """
    Return shapely Polygon for an H3 hex id using cell_to_boundary (lat, lon).
    Output polygon coordinates are (lon, lat).
    """
    latlon = cell_to_boundary(hexid)  # returns list of (lat, lon)
    coords = [(lon, lat) for lat, lon in latlon]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return Polygon(coords)


def h3_polyfill(poly: Union[Polygon, dict, list], res: int, buffer_meters: float = BUFFER_METERS) -> List[str]:
    """
    Fill an input polygon with H3 cells (v4.3.1 LatLngPoly).

    Accepts shapely Polygon, GeoJSON-like dict, or list of (lon, lat).
    We first optionally apply a small buffer (in degrees approx) to avoid centroid-edge problems,
    then build a LatLngPoly (list of (lat, lon)) and call polygon_to_cells.

    Important: ensure lon values are in [-180, 180) when calling H3.
    """
    if poly is None:
        return []

    # If shapely polygon, ensure valid and sanitized
    if isinstance(poly, Polygon) or isinstance(poly, MultiPolygon):
        p = poly
        if not p.is_valid:
            p = sanitize_swath_polygon(p)
    elif isinstance(poly, dict) and poly.get("type") == "Polygon":
        coords = poly["coordinates"][0]
        p = Polygon(coords)
    elif isinstance(poly, (list, tuple)):
        # assume list of (lon, lat)
        p = Polygon(poly)
    else:
        raise TypeError(f"h3_polyfill: unsupported polygon type {type(poly)}")

    # Quick empty guard
    if p.is_empty:
        return []

    # approximate buffer in degrees if buffer_meters > 0
    if buffer_meters and buffer_meters > 0:
        buffer_deg = buffer_meters / 111320.0
        try:
            p = p.buffer(buffer_deg)
        except Exception:
            pass

    # Build exterior coords but ensure longitudes are in [-180, 180)
    try:
        ext = list(p.exterior.coords)
    except Exception:
        return []

    # Normalize longitudes into [-180, 180) because H3 expects conventional lon range
    normalized_ext = [(_lon_wrap_180(lon), lat) for lon, lat in ext]

    # H3 wants list of (lat, lon), not (lon, lat)
    latlon = [(lat, lon) for lon, lat in normalized_ext]
    latlng = LatLngPoly(latlon)

    try:
        cells = polygon_to_cells(latlng, res)
    except Exception as e:
        LOG.debug("h3 polygon_to_cells failed: %s -- trying simplified polygon", e)
        try:
            simp = p.simplify(1e-4)
            ext = list(simp.exterior.coords)
            normalized_ext = [(_lon_wrap_180(lon), lat) for lon, lat in ext]
            latlon = [(lat, lon) for lon, lat in normalized_ext]
            cells = polygon_to_cells(LatLngPoly(latlon), res)
        except Exception as e2:
            LOG.exception("h3_polyfill ultimately failed: %s", e2)
            return []
    return list(cells)


##########################################
#  Daylight / Sun checks 

def is_daytime_at_point(lat: float, lon: float, sf_time: Any) -> bool:
    """Determine if a location is in daylight at a given Skyfield time

    Args:
        lat (float): Latitude, degrees
        lon (float): Longitude, degrees
        sf_time (skyfield.api.Time): Skyfield time object

    Returns:
        bool: True if the point is illuminated by the Sun, False if night.
    """
    # Explicitly add the ground point to the Earth object
    # This creates a correct Observer/Vector object (centered at 399) 
    # that can correctly observe targets (like the SUN, centered at 0).
    
    # Define the ground station relative to the Earth body
    station = eph['earth'] + wgs84.latlon(lat, lon)
    
    # Get the vector from the station to the sun, at time sf_time
    geometry = station.at(sf_time).observe(SUN)
    
    # Compute apparent altaz
    alt, _, _ = geometry.apparent().altaz()
    return alt.degrees > 0.0


##########################################
#  Export helpers 

def export_full_coverage_events(full_coverage_events: Dict[Tuple[str, str], List[datetime]], path: str):
    """
    Save full_coverage_events to JSON. Datetimes are ISO-formatted.
    full_coverage_events keys: (sat_name, h3_index) -> list[datetime]
    """
    out = {}
    for (sat, h3idx), times in full_coverage_events.items():
        out_key = f"{sat}|{h3idx}"
        out[out_key] = [t.isoformat() for t in times]
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    LOG.info("Saved full_coverage_events to %s", path)


##########################################
#  Main computation 

def compute_cumulative_full_coverage(
    space_track_user: str,
    space_track_pass: str,
    start: datetime,
    end: datetime,
    sats: Dict[str, int],
    regions: Dict[str, Tuple[float, float, float, float]],
    timestep_s: int,
    swaths_km: Dict[str, float],
    resolutions: List[int],
    daylight_only_for_optical: bool = True,
) -> Tuple[Dict[int, pd.DataFrame], Dict[Tuple[str, str], List[datetime]]]:
    """
    Compute cumulative "full coverage" events per H3 cell for given satellites and window.

    Google-style docstring summary:
    Args:
        space_track_user: Space-Track username
        space_track_pass: Space-Track password
        start: UTC start datetime
        end: UTC end datetime
        sats: mapping satellite_name -> NORAD_CAT_ID
        regions: mapping region_name -> (lon_min, lat_min, lon_max, lat_max)
        timestep_s: step interval (seconds)
        swaths_km: mapping satellite_name -> half_swath_km
        resolutions: list of H3 resolutions to evaluate
        daylight_only_for_optical: if True, require daytime only for optical satellites (Landsat/Sentinel-2).
                                   SAR satellites (Sentinel-1) ignored for daylight test.

    Returns:
        (results_by_res, full_coverage_events)
        - results_by_res: dict res -> pandas.DataFrame summarizing per-hex coverage
        - full_coverage_events: dict (sat_name, h3_index) -> list of datetimes (first coverage times)
    """
    # data holders
    pieces = defaultdict(list)                        # (res, sat, hexid) -> list of partial polygons
    completion_events = defaultdict(list)             # (sat, hexid) -> list of datetimes
    last_covered_time = defaultdict(lambda: datetime.min)
    invalid_swaths = []                                # log invalid swath geometries / exceptions
    total_timesteps = 0

    # build sat objects from TLEs
    sat_objects = {}
    for sat_name, norad in sats.items():
        try:
            tles = fetch_archived_tles_spacetrack(norad, start, end, space_track_user, space_track_pass)
        except Exception as e:
            LOG.exception("Failed to fetch TLEs for %s: %s", sat_name, e)
            continue
        if not tles:
            LOG.warning("No TLEs for %s; skipping", sat_name)
            continue
        sat_objects[sat_name] = build_earthsatellites_from_tles(tles, sat_name)

    # time stepping
    total_seconds = int((end - start).total_seconds())
    n_steps = max(1, total_seconds // timestep_s + 1)
    LOG.info("Sampling every %ds -> %d steps", timestep_s, n_steps)

    # build region polygons for faster intersection tests
    region_polys = [box(lonmin, latmin, lonmax, latmax) for lonmin, latmin, lonmax, latmax in regions.values()]

    for step_index in tqdm(range(max(1, n_steps - 1)), desc="timesteps"):
        t0 = start + timedelta(seconds=step_index * timestep_s)
        t1 = start + timedelta(seconds=(step_index + 1) * timestep_s)
        sf_t0 = ts.utc(t0.year, t0.month, t0.day, t0.hour, t0.minute, t0.second)
        sf_t1 = ts.utc(t1.year, t1.month, t1.day, t1.hour, t1.minute, t1.second)
        total_timesteps += 1

        for sat_name, sat_list in sat_objects.items():
            # pick best TLE for this time
            sat = pick_satellite_for_time(sat_list, sf_t0)

            # build subpoints across the timestep (start, mid, end -> reduces curvature gap)
            subpoints = []
            for i in range(SUBSAMPLES_PER_TIMESTEP):
                frac = i / (SUBSAMPLES_PER_TIMESTEP - 1) if SUBSAMPLES_PER_TIMESTEP > 1 else 0.0
                tfrac = t0 + timedelta(seconds=frac * (t1 - t0).total_seconds())
                sft = ts.utc(tfrac.year, tfrac.month, tfrac.day, tfrac.hour, tfrac.minute, tfrac.second)
                try:
                    sp = sat.at(sft).subpoint()
                    lat = sp.latitude.degrees
                    lon = sp.longitude.degrees
                    # ensure lon is within [-180,180)
                    lon = _lon_wrap_180(lon)
                    subpoints.append((lat, lon))
                except Exception as e:
                    LOG.debug("propagation failed for %s at %s: %s", sat_name, tfrac, e)
                    subpoints = []
                    break
            if not subpoints or len(subpoints) < 1:
                continue

            half_swath_km = swaths_km.get(sat_name, swaths_km.get("default", 90.0))

            # build swath polygon from multiple subpoints
            try:
                swath_poly = swath_polygon_from_many_subpoints(subpoints, half_swath_km)
            except Exception as e:
                LOG.debug("failed building swath poly for %s at %s: %s", sat_name, t0, e)
                invalid_swaths.append((sat_name, t0, "make_swath_error", str(e)))
                continue

            if swath_poly is None or swath_poly.is_empty:
                continue

            # quick region prefilter: if swath doesn't intersect any region, skip
            if not any(swath_poly.intersects(rp) for rp in region_polys):
                continue

            # for each requested res -> convert swath to candidate hexes
            for res in resolutions:
                try:
                    # slightly expand swath before polyfill to account for centroid fill behaviour
                    candidate_hexes = h3_polyfill(swath_poly, res, buffer_meters=BUFFER_METERS)
                except Exception as e:
                    LOG.exception("h3_polyfill failed for %s at %s: %s", sat_name, t0, e)
                    candidate_hexes = []

                if not candidate_hexes:
                    continue

                # for each candidate hex, compute intersection and accumulate coverage
                for hexid in candidate_hexes:
                    try:
                        hex_poly = h3_hex_polygon(hexid)
                    except Exception as e:
                        LOG.debug("failed to get hex polygon %s: %s", hexid, e)
                        continue

                    # debugging
                    """
                    print(swath_poly.area)
                    print(swath_poly.centroid.x, swath_poly.centroid.y)
                    print(hex_poly.centroid.x, hex_poly.centroid.y)
                    inter = swath_poly.intersection(hex_poly)
                    print(inter.geom_type, inter.area)
                    """
                    
                    # Normalize both into same domain (0..360) to avoid dateline mismatch before intersection
                    try:
                        sw_norm = normalize_polygon_0_360(swath_poly)
                        hex_norm = normalize_polygon_0_360(hex_poly)
                        inter = sw_norm.intersection(hex_norm)
                    except GEOSException as e:
                        LOG.debug("GEOS Exception during intersection (skipping): sat=%s hex=%s time=%s err=%s", sat_name, hexid, t0, e)
                        invalid_swaths.append((sat_name, hexid, t0.isoformat(), str(e)))
                        continue
                    except Exception as e:
                        LOG.debug("Unexpected intersection error (skipping): %s", e)
                        invalid_swaths.append((sat_name, hexid, t0.isoformat(), str(e)))
                        continue

                    if inter.is_empty:
                        continue

                    # For optical satellites (Landsat, Sentinel-2), optionally require daylight
                    require_day = False
                    if daylight_only_for_optical and ("Landsat" in sat_name or "Sentinel-2" in sat_name):
                        require_day = True

                    if require_day:
                        # use hex centroid for daylight test (cheap)
                        latc, lonc = h3.cell_to_latlng(hexid)
                        if not is_daytime_at_point(latc, lonc, sf_t0):
                            continue

                    # store piece
                    key = (res, sat_name, hexid)
                    pieces[key].append(inter)

                    # Avoid repeated union test too frequently: skip if we just recorded coverage
                    if t0 <= last_covered_time[key] + timedelta(seconds=timestep_s):
                        continue

                    # compute union safely
                    try:
                        union_geom = unary_union(pieces[key])
                    except Exception as e:
                        LOG.debug("union error for key %s: %s", key, e)
                        # if union fails, reset pieces to avoid accumulation of invalid fragments
                        pieces[key] = []
                        continue

                    # area-based test: compute area of union ∩ hex and compare with hex area
                    try:
                        # compute areas in m^2 using geod
                        # normalize union and hex to lon/lat domain
                        hex_area = polygon_area_m2(hex_poly)
                        if union_geom.is_empty or hex_area <= 0:
                            covered_fraction = 0.0
                        else:
                            # intersection of union and hex (should be subset)
                            overlap = union_geom.intersection(hex_poly)
                            overlap_area = 0.0
                            if overlap.is_empty:
                                overlap_area = 0.0
                            elif overlap.geom_type == "Polygon":
                                overlap_area = polygon_area_m2(overlap)
                            else:
                                # MultiPolygon
                                for g in overlap.geoms:
                                    if g.geom_type == "Polygon":
                                        overlap_area += polygon_area_m2(g)
                            covered_fraction = overlap_area / hex_area if hex_area > 0 else 0.0
                    except Exception as e:
                        LOG.debug("area calc failed for %s: %s", key, e)
                        covered_fraction = 0.0

                    # if coverage meets tolerance -> record full coverage event
                    if covered_fraction >= COVERAGE_TOLERANCE:
                        # double-check hex is within our desired regions (polygon-region intersection)
                        latc, lonc = h3.cell_to_latlng(hexid)
                        # note: in_many regions we used region polygons earlier
                        pt = Point(lonc, latc)
                        if not any(rp.contains(pt) or rp.intersects(h3_hex_polygon(hexid)) for rp in region_polys):
                            # hex not actually in region - skip
                            continue
                        # record event
                        completion_events[(sat_name, hexid)].append(t0)
                        last_covered_time[key] = t0
                        # reset pieces for that key so revisit intervals can be recorded anew later
                        pieces[key] = []

    # build results DataFrames per resolution
    results_by_res = {}
    for res in resolutions:
        rows = []
        # collect all hex ids seen for this res across all satellites
        seen_hexes = set(k[2] for k in pieces.keys() if k[0] == res) | set(k[1] for k in completion_events.keys() if k[0] == res if False)
        # It's easier to derive hexes from completion_events as well
        seen_hexes |= set(h for (s,h) in completion_events.keys())

        for hexid in tqdm(seen_hexes, desc="Processing hexes"):
            try:
                latc, lonc = h3.cell_to_latlng(hexid)
            except Exception:
                continue
            # ensure hex lies inside one of requested regions (use polygon test)
            hex_poly = h3_hex_polygon(hexid)
            if not any(hex_poly.intersects(rp) for rp in region_polys):
                continue
            # find first completion time if any
            times = []
            for (sat, h3id), tlist in completion_events.items():
                if h3id == hexid:
                    times.extend(tlist)
            times = sorted(times)
            first_completion = times[0].isoformat() if times else ""
            fully_covered = len(times) > 0
            rows.append({
                "res": res,
                "h3_index": hexid,
                "lon": lonc,
                "lat": latc,
                "fully_covered": fully_covered,
                "first_completion_time": first_completion,
                "max_covered_fraction": 1.0 if fully_covered else 0.0
            })
        results_by_res[res] = pd.DataFrame(rows)

    LOG.info("Done. timesteps: %d, invalid swaths: %d", total_timesteps, len(invalid_swaths))
    if invalid_swaths:
        LOG.debug("invalid_swaths sample: %s", invalid_swaths[:20])
    return results_by_res, completion_events



def calculate_revisit_rate_dataframe(
    full_coverage_events: Dict[Tuple[str, str], List[datetime]],
    combine_satellites: bool = True
) -> pd.DataFrame:
    """Calculate average revisit rates from full coverage event data

    Computes the mean revisit interval (in hours) for each H3 cell, optionally
        combining multiple satellites into a single revisit stream

    Args:
        full_coverage_events (Dict[Tuple[str, str], List[datetime]]):
            Dictionary mapping (satellite name, H3 cell) to lists of datetime coverage events.
        combine_satellites (bool, optional):
            If True, merge all satellites when calculating revisit rate.
            If False, calculate revisit rate per satellite. Defaults to True.

    Returns:
        pd.DataFrame: DataFrame containing columns:
            ["h3_index", "satellite", "res", "lon", "lat",
             "num_revisits", "revisit_rate_hours", "first_completion_time"]

    Notes:
        - Revisit rate is computed as the mean delta between consecutive full-coverage events.
        - Rows with fewer than two events are omitted (no measurable revisit rate).
    """
    
    # Define the list of columns to guarantee their existence
    REQUIRED_COLUMNS = [
        "h3_index", "satellite", "res", "lon", "lat", 
        "num_revisits", "revisit_rate_hours", "first_completion_time"
    ]

    # Flatten and Clean Data into a List of Records
    event_records = []
    
    for key, times in full_coverage_events.items():
        sat_name = None
        hex_id = None
        
        # Robust Key Unpacking
        if isinstance(key, tuple):
            if len(key) == 2:
                sat_name, hex_id = key
            elif len(key) == 1 and isinstance(key[0], tuple) and len(key[0]) == 2:
                sat_name, hex_id = key[0]

        if not hex_id:
            continue
            
        # Create a record for each *individual* event time
        for t in times:
            event_records.append({
                'sat_name': sat_name,
                'hex_id': hex_id,
                'time': t
            })
  
    # Create Base DataFrame and Define Grouping
    if not event_records:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    events_df = pd.DataFrame(event_records)
    
    # Define the column(s) to group by
    group_cols = ['hex_id'] if combine_satellites else ['sat_name', 'hex_id']

    # Group and Calculate Metrics
    def calculate_metrics(group: pd.DataFrame) -> pd.Series:
        times = group['time'].sort_values().tolist()
        
        row_data = {
            'h3_index': group['hex_id'].iloc[0],
            'satellite': group['sat_name'].iloc[0] if 'sat_name' in group.columns else 'Combined',
            'first_completion_time': times[0].isoformat() if times else None,
            'num_revisits': 0,
            'revisit_rate_hours': None
        }

        if len(times) >= 2:
            time_diffs_s = [(times[i] - times[i-1]).total_seconds() for i in range(1, len(times))]
            total_seconds = sum(time_diffs_s)
            
            row_data['num_revisits'] = len(time_diffs_s)
            row_data['revisit_rate_hours'] = (total_seconds / len(time_diffs_s)) / 3600.0

        return pd.Series(row_data)

    # Apply the calculation across all groups
    revisit_df = events_df.groupby(group_cols).apply(calculate_metrics)
    
    # Reset index to make group columns normal columns
    revisit_df = revisit_df.reset_index(drop=True)

    # Add Metadata and Final Clean-up 
    try:
        revisit_df['res'] = revisit_df['h3_index'].apply(h3.get_resolution)
    except AttributeError:
        # Older versions of H3 use this -- but better to avoid falling back to this!
        revisit_df['res'] = revisit_df['h3_index'].apply(h3.h3_get_resolution)
    
    # Ensure cell_to_latlng works:
    lat_lon = np.array([h3.cell_to_latlng(h) for h in revisit_df['h3_index']]) 
    revisit_df['lat'] = lat_lon[:, 0]
    revisit_df['lon'] = lat_lon[:, 1]
    
    # Final cleanup: drop rows that did not achieve a revisit
    final_df = revisit_df.dropna(subset=['revisit_rate_hours']).copy()
    
    # Ensure all required columns are present in the final output
    return final_df[REQUIRED_COLUMNS]