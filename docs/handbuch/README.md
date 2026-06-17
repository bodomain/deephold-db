# deephold_db Handbuch

Deutschsprachiges LaTeX-Lehrbuch für das `deephold_db`-Projekt.

## Inhalt

| Datei | Inhalt |
| --- | --- |
| `deephold_db.tex`         | Hauptdatei, bindet alle Kapitel + Anhänge ein |
| `chapters/00_vorwort.tex`  | Vorwort, Scope-Definition, Zielgruppen |
| `chapters/01_einfuehrung.tex` | Einführung, Asset-Klassen, Quellen-Stack |
| `chapters/02_grundlagen.tex` | PIT, OHLCV, Corporate Actions, VAM-Konzept |
| `chapters/03_infrastruktur.tex` | Docker, Postgres, `.env`, Makefile |
| `chapters/04_datenmodell.tex` | ER-Diagramm, 14 Tabellen, Trade-offs |
| `chapters/05_vendor_adapter.tex` | FRED, ECB, Yahoo, Stooq |
| `chapters/06_etl_pipeline.tex` | extract → validate → transform → upsert |
| `chapters/07_notebook.tex` | Plotly-Grid, Makro-Overview |
| `chapters/08_tui.tex`      | OpenTUI, React 19, `pg`-Client, 2-Pane-Layout |
| `chapters/09_tests.tex`    | pytest, bun test, Pandera-Schemas |
| `chapters/10_analytics_paper.tex` | VAM-Lite, CAGR/Sharpe, AEGIS-Vergleich |
| `appendix/a_glossar.tex`   | Glossar |
| `appendix/b_befehle.tex`   | Makefile-Befehle |
| `appendix/c_schema.tex`    | Vollständiges DDL-Schema |
| `appendix/d_literatur.tex` | Literatur (34 Quellen) |
| `Makefile`                 | Build-Automation |
| `deephold_db.pdf`         | Generiertes PDF (102 Seiten) |

## Bauen

```bash
# Vom Projekt-Root:
make handbuch                  # baut deephold_db.pdf (3 pdflatex-Passes + biber)
make handbuch-install-deps     # installiert fehlende TeX-Live-Pakete
make handbuch-clean            # räumt *.aux, *.log, *.toc, etc. auf

# Direkt in docs/handbuch/:
cd docs/handbuch && make build
```

## Voraussetzungen

- **TeX Live 2023+** mit `pdflatex` und `biber` im PATH
- Pakete: `csquotes`, `babel-german`, `listings`, `tcolorbox`, `pgf`,
  `pgfplots`, `biblatex`, `microtype`, `lmodern`, `inconsolata`,
  `fancyhdr`, `hyperref`, `tocloft`, `booktabs`, `imakeidx`, `xcolor`,
  `upquote`, `xkeyval`, `multirow`, `comment`, `geometry`, `setspace`,
  `parskip`, `amsmath`, `amssymb`

## Encoding-Hinweise

- Alle `.tex`-Dateien sind UTF-8.
- Deutsche Umlaute (ä, ö, ü, ß) werden direkt verwendet.
- `babel-german` ist geladen → Anführungszeichen werden automatisch zu „…".
- Listings: `lstlisting`-Umgebungen mit `basicstyle=\ttfamily` für Code.

## Bekannte Warnungen

- `listings`-Paket gibt bei Code mit Sonderzeichen (z.B. `π`, `…`)
  harmlose UTF-8-Warnungen aus. Die PDF wird trotzdem korrekt erzeugt.
- Falls `biber` nicht installiert ist, läuft der Build trotzdem durch —
  nur das Literaturverzeichnis enthält dann unsortierte Platzhalter.

## Lizenz

Das Handbuch steht unter derselben Lizenz wie der restliche
Projektquellcode (siehe `LICENSE` im Repo-Root). Verwendung
ausschließlich für private / nicht-kommerzielle Bildung und Forschung.
