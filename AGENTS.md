# AGENTS.md

This file is the authoritative task description for any coding/research agent
working on this repository. It is intentionally written in German (the project
language) and intentionally **concrete**: an agent should be able to execute
it without further clarification.

Scope: **Retail / Research**. No Point-in-Time, no survivorship-bias-free
universes, no intraday, no option chains, no bond-CUSIP-level.

---

# Agent Prompt: Aufbau einer Finanzmarktdatenbank

## Rolle

Du bist ein erfahrener Quant-Researcher und Data Engineer. Du baust eine
reproduzierbare, erweiterbare Finanzmarktdatenbank mit historischen Zeitreihen
auf täglicher Frequenz. Sie dient quantitativen Analysen, Portfolio-Management,
Asset Allocation, Risikomodellierung, Makroanalyse und Machine Learning.

## Ziel-Stack

- Python 3.11+, Poetry, Pandas/Polars
- SQLAlchemy 2.x, Alembic
- PostgreSQL 16 (lokal via docker-compose)
- Prefect 2.x (Orchestration) — Self-hosted Server
- Pandera + Great Expectations für Datenqualität
- structlog (Logging), tenacity (Retries), httpx (HTTP)
- pytest, pytest-postgresql
- ruff (Lint + Format), mypy (Type-Check)

## Repository-Layout

```
deephold_db/
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
├── Makefile
├── .env.example
├── .gitignore
├── README.md
├── AGENTS.md
├── config/
│   ├── tickers.yaml
│   ├── vendors.yaml
│   └── series_registry.yaml
├── src/deephold_db/
│   ├── __init__.py
│   ├── db/
│   ├── vendors/
│   ├── pipelines/
│   ├── dq/
│   └── utils/
├── sql/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/
└── docs/
    ├── data_dictionary.md
    ├── sources.md
    └── methodology.md
```

## Konfiguration

- Alle Ticker-Listen, Vendor-Endpoints und Series-IDs in YAML unter `config/`.
- Secrets ausschließlich via `.env`. Im Repo nur `.env.example`.
- Niemals Secrets im Code.

## Asset-Klassen und Mindestumfang

1. **Aktien**: Top ~500 US, ~600 EU, ~300 Japan, ~300 EM
   (Listen in `config/tickers.yaml` als Region→Ticker-Mapping).
   Felder: Open, High, Low, Close, Adjusted Close, Volume.
2. **Indizes**: S&P 500, Nasdaq 100, Dow Jones, Russell 2000, STOXX 600,
   DAX, CAC 40, FTSE 100, Nikkei 225, MSCI World, MSCI EM — jeweils
   **Price + Total Return** wenn verfügbar.
3. **Staatsanleihen**: USA, DE, UK, JP, FR, IT, ES — Laufzeiten
   3M, 6M, 1Y, 2Y, 5Y, 10Y, 30Y — **Yield täglich** (Preis nur wenn
   verfügbar).
4. **Credit-Indizes**: USD IG, USD HY, EUR IG, EUR HY (z.B. via ETF
   LQD, HYG, IGLT, HYGB).
5. **Geldmarkt**: SOFR, EFFR, ESTR, Euribor 3M/6M, SONIA.
6. **Rohstoffe**: Gold, Silber, Platin, Palladium, Kupfer, WTI, Brent,
   Erdgas, Weizen, Mais, Soja — **Spot + Front-Month Future**.
7. **FX**: EUR/USD, USD/JPY, GBP/USD, USD/CHF, AUD/USD, USD/CAD, USD/CNY.
8. **Volatilität**: VIX, VSTOXX, MOVE.
9. **Makro**: CPI, Core CPI, PPI, Unemployment, IP, M1/M2, GDP,
   PMI Manufacturing, PMI Services — pro Land US, EU, JP, UK, DE.

## Quellen (in dieser Priorität)

1. **FRED** (primär für Zinsen, Makro, FX, Indizes via ETF-Tracker) —
   API-Key via `FRED_API_KEY`.
2. **ECB SDMX** (primär für EUR-Geldmarkt, EUR-Anleiheyields, ESTR, HICP).
3. **Bundesbank** (sekundär für EUR-Detail).
4. **Yahoo Finance** via `yfinance` (nur für Aktien, ETF, Future,
   Commodity-Spot — **privater Gebrauch, ToS beachten**, dokumentieren).
5. **Stooq** (Backup, CSV-Download).
6. **OECD**, **IMF**, **World Bank** (Makro, falls nicht in FRED).

Jede Serie wird in `config/series_registry.yaml` dokumentiert mit:
`series_id`, `name`, `source`, `license`, `url`, `first_date`,
`last_date`, `frequency`, `unit`, `notes`.

## Datenmodell

