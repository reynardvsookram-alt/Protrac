/* ---- dashboard v3 (try-out): card layout after his reference mock-up; every number comes from the data ---- */
const DI={ // small inline icon set (stroke icons, currentColor)
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',users:'<circle cx="9" cy="8" r="3.2"/><path d="M3 20c.6-3.3 3-5 6-5s5.4 1.7 6 5"/><circle cx="17" cy="9" r="2.4"/><path d="M16 14.2c2.4.2 4.3 1.8 5 4.8"/>',
  wrench:'<path d="M14.7 6.3a4 4 0 0 0 5 5L12 19l-3.5.5L9 16l7.7-7.7"/><path d="M14.7 6.3 17 4"/>',pause:'<circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/>',
  doc:'<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>',alert:'<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17.5v.5"/>',
  chart:'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',flow:'<rect x="3" y="3" width="6" height="6" rx="1.5"/><rect x="15" y="15" width="6" height="6" rx="1.5"/><path d="M9 6h4a3 3 0 0 1 3 3v6"/>',
  cal:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',check:'<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m8 12 3 3 5-6"/>',
  folder:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',inbox:'<path d="M4 4h16v16H4z"/><path d="M4 13h4l2 3h4l2-3h4"/>',
  quote:'<path d="M5 4h10l4 4v12H5z"/><path d="M9 12h6M9 16h4"/>',truck:'<path d="M3 6h11v10H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>',
  box:'<path d="M3 7l9-4 9 4-9 4z"/><path d="M3 7v10l9 4 9-4V7M12 11v10"/>',gear:'<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  ok:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',plus:'<path d="M12 5v14M5 12h14"/>',arrow:'<path d="M5 12h14M13 6l6 6-6 6"/>',dots:'<circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/>'};
