# deephold_db Handbuch — Makefile
#
# Baut das LaTeX-Handbuch aus den Chapter-Files zu deephold_db.pdf.
#
# Voraussetzungen:
#   pdflatex (TeX Live 2023+)
#   biber (für Literaturverzeichnis)
#   Standardpakete: listings, tikz, pgfplots, tcolorbox, hyperref, ...
#
# Schnellstart (einmalig):
#   make install-deps     # installiert fehlende TeX-Live-Pakete
#   make                  # baut das PDF (3 Läufe für Cross-References)

LATEX      ?= pdflatex
BIBER      ?= biber
LATEXFLAGS  = -interaction=nonstopmode
SRC        = deephold_db.tex
PDF        = deephold_db.pdf

.PHONY: all build clean install-deps watch open help

all: build

build: $(PDF)

$(PDF): $(SRC) chapters/*.tex appendix/*.tex
	@echo "=== Pass 1 (TOC + Aux) ==="
	@$(LATEX) $(LATEXFLAGS) $(SRC) > /tmp/pdflatex-pass1.log 2>&1 || true
	@if ! grep -aq "Output written" /tmp/pdflatex-pass1.log; then \
	  echo "Pass 1 failed (no PDF output):" && \
	  grep -a "^!" /tmp/pdflatex-pass1.log | head -10 && \
	  exit 1; \
	fi
	@echo "=== Biber (Bibliography) ==="
	@$(BIBER) $(SRC) > /tmp/biber.log 2>&1 || true
	@echo "=== Pass 2 (Refs) ==="
	@$(LATEX) $(LATEXFLAGS) $(SRC) > /tmp/pdflatex-pass2.log 2>&1 || true
	@echo "=== Pass 3 (Final TOC) ==="
	@$(LATEX) $(LATEXFLAGS) $(SRC) > /tmp/pdflatex-pass3.log 2>&1 || true
	@echo "=== Done: $(PDF) ==="
	@ls -la $(PDF)

clean:
	@rm -f $(PDF) *.aux *.log *.toc *.out *.bbl *.bcf *.blg *.run.xml
	@echo "Cleaned auxiliary files."

# Iterativ fehlende Pakete installieren (für Erstkompilierung).
# Benötigt TeX Live mit tlmgr im PATH.
install-deps:
	@echo "Installing required TeX Live packages..."
	@for pkg in csquotes babel-german listings tcolorbox pgf pgfplots \
	           fancyhdr hyperref tocloft booktabs imakeidx biblatex biber \
	           microtype lmodern inconsolata setspace parskip geometry \
	           amsmath amssymb xcolor upquote xkeyval multirow comment; do \
	  tlmgr install $$pkg 2>&1 | grep -v "package log updated" | grep -v "already present" || true; \
	done
	@echo "Done."

watch:
	@echo "Watching .tex files. Ctrl-C to stop."
	@while true; do \
	  inotifywait -e modify $(SRC) chapters/*.tex appendix/*.tex 2>/dev/null && \
	    $(MAKE) build 2>&1 | tail -10; \
	done

open: $(PDF)
	@xdg-open $(PDF) 2>/dev/null || open $(PDF) 2>/dev/null || \
	  echo "Open $(PDF) manually."

help:
	@echo "Targets:"
	@echo "  build         - Build deephold_db.pdf (default)"
	@echo "  install-deps  - Install missing TeX Live packages"
	@echo "  clean         - Remove auxiliary files"
	@echo "  watch         - Rebuild on file changes"
	@echo "  open          - Open the PDF"
