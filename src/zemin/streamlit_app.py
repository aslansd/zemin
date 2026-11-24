from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from zemin import AuditConfig, __version__, audit_file, diff_files, generate_engineering_dossier

st.set_page_config(page_title="زمین | ممیزی فرونشست و ریسک زیرساخت", layout="wide")

st.markdown(
    """
    <style>
    html, body, [class*="css"] { direction: rtl; text-align: right; font-family: Tahoma, Vazirmatn, sans-serif; }
    [data-testid="stMetricValue"] { direction: ltr; text-align: right; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(f"زمین (zemin v{__version__}) — ممیزی آفلاین فرونشست و ریسک زیرساخت شهری")
st.caption("تحلیل داده‌های Sentinel-1 InSAR (MintPy/LiCSAR)، پیزومتر، تاب‌آوری آبخوان و اعوجاج زاویه‌ای سازه‌ها")

with st.sidebar:
    st.header("تنظیمات ممیزی")
    adapter = st.selectbox("آداپتور ورودی", ["auto", "mintpy", "licsar", "piezometer", "generic"])
    vel_warn = st.number_input("آستانه هشدار فرونشست (mm/yr)", min_value=5.0, value=20.0, step=5.0)
    vel_crit = st.number_input("آستانه بحرانی فرونشست (mm/yr)", min_value=10.0, value=50.0, step=10.0)
    ollama_model = st.text_input("مدل محلی Ollama", value="gemma3:12b")

cfg = AuditConfig(velocity_warn_mm_yr=vel_warn, velocity_crit_mm_yr=vel_crit)

tab_audit, tab_diff = st.tabs(["۱. ممیزی محدوده / کریدور (Audit)", "۲. مقایسه دو دوره زمانی (Epoch Diff)"])

with tab_audit:
    col1, col2 = st.columns(2)
    with col1:
        up = st.file_uploader("فایل InSAR / پیزومتر (.csv یا .jsonl)", type=["csv", "jsonl", "ndjson"], key="z_audit")
    with col2:
        up_poly = st.file_uploader("پلیگون GeoJSON محدوده (اختیاری)", type=["geojson", "json"], key="z_poly")

    gen_dossier = st.checkbox("تولید پرونده فنی فارسی با Ollama محلی", value=False)
    if up is not None and st.button("اجرای ممیزی فرونشست", type="primary"):
        suffix = Path(up.name).suffix or ".csv"
        poly_path: Path | None = None
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(up.getvalue())
            tmp_path = Path(tmp.name)
        try:
            if up_poly is not None:
                with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as ptmp:
                    ptmp.write(up_poly.getvalue())
                    poly_path = Path(ptmp.name)

            report = audit_file(tmp_path, config=cfg, adapter=adapter, polygon_path=poly_path)
            rd = report.to_dict()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("درجه ریسک", report.risk_grade)
            c2.metric("بیشینه نرخ فرونشست (mm/yr)", f"{report.worst_velocity_mm_yr:.1f}")
            c3.metric("بیشینه اعوجاج زاویه‌ای", rd["max_angular_distortion_inv"])
            c4.metric("نقاط داخل محدوده", f"{report.site_count}")

            if not report.findings:
                st.success("هیچ مخاطره بحرانی فرونشست شناسایی نشد.")
            else:
                for f in report.findings:
                    box = st.error if f.severity.value == "critical" else st.warning
                    box(f"**[{f.severity.value.upper()}] {f.code}** — {f.title}\n\n{f.summary}")

            st.subheader("جدول نقاط پایش‌شده")
            st.dataframe(rd["sites"], use_container_width=True)

            if gen_dossier:
                with st.spinner("در حال تدوین پرونده فنی توسط Ollama..."):
                    dossier_text = generate_engineering_dossier(report, lang="fa", model=ollama_model)
                st.subheader("پرونده فنی ژئوتکنیک")
                st.text_area("متن گزارش", dossier_text, height=280)

            st.download_button(
                "دانلود پرونده ممیزی (JSON)",
                data=json.dumps(rd, ensure_ascii=False, indent=2),
                file_name="zemin_audit_dossier.json",
                mime="application/json",
            )
        finally:
            tmp_path.unlink(missing_ok=True)
            if poly_path is not None:
                poly_path.unlink(missing_ok=True)

with tab_diff:
    c_a, c_b = st.columns(2)
    with c_a:
        up_b = st.file_uploader("فایل دوره اول (پایه)", type=["csv", "jsonl", "json"], key="zd_b")
    with c_b:
        up_a = st.file_uploader("فایل دوره دوم (جدید)", type=["csv", "jsonl", "json"], key="zd_a")
    up_dpoly = st.file_uploader("پلیگون GeoJSON مشترک (اختیاری)", type=["geojson", "json"], key="zd_p")

    if up_b is not None and up_a is not None and st.button("مقایسه روند فرونشست", type="primary"):
        sb = Path(up_b.name).suffix or ".csv"
        sa = Path(up_a.name).suffix or ".csv"
        poly_path = None
        with tempfile.NamedTemporaryFile(suffix=sb, delete=False) as tb, tempfile.NamedTemporaryFile(suffix=sa, delete=False) as ta:
            tb.write(up_b.getvalue())
            ta.write(up_a.getvalue())
            pb, pa = Path(tb.name), Path(ta.name)
        try:
            if up_dpoly is not None:
                with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as ptmp:
                    ptmp.write(up_dpoly.getvalue())
                    poly_path = Path(ptmp.name)
            res = diff_files(pb, pa, config=cfg, adapter=adapter, polygon_path=poly_path)
            m1, m2, m3 = st.columns(3)
            m1.metric("حکم تغییرات", res.verdict)
            m2.metric("تغییر نرخ فرونشست (mm/yr)", f"{res.velocity_change_mm_yr:+.1f}")
            m3.metric("درجه ریسک", f"{res.before_risk_grade} -> {res.after_risk_grade}")
            st.write("**مخاطرات برطرف‌شده:**", ", ".join(res.resolved_findings) or "هیچ")
            st.write("**مخاطرات تداوم‌یافته:**", ", ".join(res.persisting_findings) or "هیچ")
            st.write("**مخاطرات جدید:**", ", ".join(res.new_findings) or "هیچ")
            st.download_button(
                "دانلود گواهی مقایسه (JSON)",
                data=json.dumps(res.to_dict(), ensure_ascii=False, indent=2),
                file_name="zemin_epoch_diff.json",
                mime="application/json",
            )
        finally:
            pb.unlink(missing_ok=True)
            pa.unlink(missing_ok=True)
            if poly_path is not None:
                poly_path.unlink(missing_ok=True)