function ic(n,cls){return `<svg class="ic ${cls||""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${DI[n]||""}</svg>`;}
function firstName(){const s=((DB.meta&&DB.meta.emailSignoff)||"").split("\n")[0].trim();const w=s.split(/\s+/)[0]||"";return /^[A-Z][a-z]+$/.test(w)?w:"";}
function renderDashboard(c){
  const jobs=DB.jobs||[],T=todayISO(),S=jobs.map(j=>({j,s:jobState(j)})),pick=f=>S.filter(f).map(x=>x.j);
  const hr=new Date().getHours(),greet=hr<12?"Good morning":hr<17?"Good afternoon":"Good evening",nm=firstName();
  const dateTxt=new Date(T+"T00:00:00").toLocaleDateString(undefined,{weekday:"short",day:"numeric",month:"short",year:"numeric"});
  // ---- attention required ----
  const qo=pick(x=>x.s.kind==="quote"&&x.s.overdue),po=pick(x=>x.s.kind==="delivery"&&x.s.overdue),qf=jobs.filter(j=>qcSummary(j).fail>0&&j.phase!==PH.LOST);
  const ch=pick(x=>x.s.chase),held=pick(x=>!isClosed(x.j)&&isOnHold(x.j)),noqc=jobs.filter(jobNeedsChecklist),sup=allLines().filter(x=>x.s.status==="RFQ Sent");
  const att=[[qo.length,"Quote overdue","Quotes overdue","clock","t-bad","dashFilter('quoteover')"],[po.length,"Delivery overdue","Deliveries overdue","truck","t-bad","dashFilter('jobover')"],
    [qf.length,"Open QC fail","Open QC fails","wrench","t-warn","qcFilter='fail';go('qc')"],[ch.length,"Client to chase for PO","Clients to chase for PO","users","t-orange","dashFilter('chase')"],
    [sup.length,"Supplier quote awaited","Supplier quotes awaited","inbox","t-orange","dashGo('procurement')"],[held.length,"Project on hold","Projects on hold","pause","t-slate","dashFilter('onhold')"],
    [noqc.length,"In production, no QC","In production, no QC","doc","t-slate","dashFilter('nochecklist')"]].filter(a=>a[0]);
  const attHtml=`<section class="dcard dattn"><header><span class="dhic t-bad">${ic("alert")}</span><div><h3>Attention required</h3><p>Items that need your action</p></div><a class="dlink" onclick="go('jobs')">View all ${ic("arrow")}</a></header>
    <div class="attgrid">${att.length?att.map(([n,l1,ln,i,t,fn])=>`<button type="button" class="attcard ${t}" onclick="${fn}"><span class="atic">${ic(i)}</span><span class="atn">${n}</span><span class="atl">${n===1?l1:ln}</span><span class="atgo">›</span></button>`).join(""):`<div class="allclear">${ic("ok")} All clear — nothing needs you right now.</div>`}</div></section>`;
  // ---- financial overview (pipeline value by stage, excl. VAT) ----
  const val=j=>jobValue(j)??(jobCosting(j).has?jobCosting(j).sell:0);
  const st=[["RFQ (costed)","var(--warn)",jobs.filter(j=>j.phase===PH.RFQ),"rfq"],["Awaiting PO","var(--hold)",jobs.filter(j=>j.phase===PH.QUOTED),"awaitingpo"],["In hand","var(--info)",jobs.filter(j=>EXEC.includes(j.phase)),"active"],["Delivered "+T.slice(0,4),"var(--ok)",jobs.filter(j=>j.phase===PH.DONE&&(j.deliveredDate||"").slice(0,4)===T.slice(0,4)),"delivered"]].map(([l,col,list,f])=>({l,col,f,n:list.length,v:list.reduce((a,j)=>a+val(j),0)}));
  const tot=st.reduce((a,x)=>a+x.v,0);
  let acc=0;const R=15.915,segs=tot?st.filter(x=>x.v>0).map(x=>{const p=x.v/tot*100,s=`<circle r="${R}" cx="21" cy="21" fill="none" stroke="${x.col}" stroke-width="5.2" stroke-dasharray="${Math.max(0,p-0.8)} ${100-Math.max(0,p-0.8)}" stroke-dashoffset="${25-acc}"/>`;acc+=p;return s;}).join(""):"";
  const short=v=>hideVals()?"•••":v>=1e6?(Math.round(v/1e5)/10)+"M":v>=1e3?Math.round(v/1e3)+"K":Math.round(v)+"";
  const fin=`<section class="dcard"><header><span class="dhic t-ok">${ic("chart")}</span><div><h3>Financial overview</h3><p>Project value by stage (excl. VAT)</p></div><button class="btn sm ghost" onclick="toggleHideVals()">${hideVals()?"Show":"Hide"}</button></header>
    <div class="finrow"><div class="fintot"><span>Total pipeline value</span><b>TTD ${mv(tot).replace("$","")}</b></div>
      <div class="donut"><svg viewBox="0 0 42 42"><circle r="${R}" cx="21" cy="21" fill="none" stroke="var(--hover)" stroke-width="5.2"/>${segs}</svg><div class="dcen"><small>TTD</small><b>${short(tot)}</b></div></div>
      <div class="flegend">${st.map(x=>`<button type="button" onclick="dashFilter('${x.f}')"><span class="ldot" style="background:${x.col}"></span><span>${esc(x.l)}<em>TTD ${mv(x.v).replace("$","")}</em></span><b>${tot?Math.round(x.v/tot*100):0}%</b></button>`).join("")}</div></div>
    <div class="finmini">${st.map(x=>`<button type="button" class="fmini" style="--c:${x.col}" onclick="dashFilter('${x.f}')"><b>TTD ${mv(x.v).replace("$","")}</b><span>${esc(x.l)} · ${x.n}</span></button>`).join("")}</div></section>`;
  // ---- project pipeline ----
  const pIc={[PH.RFQ]:"quote",[PH.QUOTED]:"doc",[PH.PO]:"inbox",[PH.PROC]:"box",[PH.PROD]:"gear",[PH.DONE]:"ok",[PH.LOST]:"pause"};
  const pmax=Math.max(1,...PHASES.map(p=>jobs.filter(j=>j.phase===p).length));
  const pipe=`<section class="dcard"><header><span class="dhic t-info">${ic("flow")}</span><div><h3>Project pipeline</h3><p>Projects by current phase</p></div></header>
    <div class="plist">${PHASES.map((p,i)=>{const n=jobs.filter(j=>j.phase===p).length;return `<button type="button" class="prow" onclick="phaseGo(${i})"><span class="pic" style="color:var(${dotVar(p)})">${ic(pIc[p])}</span><span class="pnm">${esc(p)}</span><b>${n}</b><span class="pgbar"><span style="width:${n/pmax*100}%;background:var(${dotVar(p)})"></span></span></button>`;}).join("")}</div></section>`;
  // ---- upcoming deadlines (overdue + next 14 days) ----
  const lim=isoAdd(T,14);
  const up=S.filter(x=>!isClosed(x.j)&&!x.s.paused&&(x.s.due||x.s.followUp)).map(x=>({j:x.j,s:x.s,d:x.s.due||x.s.followUp})).filter(u=>u.d<=lim).sort((a,b)=>a.d<b.d?-1:a.d>b.d?1:0);
  const what={quote:"Submit quote",followup:"Follow up client for PO",delivery:"Deliver"};
  const chip=u=>{const dd=daysBetween(T,u.d);return u.s.overdue?["c-bad","Overdue"]:dd<0?["c-warn","Chase now"]:dd===0?["c-warn","Today"]:dd===1?["c-warn","Tomorrow"]:["c-mute",dd+" days"];};
  const dl=`<section class="dcard"><header><span class="dhic t-info">${ic("cal")}</span><div><h3>Upcoming deadlines</h3><p>Overdue and the next 14 days</p></div><a class="dlink" onclick="go('jobs');setView('calendar')">Calendar ${ic("arrow")}</a></header>
    <div class="dlist">${up.length?up.slice(0,6).map(u=>{const d=new Date(u.d+"T00:00:00"),[cc,ct]=chip(u);return `<button type="button" class="drow ${u.s.overdue?"od":""}" onclick="openJob('${u.j.id}')"><span class="dtile"><b>${d.getDate()}</b><span>${esc(d.toLocaleDateString(undefined,{month:"short"}))}</span></span><span class="dtx"><b>${what[u.s.kind]}</b><span>${esc(jobLabel(u.j))}</span></span><span class="dchip ${cc}">${ct}</span></button>`;}).join("")+(up.length>6?`<div class="dmore">+${up.length-6} more</div>`:""):`<div class="minimsg">Nothing due in the next two weeks.</div>`}</div></section>`;
  // ---- at risk ----
  const risk=[];S.forEach(({j,s})=>{if(isClosed(j))return;let r=null,cl="bad";
    if(s.overdue)r=[s.kind==="quote"?"Quote overdue":"Delivery overdue",Math.max(1,workDaysBetween(s.due,T))+" wd"];
    else if(qcSummary(j).fail>0)r=["QC fail","needs re-inspection"];
    else if(s.chase){r=["Chase client","for the PO"];cl="warn";}
    else if(isOnHold(j)){r=["On hold","clock paused"];cl="mute";}
    else if(s.soon&&s.kind==="delivery"){r=["Due soon","in "+s.left+" wd"];cl="warn";}
    if(r)risk.push({j,r,cl});});
  const riskHtml=`<section class="dcard"><header><span class="dhic t-bad">${ic("alert")}</span><div><h3>At-risk projects</h3><p>Projects that may slip</p></div></header>
    <div class="rlist">${risk.length?risk.slice(0,5).map(({j,r,cl})=>`<button type="button" class="rrow r-${cl}" onclick="openJob('${j.id}')"><span class="rno">${esc(jobNo(j))}</span><span class="rtx"><b>${esc(j.jobName)}</b><span>${esc(j.client||"")}</span></span><span class="rwhy"><b>${esc(r[0])}</b><span>${esc(r[1])}</span></span></button>`).join(""):`<div class="allclear">${ic("ok")} Nothing at risk.</div>`}</div></section>`;
  // ---- my actions (reminders) ----
  const rem=((DB.meta&&DB.meta.reminders)||[]).filter(r=>r.bucket!=="completed").sort((a,b)=>(a.bucket==="urgent"?0:1)-(b.bucket==="urgent"?0:1));
  const act=`<section class="dcard"><header><span class="dhic t-ok">${ic("check")}</span><div><h3>My actions</h3><p>Reminders and follow-ups</p></div><a class="dlink" onclick="go('reminders')">All ${ic("arrow")}</a></header>
    <div class="alist">${rem.length?rem.slice(0,6).map(r=>`<div class="arow"><button type="button" class="acb" onclick="toggleReminder('${r.id}')" title="Mark done"></button><span>${esc(r.text)}</span><em class="${r.bucket==="urgent"?"c-bad":"c-mute"}">${r.bucket==="urgent"?"Urgent":"To do"}</em></div>`).join(""):`<div class="minimsg">No open reminders.</div>`}
    <div class="rem-add"><input id="remind-in" placeholder="Add a reminder…" onkeydown="if(event.key==='Enter')addReminder('todo','remind-in')"><button class="btn primary sm" onclick="addReminder('todo','remind-in')">Add</button></div></div></section>`;
  // ---- quick stats ----
  const qs=[[jobs.filter(j=>EXEC.includes(j.phase)).length,"Active projects","folder","t-info","dashFilter('active')"],[jobs.filter(j=>j.phase===PH.RFQ).length,"RFQs to quote","quote","t-warn","dashFilter('rfq')"],
    [jobs.filter(j=>j.phase===PH.QUOTED).length,"Awaiting PO","clock","t-hold","dashFilter('awaitingpo')"],[po.length,"Projects overdue","alert",po.length?"t-bad":"t-slate","dashFilter('jobover')"]];
  const quick=`<section class="dcard"><header><span class="dhic t-info">${ic("chart")}</span><div><h3>Quick stats</h3><p>Key numbers at a glance</p></div></header>
    <div class="qgrid">${qs.map(([n,l,i,t,fn])=>`<button type="button" class="qtile" onclick="${fn}"><span class="atic ${t}">${ic(i)}</span><b>${n}</b><span>${l}</span></button>`).join("")}</div></section>`;
  // ---- recent projects table ----
  const recent=jobs.slice().sort((a,b)=>(+b.jobId||0)-(+a.jobId||0)).slice(0,6);
  const status=(j,s)=>j.phase===PH.DONE?["s-ok","Delivered"]:j.phase===PH.LOST?["s-mute","Lost"]:s.paused?["s-mute","On hold"]:s.overdue?["s-bad","At risk"]:s.chase?["s-warn","Chase client"]:s.soon?["s-warn","Due soon"]:["s-ok","On track"];
  const rows=recent.map(j=>{const s=jobState(j),[sc,stx]=status(j,s),p=jobPct(j),d=s.due||s.followUp;return `<tr onclick="openJob('${j.id}')"><td class="cellmono">${esc(jobNo(j))}</td><td><b>${esc(j.jobName)}</b></td><td>${esc(j.client||"")}</td><td><span class="badge" style="${tokStyle(PHASE_TOK[j.phase]||"idle")}">${esc(j.phase)}</span></td><td>${esc(currentStep(j)||"—")}</td><td class="${s.overdue?"late":""}">${d?esc(fmtShort(d)):"—"}</td><td class="cellmono">${jobValue(j)!=null?mv(jobValue(j)):"—"}</td><td><div class="pbar" style="min-width:110px"><span class="ptrack"><span class="pf ${p>=100?'full':''}" style="width:${p}%"></span></span><em>${p}%</em></div></td><td><span class="schip2 ${sc}">${stx}</span></td></tr>`;}).join("");
  const table=`<section class="dcard"><header><span class="dhic t-info">${ic("folder")}</span><div><h3>Recent projects</h3><p>Newest first</p></div><a class="dlink" onclick="go('jobs')">View all ${ic("arrow")}</a></header>
    <div class="tablewrap"><table class="rtab"><thead><tr><th>#</th><th>Project</th><th>Client</th><th>Phase</th><th>Current step</th><th>Due</th><th>Value</th><th>Progress</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
  c.innerHTML=`<div class="dhead3"><div class="dhl"><h1>${greet}${nm?", "+esc(nm):""} 👋</h1><p>Here's what you need to know today.</p></div>
      <div class="dhr"><button class="btn primary dnew" onclick="openForm(null,'jobs')">${ic("plus")} New project</button><div class="ddate"><b>${esc(dateTxt)}</b><span>${att.length?att.length+" thing"+(att.length>1?"s":"")+" need your attention":"All clear today"}</span></div></div></div>
    ${searchBox()}
    ${attHtml}
    <div class="dg3">${fin}${pipe}${dl}</div>
    <div class="dg3">${riskHtml}${act}${quick}</div>
    ${table}`;
}
