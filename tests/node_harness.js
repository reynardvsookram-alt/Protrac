// Protrac Node test harness: legacy-data migration, working-day maths, phase clocks, holds, filters, render smoke.
// Run: node tests/node_harness.js
const fs = require('fs'), vm = require('vm'), path = require('path');
const ROOT = path.join(__dirname, '..'), FIX = path.join(__dirname, 'fixtures');
const ext = f => { const h = fs.readFileSync(f, 'utf8'); return h.slice(h.indexOf('<script>') + 8, h.lastIndexOf('</script>')); };

function makeEl(id) {
  return { id, value: '', innerHTML: '', textContent: '', style: {}, dataset: {}, title: '',
    classList: { add() {}, remove() {}, contains() { return false; } },
    addEventListener() {}, click() {}, focus() {}, setAttribute() {}, getAttribute() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; }, closest() { return null; } };
}
function makeCtx(store) {
  const els = {};
  const document = {
    getElementById: id => (els[id] = els[id] || makeEl(id)),
    querySelectorAll: () => [], querySelector: () => null,
    addEventListener() {}, createElement: () => makeEl('x'), body: { appendChild() {}, removeChild() {} },
    documentElement: { setAttribute() {}, getAttribute: () => 'light' }
  };
  const localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } };
  const ctx = { document, localStorage, window: {}, console, setTimeout: () => 0, clearTimeout() {}, navigator: {},
    confirm: () => true, prompt: () => 'Awaiting client approval', indexedDB: { open() { return {}; } }, Blob: function () {}, URL: {} };
  ctx.window = ctx; vm.createContext(ctx);
  return { ctx, els, store };
}
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('FAIL:', m); } };
const run = (c, s) => vm.runInContext(s, c);

// ---- 1. Build legacy data with the OLD app (its own seed), plus extra edge jobs ----
// fixture = data saved by the original (pre-Protrac) tracker, anonymised
const legacy = JSON.parse(fs.readFileSync(path.join(FIX, 'legacy_v4_data.json'), 'utf8'));
legacy.jobs.push({ id: 'jfab', jobName: 'Legacy fab job', status: 'In Progress', stage: 'Fabrication', startDate: '2026-10-01', dueDate: '2026-10-20', updates: [] });
legacy.jobs.push({ id: 'jhold', jobName: 'Legacy held job', status: 'On Hold', stage: 'Design', startDate: '2026-10-05', dueDate: '2026-11-30', updates: [] });
const legacyStr = JSON.stringify(legacy);

// ---- 2. New app, fresh profile containing ONLY the legacy key ----
const N = makeCtx({ sonriz_pm_v2: legacyStr });
const appCode = ext(path.join(ROOT, 'index.html'));
vm.runInContext(appCode, N.ctx);
const c = N.ctx;
ok(N.store['protrac_v1'], 'data saved under new key');
ok(N.store['sonriz_pm_v2'] === legacyStr, 'legacy key left untouched');
const DBn = () => run(c, 'DB');
const job = n => DBn().jobs.find(j => j.jobName.startsWith(n));
ok(DBn().jobs.length === legacy.jobs.length, 'no jobs lost in migration');
ok(DBn().jobs.every(j => run(c, 'PHASES').includes(j.phase)), 'every job has a valid phase');
ok(job('Legacy silo').phase === 'Delivered', 'Completed → Delivered');
ok(job('Legacy lifting').phase === 'Quoted – Awaiting PO', 'Awaiting Approval → Quoted');
ok(job('Legacy fab').phase === 'In Production' && job('Legacy fab').dueOverride === '2026-10-20' && job('Legacy fab').poDate === '2026-10-01', 'fab stage → Production with old due as fixed date');
ok(job('Legacy tank base').phase === 'RFQ Received' && job('Legacy tank base').rfqDueDate === '2026-06-05', 'other → RFQ, old due → response deadline');
ok(job('Legacy held').holds.length === 1 && !job('Legacy held').holds[0].end && job('Legacy held').holds[0].group === 'rfq', 'On Hold status → open hold');
ok(job('Legacy cryo').holds.length === 1, 'seed On Hold job → hold');
ok(DBn().meta.managerLabel === 'Manager' && DBn().meta.followUpDays === 5, 'workflow meta defaults');
// idempotent
const before = JSON.stringify(DBn().jobs);
run(c, 'migrate()');
ok(JSON.stringify(DBn().jobs) === before, 'migrate() is idempotent');

