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

// ---- 2. Old-format data (status/stage/start/due, no phases) saved under the current key ----
const N = makeCtx({ protrac_v1: legacyStr });
const appCode = ext(path.join(ROOT, 'index.html'));
vm.runInContext(appCode, N.ctx);
const c = N.ctx;
ok(N.store['protrac_v1'] && N.store['protrac_v1'] !== legacyStr, 'old-format data migrated and re-saved');
ok(!/legacy_|_pm_v2/.test(appCode), 'no old-tracker storage key in the app');
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
ok(['Attention required', 'Financial overview', 'Project pipeline', 'Upcoming deadlines', 'At-risk projects', 'My actions', 'This month', 'Recent activity'].every(s => dash.includes(s)) && !dash.includes('Quick stats'), 'dashboard content (v3 cards, "This month" replaces Quick stats)');
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
ok(run(F.ctx, 'DB.jobs.every(j=>!j.client||/^(Client [A-Z] — .+|Other)$/.test(j.client))'), 'seed clients are anonymised');
ok(run(F.ctx, 'DB.jobs.map(j=>j.jobId).sort().join(",")') === '001,002,003,004,005,006,007,008,009,010,011', 'demo jobs numbered 001–011');

// ---- 8b. Dashboard v3 fixes (demo data) ----
{
  const D = code => run(F.ctx, code), html = () => F.els.content.innerHTML;
  D('go("dashboard")');
  const sec = (from, to) => { const h = html(); return h.slice(h.indexOf(from), h.indexOf(to, h.indexOf(from))); };
  const overIds = D('DB.jobs.filter(j=>jobState(j).overdue).map(j=>j.id)');
  ok(overIds.length > 0, 'demo has an overdue project');
  const risk = sec('At-risk projects', 'My actions'), dl = sec('Upcoming deadlines', 'At-risk projects'), att = sec('Attention required', 'Financial overview');
  ok(overIds.every(id => !risk.includes(`openJob('${id}')`)), 'fix 1: overdue projects are not listed under At-risk');
  ok(overIds.every(id => dl.includes(`openJob('${id}')`)) && att.includes("dashFilter('quoteover')"), 'fix 1: overdue projects stay in Attention + Upcoming deadlines');
  ok(/openJob\('/.test(risk) && D('DB.jobs.filter(j=>!isClosed(j)&&!jobState(j).overdue&&(qcSummary(j).fail>0||jobState(j).soon||jobState(j).chase||isOnHold(j))).length') === (risk.match(/class="rrow/g) || []).length, 'fix 1: At-risk = due soon / chase / on hold / QC fail');
  // fix 2: This month
  const mon = sec('This month', 'Recent activity');
  ok(['Quote', 'PO', 'Delivered', 'Value won'].every(s => mon.includes(s)) && ['mquoted', 'mwon', 'mdelivered'].every(f => mon.includes(`dashFilter('${f}')`)), 'fix 2: This month tiles open filtered lists');
  D(`globalThis.__M=todayISO().slice(0,7);globalThis.__L=isoAdd(__M+"-01",-3);DB.jobs.push({id:"mth1",jobId:"901",jobName:"Month test",phase:PH.PO,holds:[],updates:[],qc:{},quotes:[{rev:0,date:todayISO(),value:1000}],poValue:1234,
     phaseLog:[{phase:PH.RFQ,date:__L},{phase:PH.QUOTED,date:__L},{phase:PH.PO,date:todayISO()}],rfqDate:__L,quoteSentDate:__L,poDate:todayISO()})`);
  ok(D('inThisMonth(DB.jobs.find(j=>j.id==="mth1"),"won")') && !D('inThisMonth(DB.jobs.find(j=>j.id==="mth1"),"quoted")'), 'fix 2: phase-log dates decide what happened this month');
  D('current="jobs";jobFilter="mwon";listQ="";gridFilters={}');
  ok(D('filteredRows().some(j=>j.id==="mth1")&&filteredRows().every(j=>inThisMonth(j,"won"))'), 'fix 2: "POs won" filter lists this month\'s POs');
  D('jobFilter="mquoted"'); ok(D('!filteredRows().some(j=>j.id==="mth1")'), 'fix 2: last month\'s quote is not counted this month');
  D('go("dashboard")'); ok(sec('This month', 'Recent activity').includes('PO'), 'dashboard renders with the month test project');
  D('DB.jobs=DB.jobs.filter(j=>j.id!=="mth1")');
  // fix 3: attention filter = exactly the projects behind the cards
  D('current="jobs";jobFilter="attention";listQ="";gridFilters={}');
  const attIds = D('[...attentionJobIds()].sort().join()'), rowIds = D('filteredRows().map(j=>j.id).sort().join()');
  ok(attIds && attIds === rowIds && D('filteredRows().length') < D('DB.jobs.length'), 'fix 3: "View all" lists only the attention projects (' + D('filteredRows().length') + ' of ' + D('DB.jobs.length') + ')');
  ok(D('JOBFILTER_LABEL.attention') && D('JOBFILTER_LABEL.mwon'), 'new filters have banner labels');
  // fix 4: zero stages left out of the financial overview
  D('go("dashboard")');
  const rfqVal = D('DB.jobs.filter(j=>j.phase===PH.RFQ).reduce((a,j)=>a+(jobValue(j)??(jobCosting(j).has?jobCosting(j).sell:0)),0)');
  const fin = sec('Financial overview', 'Project pipeline');
  ok(rfqVal === 0 ? !fin.includes('RFQ (costed)') : fin.includes('RFQ (costed)'), 'fix 4: RFQ line shown only when it has a value (' + rfqVal + ')');
  ok(!/TTD 0(?![\d,])/.test(fin) && !/>0%</.test(fin), 'fix 4: no "TTD 0" or 0% lines in the financial overview');
  D('globalThis.__bak=[DB.jobs,DB.procurement];DB.jobs=[];DB.procurement=[]'); D('go("dashboard")');
  ok(html().includes('No project values yet') && html().includes('All clear') && html().includes('No projects yet'), 'empty data: dashboard explains instead of showing zeros');
  D('DB.jobs=__bak[0];DB.procurement=__bak[1]');
}


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


// ---- 10. v6 (phase-1 clean-up): migration, job numbers, folder name, undo/redo, auto production, auto QC N/A ----
const G = makeCtx({});
vm.runInContext(appCode, G.ctx);
const g = s => run(G.ctx, s);
// old data with stage / manual % / meta.statuses / meta.stages still loads, and the job fields survive
g(`DB.meta.statuses=[{name:"In Progress",tok:"prog"}];DB.meta.stages=[{name:"Paint",tok:"info"}];DB.jobs[0].stage="Paint";DB.jobs[0].percent=37;delete DB.jobs[0].phaseRedo;delete DB.jobs[0].qcAuto;delete DB.meta.projectsPath;delete DB.meta.quoteDays;migrate();`);
ok(!('statuses' in g('DB.meta')) && !('stages' in g('DB.meta')), 'v6: old Status / Stage lists dropped from settings');
ok(g('DB.jobs[0].stage') === 'Paint' && g('DB.jobs[0].percent') === 37, 'v6: old job Stage and % kept on the record (nothing deleted)');
ok(Array.isArray(g('DB.jobs[0].phaseRedo')) && g('typeof DB.jobs[0].qcAuto') === 'object' && g('DB.meta.projectsPath') === '' && g('DB.meta.quoteDays') === 5, 'v6: new fields defaulted');
{ const a = JSON.stringify(g('DB')); g('migrate()'); ok(JSON.stringify(g('DB')) === a, 'v6 migrate() idempotent'); }
// job numbers + folder name
ok(g('nextJobNo()') === '012', 'next job number = highest + 1, zero-padded');
g(`DB.jobs.push({id:"jx",jobId:"Q-99",jobName:"x",phase:PH.RFQ,holds:[],phaseLog:[],updates:[]});`);
ok(g('nextJobNo()') === '012', 'non-numeric IDs are ignored, never renumbered');
ok(g('DB.jobs.find(j=>j.id==="jx").jobId') === 'Q-99', 'existing IDs untouched');
ok(g('folderName({jobId:"006",client:"Client A — Oilfield Services",jobName:"Tank hatch cover"})') === '006. Client A Tank hatch cover', 'folder name format');
ok(g('folderName({jobId:"007",client:"Other",jobName:"Gate: 2/3 \\"rev\\""})') === '007. Gate- 2-3 -rev-', 'folder name strips Windows-illegal characters');
g('DB.meta.projectsPath="P:\\\\Projects\\\\"');
ok(g('folderPath({jobId:"006",client:"Client A — Oilfield Services",jobName:"Tank hatch cover"})') === 'P:\\Projects\\006. Client A Tank hatch cover', 'file location = projects path + folder name');
ok(g('jobQ(DB.jobs,"6",j=>j.jobName).map(j=>j.jobId).join()') === '006' && g('jobQ(DB.jobs,"006",j=>j.jobName).length') === 1, 'typing a job number finds that job');
// progress + current step come from the schedule
const pj = g('DB.jobs.find(j=>j.jobId==="006").id');
ok(g(`(()=>{const j=DB.jobs.find(x=>x.id==="${pj}");const k=schedSteps(j);return jobPct(j)===Math.round(k.filter(t=>t.status==="Done").length/k.length*100)})()`), 'progress = share of schedule steps done');
ok(g(`currentStep(DB.jobs.find(x=>x.id==="${pj}")).length>0`), 'current step read from the schedule');
// undo / redo
g(`globalThis.U={id:"u1",jobId:"099",jobName:"Undo test",client:"Other",jobType:"Build to client drawing",optFab:true,optCoat:true,phase:PH.RFQ,rfqDate:isoAdd(todayISO(),-10),rfqDueDate:isoAdd(todayISO(),5),holds:[],phaseLog:[{phase:PH.RFQ,from:"",date:isoAdd(todayISO(),-10),ts:1}],updates:[],phaseRedo:[],qcAuto:{},leadUnit:"working days"};DB.jobs.push(U);buildSchedule(U);`);
ok(!g('canUndoPhase(U)'), 'nothing to undo on a new job');
g(`phaseCtx={jobId:"u1",action:"quoted"};formMode="phase";document.getElementById("mbody");`);
g(`setPhase(U,PH.QUOTED,{date:isoAdd(todayISO(),-6)});U.leadMin=10;U.leadMax=12;setPhase(U,PH.PO,{date:isoAdd(todayISO(),-2)});U.poNumber="PO 1";`);
const nUpd = g('U.updates.length');
g('undoPhase("u1")');
ok(g('U.phase') === 'Quoted – Awaiting PO' && g('canRedoPhase(U)') && g('U.poNumber') === 'PO 1' && g('U.poDate') === g('isoAdd(todayISO(),-2)'), 'undo steps back one phase; PO number and date kept');
ok(g('jobState(U).kind') === 'followup' && !g('jd(U,"poDate")'), 'after undo the job is back on the quote clock');
ok(g('U.updates.length') === nUpd + 1 && /Undo/.test(g('U.updates[U.updates.length-1].text')), 'undo logged in Updates');
g('undoPhase("u1")');
ok(g('U.phase') === 'RFQ Received' && g('U.phaseRedo.length') === 2, 'undo again → RFQ, two redos stacked');
ok(g('DB.tasks.find(t=>t.jobRef==="u1"&&t.stepKey==="quoted").status') !== 'Done', 'schedule step un-ticks when its phase is undone');
g('redoPhase("u1")');
ok(g('U.phase') === 'Quoted – Awaiting PO' && g('U.phaseLog[U.phaseLog.length-1].date') === g('isoAdd(todayISO(),-6)'), 'redo re-applies with the original date');
ok(/Redo/.test(g('U.updates[U.updates.length-1].text')), 'redo logged in Updates');
g('setPhase(U,PH.LOST)');
ok(!g('canRedoPhase(U)') && g('U.phaseRedo.length') === 0, 'a new phase change clears redo');
g('undoPhase("u1")');
ok(g('U.phase') === 'Quoted – Awaiting PO', 'undo works from Lost too');
ok(g('JSON.parse(localStorage.getItem("protrac_v1")).jobs.find(j=>j.id==="u1").phaseRedo.length') === 1, 'redo stack is saved with the job');
// auto production (A3)
g(`setPhase(U,PH.PO);setPhase(U,PH.PROC);DB.materials.push({id:"m1",jobRef:"u1",description:"Plate",qtyReq:2,qtyOrdered:2,qtyReceived:0},{id:"m2",jobRef:"u1",description:"Angle",qtyReq:4,qtyOrdered:4,qtyReceived:0});`);
g('receiveMats(["m1"])');
ok(g('U.phase') === 'Procurement', 'one of two lines received → still Procurement');
g('DB.materials.find(m=>m.id==="m2").qtyReceived=1;autoProd(["u1"])');
ok(g('U.phase') === 'Procurement', 'part-received never fires');
g('receiveMats(["m2"])');
ok(g('U.phase') === 'In Production' && g('U.prodStartDate') === g('todayISO()'), 'all lines received → In Production, start = last receipt');
ok(/moved automatically/.test(g('U.updates[U.updates.length-1].text')), 'auto move logged in Updates');
g('undoPhase("u1")');
ok(g('U.phase') === 'Procurement', 'auto move can be undone');
g(`globalThis.V={id:"v1",jobId:"098",jobName:"No mats",phase:PH.PO,holds:[],phaseLog:[],updates:[],phaseRedo:[],qcAuto:{}};DB.jobs.push(V);autoProd(["v1"]);`);
ok(g('V.phase') === 'PO Received', 'jobs with no material lines are not moved');
g('U.phase=PH.QUOTED;autoProd(["u1"])');
ok(g('U.phase') === 'Quoted – Awaiting PO', 'only fires from PO / Procurement');
// auto QC N/A (D4)
g(`globalThis.R={id:"q1",jobId:"097",jobName:"Repair",jobType:"Repair / blast & paint",optSite:true,optFab:false,optCoat:true,phase:PH.RFQ,rfqDate:todayISO(),holds:[],phaseLog:[],updates:[],qc:{},phaseRedo:[],qcAuto:{}};DB.jobs.push(R);save();`);
ok(g('R.qc.weld.s') === 'N/A' && g('R.qc.weld.auto') === true && g('!(R.qc.blast&&R.qc.blast.s)') && g('!(R.qc.final&&R.qc.final.s)'), 'excluded QC stage set to N/A; included ones left alone');
g('qcSet("q1","weld","N/A");save()');
ok(!g('R.qc.weld.s'), 'tapping N/A again clears it, and it does not come back');
g('R.optFab=true;R.qc.weld={s:"N/A",auto:true};save()');
ok(!g('R.qc.weld.s'), 'turning the option back on clears an automatic N/A');

// ---- 11. price-book search: size order doesn't matter, no spaces needed, plate sheet + thickness ----
{ const H = makeCtx({}); vm.runInContext(appCode, H.ctx); const p = s => run(H.ctx, s);
  const names = q => p(`searchPrices(${JSON.stringify(q)},{strict:true}).map(x=>x.it.description).sort().join("|")`);
  ok(names('RHS 6 x 4') !== '' && names('RHS 4 x 6') === names('RHS 6 x 4') && names('rhs4x6') === names('RHS 6 x 4'), 'RHS 4 x 6 = RHS 6 x 4 = rhs4x6');
  ok(names('rhs 4x6x1/4') === 'RHS 6" x 4" x 1/4"', 'wall thickness stays last: 4x6x1/4 finds 6x4x1/4 only');
  ok(names('Plate 4 x 8 x 3/8') === names('plate 3/8') && names('plate 3/8') !== '', 'plate 4 x 8 x 3/8 finds the 3/8 plate (4x8 sheet)');
  ok(p('searchPrices("Plate 8 x 20 x 3/8")[0].it.description') === 'Plate 3/8" thk', 'other sheet sizes still suggest the right thickness');
  ok(names('sch40').includes('Sch 40') && names('2x2x5mm') === 'SHS 2" x 2" x 5mm (≈3/16")', 'schedule and mm sizes still match');
  const order = p('sortBySize(searchPrices("rhs",{strict:true})).map(x=>x.it.description.replace(/^(RHS|SHS) /,"").split(" x ").slice(0,2).join("x"))');
  ok(order.indexOf('2"x2"') < order.indexOf('3"x2"') && order.indexOf('3"x2"') < order.indexOf('4"x2"') && order.indexOf('4"x4"') < order.indexOf('6"x4"'), 'price book lists sizes smallest first: ' + order.slice(0, 6).join(', '));
}

// ---- 12. saved DEMO data picks up the demo price-book revisions; real data is never touched ----
{ const D = makeCtx({}); vm.runInContext(appCode, D.ctx); const d = s => run(D.ctx, s);
  // make it look like a demo saved before the revision: old categories/items, no estimates, rev unset
  d(`DB.meta.demoRev=0;DB.priceQuotes=DB.priceQuotes.filter(q=>q.response!=="Estimate");
     ["AB-01","HO-01","CN-01","PL-10"].forEach((c,i)=>{const it={id:"old"+i,code:c,category:c[0]=="A"?"Abrasives":c[0]=="H"?"Hoses":c[0]=="C"?"Consumables":"Plate",description:"old "+c,tags:"",stockLength:"",grade:"",uom:"Each",notes:"",synonyms:""};DB.priceItems.push(it);DB.priceQuotes.push({id:"oq"+i,itemRef:it.id,supplier:"Supplier A",date:todayISO(),price:10,response:"Quoted",note:"",seq:1});});
     DB.priceItems.filter(i=>i.category==="Miscellaneous").forEach(i=>i.category="Consumables");
     DB.materials.push({id:"oldm1",jobRef:DB.jobs[0].id,description:"Garnet abrasive 30/60",qtyReq:3},{id:"oldm2",jobRef:DB.jobs[0].id,description:"Masking tape",qtyReq:3});DB.procurement[0].materialRefs.push("oldm1");DB.procurement[0].item="Garnet abrasive, masking";
     DB.suppliers[4].supplies=["Abrasives","Hoses","Consumables"];DB.suppliers[4].notes="Garnet and copper-slag abrasives, blast hose, masking.";
     DB.priceItems.find(i=>i.code==="RHS-10").userNote=1; DB.priceQuotes.push({id:"mine",itemRef:DB.priceItems.find(i=>i.code==="FT-01").id,supplier:"Supplier A",date:todayISO(),price:333,response:"Quoted",note:"typed by me",seq:2});
     migrate();`);
  ok(d('!priceCats().some(c=>["Abrasives","Hoses","Consumables"].includes(c))') && d('priceCats().includes("Miscellaneous")'), 'saved demo: Abrasives / Hoses gone, Consumables → Miscellaneous');
  ok(d('!DB.priceItems.some(i=>["AB-01","HO-01","CN-01","PL-10"].includes(i.code))') && d('!DB.priceQuotes.some(q=>/^oq/.test(q.id))'), 'saved demo: removed items and their prices gone');
  ok(d('bestPrice(DB.priceItems.find(i=>i.code==="RHS-10")).est===true'), 'saved demo: estimates added where there was no price');
  ok(d('!/garnet|abrasive|masking tape|poly sheet|blast hose/i.test(JSON.stringify([DB.materials,DB.procurement.map(r=>r.item),DB.suppliers,DB.jobs.map(j=>j.updates)]))'), 'saved demo: no abrasive / hose / masking / poly sheeting left in projects, RFQs, suppliers or updates');
  ok(d('DB.suppliers.every(s=>!(s.supplies||[]).some(x=>["Abrasives","Hoses","Consumables"].includes(x)))'), 'saved demo: supplier specialities cleaned (Consumables → Miscellaneous)');
  ok(d('DB.priceQuotes.some(q=>q.id==="mine")') && d('!DB.priceQuotes.some(q=>q.itemRef===DB.priceItems.find(i=>i.code==="FT-01").id&&q.response==="Estimate")'), 'saved demo: your own prices kept, no estimate added over them');
  { const a = JSON.stringify(d('DB')); d('DB.meta.demoRev=0;migrate()'); ok(JSON.stringify(d('DB.priceQuotes.length')) === JSON.stringify(JSON.parse(a).priceQuotes.length), 'demo revision is idempotent'); }
  d(`DB.meta.isDemo=false;DB.meta.demoRev=0;DB.priceItems.push({id:"real1",code:"AB-01",category:"Abrasives",description:"my garnet",tags:"",stockLength:"",grade:"",uom:"Bag",notes:"",synonyms:""});migrate();`);
  ok(d('DB.priceItems.some(i=>i.id==="real1")'), 'real (non-demo) data is never changed by demo revisions');
}

// ---- 13. v7 project value & costing ----
{ const V = makeCtx({}); vm.runInContext(appCode, V.ctx); const v = s => run(V.ctx, s);
  ok(v('DB.jobs.filter(j=>["005","006","001"].includes(j.jobId)).every(j=>j.quotes.length&&j.costing)'), 'demo projects carry invented costings and quotes');
  ok(v('DB.jobs.find(j=>j.jobId==="005").quotes.length') === 2, 'demo shows a re-quote (Rev 1)');
  v(`delete DB.meta.dayRates;delete DB.meta.minMargin;DB.jobs.forEach(j=>delete j.quotes);migrate();`);
  ok(v('DB.meta.dayRates.fab') === 1250 && v('DB.meta.minMargin') === 10 && v('DB.jobs.every(j=>Array.isArray(j.quotes))'), 'v7: defaults added, every project has a quotes list');
  { const a = JSON.stringify(v('DB')); v('migrate()'); ok(JSON.stringify(v('DB')) === a, 'v7 migrate() idempotent'); }
  v(`globalThis.K={id:"k1",jobId:"099",jobName:"Cost test",phase:PH.QUOTED,quoteSentDate:todayISO(),holds:[],phaseLog:[],updates:[],quotes:[{rev:0,date:todayISO(),value:17399.90}],
     costing:{lines:{paintTop:{cost:1050},paintPrimer:{cost:500},labFab:{days:2},labPaint:{days:1},equip:{cost:200},consum:{cost:500},mat:{cost:4574},machine:{cost:1500},transport:{cost:500},mpi:{cost:1200}},extra:[]}};DB.jobs.push(K);`);
  const kc = v('jobCosting(K)');
  ok(Math.abs(kc.cost - 14024) < 0.01, 'cost total: days × rate for labour, typed lines, materials excl. VAT (' + kc.cost + ')');
  ok(Math.abs(kc.sell - 16713.80) < 0.01, 'sell total with default markups (' + kc.sell.toFixed(2) + ')');
  ok(Math.abs(v('jobMargin(K).amt') - (17399.90 - 14024)) < 0.01, 'margin = quoted value − cost');
  v('K.quotes.push({rev:1,date:todayISO(),value:15659.91})');
  ok(v('quoteValue(K)') === 15659.91 && v('quoteRev(K)') === 1, 'latest revision is the quoted value');
  ok(Math.abs(v('jobMargin(K).pct') - 10.446) < 0.01, 'after a 10% discount the margin is ' + v('jobMargin(K).pct').toFixed(1) + '%');
  v('setPhase(K,PH.PO);K.poValue=15500');
  ok(v('jobValue(K)') === 15500, 'after the PO the value is the PO value');
  ok(v('(()=>{const o=K.costing;delete K.costing;const r=jobMargin(K);K.costing=o;return r===null})()'), 'no costing → no margin shown (never a made-up one)');
  // a saved demo from before v7 gets the demo values on load; a real project is never given made-up values
  v(`DB.meta.demoRev=7;DB.jobs.forEach(j=>{if(j.id!=="k1"){j.quotes=[];delete j.costing;delete j.poValue;}});DB.jobs.push({id:"real",jobId:"001x",jobName:"real",phase:PH.QUOTED,holds:[],phaseLog:[],updates:[],quotes:[]});migrate();`);
  ok(v('DB.jobs.find(j=>j.jobId==="006").quotes.length===1&&!!DB.jobs.find(j=>j.jobId==="006").costing'), 'saved demo (rev 7) picks up the demo values');
  ok(v('!DB.jobs.find(j=>j.id==="real").costing&&!DB.jobs.find(j=>j.id==="real").quotes.length'), 'projects outside the demo list are left alone');
}
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
