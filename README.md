# finance_data

Retail-/Research-Finanzmarktdatenbank. Tägliche Frequenz, mehrere Asset-Klassen,
mehrere Vendor-Quellen. Ziel: quantitative Analysen, Portfolio-Management,
Asset Allocation, Risikomodellierung, Makroanalyse, ML-Features.

> **Scope:** Retail/Research. Keine echte PIT-Trennung, keine
> Survivorship-Bias-freien Universen, keine Intraday-/Tick-Daten,
> keine Option-Chains, keine Bond-CUSIP-Ebene.
> Detaillierte Aufgabenbeschreibung für Coding-/Research-Agenten: siehe
> [`AGENTS.md`](./AGENTS.md).

## Status (lokal, manuell verifiziert)

Diese erste Iteration läuft end-to-end:

- **PostgreSQL 16** läuft via `docker compose up -d` (Container `finance_pg`).
- **Alembic** hat die initiale Migration `0001_initial` angewendet → **14 Tabellen**
  + `alembic_version` in der DB.
- **SQLAlchemy-ORM** roundtrip funktioniert (Vendor, MacroSeries, MacroObservation
  insert+select getestet).
- **FRED-Vendor-Adapter** ist implementiert, fetcht über `httpx`, retry via
  `tenacity` (5s/30s/120s), rate-limit via token-bucket, parst in Polars-DF.
- **`scripts/query_db.py`** Standalone-CLI: liest `macro_observations`, gibt
  formatierte Tabelle aus, seedet Demo-Daten (oder echte FRED-Daten) wenn leer.
- **18 Unit-Tests** grün (config, FRED-Adapter, ORM-Modell-Registrierung).
- **ruff** lint + format clean.

Bewusst noch nicht da: ECB/Bundesbank/Yahoo/Stooq, Prefect-Flows, Pandera-DQ,
Inventar in `config/series_registry.yaml` und `config/tickers.yaml`.

## Quickstart (lokal, ohne Poetry)

```bash
# 1) .env anlegen
cp .env.example .env
# FRED_API_KEY in .env eintragen
#   → https://fred.stlouisfed.org/docs/api/api_key.html (kostenlos)

# 2) venv + deps
python3 -m venv .venv
.venv/bin/pip install -e .

# 3) Postgres starten
docker compose up -d postgres

# 4) Schema anlegen
.venv/bin/alembic upgrade head

# 5) Tests
.venv/bin/pytest -v
```

## Mit Poetry (wenn vorhanden)

```bash
make init          # poetry install + docker compose up + alembic upgrade head
make test          # pytest
make check         # ruff + mypy + test
```

UI: Adminer :8080, Prefect :4200 (nach `make up`).

## Query-Skript (`scripts/query_db.py`)

Standalone-CLI zum Inspizieren der DB.

```bash
# Zeigt alles in macro_observations.
# Wenn die Tabelle leer ist:
#   - mit FRED_API_KEY in .env: live 2 FRED-Serien seeden
#   - ohne FRED_API_KEY: synthetische DEMO:* Daten seeden (klar markiert)
.venv/bin/python scripts/query_db.py

# Nur bestimmte Serien
.venv/bin/python scripts/query_db.py --series DEMO:DGS3MO

# Mehr Werte pro Serie anzeigen
.venv/bin/python scripts/query_db.py --tail 20

# Read-only (kein Seed)
.venv/bin/python scripts/query_db.py --no-seed

# Demo-Daten wieder entfernen
.venv/bin/python scripts/query_db.py --reset-demo
```

Beispiel-Output (gekürzt):

