# Weather History (`weahist`) — Project Rules

Python app that fetches historical weather + air-quality data, caches it locally, and visualizes it. Core must stay framework-agnostic so a CLI today and a web app tomorrow can share it.

## Stack
- Python 3.11+, `uv` for dependency management (no pip/Poetry/`requirements.txt`).
- src layout: code under `src/weahist/`, tests under `tests/`.
- `httpx`, `pandas` + `pyarrow`, `pydantic` v2, `pydantic-settings`.
- CLI: `typer`. Web: `fastapi` + `uvicorn`. Viz: `matplotlib` and `plotly`.
- Tooling: `pytest` + `respx`, `ruff`, `mypy` (strict on `src/`).

## Data source
Open-Meteo only (no API keys): geocoding, archive weather, air quality.
AQI history may be shorter than the requested range — degrade gracefully (return what's available, log a warning, never fail the request).
Store timestamps in UTC internally; convert to the location's timezone only at display boundaries.

## Architecture
Layered, with framework code at the edges only:

```
src/weahist/
  config.py · models.py · errors.py
  clients/    # one module per upstream API
  storage/    # CacheBackend Protocol + parquet cache
  services/   # orchestration, framework-agnostic
  visualization/  # Renderer Protocol + concrete renderers
  cli.py      # Typer adapter (thin)
  api/        # FastAPI adapter (thin)
```

Hard rules:
- No `typer` / `fastapi` / `click` / `argparse` imports outside `cli.py` and `api/`.
- CLI and FastAPI must both call the same `services/` functions — never duplicate orchestration.
- Cross-layer seams use `typing.Protocol` (e.g. `CacheBackend`, `Renderer`).
- Configuration only via `pydantic-settings`; no scattered `os.getenv`.

## Coding conventions
- Type-annotate every public function; keep `mypy --strict` clean on `src/`.
- Pydantic v2 syntax; prefer `pathlib.Path` over `os.path`.
- Use module-level `logging` — no `print` in library code.
- Raise specific exceptions from a `weahist.errors` hierarchy; don't swallow errors.
- Public APIs return `pandas.DataFrame` or Pydantic models, not raw dicts.
- No premature abstraction — add a Protocol only when a second implementation is in sight.

## Testing
- All upstream HTTP mocked with `respx`; tests must not hit the network.
- Mirror `src/weahist/` structure under `tests/`.
- CLI tested via `typer.testing.CliRunner` against a fake service.

## Don'ts
- No API-key providers, frontend code, or database layer beyond the Parquet cache unless requested.
- Don't commit `.env` or cache files — keep `.gitignore` current.
- Don't add docstrings/comments to code you didn't change.
