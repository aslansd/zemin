from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .schema import GeoObservation

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 coordinates in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test on a GeoJSON [lon, lat] linear ring."""
    if len(ring) < 3:
        return False
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        if abs(yi - yj) < 1e-12 and abs(lat - yi) < 1e-12 and min(xi, xj) <= lon <= max(xi, xj):
            return True
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-18) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _extract_polygons(geojson: dict[str, Any]) -> list[list[list[list[float]]]]:
    gtype = geojson.get("type")
    if gtype == "Polygon":
        return [geojson["coordinates"]]
    if gtype == "MultiPolygon":
        return list(geojson["coordinates"])
    if gtype == "Feature":
        return _extract_polygons(geojson.get("geometry") or {})
    if gtype == "FeatureCollection":
        polys: list[list[list[list[float]]]] = []
        for feat in geojson.get("features", []):
            polys.extend(_extract_polygons(feat))
        return polys
    raise ValueError(f"Unsupported GeoJSON type for polygon filtering: {gtype!r}")


def load_geojson_polygons(path: str | Path) -> list[list[list[list[float]]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    polys = _extract_polygons(data)
    if not polys:
        raise ValueError(f"No Polygon or MultiPolygon geometries found in {path}")
    return polys


def point_in_polygons(lat: float, lon: float, polygons: list[list[list[list[float]]]]) -> bool:
    for poly in polygons:
        if not point_in_ring(lon, lat, poly[0]):
            continue
        if not any(point_in_ring(lon, lat, hole) for hole in poly[1:]):
            return True
    return False


def filter_observations_by_polygon(
    observations: list[GeoObservation],
    polygon_path: str | Path,
) -> list[GeoObservation]:
    polygons = load_geojson_polygons(polygon_path)
    return [obs for obs in observations if point_in_polygons(obs.lat, obs.lon, polygons)]