```
================================================================================
finance_data — Time Series Query
================================================================================

| Series        | Name                                     | Count | First      | Last       | Latest | Δ %    | Mean    | Min     | Max     |
|---------------|------------------------------------------|-------|------------|------------|--------|--------|---------|---------|---------|
| DEMO:DGS3MO   | DEMO 3-Month Treasury (synthetic)        |   142 | 2025-12-01 | 2026-06-16 |  5.840 | +16.92%|  5.261  |  4.851  |  5.913  |
| DEMO:CPIAUCSL | DEMO CPI All Urban Consumers (synthetic) |   142 | 2025-12-01 | 2026-06-16 | 326.55 |  +5.31%| 318.996 | 310.071 | 326.551 |
| DEMO:UNRATE   | DEMO Unemployment Rate (synthetic)       |   142 | 2025-12-01 | 2026-06-16 |  4.013 |  +2.57%|  4.039  |  3.856  |  4.229  |

--- DEMO:DGS3MO — last 10 of 142 rows ---
| date       |   value |
|------------|---------|
| 2026-06-03 | 5.79087 |
| ...        | ...     |
| 2026-06-16 | 5.84010 |
```

## Notebook (`notebooks/01_macro_overview.ipynb`)

Jupyter-Notebook, das die 9 vorhandenen Makro-Serien (5 FRED + 4 ECB) aus
der DB zieht und mit Plotly in einem 2x2-Subplot-Grid plottet:

- **(1,1) US Zinsstruktur**: DGS3MO + DGS10 + FEDFUNDS
- **(1,2) Inflation**: FRED CPI vs. ECB HICP YoY (zwei Y-Achsen)
- **(2,1) FX**: USD/EUR + GBP/EUR (links), JPY/EUR (rechts, andere Skala)
- **(2,2) Arbeitsmarkt**: UNRATE mit Fläche

Plus eine Polars-Summary-Tabelle pro Serie.

```bash
# Notebook bauen + ausführen + HTML-Export (alle Outputs eingebettet)
.venv/bin/python scripts/build_notebook.py

# Im JupyterLab öffnen
.venv/bin/jupyter lab notebooks/01_macro_overview.ipynb
```

Artefakte: `notebooks/01_macro_overview.ipynb` (mit Outputs) und
`notebooks/01_macro_overview.html` (statisches HTML, braucht Internet
für plotly.js via CDN).

## Architektur

```
                  ┌───────────────────────┐
                  │  Vendor (FRED/ECB/...)│
                  └──────────┬────────────┘
                             │ fetch()
                  ┌──────────▼────────────┐
                  │ vendors/<name>.py     │  ← token-bucket, tenacity
                  └──────────┬────────────┘
                             │ pl.DataFrame (raw)
                  ┌──────────▼────────────┐
                  │ dq/validate_raw       │  ← Pandera  (TODO)
                  └──────────┬────────────┘
                             │ transform
                  ┌──────────▼────────────┐
                  │ dq/validate_clean     │  (TODO)
                  └──────────┬────────────┘
                             │ upsert (idempotent)
                  ┌──────────▼────────────┐
                  │  PostgreSQL           │
                  │  prices_daily, ...    │
                  └───────────────────────┘
```

## Verzeichnisstruktur

```
finance_data/
├── AGENTS.md                # LLM-Agenten-Prompt
├── docker-compose.yml       # postgres + adminer + prefect
├── pyproject.toml           # deps + ruff/mypy/pytest config
├── Makefile                 # task db-up, task ingest, task test, task dq
├── alembic.ini
├── alembic/                 # Migrationen
├── config/                  # tickers.yaml, vendors.yaml, series_registry.yaml
├── src/finance_data/
│   ├── db/                  # Base, session, models
│   ├── vendors/             # Vendor-Base, FRED
│   ├── pipelines/           # Prefect-Flows (TODO)
│   ├── dq/                  # Pandera/GE (TODO)
│   └── utils/               # config, logging, retry, rate_limit
├── tests/                   # pytest
├── scripts/                 # Standalone-CLIs (query_db.py, build_notebook.py)
├── notebooks/               # Jupyter-Notebooks (01_macro_overview.ipynb)
├── sql/                     # manuelle Queries / Views
└── docs/                    # data_dictionary, sources, methodology
```

## Vendor- und Lizenzhinweise

Siehe [`docs/sources.md`](./docs/sources.md). Roh-Daten werden **nicht**
weiterverteilt. Verwendung nur für private / nicht-kommerzielle Forschung.

## Lizenz

Siehe [`LICENSE`](./LICENSE). Kein SLA.
# deephold-db