// ---- 3. Working days / holidays ----
ok(run(c, 'easter(2026)') === '2026-04-05' && run(c, 'easter(2027)') === '2027-03-28', 'Easter dates');
const h27 = run(c, 'ttHolidays(2027)').map(h => h.date);
ok(h27.includes('2027-03-26') && h27.includes('2027-03-29') && h27.includes('2027-05-27'), 'Good Friday / Easter Mon / Corpus Christi 2027');
ok(h27.includes('2027-05-31') && h27.includes('2027-08-02') && h27.includes('2027-12-27'), 'Sunday holidays observed Monday (2027)');
run(c, 'DB.meta.holidays=ttHolidays(2026).concat(ttHolidays(2027))');
ok(run(c, 'addWorkingDays("2026-10-30",1)') === '2026-11-02', 'Fri +1 wd → Mon');
ok(run(c, 'addWorkingDays("2026-12-24",2)') === '2026-12-29', 'skips Christmas + Boxing Day + weekend');
ok(run(c, 'addWorkingDays("2026-10-27",0)') === '2026-10-27', '+0 wd = same day');
ok(run(c, 'workDaysBetween("2026-10-23","2026-10-30")') === 5, '1 calendar week = 5 wd');
ok(run(c, 'workDaysBetween("2026-10-30","2026-10-23")') === -5, 'negative span');
ok(run(c, 'ymd(new Date(2026,9,27,22,30))') === '2026-10-27', 'local date (no UTC rollover at night)');

