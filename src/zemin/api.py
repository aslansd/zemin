import tempfile
from pathlib import Path
from typing import Any

from .__version__ import __version__
from .diff import diff_files
from .engine import audit_file
from .llm_dossier import generate_engineering_dossier
from .schema import AuditConfig

RTL_DASHBOARD_HTML = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>زمین (zemin) | ممیزی فرونشست شهری و ریسک زیرساخت</title>
  <style>
    :root { --bg:#0c1220; --card:#162033; --border:#2a3a54; --text:#f8fafc; --muted:#94a3b8; --accent:#38bdf8; --warn:#f59e0b; --crit:#ef4444; --ok:#10b981; }
    * { box-sizing:border-box; font-family: Tahoma, Vazirmatn, system-ui, sans-serif; }
    body { margin:0; background:var(--bg); color:var(--text); padding:24px; line-height:1.7; }
    .wrap { max-width:1120px; margin:0 auto; }
    header { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:16px; margin-bottom:24px; }
    h1 { margin:0; font-size:1.5rem; }
    .badge { background:#0c4a6e; color:#7dd3fc; padding:4px 12px; border-radius:999px; font-size:0.85rem; }
    .tabs { display:flex; gap:10px; margin-bottom:20px; }
    .tab { background:var(--card); color:var(--text); border:1px solid var(--border); padding:10px 18px; border-radius:8px; cursor:pointer; }
    .tab.active { background:var(--accent); color:#082f49; font-weight:bold; border-color:var(--accent); }
    .card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:20px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin:16px 0; }
    .kpi { background:#0c1220; border:1px solid var(--border); border-radius:10px; padding:14px; }
    .kpi .lbl { color:var(--muted); font-size:0.82rem; }
    .kpi .val { font-size:1.3rem; font-weight:bold; margin-top:4px; direction:ltr; text-align:right; }
    label { display:block; font-size:0.88rem; color:var(--muted); margin-bottom:6px; }
    input, select { width:100%; padding:9px 10px; border-radius:8px; border:1px solid var(--border); background:#0c1220; color:var(--text); }
    button.primary { background:var(--accent); color:#082f49; border:none; padding:11px 22px; border-radius:8px; font-weight:bold; cursor:pointer; margin-top:14px; }
    .finding { border-right:4px solid var(--warn); background:#0c1220; padding:12px 16px; border-radius:8px; margin-bottom:10px; }
    .finding.critical { border-right-color:var(--crit); }
    pre { background:#020617; padding:14px; border-radius:8px; overflow:auto; white-space:pre-wrap; font-size:0.9rem; }
    .hidden { display:none; }
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>زمین (zemin) — ممیزی آفلاین فرونشست و ریسک زیرساخت شهری</h1>
      <div style="color:var(--muted);font-size:0.9rem;">پایش Sentinel-1 InSAR، پیزومتر، تاب‌آوری آبخوان (Ornstein-Uhlenbeck) و اعوجاج زاویه‌ای سازه‌ها</div>
    </div>
    <span class="badge">v__VERSION__ · ۱۰۰٪ آفلاین</span>
  </header>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('audit')">۱. ممیزی محدوده و کریدور (Audit)</button>
    <button class="tab" onclick="switchTab('diff')">۲. مقایسه دو دوره زمانی (Epoch Diff)</button>
  </div>

  <section id="panel-audit" class="card">
    <div class="grid">
      <div><label>فایل داده InSAR / پیزومتر (MintPy، LiCSAR، TAMAB یا CSV)</label><input id="audit-file" type="file" accept=".csv,.jsonl,.ndjson" /></div>
      <div><label>پلیگون محدوده پروژه (GeoJSON — اختیاری)</label><input id="audit-poly" type="file" accept=".geojson,.json" /></div>
      <div><label>آداپتور ورودی</label>
        <select id="audit-adapter"><option value="auto">تشخیص خودکار (Auto)</option><option value="mintpy">MintPy / HyP3 InSAR</option><option value="licsar">COMET-LiCSAR</option><option value="piezometer">Piezometer / TAMAB</option><option value="generic">Generic CSV</option></select>
      </div>
      <div><label>گزارش فنی فارسی با Ollama محلی؟</label><select id="gen-dossier"><option value="false">خیر (سریع)</option><option value="true">بله (Ollama محلی)</option></select></div>
    </div>
    <div class="grid">
      <div><label>نام مدل Ollama</label><input id="ollama-model" type="text" value="gemma3:12b" /></div>
    </div>
    <button class="primary" onclick="runAudit()">اجرای ممیزی فرونشست</button>
    <div id="audit-out" style="margin-top:20px;"></div>
  </section>

  <section id="panel-diff" class="card hidden">
    <div class="grid">
      <div><label>فایل دوره اول (پایه)</label><input id="diff-before" type="file" accept=".csv,.jsonl,.json" /></div>
      <div><label>فایل دوره دوم (جدید)</label><input id="diff-after" type="file" accept=".csv,.jsonl,.json" /></div>
      <div><label>پلیگون مشترک (GeoJSON — اختیاری)</label><input id="diff-poly" type="file" accept=".geojson,.json" /></div>
    </div>
    <button class="primary" onclick="runDiff()">مقایسه روند و تغییر ریسک</button>
    <div id="diff-out" style="margin-top:20px;"></div>
  </section>
</div>
<script>
function switchTab(id){
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',(i===0&&id==='audit')||(i===1&&id==='diff')));
  document.getElementById('panel-audit').classList.toggle('hidden', id!=='audit');
  document.getElementById('panel-diff').classList.toggle('hidden', id!=='diff');
}
async function runAudit(){
  const f = document.getElementById('audit-file').files[0];
  if(!f){ alert('لطفاً یک فایل داده انتخاب کنید.'); return; }
  const fd = new FormData();
  fd.append('file', f);
  const poly = document.getElementById('audit-poly').files[0];
  if(poly){ fd.append('polygon_file', poly); }
  fd.append('adapter', document.getElementById('audit-adapter').value);
  fd.append('dossier', document.getElementById('gen-dossier').value);
  fd.append('model', document.getElementById('ollama-model').value);
  const out = document.getElementById('audit-out');
  out.innerHTML = 'در حال تحلیل دینامیکی...';
  const r = await fetch('/api/audit', {method:'POST', body:fd});
  const d = await r.json();
  if(!r.ok){ out.innerHTML = '<pre>'+JSON.stringify(d,null,2)+'</pre>'; return; }
  const rep = d.report;
  let html = `<div class="grid">
    <div class="kpi"><div class="lbl">درجه ریسک کلی</div><div class="val">${rep.risk_grade}</div></div>
    <div class="kpi"><div class="lbl">بیشینه نرخ فرونشست (mm/yr)</div><div class="val">${rep.worst_velocity_mm_yr}</div></div>
    <div class="kpi"><div class="lbl">بیشینه اعوجاج زاویه‌ای</div><div class="val">${rep.max_angular_distortion_inv}</div></div>
    <div class="kpi"><div class="lbl">نقاط پایش داخل محدوده</div><div class="val">${rep.site_count} (${rep.record_count} رکورد)</div></div>
  </div>`;
  html += rep.findings.length ? rep.findings.map(x=>`<div class="finding ${x.severity}"><b>[${x.severity.toUpperCase()}] ${x.code}</b> — ${x.title}<br/>${x.summary}</div>`).join('') : '<div class="finding">هیچ ریسک فرونشست بحرانی شناسایی نشد.</div>';
  if(d.dossier){ html += '<h3>پرونده فنی ژئوتکنیک (Ollama)</h3><pre>'+d.dossier+'</pre>'; }
  out.innerHTML = html;
}
async function runDiff(){
  const fb = document.getElementById('diff-before').files[0];
  const fa = document.getElementById('diff-after').files[0];
  if(!fb || !fa){ alert('هر دو فایل دوره اول و دوم را انتخاب کنید.'); return; }
  const fd = new FormData();
  fd.append('before_file', fb);
  fd.append('after_file', fa);
  const poly = document.getElementById('diff-poly').files[0];
  if(poly){ fd.append('polygon_file', poly); }
  const out = document.getElementById('diff-out');
  out.innerHTML = 'در حال مقایسه...';
  const r = await fetch('/api/diff', {method:'POST', body:fd});
  const d = await r.json();
  if(!r.ok){ out.innerHTML = '<pre>'+JSON.stringify(d,null,2)+'</pre>'; return; }
  out.innerHTML = `<div class="grid">
    <div class="kpi"><div class="lbl">حکم تغییرات</div><div class="val">${d.verdict}</div></div>
    <div class="kpi"><div class="lbl">تغییر نرخ فرونشست (mm/yr)</div><div class="val">${d.velocity_change_mm_yr}</div></div>
    <div class="kpi"><div class="lbl">تغییر درجه ریسک</div><div class="val">${d.before_risk_grade} → ${d.after_risk_grade}</div></div>
  </div>
  <div class="finding"><b>مخاطرات برطرف‌شده:</b> ${d.resolved_findings.join(', ') || 'هیچ'}<br/>
  <b>مخاطرات تداوم‌یافته:</b> ${d.persisting_findings.join(', ') || 'هیچ'}<br/>
  <b>مخاطرات جدید:</b> ${d.new_findings.join(', ') || 'هیچ'}</div>`;
}
</script>
</body>
</html>
""".replace("__VERSION__", __version__)


def create_app() -> Any:
    try:
        from fastapi import FastAPI, File, Form, HTTPException, UploadFile
        from fastapi.responses import HTMLResponse
    except ImportError as exc:
        raise ImportError(
            "FastAPI dashboard requires web extras. Install with: pip install 'zemin[web]'"
        ) from exc

    app = FastAPI(title="zemin Urban Subsidence & Infrastructure Risk Auditor", version=__version__)

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return RTL_DASHBOARD_HTML

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/api/audit")
    async def api_audit(
        file: UploadFile = File(...),
        polygon_file: UploadFile | None = File(None),
        adapter: str = Form("auto"),
        dossier: bool = Form(False),
        model: str = Form("gemma3:12b"),
    ) -> dict[str, Any]:
        suffix = Path(file.filename or "upload.csv").suffix or ".csv"
        poly_path: Path | None = None
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        try:
            if polygon_file is not None and polygon_file.filename:
                with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as ptmp:
                    ptmp.write(await polygon_file.read())
                    poly_path = Path(ptmp.name)
            report = audit_file(tmp_path, config=AuditConfig(), adapter=adapter, polygon_path=poly_path)
            text = generate_engineering_dossier(report, lang="fa", model=model) if dossier else None
            return {"report": report.to_dict(), "dossier": text}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            tmp_path.unlink(missing_ok=True)
            if poly_path is not None:
                poly_path.unlink(missing_ok=True)

    @app.post("/api/diff")
    async def api_diff(
        before_file: UploadFile = File(...),
        after_file: UploadFile = File(...),
        polygon_file: UploadFile | None = File(None),
        adapter: str = Form("auto"),
    ) -> dict[str, Any]:
        sb = Path(before_file.filename or "before.csv").suffix or ".csv"
        sa = Path(after_file.filename or "after.csv").suffix or ".csv"
        poly_path: Path | None = None
        with tempfile.NamedTemporaryFile(suffix=sb, delete=False) as tb, tempfile.NamedTemporaryFile(suffix=sa, delete=False) as ta:
            tb.write(await before_file.read())
            ta.write(await after_file.read())
            pb, pa = Path(tb.name), Path(ta.name)
        try:
            if polygon_file is not None and polygon_file.filename:
                with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as ptmp:
                    ptmp.write(await polygon_file.read())
                    poly_path = Path(ptmp.name)
            res = diff_files(pb, pa, config=AuditConfig(), adapter=adapter, polygon_path=poly_path)
            return res.to_dict()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            pb.unlink(missing_ok=True)
            pa.unlink(missing_ok=True)
            if poly_path is not None:
                poly_path.unlink(missing_ok=True)

    return app
