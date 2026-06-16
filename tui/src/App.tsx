// App: root component.
//
// Two-pane layout:
//   - left:  SeriesList (scrollable list of all series)
//   - right: SeriesDetail (header stats + tail table for selected series)
//
// State: selectedIndex, series list, refreshToken.
// Keyboard: ↑/↓ to navigate, q/Ctrl-C to quit, r to reload.

import { useEffect, useState } from "react";
import { useKeyboard, useRenderer } from "@opentui/react";

import { listSeries } from "./data/queries";
import type { SeriesRow } from "./types";
import { SeriesList } from "./components/SeriesList";
import { SeriesDetail } from "./components/SeriesDetail";

export function App() {
  const renderer = useRenderer();
  const [series, setSeries] = useState<SeriesRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [refreshToken, setRefreshToken] = useState<number>(0);

  // Load series list whenever refreshToken changes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listSeries()
      .then((rows) => {
        if (cancelled) return;
        setSeries(rows);
        setLoading(false);
        // Keep selection in bounds.
        setSelectedIndex((idx) => (idx >= rows.length ? Math.max(0, rows.length - 1) : idx));
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  useKeyboard((key) => {
    if (key.name === "q" || (key.ctrl && key.name === "c")) {
      // Tear down the TUI, then exit. The pg pool's exit-handler closes
      // the connection so the process can terminate cleanly.
      renderer.destroy();
      setTimeout(() => process.exit(0), 50);
      return;
    }
    if (key.name === "r") {
      setRefreshToken((t) => t + 1);
      return;
    }
    if (key.name === "up" || key.name === "k") {
      setSelectedIndex((i) => Math.max(0, i - 1));
      return;
    }
    if (key.name === "down" || key.name === "j") {
      setSelectedIndex((i) => Math.min(Math.max(0, series.length - 1), i + 1));
      return;
    }
    if (key.name === "home" || key.name === "g") {
      setSelectedIndex(0);
      return;
    }
    if (key.name === "end" || key.name === "G") {
      setSelectedIndex(Math.max(0, series.length - 1));
      return;
    }
  });

  const selected = series[selectedIndex];

  return (
    <box
      flexDirection="column"
      width="100%"
      height="100%"
      backgroundColor="#1a1b26"
      paddingLeft={1}
      paddingRight={1}
      paddingTop={1}
      paddingBottom={1}
    >
      <Header error={error} loading={loading} count={series.length} />
      <box flexDirection="row" gap={1} flexGrow={1}>
        <SeriesList series={series} selectedIndex={selectedIndex} loading={loading} />
        {selected ? (
          <SeriesDetail series={selected} />
        ) : (
          <box
            title="Detail"
            borderStyle="rounded"
            borderColor="#565f89"
            flexGrow={1}
            height="100%"
            paddingLeft={1}
            paddingRight={1}
          >
            <text fg="#565f89">
              {loading ? "Loading..." : error ? `Error: ${error}` : "No series selected."}
            </text>
          </box>
        )}
      </box>
      <Footer />
    </box>
  );
}

function Header({
  error,
  loading,
  count,
}: {
  error: string | null;
  loading: boolean;
  count: number;
}) {
  return (
    <box
      flexDirection="row"
      gap={2}
      borderStyle="single"
      borderColor="#7aa2f7"
      paddingLeft={1}
      paddingRight={1}
    >
      <text>
        <span fg="#bb9af7" attributes={1}>
          finance_data
        </span>
        <span fg="#565f89">  —  TUI Explorer  </span>
        <span fg="#7dcfff">
          {loading ? "loading..." : error ? `error: ${error}` : `${count} series`}
        </span>
      </text>
    </box>
  );
}

function Footer() {
  return (
    <box
      flexDirection="row"
      gap={3}
      borderStyle="single"
      borderColor="#565f89"
      paddingLeft={1}
      paddingRight={1}
    >
      <text>
        <span fg="#7aa2f7">{"\u2191/\u2193"}</span>
        <span fg="#565f89"> navigate  </span>
        <span fg="#7aa2f7">r</span>
        <span fg="#565f89"> refresh  </span>
        <span fg="#7aa2f7">g/G</span>
        <span fg="#565f89"> top/end  </span>
        <span fg="#7aa2f7">q</span>
        <span fg="#565f89"> quit</span>
      </text>
    </box>
  );
}
