# Protrac — project brief for Claude Code

Protrac is a fabrication job tracker built by and for a mechanical engineer running jobs in a steel fabrication shop in Trinidad & Tobago. It follows a job from the client's RFQ through quote, PO, purchasing, production, QC and delivery. It's his daily workspace and his portfolio piece, so **usefulness beats decoration**: every feature has to help him act on a real job.

## The owner — how to work with him
- He communicates casually, but wants **polished, professional output**, **direct answers and honest pushback**, and **step-by-step explanations**.
- He has **no laptop**. He works from a phone and a Windows desktop, and deploys through **GitHub Pages from `main`**. A cloud session pushes a branch, and the live site only updates after he merges it. Tell him that at the end of each task, with the PR link.
- He writes change requests as numbered items (C1, C2…), often with screenshots. Ask before building when a choice is genuinely his, e.g. layout options or what a field should mean. Otherwise just build.

## Hard rules
1. **Single self-contained file**: `index.html` is the whole app (HTML + CSS + vanilla JS). No frameworks, no build step, **no CDNs or network calls**. It must run offline by double-clicking. Fonts (IBM Plex Sans/Mono) are embedded as base64 woff2.
2. **No confidential or personal data in this public repo.** Never commit real client names, real supplier or company names, other people's names, backups (`*.json` exports) or price workbooks. The demo uses anonymised clients ("Client A — Oilfield Services"). The steel price book (`DEMO_PRICES`) holds **real quotes under the anonymous names "Supplier A" and "Supplier B"**: keep the prices, never the real names. **Exception: the owner's own name is allowed** ("R. Sookram" as the demo QC sign-off, "Reynard Sookram, Mechanical Engineer" as the demo RFQ email sign-off) — it's his portfolio piece, so keep it.
3. **An earlier tracker (iteration 1) existed at a previous employer. It is private history.** Don't show, name or reference it in the UI, README, demo or commit messages.
4. **Never break saved data.** Users' data lives in `localStorage` (`protrac_v1`). Every schema change needs an **idempotent** migration in `migrate()` (`migrateProtrac`, `migrateV2`, `migrateV5`, `migrateV6` …) and a test proving old data still loads. Removed fields stay on the record unless there's a reason to delete them (e.g. `job.stage` and `job.percent` are kept but no longer shown).
5. No `alert/confirm/prompt`: they're blocked in hosted viewers. Use the in-app dialogs `uiAsk`, `uiConfirm`, `openModal`.
6. Everything works at **phone width (390 px)** with no horizontal page scroll. Wide tables scroll inside `.tablewrap`.
7. Wrap `localStorage` access in try/catch.

## Current goal (agreed with the owner)
The program will be shown to a software engineering team as a polished, real tool. Work in **two phases, in this order**, and confirm the phase-1 plan with him before building.

**Phase 1: finalise the workflow — built, awaiting his sign-off.**
Seamless RFQ → delivery, no feature that doesn't make sense for a fabrication job, nothing that adds time to entering a job. What was agreed and built:
- **New-job form** = 5 fields (name, client, job-type buttons, RFQ received = today, client deadline with 3/5/10 wd chips, default `meta.quoteDays` = 5). Everything else under a collapsed "More", incl. "Already past RFQ? Start at phase…". Edit form = the same plus sections only for phases reached.
- **Removed** (data kept on records): job Stage (→ "Current step" from the schedule), manual % (→ share of schedule steps done), duplicate progress bar / fact cards / counters / phase dropdowns, the old Status and Stage settings lists, the old-tracker storage key and its tests, dead pages and functions.
- **Merged**: job tabs → Overview (with updates) · Schedule · Materials (with supplier RFQs) · QC; "Workflow options" is its own small dialog.
- **Defaults**: running job number `001…` (D1), priority Medium, lead time asked at "Quote submitted" and pre-filled at PO, QC stages outside the job's scope auto N/A.
- **Automated**: schedule re-plans when PO / lead time / deadline / holds change and rebuilds when workflow options change; all materials fully received → In Production with an Undo toast; final QC pass → "Mark delivered" button.
- **Undo / Redo** on phase changes (job page), **Board** rework, **thin auto-hiding scrollbars** app-wide.
Keep every removal behind a migration so saved data survives.

**Phase 2: aesthetics, after phase 1 is signed off.**
- A professional facelift to a modern software-engineering standard. **Design direction (his choice): the "FlowDeck" kanban reference** — dark, glassy rounded lanes, pill counts, small priority pills, quiet meta text, "+ Add" at the foot of a lane. Apply that look app-wide.
- Replace the emoji icons with one consistent icon set, inlined as SVG (still offline).
- Purposeful press/toggle micro-animations.
- A refined type scale and spacing, and a cohesive light and dark theme.

