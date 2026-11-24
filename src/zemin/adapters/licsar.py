from __future__ import annotations

from pathlib import Path

from ..schema import AdapterInfo, GeoObservation
from .base import parse_long_csv

LICSAR_PATTERNS: dict[str, tuple[str, ...]] = {
    "timestamp": (r"^epoch", r"^date$", r"^acq_time", r"^timestamp$"),
    "site_id": (r"^frame", r"^point_id", r"^pixel", r"^site_id", r"^station"),
    "lat": (r"^lat", r"^latitude$"),
    "lon": (r"^lon", r"^longitude$"),
    "displacement_mm": (r"cum_disp", r"cum_mm", r"los_mm", r"disp_mm", r"disp_m", r"up_mm"),
    "incidence_deg": (r"inc", r"look_angle"),
    "coherence": (r"avg_coh", r"coh", r"coherence"),
}


def can_parse(sample_text: str) -> bool:
    low = sample_text.lower()
    return any(tok in low for tok in ("licsar", "licsbas", "comet", "cum_disp", "frame_id", "avg_coh"))


def load_licsar_csv(path: Path, default_incidence_deg: float = 38.0) -> tuple[list[GeoObservation], AdapterInfo]:
    """Parse COMET-LiCSAR / LiCSBAS cumulative displacement CSV exports."""
    return parse_long_csv(
        path=path,
        adapter_name="licsar_insar",
        column_patterns=LICSAR_PATTERNS,
        header_markers=("epoch", "date", "cum_disp", "frame"),
        default_incidence_deg=default_incidence_deg,
    )
