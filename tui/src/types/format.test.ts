// Unit tests for pure helpers in src/types.ts (number formatting, padding).
// Run with: bun test src/types/format.test.ts

import { describe, expect, it } from "bun:test";

import { fmtNumber, fmtPct } from "../types";

describe("fmtNumber", () => {
  it("returns 'n/a' for null / undefined / NaN", () => {
    expect(fmtNumber(null)).toBe("n/a");
    expect(fmtNumber(undefined)).toBe("n/a");
    expect(fmtNumber(Number.NaN)).toBe("n/a");
  });

  it("formats numbers with default 4 digits", () => {
    expect(fmtNumber(3.14159)).toBe("3.1416");
  });

  it("respects custom digits", () => {
    expect(fmtNumber(3.14159, 2)).toBe("3.14");
    expect(fmtNumber(0.0001, 4)).toBe("0.0001");
  });

  it("uses thousands separator", () => {
    expect(fmtNumber(1234567.89)).toBe("1,234,567.89");
  });

  it("handles negative numbers", () => {
    expect(fmtNumber(-2.5)).toBe("-2.5");
  });
});

describe("fmtPct", () => {
  it("returns 'n/a' for null / undefined / NaN", () => {
    expect(fmtPct(null)).toBe("n/a");
    expect(fmtPct(undefined)).toBe("n/a");
    expect(fmtPct(Number.NaN)).toBe("n/a");
  });

  it("formats small percentages with sign and 2 digits", () => {
    expect(fmtPct(2.5)).toBe("+2.50%");
    expect(fmtPct(-1.234)).toBe("-1.23%");
  });

  it("clamps large percentages > 999% as k%", () => {
    expect(fmtPct(1234)).toBe("+1.2k%");
    expect(fmtPct(9350)).toBe("+9.3k%");
    expect(fmtPct(-2500)).toBe("-2.5k%");
  });
});