Exakt dieses Schema (keine Abweichungen ohne Migration):

```sql
-- Stammdaten
CREATE TABLE venues (
  venue_id   SERIAL PRIMARY KEY,
  code       TEXT UNIQUE NOT NULL,
  name       TEXT,
  timezone   TEXT,
  country    CHAR(2)
);

CREATE TABLE instruments (
  instrument_id   BIGSERIAL PRIMARY KEY,
  asset_class     TEXT NOT NULL,
  name            TEXT NOT NULL,
  currency        CHAR(3),
  primary_venue   INT REFERENCES venues(venue_id),
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE instrument_identifiers (
  instrument_id  BIGINT REFERENCES instruments(instrument_id),
  scheme         TEXT NOT NULL,
  value          TEXT NOT NULL,
  PRIMARY KEY (scheme, value)
);
CREATE INDEX ON instrument_identifiers(instrument_id);

CREATE TABLE vendors (
  vendor_id   SERIAL PRIMARY KEY,
  code        TEXT UNIQUE,
  license     TEXT,
  homepage    TEXT
);

CREATE TABLE trading_calendars (
  venue_id      INT REFERENCES venues(venue_id),
  date          DATE,
  is_trading_day BOOLEAN,
  PRIMARY KEY (venue_id, date)
);

-- Roh-Preise (vendor-original)
CREATE TABLE prices_raw (
  vendor_id     INT REFERENCES vendors(vendor_id),
  vendor_symbol TEXT NOT NULL,
  date          DATE NOT NULL,
  payload       JSONB NOT NULL,
  ingested_at   TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (vendor_id, vendor_symbol, date)
);

-- Bereinigte, harmonisierte Preise
CREATE TABLE prices_daily (
  instrument_id    BIGINT REFERENCES instruments(instrument_id),
  date             DATE NOT NULL,
  open             NUMERIC(18,8),
  high             NUMERIC(18,8),
  low              NUMERIC(18,8),
  close            NUMERIC(18,8),
  adjusted_close   NUMERIC(18,8),
  volume           BIGINT,
  vendor_id        INT REFERENCES vendors(vendor_id),
  PRIMARY KEY (instrument_id, date)
);
CREATE INDEX ON prices_daily(date);
CREATE INDEX ON prices_daily(instrument_id, date DESC);

CREATE TABLE corporate_actions (
  instrument_id BIGINT REFERENCES instruments(instrument_id),
  ex_date       DATE,
  action_type   TEXT,
  value         NUMERIC(18,8),
  PRIMARY KEY (instrument_id, ex_date, action_type)
);

CREATE TABLE fx_rates_daily (
  ccy_from  CHAR(3),
  ccy_to    CHAR(3),
  date      DATE,
  rate      NUMERIC(18,8),
  vendor_id INT REFERENCES vendors(vendor_id),
  PRIMARY KEY (ccy_from, ccy_to, date)
);

CREATE TABLE bond_yields (
  instrument_id BIGINT REFERENCES instruments(instrument_id),
  date          DATE,
  yield         NUMERIC(10,6),
  price         NUMERIC(10,6),
  duration      NUMERIC(10,4),
  rating        TEXT,
  PRIMARY KEY (instrument_id, date)
);

CREATE TABLE macro_series (
  series_id  TEXT PRIMARY KEY,
  name       TEXT,
  source     TEXT,
  frequency  TEXT,
  unit       TEXT
);
CREATE TABLE macro_observations (
  series_id TEXT REFERENCES macro_series(series_id),
  date      DATE,
  value     NUMERIC(18,6),
  PRIMARY KEY (series_id, date)
);

CREATE TABLE dq_runs (
  run_id        BIGSERIAL PRIMARY KEY,
  run_at        TIMESTAMPTZ DEFAULT now(),
  pipeline      TEXT,
  status        TEXT
);
CREATE TABLE dq_findings (
  run_id        BIGINT REFERENCES dq_runs(run_id),
  check_name    TEXT,
  severity      TEXT,
  affected_rows INT,
  details       JSONB
);
```

## ETL-Pipeline

- Jeder Vendor = eigener Adapter in `src/deephold_db/vendors/<vendor>.py`
  mit Interface:
  ```python
  def fetch(symbol: str, start: date, end: date) -> pl.DataFrame: ...
  def healthcheck() -> bool: ...
  ```
- Pro Asset-Klasse ein Prefect-Flow:
  `extract` → `validate_raw` → `transform` → `validate_clean` → `upsert`.
- **Idempotent**: Re-Runs dürfen keine Duplikate erzeugen (UPSERT über PK).
- **Rate-Limit-Handling**: token-bucket pro Vendor, 429/503 →
  exponential backoff via tenacity.
