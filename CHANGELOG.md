# Changelog

## 0.1.0 — Initial offline urban subsidence & infrastructure risk auditor

- **Seven dynamical and geotechnical detectors (`src/zemin/detectors.py`):**
  vertical subsidence velocity, seasonally adjusted quadratic acceleration,
  wet-season aquifer elastic-rebound failure, Ornstein-Uhlenbeck critical
  slowing down (with Marriott-Pope small-sample AR(1) bias correction and
  time-varying seasonal detrending), pairwise Haversine differential settlement /
  angular distortion against Eurocode-7 thresholds (`1/500` and `1/250`),
  groundwater/GRACE compaction coupling, and Sentinel-1 C-band phase-unwrapping /
  coherence integrity checks.
- **Zero-dependency geospatial & vendor adapters (`src/zemin/adapters/`, `src/zemin/geo.py`):**
  auto-detecting loaders for MintPy/HyP3 (wide `DYYYYMMDD` and long formats
  with LOS-to-vertical projection), COMET-LiCSAR, Iranian TAMAB/ABFA piezometer
  logs (with Persian/Arabic digit normalization), and pure-Python GeoJSON
  `Polygon`/`MultiPolygon` ray-casting.
- **Longitudinal epoch verification (`zemin diff`):** compares two survey
  periods or saved audit JSON dossiers with provenance hash checks and clear
  verdicts (`stabilizing`, `steady_forced`, `accelerating_risk`, `incomparable`).
- **Offline RTL Persian interfaces:** FastAPI (`zemin serve`), Streamlit
  dashboard, local Ollama Persian/English geotechnical dossier generator, and
  `zemin doctor`.
