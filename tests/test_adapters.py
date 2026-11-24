from __future__ import annotations

from pathlib import Path

from zemin import detect_adapter, load_with_adapter


def test_mintpy_wide_los_meter_to_vertical_mm_conversion(tmp_path: Path) -> None:
    content = """# MintPy PS-InSAR export (unit: m)
ps_id,lat,lon,inc_angle,temp_coh,D20240101,D20240401,D20240701,D20241001
PS_001,35.648,51.310,38.0,0.85,0.000,-0.020,-0.045,-0.070
"""
    p = tmp_path / "mintpy_wide.csv"
    p.write_text(content, encoding="utf-8")

    assert detect_adapter(p) == "mintpy"
    obs, info = load_with_adapter(p)
    assert info.adapter == "mintpy_insar_wide"
    assert info.displacement_unit_scale == 1000.0
    assert len(obs) == 4
    assert obs[-1].displacement_mm < -85.0
    assert obs[-1].los_projected is True


def test_licsar_long_csv_adapter(tmp_path: Path) -> None:
    content = """# COMET-LiCSAR frame 028A_05442_131313
epoch,frame_id,lat,lon,cum_disp_mm,avg_coh
2024-01-05,F028A_P1,35.650,51.312,0.0,0.82
2024-07-05,F028A_P1,35.650,51.312,-64.5,0.79
"""
    p = tmp_path / "licsar_tehran.csv"
    p.write_text(content, encoding="utf-8")

    assert detect_adapter(p) == "licsar"
    obs, info = load_with_adapter(p)
    assert info.adapter == "licsar_insar"
    assert len(obs) == 2
    assert obs[1].displacement_mm == -64.5


def test_piezometer_tamab_persian_digits_adapter(tmp_path: Path) -> None:
    content = """# TAMAB Tehran Plain Piezometer Log
date,well_id,lat,lon,settlement_mm,depth_to_water_m,grace_tws_cm
2024-01-01,WELL_18,۳۵٫۶۴۸,۵۱٫۳۱۰,۰٫۰,۴۲٫۵,-۱۰٫۲
2024-07-01,WELL_18,۳۵٫۶۴۸,۵۱٫۳۱۰,-۷۲٫۴,۴۳٫۳,-۱۱٫۰
"""
    p = tmp_path / "tamab_well18.csv"
    p.write_text(content, encoding="utf-8")

    assert detect_adapter(p) == "piezometer"
    obs, info = load_with_adapter(p)
    assert info.adapter == "piezometer_hydro"
    assert len(obs) == 2
    assert obs[1].displacement_mm == -72.4
    assert obs[1].groundwater_depth_m == 43.3
