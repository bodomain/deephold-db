// Quick DB-connectivity test. Not part of the running app.
//   bun run scripts/check-db.ts
import { listSeries, getMacroTail, getEquityTail } from "../src/data/queries";
import { closePool } from "../src/data/db";

const rows = await listSeries();
console.log(`OK: ${rows.length} series in DB`);

for (const r of rows.slice(0, 3)) {
  console.log(`  ${r.kind.padEnd(6)} ${r.id.padEnd(28)} ${r.source.padEnd(6)} ${r.n} rows`);
}

// Exercise one macro and one equity tail query.
const macro = rows.find((r) => r.kind === "macro");
if (macro) {
  const tail = await getMacroTail(macro.id, 3);
  console.log(`macro tail (${macro.id}):`, tail);
}

const equity = rows.find((r) => r.kind === "equity");
if (equity) {
  const tail = await getEquityTail(equity.id, 3);
  console.log(`equity tail (${equity.id}):`, tail);
}

await closePool();