Show him before/after screenshots, desktop and phone, for sign-off.

## Build / test loop (run before every push)
```bash
# syntax gate
python3 -c "h=open('index.html').read();open('/tmp/app.js','w').write(h[h.find('<script>')+8:h.rfind('</script>')])" && node --check /tmp/app.js
node tests/node_harness.js            # ~183 checks: migration, working days, phase clocks, holds, filters, undo/redo, auto production
python3 tests/browser_core.py         # Playwright: Excel/xlsx import, price-book import, QC, RFQ, phone layout
python3 tests/browser_purchasing.py   # purchasing flow end to end (desktop + phone)
python3 tests/browser_v4.py           # search placement, categories, RFQ email table, material table editor
python3 tests/browser_v5.py           # templates/auto timeline, suppliers, settings tabs, sidebar, fonts, demo shift
python3 tests/browser_v6.py           # phase 1: new-job form, job page, undo/redo, automation, board (mouse + touch drag), scrollbars, phone
python3 tests/browser_v7.py           # value & costing: xlsx import + paste, quote → re-quote → PO values, margin warning, dashboard, hide values, phone
node tests/shots_phase1.js after      # before/after screenshots into docs/phase1/ (desktop + phone)
python3 tests/sweep.py                # clicks every control on every page/tab (~2,400) — slow (~15 min); PHONE=1 for the phone-only layout pass
grep -nE 'fetch\(|XMLHttpRequest|cdnjs|googleapis|jsdelivr|unpkg|<link |<script src' index.html   # must print nothing
```
Playwright and Chromium are needed (`pip install playwright && playwright install chromium` if missing; in a cloud session Chromium is pre-installed — `pip install playwright==<node playwright version>` and set `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`). Fixtures are in `tests/fixtures/`, all anonymised. Screenshots go to `tests/out/` (git-ignored). Update tests when the demo data changes; don't weaken a test to make it pass. Look at real screenshots of anything visual before saying it's done.

## Wording
- **The UI says "Project", never "Job"** (his request): nav "Projects", "Add Project", "Project no.", "Back to Projects"… The code, data keys and storage keep `job` (`DB.jobs`, `jobRef`, `openJob`, `go('jobs')`) so saved data and tests don't change. New UI text must say "project".
- App subtitle: "FabShop Project tracker".

## Architecture
`DB = { jobs, tasks, procurement, materials, suppliers, checklists, priceItems, priceQuotes, meta }` persisted by `save()`, which also runs `syncAllSchedules()` and invalidates the price index.

### Job lifecycle and deadlines (core idea)
Each phase owns its own clock: **overdue = today is past the active phase's due date, the job isn't on hold, and the phase isn't closed.**

| Phase (`PH.*`) | Due date | Closes when |
|---|---|---|
| RFQ Received | `rfqDueDate` (old data may still use `rfqDate` + `rfqDays`; the edit form converts it to a date) | quote submitted to manager |
| Quoted – Awaiting PO | **none, never overdue**; after `followUpDate` it flags "chase client" | PO received / lost |
| PO Received → Procurement → In Production | `dueOverride`, or `poDate` + **max** lead time in working days (min = target) | delivered |
| Delivered / Lost | clock stopped | — |

- **Working days** skip weekends and `meta.holidays` (`ttHolidays(year)`: T&T fixed holidays, Easter-based ones, Sunday→Monday observed). Eid and Divali are added by hand each year.
- **Holds** pause the clock and extend the due date by the working days held. Holds are per clock group (`rfq` / `quote` / `exec`).
- Key functions: `addWorkingDays, workDaysBetween, jobState, jobDueMeta, setPhase, changePhase, openPhaseAction/savePhase, toggleHold`.
- **Undo / redo**: `undoPhase` pops the last `phaseLog` entry onto `job.phaseRedo` (saved with the job); `redoPhase` re-applies it with its original date; any new `setPhase` clears redo. Typed data (PO no., dates, lead time) is never deleted — `reached(j,phase)` / `jd(j,key)` make dates for phases not reached (after an undo) count as absent.
- **Automation**: `replan(j)` (= `buildSchedule(j,true)`) after phase actions, job edits and resuming a hold; `autoProd(jobIds)` moves PO/Procurement jobs whose lines are all fully received to In Production (toast with Undo).

