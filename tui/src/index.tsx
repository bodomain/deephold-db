// Entry point: boot the CliRenderer, mount <App />, and clean up the pg pool on exit.

import { createCliRenderer } from "@opentui/core";
import { createRoot } from "@opentui/react";

import { App } from "./App";
import { closePool } from "./data/db";

const renderer = await createCliRenderer({
  exitOnCtrlC: true,
  // default background; OpenTUI picks a sensible terminal mode automatically
});

const root = createRoot(renderer);
root.render(<App />);

// Best-effort cleanup. The pg pool would otherwise keep the process alive
// after the renderer exits on `q` / Ctrl-C.
process.on("exit", () => {
  void closePool().catch(() => {});
});
process.on("SIGTERM", () => {
  void closePool().finally(() => process.exit(0));
});