// ---- 4. Phase clocks ----
const T = run(c, 'todayISO()');
run(c, `globalThis.J={id:"t1",jobName:"Test",phase:PH.RFQ,rfqDate:isoAdd(todayISO(),-10),rfqDays:3,holds:[],phaseLog:[],updates:[],leadUnit:"working days"};DB.jobs.push(J);`);
let s = run(c, 'jobState(J)');
ok(s.kind === 'quote' && s.overdue, 'RFQ past response window → quote overdue');
ok(run(c, 'jobDueMeta(J).cls') === 'overdue', 'overdue class');
run(c, 'setPhase(J,PH.QUOTED)');
s = run(c, 'jobState(J)');
ok(s.kind === 'followup' && !s.overdue && J_q(), 'Quoted → never overdue');
function J_q() { return run(c, 'J.quoteSentDate') === T; }
ok(s.followUp === run(c, 'addWorkingDays(todayISO(),5)'), 'follow-up = sent + 5 wd');
run(c, 'J.quoteSentDate=isoAdd(todayISO(),-20)');
ok(run(c, 'jobState(J).chase') === true, 'chase flag after follow-up date');
// PO with lead 5–7 wd
run(c, 'J.poDate=isoAdd(todayISO(),-3);J.leadMin=5;J.leadMax=7;J.leadUnit="working days";setPhase(J,PH.PO)');
s = run(c, 'jobState(J)');
ok(s.kind === 'delivery' && s.due === run(c, 'addWorkingDays(J.poDate,7)') && s.target === run(c, 'addWorkingDays(J.poDate,5)'), 'PO due = PO+max wd, target = PO+min wd');
ok(run(c, 'J.updates.length') >= 2, 'phase changes logged as updates');
run(c, 'J.leadUnit="weeks";J.leadMin=1;J.leadMax=2');
ok(run(c, 'jobState(J).due') === run(c, 'addWorkingDays(J.poDate,10)'), '2 weeks = 10 wd');
run(c, 'J.leadUnit="working days";J.leadMin=5;J.leadMax=7');
// Hold: pauses and extends
run(c, 'J.poDate=isoAdd(todayISO(),-30)'); // well overdue
ok(run(c, 'jobState(J).overdue') === true, 'overdue before hold');
run(c, 'J.holds.push({id:"h1",start:isoAdd(todayISO(),-7),end:"",reason:"x",group:"exec"})');
s = run(c, 'jobState(J)');
ok(s.paused && !s.overdue, 'on hold → not overdue (clock paused)');
const held = run(c, 'workDaysBetween(isoAdd(todayISO(),-7),todayISO())');
ok(s.due === run(c, `addWorkingDays(addWorkingDays(J.poDate,7),${held})`), 'due extended by working days held');
run(c, 'toggleHold("t1")'); // resume
ok(run(c, 'J.holds[0].end') === T && run(c, 'isOnHold(J)') === false, 'resume closes hold');
ok(run(c, 'jobState(J).due') === s.due, 'extension kept after resume');
// RFQ-group holds don't extend delivery
run(c, 'J.holds.push({id:"h2",start:isoAdd(todayISO(),-40),end:isoAdd(todayISO(),-35),reason:"",group:"rfq"})');
ok(run(c, 'jobState(J).due') === s.due, 'RFQ hold does not affect delivery due');
// fixed date override
run(c, 'J.dueOverride=isoAdd(todayISO(),20)');
ok(run(c, 'jobState(J).target') === '' && run(c, 'jobState(J).due') === run(c, `addWorkingDays(isoAdd(todayISO(),20),${held})`), 'fixed date overrides lead (still hold-extended)');
run(c, 'J.dueOverride=""');
// delivered stops clock
run(c, 'setPhase(J,PH.DONE)');
ok(run(c, 'jobState(J).kind') === 'closed' && !run(c, 'jobState(J).overdue') && run(c, 'J.percent') === 100, 'delivered → closed, 100%');
// hold not allowed when closed
run(c, 'toggleHold("t1")');
ok(run(c, 'isOnHold(J)') === false, 'cannot hold a delivered job');
// hold auto-closes when crossing clock groups
run(c, 'J.phase=PH.RFQ;J.holds.push({id:"h3",start:todayISO(),end:"",reason:"",group:"rfq"});setPhase(J,PH.QUOTED)');
ok(run(c, 'J.holds.find(h=>h.id==="h3").end') === T, 'open hold closed on phase change');
// missing data
run(c, `DB.jobs.push({id:"t2",jobName:"NoDue",phase:PH.PO,holds:[],phaseLog:[],updates:[]})`);
ok(run(c, 'jobDueMeta(DB.jobs.find(j=>j.id==="t2")).txt') === 'Set lead time', 'missing lead time flagged');

