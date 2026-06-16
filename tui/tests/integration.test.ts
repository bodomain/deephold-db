// Integration tests against a real Postgres.
// Run with: bun test tests/integration.test.ts
//
// Requires `docker compose up -d postgres` and at least one seeded series.
// Tests silently pass (no-op) if the DB is unreachable so the suite
// stays green in environments without Postgres.

import { afterAll, beforeAll, describe, expect, it } from "bun:test";

import { closePool, query } from "../src/data/db";
import {
  getEquityStats,
  getEquityTail,
  getMacroStats,
  getMacroTail,
  listSeries,
} from "../src/data/queries";

let dbReachable = false;

beforeAll(async () => {
  try {
    await query("SELECT 1::int AS x");
    dbReachable = true;
  } catch (e) {
    console.warn(
      `[integration] Postgres unreachable, tests will no-op. Reason: ${
        e instanceof Error ? e.message : String(e)
      }`,
    );
  }
});

afterAll(async () => {
  if (dbReachable) {
    try {
      await closePool();
    } catch {
      // ignore
    }
  }
});

function guarded(name: string, fn: () => Promise<void>): () => Promise<void> {
  return async () => {
    if (!dbReachable) {
      console.warn(`[integration] skip ${name}: DB unreachable`);
      return;
    }
    await fn();
  };
}

describe("integration: listSeries", () => {
  it(
    "returns 12 series (5 macro-FRED + 4 macro-ECB + 3 equity)",
    guarded("listSeries.count", async () => {
      const rows = await listSeries();
      expect(rows.length).toBeGreaterThanOrEqual(12);
      const macro = rows.filter((r) => r.kind === "macro");
      const equity = rows.filter((r) => r.kind === "equity");
      expect(macro.length).toBeGreaterThanOrEqual(9);
      expect(equity.length).toBeGreaterThanOrEqual(3);
    }),
  );

  it(
    "macro rows carry the series_id and a 'source' of fred/ecb/demo",
    guarded("listSeries.macro", async () => {
      const rows = await listSeries();
      const macro = rows.filter((r) => r.kind === "macro");
      for (const m of macro) {
        expect(m.id).toMatch(/^(FRED|ECB|DEMO):/);
        expect(["fred", "ecb", "demo"]).toContain(m.source);
      }
    }),
  );

  it(
    "equity rows carry the YAHOO ticker (AAPL/MSFT/^GSPC) — not instrument_id",
    guarded("listSeries.equity", async () => {
      const rows = await listSeries();
      const tickers = rows
        .filter((r) => r.kind === "equity")
        .map((r) => r.id)
        .sort();
      expect(tickers).toEqual(["AAPL", "MSFT", "^GSPC"]);
    }),
  );
});

describe("integration: getMacroTail", () => {
  it(
    "FRED:DGS3MO returns 30 daily rows, most-recent first",
    guarded("getMacroTail", async () => {
      const tail = await getMacroTail("FRED:DGS3MO", 30);
      expect(tail.length).toBe(30);
      expect(tail[0]?.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      for (let i = 1; i < tail.length; i++) {
        const prev = tail[i - 1]!;
        const cur = tail[i]!;
        expect(prev.date >= cur.date).toBe(true);
      }
    }),
  );
});

describe("integration: getMacroStats", () => {
  it(
    "FRED:DGS3MO stats: n, min, max, mean are reasonable",
    guarded("getMacroStats", async () => {
      const s = await getMacroStats("FRED:DGS3MO");
      expect(s).not.toBeNull();
      expect(s!.n).toBeGreaterThan(0);
      expect(s!.min).toBeGreaterThanOrEqual(0);
      expect(s!.max).toBeLessThan(20);
      expect(s!.mean).toBeGreaterThan(0);
    }),
  );
});

describe("integration: getEquityTail", () => {
  it(
    "AAPL tail has 30 rows with valid OHLCV",
    guarded("getEquityTail", async () => {
      const tail = await getEquityTail("AAPL", 30);
      expect(tail.length).toBe(30);
      for (const row of tail) {
        expect(row.close).toBeGreaterThan(0);
        expect(row.adjusted_close).not.toBeNull();
        expect(row.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      }
    }),
  );
});

describe("integration: getEquityStats", () => {
  it(
    "AAPL stats: positive close, sensible min < max",
    guarded("getEquityStats", async () => {
      const s = await getEquityStats("AAPL");
      expect(s).not.toBeNull();
      expect(s!.n).toBeGreaterThan(100);
      expect(s!.min).toBeGreaterThan(0);
      expect(s!.min).toBeLessThan(s!.max);
    }),
  );
});
