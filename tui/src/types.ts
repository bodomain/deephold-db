// Shared types for finance-data-tui.
// Mirrors the SQL schema in src/finance_data/db/models.py.

export type SeriesKind = "macro" | "equity";

export interface SeriesRow {
  kind: SeriesKind;
  id: string;          // series_id for macro, instrument_id::text for equity
  name: string;
  source: string;      // "fred", "ecb", "yahoo", "demo"
  frequency: string;   // "D" or "M"
  unit: string;
  n: number;           // row count
}

export interface MacroObservation {
  date: string;        // YYYY-MM-DD
  value: number;
}

export interface PriceObservation {
  date: string;
  close: number;
  adjusted_close: number | null;
  volume: number | null;
}

export interface SeriesStats {
  n: number;
  first: string;
  last: string;
  min: number;
  max: number;
  mean: number;
  latest: number;
}

export function fmtNumber(n: number | null | undefined, digits = 4): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "n/a";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "n/a";
  if (Math.abs(n) > 999) return `${n >= 0 ? "+" : ""}${(n / 1000).toFixed(1)}k%`;
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}
