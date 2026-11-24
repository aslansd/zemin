# Roadmap

*Last revised 24 November 2026, against zemin 0.1.0.*

---

## Where this stands

**0.1.0**, Apache 2.0, **zero runtime dependencies for core**, **9 tests**,
**4 built-in InSAR/piezometer adapters**, **pure-Python GeoJSON polygon
filtering**, **longitudinal `zemin diff`**, and **offline RTL Persian FastAPI +
Streamlit dashboards**.

| Component | Status |
|---|---|
| 7 dynamical & geotechnical risk detectors (velocity, acceleration, rebound, OU CSD, Eurocode-7 tilt, GW coupling, InSAR integrity) | shipped |
| MintPy/HyP3, COMET-LiCSAR, TAMAB piezometer, and Generic adapters | shipped |
| Pure-Python GeoJSON Polygon/MultiPolygon spatial filtering | shipped |
| `zemin diff` epoch comparison & provenance verification | shipped |
| Offline RTL Persian FastAPI (`zemin serve`) and Streamlit dashboards | shipped |
| **Real Tehran InSAR + utility pilot (SW Tehran / Shahriar / Karaj)** | **next** |

---

## Next 30 days (pilot-driven hardening)

1. **Real Sentinel-1 frame ingest:** Run `zemin audit` on a live COMET-LiCSAR /
   ASF HyP3 time series over Tehran Districts 17–19 and validate velocities and
   differential gradients against published NCC (National Cartographic Center)
   leveling benchmarks.
2. **LineString corridor buffering:** Add pure-Python corridor buffer filtering
   (`--buffer-m 150`) for GeoJSON `LineString` assets (Tehran Metro Lines 1–7,
   ABFA trunk water mains, NIGC high-pressure gas lines).
3. **Jalali date parser & printable Persian PDF dossier:** Add native Jalali
   (`1405/07/15`) parsing for TAMAB piezometer spreadsheets and one-click RTL
   PDF engineering audit certificates for geotechnical consultancies and
   insurers.
