from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import load_with_adapter
from .schema import AdapterInfo, GeoObservation


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dict(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_observations(path: str | Path, adapter: str = "auto") -> list[GeoObservation]:
    obs, _ = load_with_adapter(path, adapter=adapter)
    return obs


def load_observations_with_info(
    path: str | Path,
    adapter: str = "auto",
) -> tuple[list[GeoObservation], AdapterInfo]:
    return load_with_adapter(path, adapter=adapter)
