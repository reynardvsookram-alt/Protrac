# Dashboard v3 — "card" layout (approved try-out, not wired in yet)

The owner reviewed this layout as a separate try-out and wants it in the app. These files are the
try-out code, saved so it isn't lost. They are **not** loaded by `index.html` yet.

- `dashboard.js` — a drop-in replacement for `function renderDashboard(c){…}` in `index.html`, plus its helpers
  (`DI` icon set, `ic()`, `firstName()`). It uses existing app functions only (`jobState`, `jobValue`, `jobCosting`,
  `mv`, `hideVals`, `dashFilter`, `phaseGo`, `qcSummary`, `allLines`, `jobLabel`, `currentStep`, `jobPct`, …).
- `dashboard.css` — append inside the main `<style>` block.
- `tryout-desktop.png`, `tryout-phone.png` — what the try-out looked like (demo data).

Sections, top to bottom: greeting + New project + date · Attention required · Financial overview (donut) ·
Project pipeline · Upcoming deadlines (overdue + 14 days) · At-risk projects · My actions (reminders) ·
Quick stats · Recent projects table. Every card / row opens the matching page or filtered list.

The try-out also forced dark mode as the default theme — **don't** carry that into the app.

See `HANDOFF.md` for the agreed fixes to make while porting it.
