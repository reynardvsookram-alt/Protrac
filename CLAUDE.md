# Protrac — project brief for Claude Code

Protrac is a fabrication job tracker built by and for a mechanical engineer running jobs in a steel fabrication shop in Trinidad & Tobago. It follows a job from the client's RFQ through quote, PO, purchasing, production, QC and delivery. It's his daily workspace and his portfolio piece, so **usefulness beats decoration**: every feature has to help him act on a real job.

## The owner — how to work with him
- He communicates casually, but wants **polished, professional output**, **direct answers and honest pushback**, and **step-by-step explanations**.
- He has **no laptop**. He works from a phone and a Windows desktop, and deploys through **GitHub Pages from `main`**. A cloud session pushes a branch, and the live site only updates after he merges it. Tell him that at the end of each task, with the PR link.
- He writes change requests as numbered items (C1, C2…), often with screenshots. Ask before building when a choice is genuinely his, e.g. layout options or what a field should mean. Otherwise just build.

## Hard rules
1. **Single self-contained file**: `index.html` is the whole app (HTML + CSS + vanilla JS). No frameworks, no build step, **no CDNs or network calls**. It must run offline by double-clicking. Fonts (IBM Plex Sans/Mono) are embedded as base64 woff2.
2. **No confidential or personal data in this public repo.** Never commit real client names, real supplier or company names, people's names, backups (`*.json` exports) or price workbooks. The demo uses anonymised clients ("Client A — Oilfield Services"). The steel price book (`DEMO_PRICES`) holds **real quotes under the anonymous names "Supplier A" and "Supplier B"**: keep the prices, never the real names.
3. **An earlier tracker (iteration 1) existed at a previous employer. It is private history.** Don't show, name or reference it in the UI, README, demo or commit messages.
4. **Never break saved data.** Users' data lives in `localStorage` (`protrac_v1`). Every schema change needs an **idempotent** migration in `migrate()` (`migrateProtrac`, `migrateV2`, `migrateV5` …) and a test proving old data still loads.
5. No `alert/confirm/prompt`: they're blocked in hosted viewers. Use the in-app dialogs `uiAsk`, `uiConfirm`, `openModal`.
6. Everything works at **phone width (390 px)** with no horizontal page scroll. Wide tables scroll inside `.tablewrap`.
7. Wrap `localStorage` access in try/catch.

## Current goal (agreed with the owner)
The program will be shown to a software engineering team as a polished, real tool. Work in **two phases, in this order**, and confirm the phase-1 plan with him before building.

**Phase 1: finalise the workflow.**
- Seamless from RFQ to delivery.
- **No feature that doesn't make sense** for a fabrication job.
- **Nothing that adds time to entering a job.**

Start by auditing every page, form and button against "does this help him act on a job, and could it take fewer taps or fields?" Then propose a list to remove, merge, default or automate, for example:
- smarter defaults;
- fields filled from what's already known;
- duplicate controls (e.g. the progress bar shown twice on the job page);
- legacy remnants (the hidden old Status field, the old-tracker import key `sonriz_pm_v2` and its tests).

Keep every removal behind a migration so saved data survives.

**Phase 2: aesthetics, after phase 1 is signed off.**
- A professional facelift to a modern software-engineering standard.
- Replace the emoji icons with one consistent icon set, inlined as SVG (still offline).
- Purposeful press/toggle micro-animations.
- A refined type scale and spacing, and a cohesive light and dark theme.

Show him before/after screenshots, desktop and phone, for sign-off.

## Build / test loop (run before every push)
```bash
# syntax gate
python3 -c "h=open('index.html').read();open('/tmp/app.js','w').write(h[h.find('<script>')+8:h.rfind('</script>')])" && node --check /tmp/app.js
node tests/node_harness.js            # ~148 checks: migration, working days, phase clocks, holds, filters
python3 tests/browser_core.py         # Playwright: Excel/xlsx import, price-book import, QC, RFQ, phone layout
python3 tests/browser_purchasing.py   # purchasing flow end to end (desktop + phone)
python3 tests/browser_v4.py           # search placement, categories, RFQ email table, material table editor
python3 tests/browser_v5.py           # templates/auto timeline, suppliers, settings tabs, sidebar, fonts, demo shift
python3 tests/sweep.py                # clicks every control on every page/tab (~2,400) — slow (~15 min); PHONE=1 for the phone-only layout pass
grep -nE 'fetch\(|XMLHttpRequest|cdnjs|googleapis|jsdelivr|unpkg|<link |<script src' index.html   # must print nothing
```
Playwright and Chromium are needed (`pip install playwright && playwright install chromium` if missing). Fixtures are in `tests/fixtures/`, all anonymised. Screenshots go to `tests/out/` (git-ignored). Update tests when the demo data changes; don't weaken a test to make it pass. Look at real screenshots of anything visual before saying it's done.

## Architecture
`DB = { jobs, tasks, procurement, materials, suppliers, checklists, priceItems, priceQuotes, meta }` persisted by `save()`, which also runs `syncAllSchedules()` and invalidates the price index.

### Job lifecycle and deadlines (core idea)
Each phase owns its own clock: **overdue = today is past the active phase's due date, the job isn't on hold, and the phase isn't closed.**

