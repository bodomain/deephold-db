// SeriesDetail: right pane with header (stats) + tail table for the selected series.

import { useEffect, useState } from "react";

import { getEquityStats, getEquityTail, getMacroStats, getMacroTail } from "../data/queries";
import type {
  MacroObservation,
  PriceObservation,
  SeriesRow,
  SeriesStats,
} from "../types";
import { fmtNumber } from "../types";

interface Props {
  series: SeriesRow;
}

function fmtDate(s: string): string {
  return s; // already YYYY-MM-DD
}

function fmtClose(n: number | null): string {
  if (n === null || Number.isNaN(n)) return "n/a";
  return n.toFixed(4);
}

function fmtVol(n: number | null): string {
  if (n === null || Number.isNaN(n)) return "n/a";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return n.toString();
}

interface DetailState {
  stats: SeriesStats | null;
  tail: (MacroObservation | PriceObservation)[];
  loading: boolean;
  error: string | null;
}

const EMPTY: DetailState = { stats: null, tail: [], loading: true, error: null };

export function SeriesDetail({ series }: Props) {
  const [state, setState] = useState<DetailState>(EMPTY);

  useEffect(() => {
    let cancelled = false;
    setState({ ...EMPTY, loading: true });

    (async () => {
      try {
        if (series.kind === "macro") {
          const [stats, tail] = await Promise.all([
            getMacroStats(series.id),
            getMacroTail(series.id, 30),
          ]);
          if (!cancelled) {
            setState({ stats, tail, loading: false, error: null });
          }
        } else {
          // For equity, `series.id` is the YAHOO symbol (e.g. "AAPL").
          const [stats, tail] = await Promise.all([
            getEquityStats(series.id),
            getEquityTail(series.id, 30),
          ]);
          if (!cancelled) {
            setState({ stats, tail, loading: false, error: null });
          }
        }
      } catch (e) {
        if (!cancelled) {
          setState({
            stats: null,
            tail: [],
            loading: false,
            error: e instanceof Error ? e.message : String(e),
          });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [series.kind, series.id]);

  const title = `${series.id}  —  ${series.name.slice(0, 40)}`;

  return (
    <box
      title={title}
      titleAlignment="left"
      borderStyle="rounded"
      borderColor="#7aa2f7"
      flexGrow={1}
      height="100%"
      flexDirection="column"
      paddingLeft={1}
      paddingRight={1}
      paddingTop={0}
    >
      {state.loading && <text fg="#565f89">Loading detail...</text>}
      {state.error && <text fg="#f7768e">Error: {state.error}</text>}
      {!state.loading && !state.error && (
        <>
          <StatsPanel series={series} stats={state.stats} />
          <text> </text>
          <TailTable kind={series.kind} tail={state.tail} />
        </>
      )}
    </box>
  );
}

function StatsPanel({ series, stats }: { series: SeriesRow; stats: SeriesStats | null }) {
  if (!stats) {
    return <text fg="#565f89">No data for this series.</text>;
  }
  return (
    <box flexDirection="column" gap={0}>
      <box flexDirection="row" gap={2}>
        <Stat label="rows" value={stats.n.toLocaleString()} />
        <Stat label="first" value={fmtDate(stats.first)} />
        <Stat label="last" value={fmtDate(stats.last)} />
        <Stat label="unit" value={series.unit} />
      </box>
      <box flexDirection="row" gap={2}>
        <Stat label="min" value={fmtNumber(stats.min)} />
        <Stat label="max" value={fmtNumber(stats.max)} />
        <Stat label="mean" value={fmtNumber(stats.mean)} />
        <Stat label="source" value={series.source} />
      </box>
    </box>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <box flexDirection="column">
      <text fg="#565f89">{label}</text>
      <text fg="#c0caf5">{value}</text>
    </box>
  );
}

function TailTable({
  kind,
  tail,
}: {
  kind: "macro" | "equity";
  tail: (MacroObservation | PriceObservation)[];
}) {
  if (tail.length === 0) {
    return <text fg="#565f89">(no rows)</text>;
  }
  return (
    <box flexDirection="column">
      {kind === "macro" ? (
        <MacroTailTable tail={tail as MacroObservation[]} />
      ) : (
        <EquityTailTable tail={tail as PriceObservation[]} />
      )}
    </box>
  );
}

function MacroTailTable({ tail }: { tail: MacroObservation[] }) {
  return (
    <>
      <text fg="#565f89">
        {padR("date", 10)}value
      </text>
      {tail.map((row) => (
        <box key={row.date} flexDirection="row" gap={2}>
          <text fg="#9aa5ce">{padR(row.date, 10)}</text>
          <text fg="#c0caf5">{fmtNumber(row.value, 4)}</text>
        </box>
      ))}
    </>
  );
}

function EquityTailTable({ tail }: { tail: PriceObservation[] }) {
  return (
    <>
      <text fg="#565f89">
        {padR("date", 10)}{padR("close", 9)}{padR("adj", 9)}vol
      </text>
      {tail.map((row) => (
        <box key={row.date} flexDirection="row" gap={1}>
          <text fg="#9aa5ce">{padR(row.date, 10)}</text>
          <text fg="#c0caf5">{padR(fmtClose(row.close), 9)}</text>
          <text fg="#9aa5ce">{padR(fmtClose(row.adjusted_close), 9)}</text>
          <text fg="#565f89">{fmtVol(row.volume)}</text>
        </box>
      ))}
    </>
  );
}

function padR(s: string, n: number): string {
  return s.length >= n ? s.slice(0, n) : s + " ".repeat(n - s.length);
}
