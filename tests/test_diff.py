from __future__ import annotations

import json
from pathlib import Path

from zemin import AuditConfig, audit_file, diff_files
from zemin.synthetic import generate_tehran_subsidence_dataset, write_observations_csv, write_sample_geojson


def test_diff_detects_accelerating_risk_and_stabilization(tmp_path: Path) -> None:
    poly = write_sample_geojson(tmp_path / "corridor.geojson")
    stable_csv = write_observations_csv(
        generate_tehran_subsidence_dataset(years=3.0, severe_basin=False, seed=1),
        tmp_path / "stable.csv",
    )
    severe_csv = write_observations_csv(
        generate_tehran_subsidence_dataset(years=3.0, severe_basin=True, seed=2),
        tmp_path / "severe.csv",
    )

    acc = diff_files(stable_csv, severe_csv, polygon_path=poly)
    assert acc.verdict == "accelerating_risk"
    assert acc.velocity_change_mm_yr < -50.0
    assert "SUBSIDENCE_VELOCITY_HAZARD" in acc.new_findings

    stab = diff_files(severe_csv, stable_csv, polygon_path=poly)
    assert stab.verdict == "stabilizing"
    assert stab.velocity_change_mm_yr > 50.0
    assert "SUBSIDENCE_VELOCITY_HAZARD" in stab.resolved_findings


def test_diff_json_flags_config_mismatch_incomparable(tmp_path: Path) -> None:
    csv_p = write_observations_csv(
        generate_tehran_subsidence_dataset(years=2.0, severe_basin=False, seed=3),
        tmp_path / "s.csv",
    )
    r1 = audit_file(csv_p, config=AuditConfig(velocity_warn_mm_yr=20.0))
    r2 = audit_file(csv_p, config=AuditConfig(velocity_warn_mm_yr=35.0))
    j1, j2 = tmp_path / "r1.json", tmp_path / "r2.json"
    j1.write_text(json.dumps(r1.to_dict()), encoding="utf-8")
    j2.write_text(json.dumps(r2.to_dict()), encoding="utf-8")

    res = diff_files(j1, j2)
    assert res.verdict == "incomparable"
    assert res.config_match is False
