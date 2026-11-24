from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GeoObservation:
    timestamp: datetime
    site_id: str
    lat: float
    lon: float
    displacement_mm: float  # Vertical displacement (negative = subsidence)
    coherence: float | None = None
    groundwater_depth_m: float | None = None
    tws_cm: float | None = None
    soil_moisture: float | None = None
    los_projected: bool = False


@dataclass(frozen=True)
class AdapterInfo:
    adapter: str
    delimiter: str = ","
    skipped_preamble_lines: int = 0
    displacement_unit_scale: float = 1.0
    los_incidence_deg: float | None = None
    resolved_columns: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Finding:
    code: str
    title: str
    severity: Severity
    summary: str
    site_id: str | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(frozen=True)
class SiteSummary:
    site_id: str
    lat: float
    lon: float
    epoch_count: int
    span_years: float
    velocity_mm_yr: float
    acceleration_mm_yr2: float
    cumulative_mm: float
    mean_coherence: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "epoch_count": self.epoch_count,
            "span_years": round(self.span_years, 3),
            "velocity_mm_yr": round(self.velocity_mm_yr, 2),
            "acceleration_mm_yr2": round(self.acceleration_mm_yr2, 2),
            "cumulative_mm": round(self.cumulative_mm, 2),
            "mean_coherence": round(self.mean_coherence, 3) if self.mean_coherence is not None else None,
        }


@dataclass(frozen=True)
class AuditConfig:
    velocity_warn_mm_yr: float = 20.0
    velocity_crit_mm_yr: float = 50.0
    accel_warn_mm_yr2: float = 8.0
    accel_crit_mm_yr2: float = 20.0
    accel_min_tstat: float = 2.5
    rebound_ratio_min: float = 0.25
    rebound_decay_warn: float = 0.40
    csd_window_epochs: int = 24
    csd_lambda_tau_limit: float = -0.35
    csd_var_tau_limit: float = 0.40
    csd_final_phi_min: float = 0.50
    csd_delta_phi_min: float = 0.15
    csd_var_ratio_min: float = 2.2
    tilt_warn_ratio: float = 1.0 / 500.0
    tilt_crit_ratio: float = 1.0 / 250.0
    tilt_min_baseline_m: float = 10.0
    tilt_max_baseline_m: float = 2500.0
    gw_drawdown_warn_m_yr: float = 0.5
    tws_loss_warn_cm_yr: float = 1.0
    compaction_ratio_warn_mm_m: float = 20.0
    coherence_min: float = 0.45
    coherence_bad_frac_limit: float = 0.15
    unwrapping_jump_mm: float = 24.0
    default_incidence_deg: float = 38.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditReport:
    tool_version: str
    audited_at_utc: str
    source_path: str
    source_sha256: str
    config_sha256: str
    polygon_path: str | None
    polygon_sha256: str | None
    record_count: int
    site_count: int
    span_years: float
    worst_velocity_mm_yr: float
    mean_velocity_mm_yr: float
    max_angular_distortion: float
    risk_grade: str
    sites: list[SiteSummary]
    findings: list[Finding]
    adapter_info: AdapterInfo | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_version": self.tool_version,
            "audited_at_utc": self.audited_at_utc,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "config_sha256": self.config_sha256,
            "polygon_path": self.polygon_path,
            "polygon_sha256": self.polygon_sha256,
            "adapter_info": self.adapter_info.to_dict() if self.adapter_info else None,
            "record_count": self.record_count,
            "site_count": self.site_count,
            "span_years": round(self.span_years, 3),
            "worst_velocity_mm_yr": round(self.worst_velocity_mm_yr, 2),
            "mean_velocity_mm_yr": round(self.mean_velocity_mm_yr, 2),
            "max_angular_distortion": round(self.max_angular_distortion, 6),
            "max_angular_distortion_inv": (
                f"1/{int(round(1.0 / self.max_angular_distortion))}"
                if self.max_angular_distortion > 1e-6
                else "0"
            ),
            "risk_grade": self.risk_grade,
            "sites": [s.to_dict() for s in self.sites],
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True)
class EpochDiffResult:
    tool_version: str
    compared_at_utc: str
    mode: str
    verdict: str
    before_source: str
    after_source: str
    before_sha256: str
    after_sha256: str
    config_match: bool
    before_worst_velocity_mm_yr: float
    after_worst_velocity_mm_yr: float
    velocity_change_mm_yr: float
    before_max_tilt: float
    after_max_tilt: float
    before_risk_grade: str
    after_risk_grade: str
    resolved_findings: list[str]
    persisting_findings: list[str]
    new_findings: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_version": self.tool_version,
            "compared_at_utc": self.compared_at_utc,
            "mode": self.mode,
            "verdict": self.verdict,
            "before_source": self.before_source,
            "after_source": self.after_source,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "config_match": self.config_match,
            "before_worst_velocity_mm_yr": round(self.before_worst_velocity_mm_yr, 2),
            "after_worst_velocity_mm_yr": round(self.after_worst_velocity_mm_yr, 2),
            "velocity_change_mm_yr": round(self.velocity_change_mm_yr, 2),
            "before_max_tilt": round(self.before_max_tilt, 6),
            "after_max_tilt": round(self.after_max_tilt, 6),
            "before_risk_grade": self.before_risk_grade,
            "after_risk_grade": self.after_risk_grade,
            "resolved_findings": self.resolved_findings,
            "persisting_findings": self.persisting_findings,
            "new_findings": self.new_findings,
            "notes": self.notes,
        }