// ---- 5. savePhase via modal (PO) ----
run(c, `J.phase=PH.QUOTED;phaseCtx={jobId:"t1",action:"po"};formMode="phase";`);
const inputs = { date: T, poNumber: 'PO-77', leadMin: '5', leadMax: '7', leadUnit: 'working days', dueOverride: '', note: 'ok' };
c.document.querySelectorAll = () => Object.entries(inputs).map(([k, v]) => ({ dataset: { k }, value: v }));
run(c, 'saveForm()');
c.document.querySelectorAll = () => [];
ok(run(c, 'J.phase') === 'PO Received' && run(c, 'J.poNumber') === 'PO-77' && run(c, 'J.poDate') === T && run(c, 'J.leadMax') === 7, 'PO modal saves lead time and moves phase');
ok(run(c, 'jobState(J).due') === run(c, 'addWorkingDays(addWorkingDays(todayISO(),7),holdExt(J,"exec"))'), 'PO modal due correct (incl. prior hold)');
// PO modal rejects missing lead
run(c, `J.phase=PH.QUOTED;phaseCtx={jobId:"t1",action:"po"};formMode="phase";`);
c.document.querySelectorAll = () => Object.entries({ date: T, poNumber: '', leadMin: '', leadMax: '', leadUnit: 'working days', dueOverride: '', note: '' }).map(([k, v]) => ({ dataset: { k }, value: v }));
run(c, 'saveForm()');
c.document.querySelectorAll = () => [];
ok(run(c, 'J.phase') === 'Quoted – Awaiting PO', 'PO without lead time is refused');
run(c, 'closeForm()');
// quickSet backwards → direct
run(c, 'quickSet("jobs","t1","phase",PH.RFQ)');
ok(run(c, 'J.phase') === 'RFQ Received', 'quick-set to RFQ applies directly');
// quickSet forward → opens modal, doesn't change yet
run(c, 'quickSet("jobs","t1","phase",PH.QUOTED)');
ok(run(c, 'J.phase') === 'RFQ Received' && run(c, 'formMode') === 'phase', 'quick-set forward opens date modal');
run(c, 'closeForm()');

// ---- 6. Filters ----
const filt = k => run(c, `(()=>{current="jobs";jobFilter="${k}";const r=filteredRows();jobFilter=null;return r.map(j=>j.id);})()`);
for (const k of ['quoteover', 'jobover', 'soon', 'rfq', 'awaitingpo', 'chase', 'active', 'onhold', 'nodue', 'nochecklist']) {
  try { const r = filt(k); ok(Array.isArray(r), 'filter ' + k); } catch (e) { ok(false, 'filter ' + k + ' threw ' + e.message); }
}
ok(filt('onhold').length >= 2, 'onhold filter finds migrated holds');
ok(filt('nodue').includes('t2'), 'nodue filter finds job without lead');
run(c, 'current="jobs";sortKey="_due";sortDir=1');
try { run(c, 'filteredRows()'); ok(true, 'sort by due'); } catch (e) { ok(false, 'sort by due ' + e.message); }
run(c, 'sortKey=null');

// ---- 7. Render smoke test ----
const smoke = (label, code) => { try { run(c, code); ok(true, label); } catch (e) { ok(false, label + ' threw: ' + e.stack.split('\n').slice(0, 3).join(' | ')); } };
smoke('dashboard', 'go("dashboard")');
const dash = N.els.content.innerHTML;
ok(dash.includes('Quotes overdue') && dash.includes('Jobs overdue') && dash.includes('Pipeline by phase'), 'dashboard content');
smoke('reminders', 'go("reminders")');
/* settings uses real DOM — covered in browser suites */
smoke('jobs grid', 'go("jobs")');
ok(N.els.content.innerHTML.includes('Due / next action'), 'grid due column');
smoke('jobs kanban', 'setView("kanban")');
ok(N.els.content.innerHTML.includes('Quoted – Awaiting PO'), 'kanban by phase');
smoke('jobs calendar', 'setView("calendar")');
for (const t of ['procurement', 'materials', 'suppliers', 'checklists']) smoke(t, `go("${t}")`);
for (const j of DBn().jobs) for (const tab of ['overview', 'checklist', 'schedule', 'materials', 'procurement', 'updates'])
  smoke(`detail ${j.jobName.slice(0, 18)}/${tab}`, `openJob("${j.id}");setDetailTab("${tab}")`);
smoke('phase modals', 'for(const a of ["quoted","po","proc","prod","done","lost","reopen"]){openPhaseAction("t1",a);closeForm();}');
smoke('job form', 'openForm(null,"jobs");closeForm();openForm("t1","jobs");closeForm()');
smoke('exportCSV jobs', 'current="jobs";csvDownload=function(h,r){globalThis.__csv=[h,r];};exportCSV()');
ok(run(c, '__csv[0].includes("Due / next action") && !__csv[0].includes("① RFQ from client")'), 'CSV has due, no headings');
smoke('settings actions', 'addTTYear;document.getElementById("hol-year").value="2028";addTTYear();setManagerLabel("Ops Manager");setFollowUpDays("7")');
ok(DBn().meta.holidays.some(h => h.date.startsWith('2028')) && DBn().meta.managerLabel === 'Ops Manager' && DBn().meta.followUpDays === 7, 'settings actions persist');

