"""Build and execute the example notebook.

Builds notebooks/01_macro_overview.ipynb from cell definitions,
then runs ``jupyter nbconvert --execute`` to embed the outputs (data
prints, plotly figures) into the .ipynb.

Re-run this script any time you change the cell sources; the notebook
itself is treated as a build artefact.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "01_macro_overview.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip("\n"))


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip("\n"))


CELLS: list[nbf.NotebookNode] = [
    md(
        """
        # finance_data — Macro + Equity Time Series Overview

        Zieht Makro-Serien aus `macro_observations` (PostgreSQL via SQLAlchemy +
        Polars) und Equity-OHLCV aus `prices_daily`, plottet mit Plotly.

        Voraussetzung: `docker compose up -d postgres` läuft, die Tabellen
        existieren (via `alembic upgrade head`) und `macro_observations` +
        `prices_daily` sind gefüllt (z.B. `python scripts/query_db.py`).
        """
    ),
    md("## 1. Setup"),
    code(
        """
        from datetime import date
        import polars as pl
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        from finance_data.db import (
            Instrument,
            InstrumentIdentifier,
            MacroObservation,
            PricesDaily,
            session_scope,
        )
        """
    ),
    md("## 2. Daten laden"),
    code(
        """
        SERIES = [
            "FRED:DGS3MO",
            "FRED:DGS10",
            "FRED:FEDFUNDS",
            "FRED:CPIAUCSL",
            "FRED:UNRATE",
            "ECB:EXR:USD.EUR.SP00.A",
            "ECB:EXR:GBP.EUR.SP00.A",
            "ECB:EXR:JPY.EUR.SP00.A",
            "ECB:ICP:U2.N.000000.4.ANR",
        ]


        def load_series(series_id: str) -> pl.DataFrame:
            with session_scope() as s:
                rows = (
                    s.query(MacroObservation)
                    .filter(MacroObservation.series_id == series_id)
                    .order_by(MacroObservation.date)
                    .all()
                )
            return pl.DataFrame(
                {"date": [r.date for r in rows], "value": [float(r.value) for r in rows]}
            )


        def load_ohlcv(yahoo_symbol: str) -> pl.DataFrame:
            with session_scope() as s:
                inst = (
                    s.query(Instrument)
                    .join(InstrumentIdentifier, InstrumentIdentifier.instrument_id == Instrument.instrument_id)
                    .filter(
                        InstrumentIdentifier.scheme == "YAHOO",
                        InstrumentIdentifier.value == yahoo_symbol,
                    )
                    .one_or_none()
                )
                if inst is None:
                    return pl.DataFrame()
                rows = (
                    s.query(PricesDaily)
                    .filter(PricesDaily.instrument_id == inst.instrument_id)
                    .order_by(PricesDaily.date)
                    .all()
                )
            return pl.DataFrame(
                {
                    "date": [r.date for r in rows],
                    "close": [float(r.close) for r in rows],
                    "adj_close": [float(r.adjusted_close) for r in rows],
                    "volume": [int(r.volume) for r in rows],
                }
            )


        data = {sid: load_series(sid) for sid in SERIES}
        equities = {sym: load_ohlcv(sym) for sym in ["AAPL", "MSFT", "^GSPC"]}

        for sid, df in data.items():
            print(f"{sid:<32} rows={df.height:>5}  range={df['date'].min()}..{df['date'].max()}")
        for sym, df in equities.items():
            print(f"YAHOO:{sym:<10} rows={df.height:>5}  range={df['date'].min()}..{df['date'].max()}")
        """
    ),
    md("## 3. Plots"),
    md(
        """
        3x2 Subplot-Grid (Macro + Equity):

        - **(1,1) US Zinsstruktur**: DGS3MO + DGS10 + FEDFUNDS
        - **(1,2) Inflation**: FRED CPI vs. ECB HICP YoY
        - **(2,1) FX**: USD/EUR + GBP/EUR (linke Y), JPY/EUR (rechte Y, andere Skala)
        - **(2,2) Arbeitsmarkt**: UNRATE
        - **(3,1) Equity Prices**: AAPL + MSFT (linke Y), S&P 500 (rechte Y, andere Skala)
        - **(3,2) Equity Volume**: AAPL + MSFT Volumen
        """
    ),
    code(
        """
        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=(
                "US Zinsstruktur (FRED)",
                "Inflation: US CPI vs. EA HICP YoY",
                "FX Major vs. EUR",
                "US Arbeitslosenquote (FRED)",
                "Equity Prices: AAPL, MSFT, S&P 500",
                "Equity Volume: AAPL, MSFT",
            ),
            specs=[
                [{"secondary_y": False}, {"secondary_y": True}],
                [{"secondary_y": True}, {"secondary_y": False}],
                [{"secondary_y": True}, {"secondary_y": False}],
            ],
            horizontal_spacing=0.10,
            vertical_spacing=0.09,
        )

        # --- (1,1) US yields ---
        for sid, color in [("FRED:FEDFUNDS", "#9467bd"), ("FRED:DGS3MO", "#1f77b4"), ("FRED:DGS10", "#d62728")]:
            df = data[sid]
            fig.add_trace(
                go.Scatter(x=df["date"], y=df["value"], name=sid.split(":")[1], line=dict(color=color, width=2)),
                row=1,
                col=1,
            )
        fig.update_yaxes(title_text="Yield (%)", row=1, col=1)

        # --- (1,2) Inflation: CPI (Index, left) vs. HICP YoY (%) right ---
        cpi = data["FRED:CPIAUCSL"]
        hicp = data["ECB:ICP:U2.N.000000.4.ANR"]
        fig.add_trace(
            go.Scatter(x=cpi["date"], y=cpi["value"], name="US CPI (NSA, Index)", line=dict(color="#ff7f0e", width=2)),
            row=1,
            col=2,
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(x=hicp["date"], y=hicp["value"], name="EA HICP YoY (%)", line=dict(color="#2ca02c", width=2)),
            row=1,
            col=2,
            secondary_y=True,
        )
        fig.update_yaxes(title_text="US CPI Index", row=1, col=2, secondary_y=False)
        fig.update_yaxes(title_text="EA HICP YoY (%)", row=1, col=2, secondary_y=True)

        # --- (2,1) FX: USD/EUR + GBP/EUR (left), JPY/EUR (right) ---
        for sid, color in [("ECB:EXR:USD.EUR.SP00.A", "#1f77b4"), ("ECB:EXR:GBP.EUR.SP00.A", "#2ca02c")]:
            df = data[sid]
            fig.add_trace(
                go.Scatter(x=df["date"], y=df["value"], name=sid.split(":")[1], line=dict(color=color, width=2)),
                row=2,
                col=1,
                secondary_y=False,
            )
        jpy = data["ECB:EXR:JPY.EUR.SP00.A"]
        fig.add_trace(
            go.Scatter(x=jpy["date"], y=jpy["value"], name="JPY/EUR (per 100 JPY)", line=dict(color="#d62728", width=2)),
            row=2,
            col=1,
            secondary_y=True,
        )
        fig.update_yaxes(title_text="EUR per USD/GBP", row=2, col=1, secondary_y=False)
        fig.update_yaxes(title_text="EUR per 100 JPY", row=2, col=1, secondary_y=True)

        # --- (2,2) Unemployment ---
        unrate = data["FRED:UNRATE"]
        fig.add_trace(
            go.Scatter(
                x=unrate["date"],
                y=unrate["value"],
                name="UNRATE",
                fill="tozeroy",
                line=dict(color="#17becf", width=2),
            ),
            row=2,
            col=2,
        )
        fig.update_yaxes(title_text="Unemployment (%)", row=2, col=2)

        # --- (3,1) Equity prices: AAPL, MSFT (left), ^GSPC (right, different scale) ---
        for sym, color in [("AAPL", "#1f77b4"), ("MSFT", "#2ca02c")]:
            df = equities[sym]
            fig.add_trace(
                go.Scatter(x=df["date"], y=df["adj_close"], name=f"{sym} (adj close)", line=dict(color=color, width=2)),
                row=3,
                col=1,
                secondary_y=False,
            )
        sp = equities["^GSPC"]
        fig.add_trace(
            go.Scatter(x=sp["date"], y=sp["close"], name="^GSPC (S&P 500)", line=dict(color="#d62728", width=2)),
            row=3,
            col=1,
            secondary_y=True,
        )
        fig.update_yaxes(title_text="AAPL/MSFT (USD)", row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="S&P 500 Index", row=3, col=1, secondary_y=True)

        # --- (3,2) Equity volume ---
        for sym, color in [("AAPL", "#1f77b4"), ("MSFT", "#2ca02c")]:
            df = equities[sym]
            fig.add_trace(
                go.Bar(x=df["date"], y=df["volume"], name=f"{sym} volume", marker_color=color, opacity=0.6),
                row=3,
                col=2,
            )
        fig.update_yaxes(title_text="Volume", row=3, col=2)
        fig.update_layout(barmode="overlay")

        fig.update_layout(
            height=1100,
            width=1300,
            title_text="finance_data — Macro + Equity Overview",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=-0.05, xanchor="center", x=0.5),
        )
        fig.show()
        """
    ),
    md("## 4. Summary-Statistik pro Serie"),
    code(
        """
        rows = []
        for sid, df in data.items():
            v = df["value"]
            rows.append(
                {
                    "series_id": sid,
                    "rows": df.height,
                    "first": df["date"].min(),
                    "last": df["date"].max(),
                    "latest": float(v[-1]),
                    "min": float(v.min()),
                    "max": float(v.max()),
                    "mean": float(v.mean()),
                    "std": float(v.std()),
                }
            )
        for sym, df in equities.items():
            v = df["adj_close"]
            rows.append(
                {
                    "series_id": f"YAHOO:{sym}",
                    "rows": df.height,
                    "first": df["date"].min(),
                    "last": df["date"].max(),
                    "latest": float(v[-1]),
                    "min": float(v.min()),
                    "max": float(v.max()),
                    "mean": float(v.mean()),
                    "std": float(v.std()),
                }
            )
        summary = pl.DataFrame(rows)
        print(summary)
        """
    ),
    md(
        """
        ## 5. Nächste Schritte

        - Mehr Serien: `config/series_registry.yaml` erweitern
        - Andere Asset-Klassen: `prices_daily` (Aktien) via Yahoo-Adapter
        - Inkrementelles Update: `make ingest-all` (geplant)
        - DQ-Checks: `src/finance_data/dq/` (Pandera-Schemas, geplant)
        """
    ),
]


def main() -> int:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook()
    nb.cells = CELLS
    nb.metadata = {
        "kernelspec": {
            "name": "python3",
            "display_name": "Python 3",
            "language": "python",
        },
        "language_info": {"name": "python", "version": sys.version.split()[0]},
    }

    with NOTEBOOK_PATH.open("w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print(f"wrote {NOTEBOOK_PATH}")

    print("executing notebook (this may take a few seconds)...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
            "--ExecutePreprocessor.timeout=180",
            str(NOTEBOOK_PATH),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr, file=sys.stderr)
        return result.returncode
    print(f"executed → {NOTEBOOK_PATH}")

    # Also export a static HTML view for quick inspection without Jupyter.
    html_path = NOTEBOOK_PATH.with_suffix(".html")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "html",
            str(NOTEBOOK_PATH),
            "--output",
            html_path.name,
        ],
        cwd=NOTEBOOK_PATH.parent,
        check=True,
    )
    print(f"html export → {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
