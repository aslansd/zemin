from __future__ import annotations

import csv
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schema import AdapterInfo, GeoObservation

_PERSIAN_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬", "01234567890123456789.,")

_TIMESTAMP_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y%m%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
)


def normalize_digits(text: str) -> str:
    return text.translate(_PERSIAN_ARABIC_DIGITS).strip()


def parse_float(raw: Any, decimal_comma: bool = False) -> float | None:
    if raw is None:
        return None
    text = normalize_digits(str(raw))
    if not text or text.lower() in {"na", "n/a", "nan", "null", "none", "-", "--", "nodata"}:
        return None
    text = re.sub(r"\s*(mm|cm|m|deg|°)$", "", text, flags=re.IGNORECASE).strip()
    if decimal_comma and "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text and re.match(r"^-?\d+,\d{1,3}$", text):
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_timestamp(raw: Any) -> datetime:
    text = normalize_digits(str(raw))
    if not text:
        raise ValueError("Empty timestamp")
    if text.startswith(("D", "d")) and re.fullmatch(r"[Dd]\d{8}", text):
        text = text[1:]
    if re.fullmatch(r"\d{10}(\.\d+)?", text):
        return datetime.fromtimestamp(float(text), tz=timezone.utc).replace(tzinfo=None)
    iso = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(iso)
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
    except ValueError:
        pass
    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date/timestamp format: {raw!r}")


def detect_delimiter(header_line: str) -> str:
    for delim in (";", ",", "\t"):
        if delim in header_line and len(header_line.split(delim)) >= 2:
            return delim
    return ","


def infer_displacement_scale_to_mm(col_name: str) -> float:
    low = col_name.lower()
    if any(tok in low for tok in ("_m", "(m)", "[m]", "meters", "metre")) and "mm" not in low and "cm" not in low:
        return 1000.0
    if any(tok in low for tok in ("_cm", "(cm)", "[cm]")) and "mm" not in low:
        return 10.0
    return 1.0


def match_columns(fieldnames: list[str], patterns: dict[str, tuple[str, ...]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    cleaned = [(c, re.sub(r"\s+", " ", c.strip().lower())) for c in fieldnames if c]
    for canonical, regexes in patterns.items():
        for rx in regexes:
            compiled = re.compile(rx, flags=re.IGNORECASE)
            for orig, low in cleaned:
                if compiled.search(low):
                    mapping[canonical] = orig
                    break
            if canonical in mapping:
                break
    return mapping


def project_los_to_vertical(los_mm: float, incidence_deg: float) -> float:
    cos_theta = math.cos(math.radians(incidence_deg))
    if abs(cos_theta) < 0.2:
        return los_mm
    return los_mm / cos_theta


def parse_long_csv(
    path: Path,
    adapter_name: str,
    column_patterns: dict[str, tuple[str, ...]],
    header_markers: tuple[str, ...],
    project_los: bool = False,
    default_incidence_deg: float = 38.0,
    max_preamble_lines: int = 25,
) -> tuple[list[GeoObservation], AdapterInfo]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = 0
    delimiter = ","

    for idx, line in enumerate(lines[:max_preamble_lines]):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cand_delim = detect_delimiter(stripped)
        cols = [c.strip().strip('"').lower() for c in stripped.split(cand_delim)]
        if len(cols) >= 2 and any(any(m in c for m in header_markers) for c in cols):
            header_idx = idx
            delimiter = cand_delim
            break

    data_lines = lines[header_idx:]
    if not data_lines:
        raise ValueError(f"No tabular data found in {path}")

    reader = csv.DictReader(data_lines, delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError(f"Empty CSV header in {path}")

    col_map = match_columns(list(reader.fieldnames), column_patterns)
    if "timestamp" not in col_map or "displacement_mm" not in col_map:
        raise ValueError(
            f"Adapter '{adapter_name}' could not resolve required date/timestamp and displacement columns "
            f"from headers {reader.fieldnames!r} (resolved={col_map})."
        )

    disp_scale = infer_displacement_scale_to_mm(col_map["displacement_mm"])
    dec_comma = delimiter == ";"
    used_los = project_los or ("los" in col_map["displacement_mm"].lower())
    inc_used: float | None = None
    observations: list[GeoObservation] = []

    for row in reader:
        if not row:
            continue
        raw_ts = row.get(col_map["timestamp"])
        raw_disp = parse_float(row.get(col_map["displacement_mm"]), decimal_comma=dec_comma)
        if not raw_ts or raw_disp is None:
            continue
        try:
            ts = parse_timestamp(raw_ts)
        except ValueError:
            continue

        def opt(name: str) -> float | None:
            src = col_map.get(name)
            return parse_float(row.get(src), decimal_comma=dec_comma) if src else None

        disp_mm = raw_disp * disp_scale
        if used_los:
            inc_val = opt("incidence_deg")
            angle = inc_val if inc_val is not None else default_incidence_deg
            inc_used = angle
            disp_mm = project_los_to_vertical(disp_mm, angle)

        site_col = col_map.get("site_id")
        site_id = normalize_digits(str(row.get(site_col) or "SITE_01")) if site_col else "SITE_01"
        lat = opt("lat")
        lon = opt("lon")

        observations.append(
            GeoObservation(
                timestamp=ts,
                site_id=site_id or "SITE_01",
                lat=lat if lat is not None else 35.6500,
                lon=lon if lon is not None else 51.3100,
                displacement_mm=round(disp_mm, 4),
                coherence=opt("coherence"),
                groundwater_depth_m=opt("groundwater_depth_m"),
                tws_cm=opt("tws_cm"),
                soil_moisture=opt("soil_moisture"),
                los_projected=used_los,
            )
        )

    observations.sort(key=lambda o: (o.site_id, o.timestamp))
    info = AdapterInfo(
        adapter=adapter_name,
        delimiter=delimiter,
        skipped_preamble_lines=header_idx,
        displacement_unit_scale=disp_scale,
        los_incidence_deg=inc_used,
        resolved_columns=col_map,
    )
    return observations, info
