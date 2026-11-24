from __future__ import annotations

import csv
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

from .schema import GeoObservation

TEHRAN_D18_CORRIDOR_GEOJSON = {
    "type": "FeatureCollection",
    "name": "Tehran_District18_Azadegan_Corridor",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "SW Tehran District 18 Water Main & Metro Corridor",
                "city": "Tehran",
                "asset_type": "metro_and_water_trunk",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [51.2950, 35.6350],
                        [51.3300, 35.6350],
                        [51.3300, 35.6650],
                        [51.2950, 35.6650],
                        [51.2950, 35.6350],
                    ]
                ],
            },
        }
    ],
}


def write_sample_geojson(path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(TEHRAN_D18_CORRIDOR_GEOJSON, indent=2), encoding="utf-8")
    return out


def generate_tehran_subsidence_dataset(
    years: float = 3.0,
    repeat_days: int = 12,
    severe_basin: bool = True,
    seed: int = 42,
    start_date: datetime | None = None,
) -> list[GeoObservation]:
    """Generate realistic Sentinel-1 12-day InSAR + piezometer + GRACE dataset for Tehran."""
    rng = random.Random(seed)
    start = start_date or datetime(2023, 10, 1)
    n_epochs = int((years * 365.25) / repeat_days) + 1

    if not severe_basin:
        sites = [
            ("SHM_01", 35.6450, 51.3050, -1.2, 0.0, 4.2),
            ("SHM_02", 35.6458, 51.3050, -1.6, 0.0, 4.0),
            ("SHM_03", 35.6450, 51.3060, -1.4, 0.0, 4.1),
        ]
    else:
        sites = [
            ("D18_BOWL_A", 35.6480, 51.3100, -135.0, -28.0, 5.5),
            ("D18_EDGE_B", 35.6489, 51.3100, -35.0, -4.0, 3.8),
            ("D18_TRUNK_C", 35.6480, 51.3114, -110.0, -18.0, 4.5),
            ("OUTSIDE_CTRL", 35.7900, 51.4300, -1.0, 0.0, 3.5),
        ]

    obs: list[GeoObservation] = []
    for sid, lat, lon, v0, acc, base_amp in sites:
        ar_state = 0.0
        for k in range(n_epochs):
            ts = start + timedelta(days=k * repeat_days)
            t = (ts - start).total_seconds() / (365.25 * 86400.0)
            frac = k / max(1, n_epochs - 1)

            if severe_basin and sid == "D18_BOWL_A":
                phi = 0.05 + 0.87 * frac
                sigma = 0.6 + 1.8 * frac
                ar_state = phi * ar_state + rng.gauss(0, sigma)
                amp_t = base_amp * (1.0 - 0.75 * frac)
                disp = v0 * t + 0.5 * acc * (t ** 2) + amp_t * math.sin(2.0 * math.pi * t) + ar_state
                coh = 0.82 + rng.gauss(0, 0.03)
                gw = 42.0 + 1.45 * t + 0.6 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.08)
                tws = -1.15 * t + 0.9 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.12)
            elif severe_basin and sid == "D18_TRUNK_C":
                ar_state = 0.25 * ar_state + rng.gauss(0, 0.9)
                amp_t = base_amp * (1.0 - 0.35 * frac)
                disp = v0 * t + 0.5 * acc * (t ** 2) + amp_t * math.sin(2.0 * math.pi * t) + ar_state
                if k >= 45:
                    disp -= 28.0
                coh = 0.38 if (20 <= k < 38) else (0.76 + rng.gauss(0, 0.04))
                gw = 36.0 + 0.85 * t + 0.5 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.08)
                tws = -1.15 * t + 0.9 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.12)
            elif severe_basin and sid == "D18_EDGE_B":
                ar_state = 0.22 * ar_state + rng.gauss(0, 0.8)
                amp_t = base_amp * (1.0 - 0.25 * frac)
                disp = v0 * t + 0.5 * acc * (t ** 2) + amp_t * math.sin(2.0 * math.pi * t) + ar_state
                coh = 0.84 + rng.gauss(0, 0.03)
                gw = 32.0 + 0.65 * t + 0.5 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.08)
                tws = -1.15 * t + 0.9 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.12)
            else:
                ar_state = 0.20 * ar_state + rng.gauss(0, 0.6)
                disp = v0 * t + base_amp * math.sin(2.0 * math.pi * t) + ar_state
                coh = 0.88 + rng.gauss(0, 0.02)
                gw = 18.0 + 0.08 * t + 0.7 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.05)
                tws = -0.10 * t + 0.8 * math.sin(2.0 * math.pi * t) + rng.gauss(0, 0.08)

            obs.append(
                GeoObservation(
                    timestamp=ts,
                    site_id=sid,
                    lat=lat,
                    lon=lon,
                    displacement_mm=round(disp, 2),
                    coherence=round(max(0.05, min(0.99, coh)), 3),
                    groundwater_depth_m=round(gw, 2),
                    tws_cm=round(tws, 2),
                )
            )
    return obs


def write_observations_csv(observations: list[GeoObservation], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "timestamp",
        "site_id",
        "lat",
        "lon",
        "displacement_mm",
        "coherence",
        "groundwater_depth_m",
        "tws_cm",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for o in observations:
            writer.writerow(
                {
                    "timestamp": o.timestamp.date().isoformat(),
                    "site_id": o.site_id,
                    "lat": o.lat,
                    "lon": o.lon,
                    "displacement_mm": o.displacement_mm,
                    "coherence": o.coherence,
                    "groundwater_depth_m": o.groundwater_depth_m,
                    "tws_cm": o.tws_cm,
                }
            )
    return out