// ---- 8. Fresh profile (no data at all) ----
const F = makeCtx({});
vm.runInContext(appCode, F.ctx);
ok(run(F.ctx, 'DB.jobs.length') === 11 && run(F.ctx, 'DB.jobs.every(j=>PHASES.includes(j.phase))'), 'fresh seed valid');
const fs_ = run(F.ctx, 'DB.jobs.map(j=>jobState(j))');
ok(fs_.some(s => s.kind === 'quote' && s.overdue) && fs_.some(s => s.chase), 'seed demonstrates quote-overdue and chase');
run(F.ctx, 'go("dashboard")');
ok(!/sonriz|marc/i.test(JSON.stringify(run(F.ctx, 'DB'))), 'seed has no company names');


// ---- 9. v2 migrations on legacy data (context N came from the OLD app's data) ----
const mats = run(c, 'DB.materials');
ok(mats.length >= 2 && mats.every(m => !('materialId' in m) && !('qtyOnHand' in m) && 'lineNo' in m), 'old material lines converted');
ok(mats.some(m => m.lineNo === 'MAT-001' && /12.7 thk/.test(m.size)), 'old thickness → size text');
const tpl = run(c, 'DB.meta.checklistTemplates.map(t=>t.type)');
ok(['Welding / Fabrication','Sandblasting','Painting','Final Inspection'].every(t => tpl.includes(t)), 'QC templates → 4 stages: ' + tpl.join(', '));
ok(run(c, 'DB.meta.checklistTemplates.find(t=>t.stage==="weld").items.some(i=>/WPS/.test(i)) && DB.meta.checklistTemplates.find(t=>t.stage==="weld").items.some(i=>/Squareness/.test(i))'), 'welding + fabrication items merged');
ok(run(c, 'DB.checklists.every(c=>["weld","blast","paint","final"].includes(c.stage))'), 'old checklist items assigned to a QC stage');
ok(run(c, 'Array.isArray(DB.priceItems)&&Array.isArray(DB.priceQuotes)'), 'price book arrays added to old data');
run(c, 'migrate()');
const b4 = JSON.stringify(run(c, 'DB'));
run(c, 'migrate()');
{const A=JSON.parse(b4),B=JSON.parse(JSON.stringify(run(c,'DB')));const d=(x,y,p)=>{if(JSON.stringify(x)===JSON.stringify(y))return;if(typeof x!=='object'||!x||!y){console.log('DIFF',p,JSON.stringify(x)&&JSON.stringify(x).slice(0,90),'→',JSON.stringify(y)&&JSON.stringify(y).slice(0,90));return;}for(const k of new Set([...Object.keys(x),...Object.keys(y)]))d(x[k],y[k],p+'.'+k);};d(A,B,'DB');}
ok(JSON.stringify(run(c, 'DB')) === b4, 'v2 migrate() idempotent');
// v1 Protrac backup (pre-v2) loads through restore path
const V1 = makeCtx({});
vm.runInContext(ext(path.join(FIX, 'protrac_v1.html')), V1.ctx);
const v1data = run(V1.ctx, 'JSON.stringify(DB)');
run(c, `DB=JSON.parse(${JSON.stringify(v1data)});migrate();`);
ok(run(c, 'DB.jobs.length') === 6 && run(c, 'DB.jobs.every(j=>j.qc&&PHASES.includes(j.phase))') && run(c, 'DB.materials.every(m=>"lineNo" in m)'), 'Protrac v1 backup migrates to v2');
ok(run(c, 'typeof searchPrices("4x4").length') === 'number', 'price search on empty book');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
