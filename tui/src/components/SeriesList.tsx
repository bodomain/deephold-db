// SeriesList: left pane with all series (macro + equity).
// Receives a flat list of SeriesRow, highlights the selected one.

import type { SeriesRow } from "../types";

interface Props {
  series: SeriesRow[];
  selectedIndex: number;
  loading: boolean;
}

const KIND_BADGE: Record<string, string> = {
  macro: "M",
  equity: "E",
};

const KIND_COLOR: Record<string, string> = {
  macro: "#7aa2f7",
  equity: "#9ece6a",
};

const SOURCE_COLOR: Record<string, string> = {
  fred: "#7dcfff",
  ecb: "#bb9af7",
  yahoo: "#f7768e",
  demo: "#565f89",
};

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "\u2026";
}

function rightPad(s: string, n: number): string {
  return s.length >= n ? s.slice(0, n) : s + " ".repeat(n - s.length);
}

function leftPad(s: string, n: number): string {
  return s.length >= n ? s.slice(s.length - n) : " ".repeat(n - s.length) + s;
}

export function SeriesList({ series, selectedIndex, loading }: Props) {
  if (loading) {
    return (
      <box
        title="Series"
        borderStyle="single"
        borderColor="#565f89"
        width={36}
        height="100%"
        flexDirection="column"
        paddingLeft={1}
        paddingRight={1}
      >
        <text fg="#565f89">Loading...</text>
      </box>
    );
  }

  if (series.length === 0) {
    return (
      <box
        title="Series"
        borderStyle="single"
        borderColor="#565f89"
        width={36}
        height="100%"
        flexDirection="column"
        paddingLeft={1}
      >
        <text fg="#f7768e">No series in DB.</text>
        <text fg="#565f89">Run scripts/query_db.py first.</text>
      </box>
    );
  }

  return (
    <box
      title={`Series (${series.length})`}
      borderStyle="single"
      borderColor="#565f89"
      width={36}
      height="100%"
      flexDirection="column"
      paddingLeft={1}
      paddingRight={1}
    >
      {series.map((s, i) => {
        const isSel = i === selectedIndex;
        const marker = isSel ? "\u25b8 " : "  ";
        const badge = KIND_BADGE[s.kind] ?? "?";
        const badgeColor = KIND_COLOR[s.kind] ?? "#c0caf5";
        const srcColor = SOURCE_COLOR[s.source] ?? "#c0caf5";
        const id = truncate(s.id, 18);
        const n = leftPad(s.n.toLocaleString(), 5);
        return (
          <text key={`${s.kind}:${s.id}`}>
            <span fg={isSel ? "#e0af68" : "#565f89"}>{marker}</span>
            <span fg={badgeColor}>{badge} </span>
            <span fg={isSel ? "#c0caf5" : "#9aa5ce"}>{rightPad(id, 18)} </span>
            <span fg={srcColor}>{rightPad(s.source, 5)} </span>
            <span fg="#565f89">{n}</span>
          </text>
        );
      })}
    </box>
  );
}
