from __future__ import annotations

import json
import urllib.error
import urllib.request

from .schema import AuditReport


def _fallback_dossier(report: AuditReport, lang: str) -> str:
    if lang == "fa":
        lines = [
            f"پرونده فنی ممیزی فرونشست و ریسک زیرساخت (zemin v{report.tool_version})",
            f"درجه ریسک کلی: {report.risk_grade} | بیشینه نرخ فرونشست: {report.worst_velocity_mm_yr:.1f} mm/yr",
            f"بیشینه اعوجاج زاویه‌ای (نشست نامتقارن): {report.to_dict()['max_angular_distortion_inv']}",
            "",
        ]
        for idx, f in enumerate(report.findings, 1):
            lines.append(f"{idx}. [{f.severity.value.upper()}] {f.code} — {f.title}")
            lines.append(f"   شرح فنی: {f.summary}")
        return "\n".join(lines)

    lines = [
        f"Urban Subsidence & Infrastructure Risk Dossier (zemin v{report.tool_version})",
        f"Overall Risk Grade: {report.risk_grade} | Worst velocity: {report.worst_velocity_mm_yr:.1f} mm/yr",
        f"Max angular distortion: {report.to_dict()['max_angular_distortion_inv']}",
        "",
    ]
    for idx, f in enumerate(report.findings, 1):
        lines.append(f"{idx}. [{f.severity.value.upper()}] {f.code} — {f.title}")
        lines.append(f"   Details: {f.summary}")
    return "\n".join(lines)


def generate_engineering_dossier(
    report: AuditReport,
    lang: str = "fa",
    model: str = "gemma3:12b",
    ollama_url: str = "http://localhost:11434/api/generate",
    timeout_sec: int = 60,
) -> str:
    """Turn deterministic subsidence audit JSON into a Persian/English geotechnical dossier via local Ollama."""
    if not report.findings:
        return (
            "در محدوده بررسی‌شده، هیچ خطر فرونشست بحرانی یا نشست نامتقارن سازه‌ای شناسایی نشد."
            if lang == "fa"
            else "No critical subsidence or differential settlement hazards detected within the audited polygon."
        )

    directive = (
        "Write a concise, authoritative geotechnical and urban-infrastructure risk dossier in natural Persian (Farsi) "
        "for a Tehran civil consultancy, Tehran Metro, or ABFA water utility engineer."
        if lang == "fa"
        else "Write a concise, authoritative geotechnical and urban-infrastructure risk dossier in English."
    )
    prompt = (
        f"{directive}\n"
        "Structure the response into: (1) Executive Risk Summary, (2) Structural & Utility Exposure "
        "(foundations, water/gas mains, tunnels), (3) Immediate Field Verification & Mitigation Actions. "
        "Cite only numbers present in the JSON.\n\n"
        f"AUDIT JSON:\n{json.dumps(report.to_dict(), ensure_ascii=False, indent=2)}"
    )

    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        ollama_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = str(body.get("response", "")).strip()
            return text or _fallback_dossier(report, lang)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return _fallback_dossier(report, lang)
