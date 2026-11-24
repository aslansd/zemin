from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .__version__ import __version__
from .engine import audit_file
from .schema import AuditConfig, EpochDiffResult


def _verdict_from_metrics(
    vel_change: float,
    new_faults: list[str],
) -> str:
    if vel_change <= -10.0 or new_faults:
        return "accelerating_risk"
    if vel_change >= 10.0 and not new_faults:
        return "stabilizing"
    return "steady_forced"


def diff_json_reports(before_path: Path, after_path: Path) -> EpochDiffResult:
    b = json.loads(before_path.read_text(encoding="utf-8"))
    a = json.loads(after_path.read_text(encoding="utf-8"))

    cfg_match = b.get("config_sha256") == a.get("config_sha256")
    poly_match = b.get("polygon_sha256") == a.get("polygon_sha256")
    codes_b = {f["code"] for f in b.get("findings", [])}
    codes_a = {f["code"] for f in a.get("findings", [])}

    v_b = float(b.get("worst_velocity_mm_yr", 0.0))
    v_a = float(a.get("worst_velocity_mm_yr", 0.0))
    v_delta = v_a - v_b
    new_faults = sorted(codes_a - codes_b)

    notes: list[str] = []
    if not cfg_match or not poly_match:
        verdict = "incomparable"
        if not cfg_match:
            notes.append("Audit config_sha256 differs between reports; re-audit raw files under one config.")
        if not poly_match:
            notes.append("GeoJSON polygon_sha256 differs between reports; footprints do not match.")
    else:
        verdict = _verdict_from_metrics(v_delta, new_faults)

    return EpochDiffResult(
        tool_version=__version__,
        compared_at_utc=datetime.now(timezone.utc).isoformat(),
        mode="report_json",
        verdict=verdict,
        before_source=str(before_path),
        after_source=str(after_path),
        before_sha256=str(b.get("source_sha256", "")),
        after_sha256=str(a.get("source_sha256", "")),
        config_match=cfg_match and poly_match,
        before_worst_velocity_mm_yr=v_b,
        after_worst_velocity_mm_yr=v_a,
        velocity_change_mm_yr=v_delta,
        before_max_tilt=float(b.get("max_angular_distortion", 0.0)),
        after_max_tilt=float(a.get("max_angular_distortion", 0.0)),
        before_risk_grade=str(b.get("risk_grade", "LOW")),
        after_risk_grade=str(a.get("risk_grade", "LOW")),
        resolved_findings=sorted(codes_b - codes_a),
        persisting_findings=sorted(codes_b & codes_a),
        new_findings=new_faults,
        notes=notes,
    )


def diff_files(
    before_path: str | Path,
    after_path: str | Path,
    config: AuditConfig | None = None,
    adapter: str = "auto",
    polygon_path: str | Path | None = None,
) -> EpochDiffResult:
    pb, pa = Path(before_path), Path(after_path)
    if pb.suffix.lower() == ".json" and pa.suffix.lower() == ".json":
        return diff_json_reports(pb, pa)

    rep_b = audit_file(pb, config=config, adapter=adapter, polygon_path=polygon_path)
    rep_a = audit_file(pa, config=config, adapter=adapter, polygon_path=polygon_path)

    codes_b = {f.code for f in rep_b.findings}
    codes_a = {f.code for f in rep_a.findings}
    new_faults = sorted(codes_a - codes_b)
    v_delta = rep_a.worst_velocity_mm_yr - rep_b.worst_velocity_mm_yr
    verdict = _verdict_from_metrics(v_delta, new_faults)

    notes: list[str] = []
    if rep_b.site_count != rep_a.site_count:
        notes.append(f"Site count changed from {rep_b.site_count} to {rep_a.site_count}; check scatterer coherence.")

    return EpochDiffResult(
        tool_version=__version__,
        compared_at_utc=datetime.now(timezone.utc).isoformat(),
        mode="telemetry_diff",
        verdict=verdict,
        before_source=str(pb),
        after_source=str(pa),
        before_sha256=rep_b.source_sha256,
        after_sha256=rep_a.source_sha256,
        config_match=True,
        before_worst_velocity_mm_yr=rep_b.worst_velocity_mm_yr,
        after_worst_velocity_mm_yr=rep_a.worst_velocity_mm_yr,
        velocity_change_mm_yr=v_delta,
        before_max_tilt=rep_b.max_angular_distortion,
        after_max_tilt=rep_a.max_angular_distortion,
        before_risk_grade=rep_b.risk_grade,
        after_risk_grade=rep_a.risk_grade,
        resolved_findings=sorted(codes_b - codes_a),
        persisting_findings=sorted(codes_b & codes_a),
        new_findings=new_faults,
        notes=notes,
    )
