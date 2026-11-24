# Testing zemin

```bash
uv pip install -e ".[dev,web]"
pytest -v
```

## Suites

| File | Tests | Needs | What it verifies |
|---|---|---|---|
| `tests/test_zemin.py` | 3 | nothing | Version parity (`__version__` vs `pyproject.toml`), zero false positives on North Tehran bedrock control, GeoJSON spatial filtering + all 7 hazards on SW Tehran District 18 |
| `tests/test_adapters.py` | 3 | nothing | MintPy wide `DYYYYMMDD` + LOS-to-vertical scaling, COMET-LiCSAR long CSV, TAMAB piezometer Persian digits |
| `tests/test_diff.py` | 2 | nothing | `accelerating_risk` vs `stabilizing` verdicts, JSON config-hash mismatch (`incomparable`) |
| `tests/test_web.py` | 1 | `fastapi`, `httpx` | `/api/health`, RTL Persian HTML UI, multipart `/api/audit` + `/api/diff` with GeoJSON polygon upload |

## CLI smoke test

```bash
zemin doctor
zemin audit examples/tehran_d18_insar.csv --polygon examples/tehran_d18_corridor.geojson
zemin diff examples/tehran_d18_insar.csv examples/tehran_control_stable.csv --polygon examples/tehran_d18_corridor.geojson
```
