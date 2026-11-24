from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..schema import AdapterInfo, GeoObservation
from .generic import load_generic_geo
from .licsar import can_parse as is_licsar
from .licsar import load_licsar_csv
from .mintpy import can_parse as is_mintpy
from .mintpy import load_mintpy_csv
from .piezometer import can_parse as is_piezometer
from .piezometer import load_piezometer_csv

ADAPTER_REGISTRY: dict[str, Callable[[Path], tuple[list[GeoObservation], AdapterInfo]]] = {
    "mintpy": load_mintpy_csv,
    "licsar": load_licsar_csv,
    "piezometer": load_piezometer_csv,
    "generic": load_generic_geo,
}


def detect_adapter(path: Path) -> str:
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        return "generic"
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    if is_mintpy(sample):
        return "mintpy"
    if is_licsar(sample):
        return "licsar"
    if is_piezometer(sample):
        return "piezometer"
    return "generic"


def load_with_adapter(
    path: str | Path,
    adapter: str = "auto",
) -> tuple[list[GeoObservation], AdapterInfo]:
    p = Path(path)
    chosen = detect_adapter(p) if adapter == "auto" else adapter.lower()
    if chosen not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter '{adapter}'. Choose from: auto, {', '.join(ADAPTER_REGISTRY)}")
    return ADAPTER_REGISTRY[chosen](p)


__all__ = ["ADAPTER_REGISTRY", "detect_adapter", "load_with_adapter"]
