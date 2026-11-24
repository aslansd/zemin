from .__version__ import __version__
from .adapters import ADAPTER_REGISTRY, detect_adapter, load_with_adapter
from .diff import diff_files, diff_json_reports
from .engine import audit_file, audit_observations
from .geo import filter_observations_by_polygon, haversine_m, load_geojson_polygons
from .llm_dossier import generate_engineering_dossier
from .schema import (
    AdapterInfo,
    AuditConfig,
    AuditReport,
    EpochDiffResult,
    Finding,
    GeoObservation,
    Severity,
    SiteSummary,
)

__all__ = [
    "__version__",
    "ADAPTER_REGISTRY",
    "AdapterInfo",
    "AuditConfig",
    "AuditReport",
    "EpochDiffResult",
    "Finding",
    "GeoObservation",
    "Severity",
    "SiteSummary",
    "audit_file",
    "audit_observations",
    "detect_adapter",
    "diff_files",
    "diff_json_reports",
    "filter_observations_by_polygon",
    "generate_engineering_dossier",
    "haversine_m",
    "load_geojson_polygons",
    "load_with_adapter",
]
