# Protrac — Handoff / Continuation Brief

Upload BOTH files at the start of a new chat:
1. `Protrac.html` — the app (single self-contained file; this IS the source code)
2. `PROTRAC_HANDOFF.md` — this brief (optionally also `protrac_harness.js`, the Node test harness)

Then say: *"Continue building Protrac. Read the handoff and the HTML file first."*

> First instruction for the next assistant: extract the code with
> `html[html.find('<script>')+8 : html.rfind('</script>')]`, run `node --check`,
> run `node protrac_harness.js` (needs the old tracker saved as `orig.html` beside it for the
> legacy-migration test, or drop section 1–2 of the harness), and skim §9 before editing.

---

## 1. Who / what
- **Reynard** — mechanical engineer, Trinidad. Tracks fabrication jobs from client RFQ through quote, PO, procurement, production and delivery; also does QC.
- Protrac was renamed from "SONRIZ Project Tracker" (Oct 2026). **All company branding removed.** Quotes are "submitted to Manager" (label editable in Settings).
- Preferences: direct, honest pushback, step-by-step reasoning, polished output.

## 2. App basics
Single offline `.html`, vanilla JS, no CDNs. Chrome/Edge "Install page as app" for desktop use.
- Data: `localStorage` **`protrac_v1`**. On first run, if empty, it imports **`sonriz_pm_v2`** (old key, left untouched as a safety copy).
- Theme: `protrac_theme` (falls back to `sonriz_theme`). Save-folder handle: IndexedDB `protrac_fs` (folder must be re-picked once after the rename).
- Backups: `Protrac_backup_YYYY-MM-DD.json`. Old SONRIZ backups restore fine (migrated on load).

## 3. The core change: phase-driven deadlines (v1, Oct 2026)
Problem solved: one `dueDate` per job made jobs read "overdue" while waiting on the client.
**Each phase owns its own clock. Overdue = today > active phase's due AND not on hold AND phase not closed.**

| Phase (`PH.*`) | Clock | Due date | Closes when |
|---|---|---|---|
| RFQ Received | rfqDate | `rfqDueDate` or rfqDate + `rfqDays` wd | Quote submitted to Manager |
| Quoted – Awaiting PO | quoteSentDate | **none — never overdue**; `followUpDate` (default sent + `meta.followUpDays` wd) → "chase client" | PO received / Lost |
| PO Received → Procurement → In Production | poDate | `dueOverride` or poDate + **leadMax** wd; **leadMin** = target | Delivered |
| Delivered / Lost / Declined | — | clock stopped | — |

Decisions (from Reynard, locked):
- **Working days** (Mon–Fri minus `meta.holidays`). Weeks = 5 wd.
- Ranges "5–7 days": **max = due, min = target.**
- **On hold pauses the clock and extends the due date** by every working day held. Holds are per clock group (`rfq` / `quote` / `exec`); an open hold auto-closes when the job crosses into a different group.
- Stage (Fabrication/Sandblast/Paint/QC…) stays as a sub-field inside production. **Old Status field retired** (kept in data, hidden).

Holidays: `ttHolidays(year)` generates T&T fixed holidays + Good Friday / Easter Monday / Corpus Christi, Sunday → Monday observed. **Eid-ul-Fitr and Divali must be added manually each year** (gazetted). Seeded for current + next year on migration.

Transitions are buttons on the job page (and quick-select / kanban drag, which open the same date dialog for forward moves). Every phase change is auto-logged to the job's Updates and to `phaseLog[]`.

## 4. Data model (current)
`DB = { jobs, tasks, procurement, materials, suppliers, checklists, meta }`

**jobs**: jobName, jobId, client, **phase**, stage, priority, **rfqDate, rfqDueDate, rfqDays, quoteSentDate, followUpDate, poNumber, poDate, leadMin, leadMax, leadUnit ("working days"|"weeks"), dueOverride, procStartDate, prodStartDate, deliveredDate, lostDate**, percent, fileLocation, materialListLoc, notes, updates[], **holds[] {id,start,end,reason,group}**, **phaseLog[] {phase,from,date,ts,migrated?}**. Legacy (hidden): status, startDate, dueDate.

**meta** adds: `managerLabel`, `followUpDays`, `holidays[{date,name}]`. Others unchanged (clients, statuses, priorities, stages, checklistTemplates, reminders, reminderSeq).

Other tables unchanged from SONRIZ v4 (tasks 2-level with roll-up; procurement = supplier RFQs with per-supplier lines; materials; suppliers; checklists with templates).

### Migration (`migrateProtrac`, idempotent; only touches jobs without a valid phase)
- status Completed or stage Complete → Delivered (deliveredDate = old due)
- status Awaiting Approval → Quoted (quoteSentDate = old start — **verify**)
- stage Fabrication/Sandblast/Paint/QC → In Production (poDate = old start, old due → `dueOverride`)
- everything else → RFQ Received (old start → rfqDate, old due → rfqDueDate)
- status On Hold → open hold starting the migration date

## 5. Dashboard (decision surface)
KPIs (all click → filtered Jobs): Quotes overdue · Jobs overdue · Due ≤ 5 wd · RFQs to quote · Awaiting PO · Active jobs.
Sub-lines: chase client for PO · supplier quotes awaited · on hold · **missing deadline/lead time** · no QC checklist.
Panels: Reminders · Pipeline by phase · Recent updates · Next deadlines (tagged Quote / Delivery / Follow-up).
`jobFilter` keys: quoteover, jobover, soon, rfq, awaitingpo, chase, active, onhold, nodue, nochecklist.

