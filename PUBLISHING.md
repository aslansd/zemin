# Publishing zemin

```bash
pip install build twine
```

1. Bump version in both `src/zemin/__version__.py` and `pyproject.toml`
   (`test_version_matches_pyproject` enforces parity).
2. Update `CHANGELOG.md`.
3. Verify:
   ```bash
   pytest -v
   ruff check src tests
   zemin doctor
   ```
4. Build and validate:
   ```bash
   rm -rf dist build src/*.egg-info
   python -m build
   python -m twine check dist/*
   ```
5. Test the wheel in a clean virtual environment:
   ```bash
   python -m venv /tmp/zemin-check
   /tmp/zemin-check/bin/pip install dist/zemin-*.whl
   /tmp/zemin-check/bin/zemin doctor
   /tmp/zemin-check/bin/zemin demo --out-csv /tmp/zemin-check/demo.csv --out-geojson /tmp/zemin-check/demo.geojson
   ```
6. Upload and tag:
   ```bash
   python -m twine upload dist/*
   git tag v0.1.0 && git push --tags
   ```
