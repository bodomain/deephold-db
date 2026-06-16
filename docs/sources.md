# Quellen, Lizenzen, ToS

Pro Vendor: URL, Lizenz, ToS-Auszug, letzter Abruf, **Zweck (privat / Forschung)**.
Wird vom implementierenden Agenten gepflegt und beim Hinzufügen eines neuen
Vendors aktualisiert.

## 1. FRED — Federal Reserve Economic Data

- **URL:** https://fred.stlouisfed.org/
- **API:** https://fred.stlouisfed.org/docs/api/api_key.html
- **Lizenz:** Public Domain (US Government)
- **Zweck:** Forschung, nicht-kommerziell
- **Hinweis:** API-Key erforderlich; 120 req/min
- **Letzter Abruf:** TODO

## 2. ECB — Statistical Data Warehouse

- **URL:** https://data.ecb.europa.eu/
- **API:** https://data-api.ecb.europa.eu/service
- **Lizenz:** © European Central Bank, CC BY 4.0
- **Zweck:** Forschung, nicht-kommerziell
- **Hinweis:** SDMX 2.1 REST, Attribution empfohlen
- **Letzter Abruf:** TODO

## 3. Bundesbank

- **URL:** https://www.bundesbank.de/en/statistics/time-series-databases
- **API:** https://api.statistiken.bundesbank.de/rest
- **Lizenz:** Public Domain, Disclaimer der Bundesbank beachten
- **Zweck:** Forschung, nicht-kommerziell
- **Hinweis:** SDMX
- **Letzter Abruf:** TODO

## 4. Yahoo Finance (via yfinance)

- **URL:** https://finance.yahoo.com/
- **API:** undokumentiert, via `yfinance`
- **Lizenz:** Yahoo Terms of Service — **privater Gebrauch**, keine
  Weiterverteilung der Roh-Daten
- **Zweck:** Forschung, nicht-kommerziell, **privat**
- **Hinweis:** Rate-Limits, Schema-Änderungen möglich
- **Letzter Abruf:** TODO

## 5. Stooq

- **URL:** https://stooq.com/
- **Lizenz:** Free for personal use
- **Zweck:** Forschung, nicht-kommerziell
- **Hinweis:** CSV-Download, Backup-Quelle
- **Letzter Abruf:** TODO

## 6. OECD / IMF / World Bank

Siehe `config/vendors.yaml` für Endpoints. Werden nur aktiviert, wenn Lücken
in FRED/ECB bestehen.

## Weiterverteilung

**Roh-Daten** werden in diesem Repo **nicht** weitergegeben. Verarbeitete,
harmonisierte Zeitreihen sind zur Forschungszwecken lokal nutzbar.

## Aktualisierungsplan

- **Quartalsweise:** ToS der aktiven Vendoren prüfen, Link-Rot dokumentieren.
- **Bei License-Change:** betroffene Vendoren in `config/vendors.yaml`
  deaktivieren und DQ-Alert triggern.