- **Symbol-Mapping**: yfinance-Ticker → `instrument_id` via
  `instrument_identifiers.scheme='YAHOO'`. Beim Insert: `lookup_or_create`
  für das Instrument.

## Datenqualität

Mindestens diese Checks (Pandera-Schemata oder GE-Suites):

1. PK-Eindeutigkeit `(instrument_id, date)`.
2. OHLC-Konsistenz: `low ≤ open, close ≤ high`.
3. Keine negativen Preise/Volumes.
4. Adjusted-Close ≈ Close × Split-Faktor (per `corporate_actions`).
5. Keine Lücken > 5 Handelstage ohne Eintrag in `dq_findings`.
6. Ausreißer: Tages-Return > 6σ rolling(252) → Flag in `dq_findings`,
   **nicht** löschen.
7. Currency-Coverage: jedes Instrument hat Currency gesetzt.
8. Vendor-Coverage: jede Zeile in `prices_daily` hat `vendor_id`.

## Update-Strategie

- **Initial**: 30 Jahre Historie pro Serie, batched (max. 500 Symbole
  pro Run, max. 5 parallele Vendor-Worker).
- **Inkrementell**: täglich 02:00 lokal, `last_date in prices_daily + 1`
  bis `today`, idempotent.
- **Retry**: 3 Versuche, Backoff 5s/30s/120s.
- **Failure-Isolation**: ein Vendor schlägt fehl → andere laufen weiter;
  Failures landen in `dq_findings` + Log-Alert.

## Backtest-Support

Auch im Retail-Scope wichtig:

- Alle Preise in `prices_daily` sind **PIT-konsistent**: `adjusted_close`
  ist so berechnet, wie es am `date` gültig war — keine rückwirkenden
  Korrekturen ohne Versions-Marker.
- `corporate_actions` ist Pflicht für jedes Split-/Dividenden-Event.
- `fx_rates_daily` enthält den **historischen** Cross-Rate, kein
  „heutiger EUR/USD auf alte Daten gemappt".

## Reproduzierbarkeit

- `make init` → `poetry install` + Stack hoch + `alembic upgrade head`.
- `make up` / `make down` → docker-compose.
- `make migrate` → alembic upgrade head.
- `make revision m="..."` → neue alembic-Revision.
- `make ingest-<asset_class>` → eine Klasse (z.B. `ingest-equities`).
- `make ingest-all` → komplett, idempotent.
- `make test` → pytest + pandera-Schemas.
- `make dq-report` → HTML-Report aus `dq_runs`/`dq_findings` der letzten
  7 Tage.
- `make dq-full` → vollständige DB-Validierung.
- `make format` / `make lint` / `make typecheck`.

## Legal / Compliance

- `docs/sources.md` listet pro Vendor: URL, Lizenz, ToS-Auszug,
  letzter Abruf, **Zweck (privat / Forschung)**.
- Keine Weiterverteilung der Roh-Daten.
- `LICENSE` im Repo: nicht-kommerziell, kein SLA.

## Deliverables (in dieser Reihenfolge)

1. `docker-compose.yml` (postgres + adminer + prefect-server).
2. `pyproject.toml` + `poetry.lock`.
3. `Makefile`.
4. SQLAlchemy-Models + Alembic-Migrationen.
5. Vendor-Adapter (zuerst FRED, dann ECB, dann Yahoo, dann Stooq).
6. Prefect-Flows je Asset-Klasse.
7. DQ-Checks + Report-Skript.
8. `config/tickers.yaml`, `config/vendors.yaml`,
   `config/series_registry.yaml` mit **vollständigen Listen**
   (kein „TODO" — der Agent inventarisiert selbst).
9. `docs/data_dictionary.md`, `docs/sources.md`, `docs/methodology.md`,
   `README.md`.
10. Tests: mind. 1 pro Vendor + 1 pro Flow + 1 pro DQ-Check.
11. End-to-End-Smoketest:
    `make init && make ingest-indexes && \
     psql -c "select count(*) from prices_daily"`
    liefert eine positive Zahl.

## Regeln

- **Keine** Annahmen über Bibliotheken ohne sie im `pyproject.toml` zu sehen.
- **Keine** Ticker oder Series-IDs hardcoded im Code — nur in YAML.
- **Keine** Mock-Daten in Production-Code-Pfaden.
- **Kein** silent fallback: Vendor-Down → Failure in `dq_findings`.
- Am Ende: finaler Statusbericht — was läuft, was fehlt, was als nächstes käme.

## Explizit draußen (für später)

- CRSP-äquivalente PIT-Daten
- historische Index-Mitglieder
- historische Ratings
- Delisting-Returns
- echte Continuous-Future-Konstruktion mit Roll-Kalender
- Option-Chains
- Bond-CUSIP-Ebene
- Multi-Vendor-Reconciliation
