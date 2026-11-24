from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..schema import AdapterInfo, GeoObservation
from .base import infer_displacement_scale_to_mm, match_columns, normalize_digits, parse_float, parse_long_csv, parse_timestamp

GENERIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "timestamp": (r"^timestamp$", r"^date$", r"^time$", r"^epoch$"),
    "site_id": (r"^site_id$", r"^point_id$", r"^station$", r"^id$"),
    "lat": (r"^lat$", r"^latitude$"),
    "lon": (r"^lon$", r"^longitude$"),
    "displacement_mm": (r"^displacement_mm$", r"^disp_mm$", r"^vert_mm$", r"^settlement_mm$", r"^displacement_m$"),
    "coherence": (r"^coherence$", r"^coh$"),
    "groundwater_depth_m": (r"^groundwater_depth_m$", r"^gw_depth_m$", r"^dtw_m$"),
    "tws_cm": (r"^tws_cm$", r"^grace_tws_cm$"),
    "soil_moisture": (r"^soil_moisture$", r"^sm$"),
}


def load_generic_geo(path: Path) -> tuple[list[GeoObservation], AdapterInfo]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_long_csv(
            path=path,
            adapter_name="generic_csv",
            column_patterns=GENERIC_PATTERNS,
            header_markers=("timestamp", "date", "epoch", "displacement"),
            max_preamble_lines=5,
        )
    if suffix in {".jsonl", ".ndjson"}:
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        if not rows:
            raise ValueError(f"No records found in {path}")
        col_map = match_columns(list(rows[0].keys()), GENERIC_PATTERNS)
        if "timestamp" not in col_map or "displacement_mm" not in col_map:
            raise ValueError(f"JSONL must contain timestamp and displacement_mm (resolved={col_map}).")
        scale = infer_displacement_scale_to_mm(col_map["displacement_mm"])
        obs: list[GeoObservation] = []
        for row in rows:
            raw_ts = row.get(col_map["timestamp"])
            raw_d = parse_float(row.get(col_map["displacement_mm"]))
            if not raw_ts or raw_d is None:
                continue

            def opt(name: str) -> float | None:
                src = col_map.get(name)
                return parse_float(row.get(src)) if src else None

            site_col = col_map.get("site_id")
            obs.append(
                GeoObservation(
                    timestamp=parse_timestamp(raw_ts),
                    site_id=normalize_digits(str(row.get(site_col) or "SITE_01")) if site_col else "SITE_01",
                    lat=opt("lat") if opt("lat") is not None else 35.6500,
                    lon=opt("lon") if opt("lon") is not None else 51.3100,
                    displacement_mm=round(raw_d * scale, 4),
                    coherence=opt("coherence"),
                    groundwater_depth_m=opt("groundwater_depth_m"),
                    tws_cm=opt("tws_cm"),
                    soil_moisture=opt("soil_moisture"),
                )
            )
        obs.sort(key=lambda o: (o.site_id, o.timestamp))
        return obs, AdapterInfo(
            adapter="generic_jsonl",
            delimiter="jsonl",
            displacement_unit_scale=scale,
            resolved_columns=col_map,
        )
    raise ValueError(f"Unsupported file format '{suffix}'. Use .csv or .jsonl.")
