from __future__ import annotations

import csv
import re
from pathlib import Path

from ..schema import AdapterInfo, GeoObservation
from .base import (
    detect_delimiter,
    match_columns,
    normalize_digits,
    parse_float,
    parse_long_csv,
    parse_timestamp,
    project_los_to_vertical,
)

MINTPY_LONG_PATTERNS: dict[str, tuple[str, ...]] = {
    "timestamp": (r"^date$", r"^epoch$", r"^timestamp$", r"^acq_date$"),
    "site_id": (r"^point_id$", r"^pid$", r"^ps_id$", r"^site_id$", r"^pixel_id$"),
    "lat": (r"^lat", r"^latitude$"),
    "lon": (r"^lon", r"^longitude$"),
    "displacement_mm": (r"los.*disp", r"los_mm", r"los_m", r"disp_los", r"displacement", r"vert_mm"),
    "incidence_deg": (r"inc_angle", r"incidence", r"theta"),
    "coherence": (r"temp_coh", r"temporal_coherence", r"^coh", r"coherence"),
    "groundwater_depth_m": (r"gw_depth", r"depth_to_water", r"piezo"),
    "tws_cm": (r"tws", r"grace"),
}

_DATE_COL_RE = re.compile(r"^[Dd]?(\d{8}|\d{4}-\d{2}-\d{2})$")


def can_parse(sample_text: str) -> bool:
    low = sample_text.lower()
    if any(tok in low for tok in ("mintpy", "hyp3", "aria", "temp_coh", "temporal_coherence", "los_disp", "los_m")):
        return True
    first_lines = [ln for ln in sample_text.splitlines()[:10] if ln.strip() and not ln.strip().startswith("#")]
    for ln in first_lines:
        cols = [c.strip().strip('"') for c in ln.split(detect_delimiter(ln))]
        date_cols = [c for c in cols if _DATE_COL_RE.match(c)]
        if len(date_cols) >= 3:
            return True
    return False


def load_mintpy_csv(path: Path, default_incidence_deg: float = 38.0) -> tuple[list[GeoObservation], AdapterInfo]:
    """Parse MintPy / ASF HyP3 / PS-InSAR CSV exports (supports both long format and wide DYYYYMMDD epoch matrices)."""
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = 0
    delimiter = ","
    wide_date_cols: list[str] = []

    for idx, ln in enumerate(lines[:20]):
        stripped = ln.strip()
        if not stripped or stripped.startswith("#"):
            continue
        delim = detect_delimiter(stripped)
        cols = [c.strip().strip('"') for c in stripped.split(delim)]
        dcols = [c for c in cols if _DATE_COL_RE.match(c)]
        if len(dcols) >= 3:
            header_idx = idx
            delimiter = delim
            wide_date_cols = dcols
            break

    if not wide_date_cols:
        return parse_long_csv(
            path=path,
            adapter_name="mintpy_insar",
            column_patterns=MINTPY_LONG_PATTERNS,
            header_markers=("date", "epoch", "timestamp", "los"),
            default_incidence_deg=default_incidence_deg,
        )

    reader = csv.DictReader(lines[header_idx:], delimiter=delimiter)
    fieldnames = list(reader.fieldnames or [])
    col_map = match_columns(fieldnames, MINTPY_LONG_PATTERNS)
    dec_comma = delimiter == ";"
    header_text = " ".join(lines[:header_idx + 1]).lower()
    disp_scale = 1000.0 if ("unit: m" in header_text or "(m)" in header_text) and "mm" not in header_text else 1.0
    is_los = "vert" not in header_text

    obs: list[GeoObservation] = []
    inc_used: float | None = None
    for row_idx, row in enumerate(reader, 1):
        site_col = col_map.get("site_id")
        site_id = normalize_digits(str(row.get(site_col) or f"PS_{row_idx:03d}")) if site_col else f"PS_{row_idx:03d}"
        lat = parse_float(row.get(col_map["lat"]), dec_comma) if "lat" in col_map else 35.6500
        lon = parse_float(row.get(col_map["lon"]), dec_comma) if "lon" in col_map else 51.3100
        coh = parse_float(row.get(col_map["coherence"]), dec_comma) if "coherence" in col_map else None
        inc = parse_float(row.get(col_map["incidence_deg"]), dec_comma) if "incidence_deg" in col_map else default_incidence_deg
        if is_los and inc is not None:
            inc_used = inc

        for dcol in wide_date_cols:
            raw_v = parse_float(row.get(dcol), dec_comma)
            if raw_v is None:
                continue
            disp_mm = raw_v * disp_scale
            if is_los and inc is not None:
                disp_mm = project_los_to_vertical(disp_mm, inc)
            obs.append(
                GeoObservation(
                    timestamp=parse_timestamp(dcol),
                    site_id=site_id,
                    lat=lat if lat is not None else 35.6500,
                    lon=lon if lon is not None else 51.3100,
                    displacement_mm=round(disp_mm, 4),
                    coherence=coh,
                    los_projected=is_los,
                )
            )

    obs.sort(key=lambda o: (o.site_id, o.timestamp))
    return obs, AdapterInfo(
        adapter="mintpy_insar_wide",
        delimiter=delimiter,
        skipped_preamble_lines=header_idx,
        displacement_unit_scale=disp_scale,
        los_incidence_deg=inc_used,
        resolved_columns={**col_map, "epoch_columns": f"{len(wide_date_cols)} epochs"},
    )