| Phase (`PH.*`) | Due date | Closes when |
|---|---|---|
| RFQ Received | `rfqDueDate`, or `rfqDate` + `rfqDays` working days | quote submitted to manager |
| Quoted – Awaiting PO | **none, never overdue**; after `followUpDate` it flags "chase client" | PO received / lost |
| PO Received → Procurement → In Production | `dueOverride`, or `poDate` + **max** lead time in working days (min = target) | delivered |
| Delivered / Lost | clock stopped | — |

- **Working days** skip weekends and `meta.holidays` (`ttHolidays(year)`: T&T fixed holidays, Easter-based ones, Sunday→Monday observed). Eid and Divali are added by hand each year.
- **Holds** pause the clock and extend the due date by the working days held. Holds are per clock group (`rfq` / `quote` / `exec`).
- Key functions: `addWorkingDays, workDaysBetween, jobState, jobDueMeta, setPhase, changePhase, openPhaseAction/savePhase, toggleHold`.

### Job templates and the auto timeline (Schedule tab)
- **Job types**: `JOB_TYPES` (Design & build, Build to client drawing, Repair / blast & paint) pre-tick `optSite, optConcept, optFab, optCoat, optAssembly`.
- **Template steps**: `meta.wfSteps` (default `WF_DEFAULT`, editable in Settings → Job templates), each `{key,name,sec,days,when,auto}`. Sections (`WF_SECTIONS`) become parent tasks with `stepKey "sec:x"`; steps are child tasks.
- **Planning**: `planSteps` sets working-day dates. The quote side runs from the RFQ date (squeezed to the client's deadline); the rest runs from the PO date (scaled to the lead time).
- **Building**: `buildSchedule(j, keep)` creates or merges a schedule. Rebuilding keeps ticked dates and hand-edited dates (`manualDates`).
- **Auto ticks**: `stepEvent` covers rfq, suprfq, quoted, po, order, received, fab/qcweld, blast, coat/qcpaint, final and delivered, using QC Pass/N/A (Fail sets `failed`). `syncSchedule` marks earlier human steps as **inferred** (≈). `tickStep` ticks a human step today and logs an Update.
- **Rendering**: `renderWorkflow` shows the "Timeline so far" strip, Step / Planned / Actual rows and the Gantt (`ganttSVG`).

### Purchasing (materials → RFQ → quotes → order → receive)
- **Material lines**: `DB.materials`, with stages from `matStage` (toorder / waiting / ordered / received).
- **Page**: `renderPurchasing` has four clickable stage cards.
- **RFQs**: `openRfqFromMaterials` creates the RFQ. Per-item supplier quotes go through `openQuote`/`saveQuote2` and are logged to the price book. Then `openCompare`/`saveCompare` picks the cheapest and orders it.
- **Delivery**: `receiveMats`, with MTR tracking.
- **RFQ email**: `showRfqText` with `copyRich`, which copies an HTML table plus a plain-text fallback.
- **Material entry**: the spreadsheet-style table editor (`startGrid`/`gridSave`), paste from Excel, or `.xlsx` import (`openImport` with the built-in `readXlsx`: unzip, `DecompressionStream`, DOMParser).

### Price book and suppliers
- **Data**: `DB.priceItems` and `DB.priceQuotes` (`supplier` is the supplier's name).
- **Lookups**: `latestBySupplier`, `bestPrice`, size-aware search (`normText`, `scoreItem`, index in `pbIndex`/WeakMap `pbT`), and `autoPriceMaterials`, which links only confident matches.
- **Import**: `importPriceWorkbook` reads a workbook with "Price Book" + "Quote Log" sheets.
- **Suppliers page**: `renderSuppliers` shows cards; `renderSupplier` is the profile, showing what they sell, stats (`supStats`) and RFQ history. Supplier `rating` is Preferred / Approved / Backup / Avoid.

### QC
`job.qc[weld|blast|paint|final] = {s,date,by,note}`, one tap Pass/Fail/N/A. Optional item checks live in `DB.checklists` (with `stage`). There is also a QC register page.

### UI shell
- **Navigation**: `buildNav`, `go`, `render` (PAGES map), `renderDetail` (job page; tabs Overview · Updates · Schedule · Procurement · Materials · QC).
- **Layout**: collapsible sidebar (`toggleSide`). Settings is split into tabs (`setTab`).
- **Search**: `listSearch()` sits below the filters on list pages.
- **Motion**: `pageAnim()` page transition, with `prefers-reduced-motion` respected.

### Demo data
- **Building**: `seed()` + `seedSchedules()` create 11 anonymised jobs on working-day offsets from today (`wdOff`).
- **Staying current**: while `meta.isDemo` is set, `keepDemoCurrent()` shifts every date by the working days since `meta.demoAnchor`, so the demo is never stale. "Start empty" clears the flag.
- **Prices**: the demo price book (`DEMO_PRICES`) is real steel quotes under "Supplier A" / "Supplier B". The other demo suppliers and their items are illustrative.

## Roadmap / ideas (confirm priority with the owner first)
- Stock-length nesting (cut list → lengths/sheets) so material totals use real stock quantities.
- Quotation builder (labour by trade, materials from the price book, coatings, margin) feeding the "Prepare quotation" step.
- Win-rate and turnaround stats across jobs (data already in `phaseLog` and dates).
- Downloads in the claude.ai-hosted copy (needs that platform's downloads capability); they already work on GitHub Pages.
- Parked: engineering calculator / unit converter (he has a separate fab-shop tool).
