# Installing zemin

## Core auditor (zero dependencies)

```bash
pip install zemin
```

Python 3.10+ only. Requires no GDAL, no Shapely, no internet access, and no
cloud API keys.

Verify:

```bash
python -c "import zemin; print(zemin.__version__)"
zemin doctor
```

---

## Optional dashboard extras

| Extra | Command | Adds |
|---|---|---|
| `web` | `pip install "zemin[web]"` | FastAPI backend + self-contained RTL Persian UI (`zemin serve`) |
| `streamlit` | `pip install "zemin[streamlit]"` | Interactive RTL Persian Streamlit dashboard |
| `all` | `pip install "zemin[all]"` | Both FastAPI and Streamlit dashboards |
| `dev` | `pip install -e ".[dev]"` | `pytest`, `ruff`, and `httpx` |

### Local editable setup with `uv`

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,web,streamlit]"
zemin doctor
```

---

## Local Persian geotechnical dossiers (Ollama)

`zemin audit --dossier fa` calls a local Ollama daemon at
`http://localhost:11434/api/generate` using Python's standard `urllib`. If
Ollama is stopped, `zemin` automatically falls back to a deterministic Persian
or English technical summary. Recommended local model for Persian: `gemma3:12b`.
