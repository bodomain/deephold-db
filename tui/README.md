# deephold-db-tui

OpenTUI-basierter Daten-Explorer für die `deephold_db`-PostgreSQL-DB.

Schnelles, interaktives TUI-Frontend (kein Jupyter nötig) zum Browsen
der Macro- und Equity-Serien.

## Quick Start (TL;DR)

```bash
# 1. Bun einmalig installieren
curl -fsSL https://bun.sh/install | bash

# 2. Postgres + Daten sicherstellen
docker compose up -d postgres
.venv/bin/alembic upgrade head
.venv/bin/python scripts/query_db.py     # seedet FRED + ECB + Yahoo

# 3. TUI starten
cd tui && bun install && bun run start
# oder vom Repo-Root:
make tui
```

Dann navigierst du mit `↑/↓` durch die 12 Serien, siehst rechts die letzten
30 Werte + Stats, drückst `q` zum Beenden.

## Bedienung (Tastatur)

| Taste | Aktion |
|---|---|
| `↑` / `k` | Selection nach oben |
| `↓` / `j` | Selection nach unten |
| `g` / `Home` | Zum Anfang der Liste |
| `G` / `End` | Zum Ende der Liste |
| `r` | Series-Liste neu laden (für Live-Refresh nach Seed) |
| `q` / `Ctrl-C` | TUI beenden |

## Was du im TUI siehst

```
┌─ deephold_db — TUI Explorer    12 series ─────────────────┐
├─Series (12)──────────┬─AAPL — Apple Inc.────────────────────┤
│ ▸ E AAPL      yahoo  │  rows  499   first 2024-06-17        │
│   E MSFT      yahoo  │  last  2026-06-12   unit USD         │
│   E ^GSPC     yahoo  │  min   172.42  max 315.22            │
│   M ECB:EXR:GBP.EU…  │  mean  239.9691 source yahoo         │
│   M ECB:EXR:JPY.EU…  │                                      │
│   M ECB:EXR:USD.EU…  │ date        close   adj     vol       │
│   M ECB:ICP:U2.N.00…  │ 2026-06-12  291.13  291.13  38.74M   │
│   M FRED:CPIAUCSL     │ 2026-06-10  291.58  291.58  52.79M   │
│   M FRED:DGS10        │ 2026-06-08  301.54  301.54  77.95M   │
│   M FRED:DGS3MO       │ 2026-06-04  311.23  311.23  44.87M   │
│   M FRED:FEDFUNDS     │ …                                  │
│   M FRED:UNRATE       │                                      │
├─ ↑/↓ navigate  r refresh  g/G top/end  q quit ─────────────┤
```

**Linke Seite (Series-Liste):**

- `▸` = aktuelle Selection
- `M` / `E` = Macro (FRED, ECB) / Equity (Yahoo) Badge
- Series-ID (z.B. `AAPL`, `FRED:DGS3MO`, `ECB:EXR:USD.EUR.SP00.A`)
- Vendor-Tag (`fred` / `ecb` / `yahoo`)
- Row-Count rechtsbündig

**Rechte Seite (Detail):**

- Stats-Zeile: rows, first/last date, unit
- Stats-Zeile: min, max, mean, source
- 30-Zeilen-Tail-Tabelle:
  - **Macro:** `date, value`
  - **Equity:** `date, close, adj, vol` (Volume in M/B formatiert)

## Setup (detailliert)

```bash
# Voraussetzungen
# 1. Bun installieren: curl -fsSL https://bun.sh/install | bash
# 2. Postgres läuft (docker compose up -d postgres)
# 3. Schema + Daten sind da: alembic upgrade head, scripts/query_db.py

# Dependencies installieren + starten
cd tui
bun install
bun run start
```

Oder via Makefile vom Repo-Root:

```bash
make tui
```

## Tests

```bash
# Alle Tests (Unit + Integration)
make tui-test
# oder
cd tui && bun test

# Nur Unit-Tests (kein DB nötig)
bun run test:unit

# Nur Integration-Tests (braucht laufendes Postgres)
bun run test:integration
```

**Was getestet wird:**

| Datei | Typ | Was |
|---|---|---|
| `src/data/queries.test.ts` | Unit (mocked pg) | SQL-String, Row-Mapping, Param-Übergabe |
| `src/data/db.test.ts` | Unit | Pool-Public-API, env-var-Resolution |
| `src/types/format.test.ts` | Unit | Pure-Funktionen (fmtNumber, fmtPct) |
| `tests/integration.test.ts` | Integration | Echtes Postgres, 12 Series, OHLCV-Validierung |

