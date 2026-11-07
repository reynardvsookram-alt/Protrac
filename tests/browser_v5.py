import os
APP="file://"+os.path.abspath(os.path.join(os.path.dirname(__file__),"..","index.html"))
FIX=os.path.join(os.path.dirname(os.path.abspath(__file__)),"fixtures")
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"out");os.makedirs(OUT,exist_ok=True)
import asyncio
from playwright.async_api import async_playwright
async def main():
  res=[];ok=lambda c,m:res.append((bool(c),m))
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={"width":1400,"height":900})
    pg=await ctx.new_page();errs=[];pg.on("pageerror",lambda e:errs.append(str(e)));E=pg.evaluate
    await pg.goto(APP);await pg.wait_for_timeout(400)
    # fonts
    ok(await E("document.fonts.check('14px \"IBM Plex Sans\"')") and "IBM Plex Sans" in await E("getComputedStyle(document.body).fontFamily"),"IBM Plex Sans embedded and in use")
    # C3 tab order
    jid=await E("DB.jobs.find(j=>j.jobId==='004').id")
    await E(f"openJob('{jid}')")
    tabs=await E("Array.from(document.querySelectorAll('.jtabs button')).map(b=>b.textContent.replace(/[^A-Za-z]/g,''))")
    ok([t.rstrip('0123456789') for t in tabs]==["Overview","Schedule","Materials","QC"],f"tab order {tabs}")
    # C2 parent task list only from this job
    await E(f"openJob('{jid}','schedule')")
    t=await E(f"DB.tasks.find(t=>t.jobRef==='{jid}'&&t.parentTask&&!t.stepKey.startsWith('sec'))")
    await E(f"openForm('{t['id']}','tasks')")
    opts=await E("Array.from(document.querySelectorAll('#mbody [data-k=parentTask] option')).map(o=>o.value).filter(Boolean)")
    ok(opts and await E(f"{opts!r}.every(id=>DB.tasks.find(t=>t.id===id).jobRef==='{jid}')"),f"parent-task list only shows this job's tasks ({len(opts)})")
    await E("closeForm()")
    # C1 gantt labels don't overlap
    ov=await E("(()=>{const ts=Array.from(document.querySelectorAll('.gantt text.gaxis'));const bx=ts.map(t=>t.getBBox());let bad=0;for(let i=0;i<bx.length;i++)for(let j=i+1;j<bx.length;j++){const a=bx[i],b=bx[j];if(a.x<b.x+b.width&&b.x<a.x+a.width&&a.y<b.y+b.height&&b.y<a.y+a.height)bad++;}return [ts.length,bad]})()")
    ok(ov[0]>2 and ov[1]==0,f"gantt axis labels don't overlap {ov}")
    # templates: new job via form builds schedule
    await E("openForm(null,'jobs')")
    await pg.fill('#mbody [data-k="jobName"]','Test — lifting beam')
    await pg.click('#mbody .segbtn[data-jt="Repair / blast & paint"]')
    ok(await E("document.querySelector('#mbody [data-k=jobType]').value")=="Repair / blast & paint","job type is a one-tap button")
    ok(await E("document.querySelector('#mbody [data-k=optSite]').checked && !document.querySelector('#mbody [data-k=optConcept]').checked"),"job type ticks its workflow options")
    await E("document.querySelector('#mbody [data-k=optFab]').checked=true")
    await E("saveForm()")
    nj=await E("DB.jobs.find(j=>j.jobName==='Test — lifting beam')")
    steps=await E(f"DB.tasks.filter(t=>t.jobRef==='{nj['id']}'&&t.parentTask).sort((a,b)=>a.order-b.order).map(t=>t.stepKey)")
    ok("site" in steps and "fab" in steps and "concept" not in steps and "assembly" not in steps,f"schedule built from type+options ({len(steps)} steps)")
    ok(await E(f"DB.tasks.filter(t=>t.jobRef==='{nj['id']}'&&t.parentTask).every(t=>t.startDate&&t.endDate)"),"every step has planned dates")
    ok(await E(f"DB.tasks.filter(t=>t.jobRef==='{nj['id']}'&&t.parentTask&&t.startDate&&t.status!=='Done').every(t=>isWorkDay(t.startDate))"),"planned starts fall on working days (ticked steps keep their real date — the RFQ may arrive on a Saturday)")
    # auto ticks: quote submitted / PO
    await E(f"openJob('{nj['id']}','schedule');openPhaseAction('{nj['id']}','quoted')");await E("saveForm()")
    ok(await E(f"DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='quoted').status")=="Done","quote submitted ticks its step")
    ok(await E(f"DB.tasks.filter(t=>t.jobRef==='{nj['id']}'&&['site','sitereport','mto','quoteprep'].includes(t.stepKey)).every(t=>t.status==='Done'&&t.inferred)"),"earlier human steps assumed done (≈)")
    await E(f"openPhaseAction('{nj['id']}','po')");await pg.fill('#mbody [data-k="leadMax"]','10');await E("saveForm()")
    ok(await E(f"DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='po').doneDate")==await E("todayISO()"),"PO ticks its step with today's date")
    # QC ticks fabrication
    await E(f"qcSet('{nj['id']}','weld','Pass')")
    ok(await E(f"['fab','qcweld'].every(k=>DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey===k).status==='Done')"),"fabrication QC pass ticks fab + QC steps")
    await E(f"qcSet('{nj['id']}','weld','Pass')")
    ok(await E(f"DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='qcweld').status")!="Done","undoing QC un-ticks the step")
    # manual tick → update logged
    st=await E(f"DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='blast').id")
    await E(f"qcSet('{nj['id']}','blast','Pass')")
    an=await E(f"DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='sitereport').id")
    n0=await E(f"DB.jobs.find(j=>j.id==='{nj['id']}').updates.length")
    await E(f"tickStep('{an}')")
    ok(await E(f"DB.tasks.find(t=>t.id==='{an}').inferred")==False and await E(f"DB.jobs.find(j=>j.id==='{nj['id']}').updates.length")==n0+1,"ticking a step confirms it and logs an update")
    # rebuild keeps done dates
    d=await E(f"DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='po').doneDate")
    await E(f"rebuildSchedule('{nj['id']}')");await E("document.getElementById('askok').onclick()")
    ok(await E(f"DB.tasks.find(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='po').doneDate")==d,"rebuild keeps done dates")
    # template editing
    await E("go('settings');setTab='templates';render()")
    ok(await E("document.querySelectorAll('.tplrow').length")==await E("wfSteps().length"),"template editor lists every step")
    await E("wfAdd()");await pg.fill("#askin","Load test");await E("document.getElementById('askok').onclick()")
    ok(await E("wfSteps().some(s=>s.name==='Load test')"),"add template step")
    await E("startSchedule(DB.jobs.find(j=>j.jobId==='011').id,'Build to client drawing')")
    ok(await E("DB.tasks.some(t=>t.taskName==='Load test'&&t.jobRef===DB.jobs.find(j=>j.jobId==='011').id)"),"new step used by new schedules")
    # settings tabs
    await E("go('settings')")
    for k in ["general","workflow","templates","lists","qc","data"]:
      await E(f"setTab='{k}';render()")
      ok(await E("document.querySelectorAll('.setbody .panel').length")>0,f"settings tab '{k}' has content")
    # suppliers
    await E("go('suppliers')")
    ok(await E("document.querySelectorAll('.supcard').length")==5 and "Will Not Supply" not in await pg.inner_text("#content"),"supplier cards, no confusing status filters")
    await pg.fill("#lsearch","Hempel"); ok(await E("document.querySelectorAll('.supcard').length")==1,"search by brand")
    await pg.fill("#lsearch","U-bolt"); ok(await E("document.querySelectorAll('.supcard').length")>=1,"search by an item they sell")
    await pg.fill("#lsearch","")
    await E("document.querySelector('.supcard').click()"); ok(await E("!!supView") and "what they sell" in (await pg.inner_text("#content")).lower(),"clicking a supplier opens their profile")
    sid=await E("DB.suppliers.find(s=>s.company==='Stainless & Fasteners Co.').id")
    await E(f"openSupplier('{sid}')")
    ok("SS316" in await pg.inner_text("#content"),"stainless supplier lists SS316 items")
    ok(await E(f"supStats(DB.suppliers.find(s=>s.id==='{sid}')).avgReply")==1,"avg reply time computed from RFQs")
    await E(f"openSupItem('{sid}')");await pg.fill('#mbody [data-k="desc"]','Expanded metal 3/4" #9');await pg.fill('#mbody [data-k="price"]','780');await E("saveForm()")
    ok(await E("DB.priceItems.some(i=>i.description==='Expanded metal 3/4\" #9')") and "Expanded metal" in await pg.inner_text("#content"),"add item they sell → price book + profile")
    await E(f"setRating('{sid}','Preferred')"); ok(await E(f"DB.suppliers.find(s=>s.id==='{sid}').rating")=="Preferred","rating saved")
    await E(f"openForm('{sid}','suppliers')");await pg.fill('#mbody [data-k="company"]','SS & Fasteners Ltd');await E("saveForm()")
    ok(await E("DB.priceQuotes.some(q=>q.supplier==='SS & Fasteners Ltd')&&!DB.priceQuotes.some(q=>q.supplier==='Stainless & Fasteners Co.')"),"renaming a supplier keeps its prices")
    # layout
    await E("toggleSide()"); ok(await E("document.querySelector('.app').classList.contains('collapsed')&&localStorage.getItem('protrac_side')==='1'"),"sidebar collapses and remembers")
    await pg.reload();await pg.wait_for_timeout(300); ok(await E("document.querySelector('.app').classList.contains('collapsed')"),"collapsed state survives reload")
    await E("toggleSide()")
    t0=await E("document.documentElement.getAttribute('data-theme')");await E("document.getElementById('tswitch').click()")
    ok(await E("document.documentElement.getAttribute('data-theme')")!=t0 and await E("document.getElementById('tswitch').getAttribute('aria-checked')")==("true" if t0=="light" else "false"),"theme toggle switch")
    ok(await E("!document.querySelector('.side-foot button')"),"side menu has no button stack any more")
    # motion
    await E("go('jobs')"); await pg.wait_for_timeout(30); ok(await E("document.getElementById('content').classList.contains('pgin')"),"page transition on navigation")
    # demo shift
    r=await E("(()=>{const j=DB.jobs.find(j=>j.jobId==='006');const before=jobDueMeta(j).txt;DB.meta.demoAnchor=shiftWD(todayISO(),-5);DB.jobs.forEach(x=>{['rfqDate','poDate','quoteSentDate','rfqDueDate'].forEach(k=>{if(x[k])x[k]=shiftWD(x[k],-5)})});keepDemoCurrent();return [before,jobDueMeta(j).txt,DB.meta.demoAnchor===todayISO()]})()")
    ok(r[2],f"demo dates re-anchored to today {r}")
    ok(not errs,"no errors: "+"; ".join(errs[:2]))
    # phone
    m=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2);mp=await m.new_page()
    await mp.goto(APP);await mp.wait_for_timeout(300)
    for code,name in [("openJob(DB.jobs.find(j=>j.jobId==='009').id,'schedule')","m5_sched"),("go('suppliers')","m5_sup"),("openSupplier(DB.suppliers[0].id)","m5_supp"),("go('settings');setTab='templates';render()","m5_tpl"),("go('dashboard')","m5_dash")]:
      await mp.evaluate(code);await mp.wait_for_timeout(350)
      sw=await mp.evaluate("document.documentElement.scrollWidth"); ok(sw<=392,f"{name}: fits phone ({sw})")
      await mp.screenshot(path=os.path.join(OUT,name+".png"))
    await b.close()
  for c,m_ in res: print(("PASS " if c else "FAIL ")+m_)
  print(sum(c for c,_ in res),"/",len(res))
asyncio.run(main())
