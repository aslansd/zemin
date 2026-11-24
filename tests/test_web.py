from __future__ import annotations

from pathlib import Path
import pytest

from zemin.synthetic import generate_tehran_subsidence_dataset, write_observations_csv, write_sample_geojson


def test_fastapi_audit_and_diff_endpoints(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from zemin.api import create_app

    client = TestClient(create_app())
    assert client.get("/api/health").status_code == 200
    assert 'dir="rtl"' in client.get("/").text

    poly = write_sample_geojson(tmp_path / "d18.geojson")
    fb = write_observations_csv(
        generate_tehran_subsidence_dataset(years=3.0, severe_basin=True, seed=1),
        tmp_path / "severe.csv",
    )
    fa = write_observations_csv(
        generate_tehran_subsidence_dataset(years=3.0, severe_basin=False, seed=2),
        tmp_path / "stable.csv",
    )

    with fb.open("rb") as f, poly.open("rb") as fp:
        r_audit = client.post(
            "/api/audit",
            files={
                "file": ("severe.csv", f, "text/csv"),
                "polygon_file": ("d18.geojson", fp, "application/geo+json"),
            },
        )
    assert r_audit.status_code == 200
    assert r_audit.json()["report"]["risk_grade"] == "SEVERE"

    with fb.open("rb") as f1, fa.open("rb") as f2, poly.open("rb") as fp:
        r_diff = client.post(
            "/api/diff",
            files={
                "before_file": ("severe.csv", f1, "text/csv"),
                "after_file": ("stable.csv", f2, "text/csv"),
                "polygon_file": ("d18.geojson", fp, "application/geo+json"),
            },
        )
    assert r_diff.status_code == 200
    assert r_diff.json()["verdict"] == "stabilizing"