## 6. Bugs fixed in v1
- `todayISO()` used UTC → after 8 pm in T&T it returned tomorrow. Now local date (`ymd`). Calendar cells too.
- Restore-from-backup never saved to storage (lost on reload unless something else was edited). Now saves.

## 6b. v2 (27 Oct 2026) — interview demo build (Ramps)
Purpose: demo for a Ramps interview; judged on usefulness. Reynard has no laptop → hosted demo link (claude.ai artifact, private until shared) + GitHub Pages repo (`protrac-github/`: index.html, README.md, screenshots). Artifact variant = same file with doctype/html/head/body tags stripped; downloads (backup/CSV) don't work inside the artifact viewer, they do on GitHub Pages.
- **In-app dialogs** (`uiAsk`, `uiConfirm`, `openModal`) replace every confirm()/prompt() (blocked in hosted viewers).
- **Materials v2**: fields lineNo, description, size, grade, qtyReq, unit, length, qtyOrdered, qtyReceived, supplierRef, unitCost (manual), heatNo, mtr, notes, priceItemRef, rfqRef, group (source sheet). Status derived (`matStatus`: Required → RFQ sent → Ordered → Received); tap chip advances. Old fields migrated in `migrateV2`.
- **Excel import** (`openImport`): paste TSV from Excel or pick .xlsx/.csv; own xlsx reader (`unzip`+`DecompressionStream`+DOMParser, `readXlsx`), header-row detection, synonym column mapping (`IMPORT_TARGETS`), multi-sheet, skips TOTAL/section rows, then auto-prices.
- **Price book**: `DB.priceItems` {code,category,description,tags,stockLength,grade,uom,notes,synonyms} + `DB.priceQuotes` {itemRef,supplier(name),date,price,response,note,seq}. Latest priced per supplier → best. `importPriceWorkbook` reads Reynard's PLSP/Union workbook ('Price Book' + 'Quote Log' sheets; falls back to '<supplier> Latest' columns). Size-aware search (`normText`, `scoreItem`); `autoPriceMaterials` links only confident matches; `openMatch` for manual pick.
- **Supplier RFQ from materials**: select lines → `openRfqFromMaterials` → RFQ with materialRefs + supplier lines; `rfqText` email + `rfqTSV`; supplier line Ordered/Received updates linked materials; job PO→Procurement automatically; nudge to production when all received.
- **QC v2**: `job.qc[weld|blast|paint|final] = {s,date,by,note}`; one tap Pass/Fail/N/A (Fail asks for defect note), stamped with `meta.inspectorName`; optional detailed items (DB.checklists with `stage`). QC Register page; delivered dialog warns if final not passed. Templates migrated to the 4 stages.
- **Dashboard**: global search (jobs / materials / prices), dismissible "How Protrac works" guide, open-QC-fail nudge. Nav: Dashboard, Jobs, Materials, Supplier RFQs, Price Book, QC, Suppliers, Reminders, Settings.
- **Demo seed**: 11 jobs from real job types with anonymised clients (Client A–D), demo price book from his workbook with supplier names hidden and prices scaled per item (`DEMO_PRICES`, `meta.demoPrices` banner). Settings: Reload demo / Start empty.
- **Mobile**: tested at 390 px, no horizontal scroll.
- Tests: `protrac_harness.js` (150, Node; needs orig SONRIZ html as `orig.html` and `Protrac_v1.html` beside it for migration tests) and `protrac_browser_test.py` (36, Playwright; needs the price workbook path).

## 7. Pending roadmap (unchanged order, carried over)
1. ~~Supplier price layer~~ and ~~materials quantities~~ — done in v2. Next: log a supplier's quoted prices straight from an RFQ line into the price book; stock-length nesting (cut list → lengths/sheets) so line totals use real stock quantities.
2. Downloads inside the hosted artifact (would need the `downloads` capability).
3. ~~Prominent search~~ — done (dashboard global search).
4. UI polish last (collapsible nav, fewer labels). Known nit: job page shows the progress bar twice (header + overview).
5. Small: task "blocking" indicator; decide fate of global Materials/Procurement tabs.
Possible next on the phase model: win-rate and average turnaround stats across jobs (data already captured in phaseLog/dates).
Parked: engineering calc / unit converter.

## 8. Build / test / ship loop
1. Patch → extract JS → `node --check`.
2. `node protrac_harness.js` — 141 assertions: legacy migration (runs the OLD app to generate legacy data), holiday/working-day maths, every phase clock, holds, PO dialog, filters, CSV, render smoke of every view and every job tab, fresh-seed sanity.
3. Offline grep: `fetch(|XMLHttpRequest|cdnjs|googleapis|jsdelivr|unpkg|<link |<script src` must be empty.
4. Headless screenshot check (Playwright) of dashboard, job page, PO dialog, settings — zero page errors.

## 9. Key function map (new in Protrac)
Dates: `ymd, isoAdd, holidaySet, isWorkDay, addWorkingDays, workDaysBetween, easter, ttHolidays`
Engine: `phaseGroup, isClosed, openHold, isOnHold, holdDays, holdExt, leadWD, rfqBaseDue, execBaseDue, execDue, jobDue, jobState, jobDueMeta, setPhase, changePhase, toggleHold, prevOpenPhase`
UI: `phaseActions, phaseStepper, openPhaseAction, savePhase (formMode "phase"), jobTimeline, holidayRows, addHoliday, removeHoliday, addTTYear, setManagerLabel, setFollowUpDays`
Constants: `PH, PHASES, PHASE_TOK, EXEC, CLOSED, PROD_STAGES, SOON_WD=5, PHASE_ACTION`
Everything else as in the SONRIZ v4 map (render*, migrate, forms, RFQ lines, reminders, backup/CSV).