### Job numbers and folders
- `jobId` is a plain running number (`001`, `002`…). `nextJobNo()` = highest numeric ID + 1; non-numeric IDs are left alone. `jobLabel(j)` = "006 · Tank hatch cover" is used everywhere a job is shown (`refName("jobs")` returns it too).
- Typing just a number in any job search finds that job number (`jobQ`, `jobNoFilter`).
- The project list defaults to **newest first** (job no. descending); tapping the header toggles.
- `folderName(j)` = "006. Client A Tank hatch cover" (client cut at " — ", Windows-illegal characters replaced). `meta.projectsPath` + folder name pre-fills a new job's File location (`folderPath`). "Copy folder name" is on the job page.

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
- **Size matching ignores order and spacing**: `normText` splits "rhs4x6" → "rhs 4x6" and `canonDim` sorts the sides of every size (4x6 = 6x4; with 3+ parts the last one, the wall / thickness, stays last). `dimParts` lets "4x8x3/8" match a 3/8 plate on a 4x8 sheet; `tokHit` is the strict check.
- **Price book order**: `sortBySize` — category, then size ascending (2x2 → 3x2 → 4x2 → 4x4…, thinner wall first).
- **Price book layout** (`renderPriceRows`): one table per category, each with a column for every supplier that has quoted something in that category (A→Z) plus Best; fixed column widths so rows line up with their headings; tables scroll sideways inside `.tablewrap` on phone.
- **Price safety**: every price-history line has a ✕ (`delPriceQuote`; a price that came from an RFQ reply is cleared on that reply too). New prices that are under half or over double the item's last price (`priceOff`, `lastPrice`) trigger a "Check this price" dialog (`priceGuard`, Keep / Fix) in all three entry points: Log a price (`savePriceForms`), Enter quote on an RFQ (`saveQuote2`) and a supplier's "add an item" (`saveSupItem`). Spreadsheet import is not checked.
- **Import**: `importPriceWorkbook` reads a workbook with "Price Book" + "Quote Log" sheets.
- **Suppliers page**: `renderSuppliers` shows cards; `renderSupplier` is the profile, showing what they sell, stats (`supStats`) and RFQ history. Supplier `rating` is Preferred / Approved / Backup / Avoid.