Integration-Tests **no-op'en** (kein Fail) wenn die DB nicht erreichbar ist —
so bleibt die Suite grün, auch wenn Postgres temporär down ist.

**Stand:** 27 Tests, 4 Dateien, 203 `expect()`-Calls, ~200 ms.

## Architektur

```
tui/
├── package.json         # Bun + OpenTUI + React 19
├── tsconfig.json
├── src/
│   ├── index.tsx        # Entry: createCliRenderer → createRoot
│   ├── App.tsx          # Root: 2-Pane-Layout, State, Keyboard
│   ├── components/
│   │   ├── SeriesList.tsx   # linke Seite: 12 Serien mit Badges
│   │   └── SeriesDetail.tsx # rechte Seite: Stats + Tail-Tabelle
│   ├── data/
│   │   ├── db.ts        # pg-Pool
│   │   └── queries.ts   # 4 SQL-Queries: list, macro tail/stats, equity tail/stats
│   └── types.ts
```

## SQL-Queries

Alle read-only, gegen die `finance`-DB:

- `listSeries()` — UNION ALL macro + equity
- `getMacroTail(series_id, limit)` — letzte N Werte einer Macro-Serie
- `getMacroStats(series_id)` — Aggregat (count, min, max, mean, range)
- `getEquityTail(yahoo_symbol, limit)` — letzte N OHLCV via JOIN auf `instrument_identifiers`
- `getEquityStats(yahoo_symbol)` — Aggregat für equity

## Environment

| Variable | Default | Zweck |
|---|---|---|
| `PGHOST` | `localhost` | Postgres host |
| `PGPORT` | `5432` | Postgres port |
| `PGUSER` | `deephold` | Postgres user |
| `PGPASSWORD` | `deephold` | Postgres password |
| `PGDATABASE` | `deephold` | Database name |

Die Defaults entsprechen dem Python-Stack (`docker-compose.yml`).

## Tech-Stack

- **Bun** (Runtime) — OpenTUI-Default, schneller als Node
- **@opentui/core 0.4** — Zig-Core mit C-ABI
- **@opentui/react 0.4** — React-Bindings
- **React 19.2** — peer-dep von @opentui/react
- **pg 8** — Postgres-Client
- **TypeScript 5** strict

## Out of Scope (für später)

- ASCII-Sparklines im Detail
- Such-Filter (`/`)
- Multi-Series-Vergleich
- CSV-Export
- Plot-Mode mit Maus-Hover
- Refresh-Button, der Python-Seeder triggert

Diese Erweiterungen sind in AGENTS.md dokumentiert.

## Manueller Test (interaktive TUI)

Vor dem Deploy oder nach Code-Änderungen die Checkliste durchgehen:

| # | Schritt | Erwartung |
|---|---|---|
| 1 | `make tui` starten | TUI öffnet, Header "deephold_db — TUI Explorer" sichtbar |
| 2 | Initial-Load | "12 series" in der Header-Zeile, nicht "loading..." |
| 3 | Erste Zeile selektiert | AAPL (▸) ist markiert, Detail zeigt Apple-Daten |
| 4 | `↓` 4x drücken | Selection wandert zu MSFT → ^GSPC → GBP/EUR → JPY/EUR |
| 5 | `↑` 2x drücken | Zurück zu ^GSPC (Index, höchste Kurswerte) |
| 6 | `g` drücken | Selection springt zum ersten Eintrag (AAPL) |
| 7 | `G` drücken | Selection springt zum letzten Eintrag (UNRATE) |
| 8 | `r` drücken | Series-Liste wird neu geladen (kurz "loading...") |
| 9 | `k` und `j` testen (Vim-style) | Wie `↑` und `↓` |
| 10 | Macro-Serie wählen (z.B. DGS3MO) | Detail zeigt 30 tägliche Yields, neueste oben |
| 11 | Equity-Serie wählen (z.B. AAPL) | Detail zeigt OHLCV-Tabelle, Volume in M/B formatiert |
| 12 | `q` drücken | TUI beendet sauber, Terminal-Prompt zurück |

**Negativtests (was *nicht* passieren soll):**

- Beim Navigieren: keine „TypeError" oder „undefined"-Fehler im Terminal
- Beim Refresh (`r`): keine doppelten Einträge, kein „stale state"
- Beim Quit (`q`): Prozess endet wirklich (kein hängender bg-job)
- Bei sehr langen Serien-IDs: kein Overflow, sauber mit `…` trunkiert
- Bei Equity-Serien: ID ist der YAHOO-Ticker, nicht die `instrument_id`
