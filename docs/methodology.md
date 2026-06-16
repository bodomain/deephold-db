# Methodik

Wie werden Daten erfasst, transformiert, validiert und gespeichert?

## Erfassung (Extract)

- Jeder Vendor liefert rohe Zeitreihen. Diese werden **unverändert** in
  `prices_raw` (JSONB) abgelegt.
- Vendor-spezifische Identifier werden in `instrument_identifiers` mit
  `scheme='<vendor>'` abgelegt.
- Pro Vendor: token-bucket (Rate-Limit), tenacity-Retry (5s/30s/120s).

## Transformation (Transform)

- Mapping `vendor_symbol → instrument_id` via `instrument_identifiers`.
- Harmonisierung: Datumsformat, Currency (sofern vom Vendor geliefert),
  Numeric-Precision.
- **Adjusted Close** wird entweder vom Vendor übernommen (z.B. yfinance) oder
  aus `corporate_actions` rekonstruiert. Pro Datum genau **eine** Quelle der
  Wahrheit.

## Validierung (DQ)

Acht Mindest-Checks (siehe AGENTS.md):
1. PK-Eindeutigkeit
2. OHLC-Konsistenz
3. Keine negativen Werte
4. Adjusted-Close vs. Corporate-Actions-Konsistenz
5. Lückendetektion (> 5 Handelstage)
6. Ausreißer-Flag (6σ)
7. Currency-Coverage
8. Vendor-Coverage

Befunde landen in `dq_findings` (kein Löschen — nur Flagging).

## Idempotenz

- **Initial:** Batches (max. 500 Symbole / 5 parallele Worker).
- **Inkrementell:** `last_date in prices_daily + 1` bis `today`.
- **UPSERT** auf `(instrument_id, date)` bzw. `(vendor_id, vendor_symbol, date)`.

## Point-in-Time (Retail-Level)

Auch ohne echte PIT-Maschinerie gilt:
- `adjusted_close` ist so gespeichert, wie es am `date` gültig war.
- Re-Run einer historischen Aktualisierung schreibt `prices_raw` mit
  `ingested_at`, das als Versions-Marker dient.
- `corporate_actions` ist Pflicht für jedes Split-/Dividenden-Event.

## FX-Konvertierung

- Cross-Currency-Rates werden historisch konsistent in `fx_rates_daily`
  gespeichert.
- Keine „heutigen" EUR/USD auf alte Daten gemappt — der historische Cross-Rate
  ist die einzige zulässige Quelle für Conversion.

## Calendars

- `trading_calendars(venue_id, date, is_trading_day)` ist die Quelle der
  Wahrheit für „war dieser Tag ein Handelstag?".
- Lücken-Detektion in `prices_daily` läuft gegen `trading_calendars`,
  nicht gegen `date`-Differenzen.

## Failure-Isolation

- Vendor-Failure → `dq_findings` (severity=ERROR) + Log-Alert.
- Andere Vendoren laufen weiter (pro-Vendor-Flow, nicht globaler Flow).
