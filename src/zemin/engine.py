from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from .__version__ import __version__
from .detectors import (
    detect_aquifer_rebound_failure,
    detect_critical_slowing_down,
    detect_differential_settlement,
    detect_groundwater_coupling,
    detect_insar_data_integrity,
    detect_subsidence_acceleration,
    detect_subsidence_velocity,
    group_by_site,
    summarize_sites,
)
from .geo import filter_observations_by_polygon
from .io import load_observations_with_info, sha256_dict, sha256_file
from .schema import AdapterInfo, AuditConfig, AuditReport, GeoObservation, Severity

_SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


def _compute_risk_grade(findings: list) -> str:
    n_crit = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    n_warn = sum(1 for f in findings if f.severity == Severity.WARNING)
    if n_crit >= 2:
        return "SEVERE"
    if n_crit == 1 or n_warn >= 3:
        return "HIGH"
    if n_warn >= 1:
        return "MODERATE"
    return "LOW"


def audit_observations(
    observations: list[GeoObservation],
    config: AuditConfig | None = None,
    source_path: str = "<in-memory>",
    source_sha256: str = "",
    polygon_path: str | None = None,
    polygon_sha256: str | None = None,
    adapter_info: AdapterInfo | None = None,
) -> AuditReport:
    cfg = config or AuditConfig()
    if not observations:
        raise ValueError("No geospatial observations available inside the selected footprint.")

    grouped = group_by_site(observations)
    summaries = summarize_sites(grouped)

    findings = []
    findings.extend(detect_subsidence_velocity(summaries, cfg))
    findings.extend(detect_subsidence_acceleration(grouped, cfg))
    findings.extend(detect_aquifer_rebound_failure(grouped, cfg))
    findings.extend(detect_critical_slowing_down(grouped, cfg))
    max_tilt, tilt_findings = detect_differential_settlement(summaries, cfg)
    findings.extend(tilt_findings)
    findings.extend(detect_groundwater_coupling(grouped, cfg))
    findings.extend(detect_insar_data_integrity(grouped, cfg))

    findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity], f.code))

    worst_vel = min(s.velocity_mm_yr for s in summaries)
    mean_vel = mean(s.velocity_mm_yr for s in summaries)
    max_span = max(s.span_years for s in summaries)

    return AuditReport(
        tool_version=__version__,
        audited_at_utc=datetime.now(timezone.utc).isoformat(),
        source_path=source_path,
        source_sha256=source_sha256,
        config_sha256=sha256_dict(cfg.to_dict()),
        polygon_path=polygon_path,
        polygon_sha256=polygon_sha256,
        record_count=len(observations),
        site_count=len(summaries),
        span_years=max_span,
        worst_velocity_mm_yr=worst_vel,
        mean_velocity_mm_yr=mean_vel,
        max_angular_distortion=max_tilt,
        risk_grade=_compute_risk_grade(findings),
        sites=summaries,
        findings=findings,
        adapter_info=adapter_info,
    )


def audit_file(
    path: str | Path,
    config: AuditConfig | None = None,
    adapter: str = "auto",
    polygon_path: str | Path | None = None,
) -> AuditReport:
    p = Path(path)
    obs, info = load_observations_with_info(p, adapter=adapter)
    poly_str: str | None = None
    poly_hash: str | None = None
    if polygon_path is not None:
        pp = Path(polygon_path)
        obs = filter_observations_by_polygon(obs, pp)
        poly_str = str(pp)
        poly_hash = sha256_file(pp)

    return audit_observations(
        observations=obs,
        config=config,
        source_path=str(p),
        source_sha256=sha256_file(p),
        polygon_path=poly_str,
        polygon_sha256=poly_hash,
        adapter_info=info,
    )
