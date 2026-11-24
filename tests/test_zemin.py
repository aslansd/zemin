from __future__ import annotations

import re
from pathlib import Path

import zemin
from zemin import AuditConfig, audit_file, audit_observations
from zemin.synthetic import generate_tehran_subsidence_dataset, write_observations_csv, write_sample_geojson


def test_version_matches_pyproject() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, flags=re.MULTILINE)
    assert m is not None
    assert zemin.__version__ == m.group(1)


def test_stable_north_tehran_bedrock_has_zero_false_positives() -> None:
    obs = generate_tehran_subsidence_dataset(years=3.0, repeat_days=12, severe_basin=False, seed=7)
    report = audit_observations(obs, config=AuditConfig())
    assert report.findings == []
    assert report.risk_grade == "LOW"
    assert report.site_count == 3


def test_sw_tehran_district18_polygon_catches_all_seven_hazards(tmp_path: Path) -> None:
    obs = generate_tehran_subsidence_dataset(years=3.0, repeat_days=12, severe_basin=True, seed=42)
    csv_p = write_observations_csv(obs, tmp_path / "d18.csv")
    poly_p = write_sample_geojson(tmp_path / "d18.geojson")

    report = audit_file(csv_p, config=AuditConfig(), polygon_path=poly_p)
    assert report.site_count == 3
    assert "OUTSIDE_CTRL" not in {s.site_id for s in report.sites}
    assert report.risk_grade == "SEVERE"
    assert report.polygon_sha256 is not None and len(report.polygon_sha256) == 64

    codes = {f.code for f in report.findings}
    expected = {
        "SUBSIDENCE_VELOCITY_HAZARD",
        "SUBSIDENCE_ACCELERATION",
        "AQUIFER_REBOUND_FAILURE",
        "CRITICAL_SLOWING_DOWN",
        "DIFFERENTIAL_SETTLEMENT_TILT",
        "GROUNDWATER_COMPACTION_COUPLING",
        "INSAR_DATA_INTEGRITY",
    }
    assert expected.issubset(codes)
