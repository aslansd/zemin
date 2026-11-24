from __future__ import annotations

from pathlib import Path

from ..schema import AdapterInfo, GeoObservation
from .base import parse_long_csv

PIEZOMETER_PATTERNS: dict[str, tuple[str, ...]] = {
    "timestamp": (r"^date$", r"^obs_date$", r"^timestamp$", r"^time$"),
    "site_id": (r"well_id", r"piezo_id", r"station_id", r"site_id", r"chah"),
    "lat": (r"^lat", r"^y_wgs84", r"^northing_deg"),
    "lon": (r"^lon", r"^x_wgs84", r"^easting_deg"),
    "displacement_mm": (r"subsidence_mm", r"settlement_mm", r"disp_mm", r"vert_mm", r"extensometer_mm", r"displacement_mm"),
    "coherence": (r"coh",),
    "groundwater_depth_m": (r"depth_to_water", r"water_depth", r"gw_depth", r"dtw_m", r"piezo_m", r"head_depth"),
    "tws_cm": (r"grace_tws", r"tws_cm", r"tws"),
    "soil_moisture": (r"soil_moisture", r"era5_sm", r"swvl"),
}


def can_parse(sample_text: str) -> bool:
    low = sample_text.lower()
    return any(tok in low for tok in ("tamab", "abfa", "well_id", "piezo", "depth_to_water", "dtw_m", "extensometer"))


def load_piezometer_csv(path: Path) -> tuple[list[GeoObservation], AdapterInfo]:
    """Parse Iranian TAMAB/ABFA piezometer, extensometer, and GRACE/ERA5 hydro-subsidence logs (supports Persian digits)."""
    return parse_long_csv(
        path=path,
        adapter_name="piezometer_hydro",
        column_patterns=PIEZOMETER_PATTERNS,
        header_markers=("date", "well", "piezo", "timestamp", "dtw"),
        project_los=False,
    )