### Project value & costing (v7, all figures **excl. VAT** — his decision)
- `j.quotes=[{rev,date,value,ref,note}]`: Rev 0 is saved in the **Quote submitted** dialog (value pre-filled from the costing's sell total); **Re-quote** (Overview → Value & costing, while Quoted) adds Rev 1, 2… with −5 / −10 / −15 % chips and shows the margin before/after, warning below `meta.minMargin` (default 10 %). `quoteValue` = latest revision.
- `j.poValue`: asked in the PO dialog, pre-filled from the latest revision. `jobValue` = PO value once the PO is in, else the latest quote.
- `j.costing={lines:{key:{cost,markup,days}},extra:[…]}` mirrors his colleague's costing sheet (`COST_LINES_DEFAULT`: paint top coat / primer, labour fab / blast & paint (days × `meta.dayRates`), equipment, consumables, materials (auto from the material list unless typed), machine shop, transport, MPI; default markups 10/10/35/35/10/10/20/10/0/0, editable in Settings → General → Costing defaults). `jobCosting`, `jobMargin`.
- **Getting the costing in = import or paste, typing is the fallback**: `costImport` reads the .xlsx (finds the sheet with a "Markup" heading), `costPaste` takes copied cells; both go through `costFromRows` (columns by heading name, % cells stored as 0.1 handled, unknown lines added as extra lines, the sheet's "total" row is checked against the computed sell total). Line names matched by `COST_MATCH` (note "labor" and "labour").
- Dashboard `valueRow` = the **Money** panel, plain headings (he found "order book / win rate" confusing): *Where the money is* — "Quoted — waiting on the client", "Won — work in hand", "Delivered in <year>" with a split bar; *How we're doing* — "Profit on won work" (costed projects only, flags ones below the minimum) and "Quotes won" ("5 of 6", plus % of quoted value). Every block opens the matching project list (`awaitingpo`, `active`, `delivered`, `costed`, `winloss`). **Hide values** (`toggleHideVals`, per device in localStorage `protrac_hidevals`) masks every money figure (`mv`). Project list has a Value column (`_val`), CSV export has value / cost / margin columns.
- Demo: invented costings and quotes (`DEMO_VALUES`, `demoValues()`), never his real figures; 005 shows a re-quote that drops below the minimum margin.

### QC
`job.qc[weld|blast|paint|final] = {s,date,by,note}`, one tap Pass/Fail/N/A. Optional item checks live in `DB.checklists` (with `stage`). There is also a QC register page. `qcAutoNA` (run from `save()`) sets stages the workflow leaves out to N/A once (`auto:true`, tracked in `job.qcAuto`); clearing it by hand sticks, and switching the option back on clears it.

### UI shell
- **Navigation**: `buildNav`, `go`, `render` (PAGES map), `renderDetail` (job page; tabs Overview · Schedule · Materials · QC — old tab ids `updates`/`procurement` alias to `overview`/`materials`).
- **Job form**: `jobFormHTML` / `wireJobForm` / `pickJobType` / `pickDeadline`; workflow options dialog `openWfOpts`. Job list columns come from `SCHEMA.jobs.gridCols` (`_step` = `currentStep`, `_pct` = `jobPct`).
- **Calendar** (`renderCalendar`): Monday-first weeks, only as many weeks as the month needs, columns `repeat(7,minmax(0,1fr))` (**never plain `1fr`** — long names widened columns and pushed Fri–Sun off the card), today highlighted plus a "Today is …" pill, weekends and `meta.holidays` shaded, deadlines colour-coded (quote / delivery / follow-up / overdue). On phone the cells show dots and a dated list (`.calagenda`) sits under the grid.
- **Board** (`renderKanban`): lanes fill the screen (`boardSize`), arrows step one lane (`boardStep`), wheel rules in `initBoard`, pointer-event drag that works with touch (press-and-hold) in `kDown/kMove/kUp`; dropping calls `changePhase`, so the phase dialog still opens. Lanes use `overscroll-behavior-y:contain` only — **never plain `contain`**, which blocked sideways swipes and thumb-wheel scrolling from reaching the board. Horizontal wheel (`deltaX`, e.g. MX Master thumb wheel) is applied to the board explicitly; lane snapping is off for mouse/trackpad (`pointer:fine`).
- **Scrollbars**: thin and transparent until hover / scroll (`.is-scrolling`), none on phone; sideways scrollers get `fade-l`/`fade-r` edge fades (observer at the end of the script).
- **Layout**: collapsible sidebar (`toggleSide`). Settings is split into tabs (`setTab`).
- **Search**: `listSearch()` sits below the filters on list pages.
- **Motion**: `pageAnim()` page transition, with `prefers-reduced-motion` respected. Its animation uses fill-mode `backwards`, **never `both`/`forwards`**: a kept transform turns every top-level block into its own layer painted in page order, which hid the dashboard search results behind the KPI cards. Any dropdown inside `#content` needs its own `position:relative; z-index` (as `.gsearch` has).

### Demo data
- **Building**: `seed()` + `seedSchedules()` create 11 anonymised jobs on working-day offsets from today (`wdOff`).
- **Staying current**: while `meta.isDemo` is set, `keepDemoCurrent()` shifts every date by the working days since `meta.demoAnchor`, so the demo is never stale. "Start empty" clears the flag.
- **Prices**: the demo price book (`DEMO_PRICES`) is real steel quotes under "Supplier A" / "Supplier B". The other demo suppliers and their items are illustrative.
- **Drafted estimates**: items the real quote log never priced (Sch 80 / 3" / 20" pipe, pipe fittings, UHMW-PE sheet) carry demo prices with `response:"Estimate"` and a note saying so; the price book marks them **est.** (`.estflag`, `bestPrice().est`). Never present an estimate as a quote.
- **Demo revisions reach saved demos**: seed changes alone only show after "Demo data" is reloaded, which confused him ("you say it's done but I still see it"). `migrateDemo()` (run from `migrate()`, only when `meta.isDemo`, guarded by `meta.demoRev` < `DEMO_REV`) re-applies demo clean-ups to saved demo data: drops `DEMO_DROP` items, renames categories, adds `DEMO_EST` estimates where there is no real price, cleans demo materials / RFQs / suppliers / updates. **Bump `DEMO_REV` and extend `migrateDemo` whenever the demo changes.** Real data (`isDemo` false) is never touched.
- **Demo categories he removed**: Abrasives, Hoses, the masking tape / poly sheeting items and the 1" A572 cut-pieces plate; "Consumables" is now **Miscellaneous**. Price items and whole categories can be deleted in the app (`delPriceItem`, `removePriceCat` asks and deletes the items too).

## Roadmap / ideas (confirm priority with the owner first)
- **Job ↔ folder linking (future).** He keeps one server folder per job, named "006. Client Job name", with fixed subfolders (email request, quotation, RFQs sent/received, drawings, material list & costing, weld maps, MTRs, additional info). The foundation is in place: running job number, `folderName()` format and `meta.projectsPath`. Next step could be creating the folder + subfolders from the job (File System Access API, desktop Chrome/Edge only; may be blocked on a company server drive) — he chose to skip it for now.
- Stock-length nesting (cut list → lengths/sheets) so material totals use real stock quantities.
- Quotation builder: the costing + value tracking is in (v7); still open — generating the quotation document itself (scope / procedures, terms, validity) from the project.
- Win-rate and turnaround stats across jobs (data already in `phaseLog` and dates).
- Downloads in the claude.ai-hosted copy (needs that platform's downloads capability); they already work on GitHub Pages.
- Parked: engineering calculator / unit converter (he has a separate fab-shop tool).
