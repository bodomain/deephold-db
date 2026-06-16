# Data Dictionary

Detaillierte Spalten-Dokumentation für jede Tabelle. Wird vom implementierenden
Agenten gefüllt, sobald die Modelle stehen.

## Übersicht

| Tabelle               | Zweck                                      | Primärschlüssel                            |
|-----------------------|--------------------------------------------|--------------------------------------------|
| `venues`              | Börsen/Handelsplätze                       | `venue_id`                                 |
| `instruments`         | Asset-Master                               | `instrument_id`                            |
| `instrument_identifiers` | Cross-Vendor-ID-Mapping                  | `(scheme, value)`                          |
| `vendors`             | Datenquellen                               | `vendor_id`                                |
| `trading_calendars`   | Handelstage je Venue                       | `(venue_id, date)`                         |
| `prices_raw`          | Roh-Vendor-Payload (JSONB)                 | `(vendor_id, vendor_symbol, date)`         |
| `prices_daily`        | Harmonisierte OHLCV-Serie                  | `(instrument_id, date)`                    |
| `corporate_actions`   | Splits / Dividenden / Spinoffs             | `(instrument_id, ex_date, action_type)`    |
| `fx_rates_daily`      | Cross-Currency-FX                          | `(ccy_from, ccy_to, date)`                 |
| `bond_yields`         | Bond-spezifische Felder (yield, duration)  | `(instrument_id, date)`                    |
| `macro_series`        | Stammdaten zu Makro-Serien                 | `series_id`                                |
| `macro_observations`  | Makro-Beobachtungen                        | `(series_id, date)`                        |
| `dq_runs`             | DQ-Lauf-Metadaten                          | `run_id`                                   |
| `dq_findings`         | DQ-Befunde                                 | `run_id` (FK), `check_name`                 |

## Spaltenreferenz

Wird nach Implementierung der ORM-Modelle gefüllt.

## Identifier-Schemes

`scheme`-Werte für `instrument_identifiers`:
- `ISIN`, `CUSIP`, `SEDOL`, `RIC`, `BBG`, `YAHOO`, `STOOQ`, `FRED`, `ECB`
