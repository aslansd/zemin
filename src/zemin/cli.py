from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import sys
from pathlib import Path

from .__version__ import __version__
from .adapters import ADAPTER_REGISTRY
from .diff import diff_files
from .engine import audit_file
from .llm_dossier import generate_engineering_dossier
from .schema import AuditConfig, AuditReport, EpochDiffResult
from .synthetic import generate_tehran_subsidence_dataset, write_observations_csv, write_sample_geojson


def _print_report(report: AuditReport) -> None:
    rd = report.to_dict()
    adapter_name = report.adapter_info.adapter if report.adapter_info else "in-memory"
    print(f"zemin v{report.tool_version} | adapter={adapter_name} | grade={report.risk_grade}")
    print(f"source={report.source_path} (sha256={report.source_sha256[:16]}...)")
    if report.polygon_path:
        print(f"polygon={report.polygon_path} (sha256={(report.polygon_sha256 or '')[:16]}...)")
    print(
        f"sites={report.site_count} | records={report.record_count} | span={report.span_years:.2f} yr | "
        f"worst_vel={report.worst_velocity_mm_yr:.1f} mm/yr | max_tilt={rd['max_angular_distortion_inv']}"
    )
    print("-" * 78)
    if not report.findings:
        print("OK: No critical urban subsidence or structural settlement hazards detected.")
        return
    for f in report.findings:
        print(f"[{f.severity.value.upper():8}] {f.code:<30} | {f.title}")
        print(f"           {f.summary}")


def _print_diff(res: EpochDiffResult) -> None:
    print(f"zemin diff v{res.tool_version} | mode={res.mode} | verdict={res.verdict.upper()}")
    print(f"--- before: {res.before_source} ({res.before_sha256[:12]})")
    print(f"+++ after:  {res.after_source} ({res.after_sha256[:12]})")
    print("-" * 78)
    print(
        f"worst velocity: {res.before_worst_velocity_mm_yr:.1f} -> {res.after_worst_velocity_mm_yr:.1f} mm/yr "
        f"(delta={res.velocity_change_mm_yr:+.1f} mm/yr)"
    )
    print(f"risk grade    : {res.before_risk_grade} -> {res.after_risk_grade}")
    print(f"resolved ({len(res.resolved_findings)})  : {', '.join(res.resolved_findings) or 'none'}")
    print(f"persisting ({len(res.persisting_findings)}): {', '.join(res.persisting_findings) or 'none'}")
    print(f"new hazards ({len(res.new_findings)}): {', '.join(res.new_findings) or 'none'}")
    for note in res.notes:
        print(f"note          : {note}")


def _run_doctor() -> int:
    print(f"zemin {__version__}")
    print(f"python {platform.python_version()} on {platform.system()} {platform.machine()}")
    try:
        meta_ver = importlib.metadata.version("zemin")
    except importlib.metadata.PackageNotFoundError:
        meta_ver = "uninstalled"
    print(f"package metadata: {meta_ver}")
    print("")
    print("Built-in InSAR / hydro-geotechnical adapters (zero dependencies):")
    for name in ADAPTER_REGISTRY:
        print(f"  {name:<12} ok")
    print("")
    print("Optional dashboard extras:")
    for pkg in ("fastapi", "uvicorn", "streamlit"):
        status = "ok" if importlib.util.find_spec(pkg) is not None else "-       not installed"
        print(f"  {pkg:<12} {status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zemin",
        description="Offline urban subsidence, aquifer resilience, and infrastructure risk auditor.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_audit = sub.add_parser("audit", help="Audit an InSAR or piezometer CSV/JSONL file.")
    p_audit.add_argument("file", help="Path to telemetry .csv or .jsonl")
    p_audit.add_argument("--polygon", type=str, default=None, help="GeoJSON Polygon/MultiPolygon footprint filter")
    p_audit.add_argument("--adapter", default="auto", help="Adapter: auto, mintpy, licsar, piezometer, generic")
    p_audit.add_argument("--json-out", type=str, default=None, help="Write versioned engineering audit JSON")
    p_audit.add_argument("--dossier", choices=("fa", "en"), default=None, help="Generate engineering dossier via Ollama")
    p_audit.add_argument("--model", type=str, default="gemma3:12b", help="Local Ollama model name")

    p_diff = sub.add_parser("diff", help="Compare two survey epochs or saved audit JSON dossiers.")
    p_diff.add_argument("before", help="Baseline survey CSV/JSONL or audit JSON")
    p_diff.add_argument("after", help="Follow-up survey CSV/JSONL or audit JSON")
    p_diff.add_argument("--polygon", type=str, default=None, help="Shared GeoJSON polygon filter")
    p_diff.add_argument("--adapter", default="auto", help="Adapter for telemetry files")
    p_diff.add_argument("--json-out", type=str, default=None, help="Write epoch diff JSON")

    p_demo = sub.add_parser("demo", help="Generate synthetic SW Tehran District 18 dataset + GeoJSON and audit it.")
    p_demo.add_argument("--out-csv", type=str, default="tehran_d18_insar.csv")
    p_demo.add_argument("--out-geojson", type=str, default="tehran_d18_corridor.geojson")
    p_demo.add_argument("--clean", action="store_true", help="Generate stable North Tehran bedrock control dataset")

    sub.add_parser("doctor", help="Inspect Python environment, built-in adapters, and optional UI extras.")

    p_serve = sub.add_parser("serve", help="Run the offline RTL Persian FastAPI dashboard.")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.cmd == "doctor":
        return _run_doctor()

    if args.cmd == "demo":
        obs = generate_tehran_subsidence_dataset(years=3.0, repeat_days=12, severe_basin=not args.clean)
        csv_path = write_observations_csv(obs, args.out_csv)
        poly_path = write_sample_geojson(args.out_geojson)
        report = audit_file(csv_path, config=AuditConfig(), polygon_path=poly_path)
        _print_report(report)
        return 0

    if args.cmd == "audit":
        report = audit_file(args.file, config=AuditConfig(), adapter=args.adapter, polygon_path=args.polygon)
        _print_report(report)
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"\nSaved audit dossier JSON -> {args.json_out}")
        if args.dossier:
            print("\n" + "=" * 78)
            print(generate_engineering_dossier(report, lang=args.dossier, model=args.model))
        return 0

    if args.cmd == "diff":
        res = diff_files(args.before, args.after, config=AuditConfig(), adapter=args.adapter, polygon_path=args.polygon)
        _print_diff(res)
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps(res.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"\nSaved epoch diff JSON -> {args.json_out}")
        return 0 if res.verdict in {"stabilizing", "steady_forced"} else 1

    if args.cmd == "serve":
        try:
            import uvicorn
        except ImportError:
            print("Missing web dependencies. Run: pip install 'zemin[web]'", file=sys.stderr)
            return 1
        from .api import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
