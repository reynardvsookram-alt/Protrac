"""Phase-1 workflow clean-up: new-job form, job page, undo/redo, automation, board, scrollbars, phone layout.
Run: python3 tests/browser_v6.py"""
import os, asyncio
from playwright.async_api import async_playwright
APP = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUT, exist_ok=True)
res = []
def ok(c, m): res.append((bool(c), m))


async def desktop(b):
    ctx = await b.new_context(viewport={"width": 1366, "height": 860}, permissions=["clipboard-read", "clipboard-write"])
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); E = pg.evaluate
    await pg.goto(APP); await pg.wait_for_timeout(400)

    # ---- new-job form: 5 fields up front, the rest under More ----
    await E("go('jobs');openForm(null,'jobs')")
    vis = await E("Array.from(document.querySelectorAll('#mbody [data-k]')).filter(e=>!e.closest('details')&&e.type!=='hidden').map(e=>e.dataset.k)")
    ok(vis == ["jobName", "client", "reqMPI", "reqLoad", "reqWeldMap", "rfqDate", "rfqDueDate"] and await E("document.querySelectorAll('#mbody .segbtn').length") == 5,
       f"new job: name, client, 3 job-type buttons, client requirements + delivery (v8), RFQ date, deadline up front ({vis})")
    ok(await E("!document.querySelector('#mbody [data-k=phase],#mbody [data-k=stage],#mbody [data-k=percent],#mbody [data-k=rfqDays]')"), "no Phase / Stage / % / within-N-days fields")
    ok(await E("document.querySelector('#mbody details.more').open") is False, "More is collapsed")
    ok(await E("document.querySelector('#mbody [data-k=jobId]').value") == "012", "job no. pre-filled with the next number")
    ok(await E("document.querySelector('#mbody [data-k=priority]').value") == "Medium", "priority defaults to Medium")
    ok(await E("document.querySelector('#mbody [data-k=rfqDueDate]').value===addWorkingDays(todayISO(),5)") and await E("document.querySelector('#mbody .qchip.on').dataset.n") == "5",
       "deadline defaults to 5 working days")
    await pg.click("#mbody .qchip[data-n='3']")
    ok(await E("document.querySelector('#mbody [data-k=rfqDueDate]').value===addWorkingDays(todayISO(),3)"), "3 wd chip sets the deadline")
    await pg.fill("#mbody [data-k=rfqDate]", await E("isoAdd(todayISO(),-2)")); await pg.dispatch_event("#mbody [data-k=rfqDate]", "change")
    ok(await E("document.querySelector('#mbody [data-k=rfqDueDate]').value===addWorkingDays(isoAdd(todayISO(),-2),3)"), "changing the RFQ date moves a chip deadline with it")
    await pg.click("#mbody .segbtn[data-jt='Design & build']")
    ok(await E("document.querySelector('#mbody [data-k=optConcept]').checked"), "job-type button ticks its workflow options")
    await E("DB.meta.projectsPath='P:\\\\Projects'")
    await pg.fill("#mbody [data-k=jobName]", "Tank hatch cover")
    await E("(()=>{const s=document.querySelector('#mbody [data-k=client]');s.value=s.options[1].value;})()")
    await E("saveForm()")
    nj = await E("DB.jobs.find(j=>j.jobName==='Tank hatch cover')")
    ok(nj and nj["jobId"] == "012" and nj["phase"] == "RFQ Received" and nj["priority"] == "Medium", "new job saved as 012, RFQ, Medium")
    ok(nj["fileLocation"].startswith("P:\\Projects\\012. ") and nj["fileLocation"].endswith("Tank hatch cover"), f"file location = projects path + folder name ({nj['fileLocation']})")
    ok(await E(f"DB.tasks.some(t=>t.jobRef==='{nj['id']}'&&t.stepKey==='concept')"), "schedule built from the job type")
    await E("openForm(null,'jobs')")
    ok(await E("document.querySelector('#mbody [data-k=client]').value") == nj["client"] and await E("document.querySelector('#mbody .segbtn.on').dataset.jt") == "Design & build",
       "next new job remembers the last client and job type")
    await E("closeForm()")

    # ---- already past RFQ → start at a later phase ----
    await E("openForm(null,'jobs')"); await pg.fill("#mbody [data-k=jobName]", "Running project")
    await E("document.querySelector('#mbody [data-k=_startPhase]').value='In Production'"); await E("saveForm()")
    ok(await E("formMode") == "phase" and await E("!!document.querySelector('#mbody [data-k=leadMax]')"), "start at Production → PO dialog opens")
    await pg.fill("#mbody [data-k=leadMax]", "15"); await E("saveForm()")
    rj = await E("DB.jobs.find(j=>j.jobName==='Running project')")
    ok(rj["phase"] == "In Production" and rj["poDate"] and rj["prodStartDate"], "job lands in production with its PO date")

    # ---- job page: no duplicates, 4 tabs, copy folder name ----
    jid = await E("DB.jobs.find(j=>j.jobId==='006').id")
    await E(f"openJob('{jid}')")
    tabs = await E("Array.from(document.querySelectorAll('.jtabs button')).map(b=>b.textContent.replace(/[^A-Za-z]/g,''))")
    ok(tabs == ["Overview", "Schedule", "Materials", "QC"], f"job tabs {tabs}")
    ok(await E("document.querySelectorAll('.dprog').length") == 1, "one progress bar")
    ok(await E("!document.querySelector('.ovgrid,.ovcounts,.quicksel')"), "no duplicate fact cards, counters or phase dropdowns")
    ok((await E("document.querySelector('.dt').textContent")).startswith("006 · "), "job number in front of the name")
    ok(await E("!!document.getElementById('updtext')"), "post-update box on Overview")
    await E(f"copyFolderName('{jid}')"); await pg.wait_for_timeout(100)
    ok(await E("navigator.clipboard.readText()") == "006. Client B Dual batch mixer — blast, prime & paint", "copy folder name")
    ok("Next: " in await pg.inner_text(".dmeta"), "current step shown on the job page")
    await E(f"openJob('{jid}','procurement')")
    ok(await E("detailTab") == "materials" and "supplier rfqs" in (await pg.inner_text(".jbody")).lower(), "old Procurement tab → Materials tab with RFQs below")

    # ---- undo / redo ----
    await E(f"openJob('{jid}')")
    ok(await pg.locator(".phacts button", has_text="Undo").count() == 1 and await pg.locator(".phacts button", has_text="Redo").count() == 0, "Undo shown, Redo hidden")
    await pg.locator(".phacts button", has_text="Undo").click()
    ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').phase") == "PO Received", "Undo steps back to PO Received (no Procurement phase)")
    await pg.locator(".phacts button", has_text="Redo").click()
    ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').phase") == "In Production", "Redo re-applies")
    await pg.reload(); await pg.wait_for_timeout(300)
    await E(f"openJob('{jid}')"); await pg.locator(".phacts button", has_text="Undo").click(); await pg.reload(); await pg.wait_for_timeout(300); await E(f"openJob('{jid}')")
    ok(await pg.locator(".phacts button", has_text="Redo").count() == 1, "redo survives closing the app")
    await pg.locator(".phacts button", has_text="Redo").click()

    # ---- stepper: every step is clickable ----
    sj = await E("DB.jobs.find(j=>j.jobId==='009').id")
    await E(f"openJob('{sj}')")
    ok(await E("document.querySelectorAll('.stepper button.step').length") == 6, "stepper steps are buttons")
    await pg.click(".stepper .step[data-ph='PO Received']")
    ok(await E("formMode") == "phase" and await E("phaseCtx.action") == "po" and await E("phaseCtx.target") == "PO Received", "tap a later step → its phase dialog")
    await E("closeForm()")
    await pg.click(".stepper .step[data-ph='In Production']")
    ok(await E("phaseCtx.action") == "po" and await E("phaseCtx.target") == "In Production", "skipping ahead past PO asks for the PO first")
    await E("closeForm()")
    await pg.click(".stepper .step[data-ph='RFQ Received']")
    ok("current phase" in (await pg.inner_text("#toast")).lower(), "tap the current step → just says so")
    await E(f"openJob('{jid}')"); await pg.click(".stepper .step[data-ph='Quoted – Awaiting PO']")
    ok(await E("document.getElementById('askscrim').classList.contains('show')"), "tap an earlier step → asks before moving back")
    await E("document.getElementById('askok').onclick()")
    ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').phase") == "Quoted – Awaiting PO" and await E(f"!!DB.jobs.find(j=>j.id==='{jid}').poNumber"), "moved back; PO number kept")
    await pg.locator(".phacts button", has_text="Undo").click()
    ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').phase") == "In Production", "Undo puts it forward again")

    # ---- edit form: phase sections only for phases reached ----
    await E(f"openForm('{jid}','jobs')")
    ks = await E("Array.from(document.querySelectorAll('#mbody [data-k]')).map(e=>e.dataset.k)")
    ok("poNumber" in ks and "quoteSentDate" in ks and "deliveredDate" not in ks and "phase" not in ks, "edit form shows reached phases only")
    await E("closeForm()")
    rfqj = await E("DB.jobs.find(j=>j.jobId==='009').id")
    await E(f"openForm('{rfqj}','jobs')")
    ok(await E("!document.querySelector('#mbody [data-k=poNumber],#mbody [data-k=quoteSentDate]')"), "RFQ job edit form has no quote / PO fields")
    await E("closeForm()")

    # ---- workflow options dialog → auto rebuild (M3 + A2) ----
    await E(f"openJob('{rfqj}','schedule')"); await pg.locator("button", has_text="Workflow options").click()
    ok(await E("formMode") == "wfopts" and await E("document.querySelectorAll('#mbody [data-k]').length") == 10, "workflow options dialog: job type + 5 options + 3 client requirements + delivery")
    had = await E(f"DB.tasks.some(t=>t.jobRef==='{rfqj}'&&t.stepKey==='assembly')")
    await E("document.querySelector('#mbody [data-k=optAssembly]').checked=" + ("false" if had else "true")); await E("saveForm()")
    ok(await E(f"DB.tasks.some(t=>t.jobRef==='{rfqj}'&&t.stepKey==='assembly')") != had, "schedule rebuilt by itself")

    # ---- A1: PO + lead time re-plans the schedule ----
    await E(f"openPhaseAction('{rfqj}','quoted')"); await pg.fill("#mbody [data-k=leadMax]", "12"); await E("saveForm()")
    ok(await E(f"DB.jobs.find(j=>j.id==='{rfqj}').leadMax") == 12, "lead time captured at quote submitted")
    await E(f"openPhaseAction('{rfqj}','po')")
    ok(await E("document.querySelector('#mbody [data-k=leadMax]').value") == "12", "PO dialog pre-filled with the quoted lead time")
    await E("saveForm()")
    ok(await E(f"(()=>{{const j=DB.jobs.find(x=>x.id==='{rfqj}');return DB.tasks.find(t=>t.jobRef===j.id&&t.stepKey==='delivered').endDate===execDue(j)}})()"), "delivery step re-planned to the PO due date")

    # ---- v8: all received → production is OFFERED (he starts production himself), Undo after ----
    pj = await E("DB.jobs.find(j=>j.jobId==='007').id")
    ok(await E(f"DB.jobs.find(j=>j.id==='{pj}').phase") == "PO Received", "demo 007 waits at PO Received (no Procurement phase)")
    await E(f"openJob('{pj}','materials');receiveMats(jobMats('{pj}').map(m=>m.id))")
    ok(await E(f"DB.jobs.find(j=>j.id==='{pj}').phase") == "PO Received", "all lines received → still PO Received")
    ok(await pg.locator("#toast .toastbtn", has_text="Start production").count() == 1, "toast offers Start production")
    await pg.locator("#toast .toastbtn").click(); await pg.wait_for_timeout(60)
    ok(await E("formMode") == "phase" and await E("phaseCtx.action") == "prod", "…which opens the Start production dialog")
    await E("saveForm()")
    ok(await E(f"DB.jobs.find(j=>j.id==='{pj}').phase") == "In Production", "saved → In Production")
    await E(f"openJob('{pj}')"); await pg.locator(".phacts button", has_text="Undo").click()
    ok(await E(f"DB.jobs.find(j=>j.id==='{pj}').phase") == "PO Received", "Undo moves it back to PO Received")

    # ---- A4 + D4: QC ----
    await E(f"openJob('{jid}','checklist');qcSet('{jid}','final','Pass')")
    ok(await pg.locator(".jbody button", has_text="Mark collected").count() == 1, "final inspection passed → Mark collected button (client collects 006)")
    ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').qc.weld.s") == "N/A", "repair job without fabrication: welding QC auto N/A")

    # ---- projects: newest first by default, header still toggles; "Project" wording ----
    await E("go('jobs')")
    nos = await E("Array.from(document.querySelectorAll('tbody tr .jno')).map(e=>e.textContent)")
    ok(nos == sorted(nos, reverse=True) and nos[0] == "013", f"project list newest first ({nos[:3]})")
    await pg.click("thead th:first-child")
    nos2 = await E("Array.from(document.querySelectorAll('tbody tr .jno')).map(e=>e.textContent)")
    ok(nos2 == sorted(nos2), "tap the header → oldest first")
    await E("go('jobs')")
    ok(await E("!/\\bjobs?\\b/i.test(document.body.innerText)") and "Projects" in await pg.inner_text("#nav"), "UI says Project, not Job")
    ok(await E("document.querySelector('.brand .sub, .bname .sub').textContent") == "FabShop Project tracker", "subtitle")
    # ---- search by job number ----
    await E("go('jobs')"); await pg.fill("#lsearch", "4"); await pg.wait_for_timeout(50)
    ok(await E("document.querySelectorAll('tbody tr').length") == 1 and "004" in await pg.inner_text("tbody"), "typing 4 finds job 004")
    await pg.fill("#lsearch", "")
    ok("current step" in (await pg.inner_text("thead")).lower() and "stage" not in (await pg.inner_text("thead")).lower(), "list shows Current step, not Stage")
    ok(await E("!document.querySelector('select[data-filter=stage]')"), "Stage filter gone")

    # ---- board ----
    await E("go('jobs');setView('kanban')"); await pg.wait_for_timeout(150)
    ok(await E("document.querySelectorAll('.laneadd').length") == 1 and await E("!!document.querySelector('.lane[data-status=\"RFQ Received\"] .laneadd')"), "+ Add only on the RFQ lane")
    ok(await E("document.getElementById('board').getBoundingClientRect().bottom<=innerHeight") and await E("document.documentElement.scrollHeight<=innerHeight+2"), "board fills the screen height, page doesn't scroll")
    ok(await E("document.getElementById('board').classList.contains('can-r')&&!document.getElementById('board').classList.contains('can-l')"), "only the right arrow shows at the start")
    ok(await E("getComputedStyle(document.querySelector('.barrow.l')).opacity") == "0", "left arrow hidden")
    await pg.click(".barrow.r"); await pg.wait_for_timeout(600)
    step = await E("(()=>{const l=document.querySelectorAll('.lane');return l[1].offsetLeft-l[0].offsetLeft})()")
    ok(abs(await E("document.getElementById('boardscroll').scrollLeft") - step) < 3, "one click = one lane")
    ok(await E("document.getElementById('board').classList.contains('can-l')"), "left arrow appears")
    await pg.click(".barrow.l"); await pg.wait_for_timeout(600)
    ok(await E("document.getElementById('boardscroll').scrollLeft") < 3, "left arrow goes back one lane")
    # all the way right (the end isn't on a lane edge), then the left arrow must still step back lane by lane
    for _ in range(8):
        if not await E("document.getElementById('board').classList.contains('can-r')"): break
        await pg.click(".barrow.r"); await pg.wait_for_timeout(650)
    xs = [await E("document.getElementById('boardscroll').scrollLeft")]
    ok(not await E("document.getElementById('board').classList.contains('can-r')"), "right arrow reaches the end and hides")
    for _ in range(8):
        if not await E("document.getElementById('board').classList.contains('can-l')"): break
        await pg.click(".barrow.l"); await pg.wait_for_timeout(650); xs.append(await E("document.getElementById('boardscroll').scrollLeft"))
    ok(len(xs) > 2 and all(b < a for a, b in zip(xs, xs[1:])) and xs[-1] < 3, f"from the far right, left arrow steps back every click to the start ({[round(x) for x in xs]})")
    hb = await pg.locator(".lane[data-status='PO Received'] .lanehd").bounding_box()
    await pg.mouse.move(hb["x"] + 20, hb["y"] + 10); await pg.mouse.wheel(0, 200); await pg.wait_for_timeout(200)
    ok(await E("document.getElementById('boardscroll').scrollLeft") > 100, "wheel over a lane header scrolls the board sideways")
    await E("document.getElementById('boardscroll').scrollLeft=0"); await pg.wait_for_timeout(100)
    await E("(()=>{const lb=document.querySelector('.lane .lanebody');lb.style.maxHeight='120px';})()")
    cb = await pg.locator(".lane[data-status='RFQ Received'] .lanebody").bounding_box()
    await pg.mouse.move(cb["x"] + 40, cb["y"] + 40); await pg.mouse.wheel(0, 150); await pg.wait_for_timeout(200)
    ok(await E("document.getElementById('boardscroll').scrollLeft") < 3 and await E("document.querySelector('.lane .lanebody').scrollTop") > 0, "wheel over a lane's cards scrolls that lane")
    await E("document.querySelector('.lane .lanebody').style.maxHeight=''")
    await pg.keyboard.down("Shift"); await pg.mouse.wheel(0, 200); await pg.keyboard.up("Shift"); await pg.wait_for_timeout(200)
    ok(await E("document.getElementById('boardscroll').scrollLeft") > 100, "Shift+wheel scrolls sideways anywhere")
    # horizontal wheel (mouse thumb wheel / touchpad) over the cards moves the board both ways
    await E("document.getElementById('boardscroll').scrollLeft=0"); await pg.wait_for_timeout(100)
    cb2 = await pg.locator(".lane[data-status='RFQ Received'] .kcard").first.bounding_box()
    await pg.mouse.move(cb2["x"] + 40, cb2["y"] + 20)
    for _ in range(6): await pg.mouse.wheel(300, 0); await pg.wait_for_timeout(80)
    far = await E("document.getElementById('boardscroll').scrollLeft")
    for _ in range(8): await pg.mouse.wheel(-300, 0); await pg.wait_for_timeout(80)
    ok(far > 300 and await E("document.getElementById('boardscroll').scrollLeft") < 3, f"thumb wheel scrolls the board right and back left, over the cards too ({round(far)})")
    await E("document.getElementById('boardscroll').scrollLeft=0"); await pg.wait_for_timeout(100)
    # mouse drag RFQ card → Quoted lane opens the phase dialog
    src = await pg.locator(".lane[data-status='RFQ Received'] .kcard").first.bounding_box()
    dst = await pg.locator(".lane[data-status='Quoted – Awaiting PO'] .lanebody").bounding_box()
    await pg.mouse.move(src["x"] + 30, src["y"] + 20); await pg.mouse.down()
    for i in range(1, 11):
        await pg.mouse.move(src["x"] + 30 + (dst["x"] + 60 - src["x"] - 30) * i / 10, src["y"] + 20 + (dst["y"] + 80 - src["y"] - 20) * i / 10)
    ok(await E("!!document.querySelector('.kghost')&&!!document.querySelector('.lane.drop')"), "dragging shows a ghost card and highlights the lane")
    await pg.mouse.up(); await pg.wait_for_timeout(150)
    ok(await E("formMode") == "phase" and await E("phaseCtx.action") == "quoted", "drop on Quoted opens the quote dialog")
    await E("closeForm()")
    await pg.locator(".kcard").first.click(); await pg.wait_for_timeout(100)
    ok(await E("!!detailJob"), "a plain click on a card opens the job")
    await pg.screenshot(path=os.path.join(OUT, "v6_desk_job.png"))

    # ---- dashboard search results sit above the Attention cards (was hidden behind them) ----
    for w, hgt in [(1366, 800), (1024, 700)]:
        await pg.set_viewport_size({"width": w, "height": hgt})
        await E("DB.meta.hideGuide=true;save();go('dashboard')"); await pg.wait_for_timeout(30)
        await pg.fill("#gsq", "rhs"); await pg.wait_for_timeout(80)
        for when in ("during the page animation", "after it"):
            hidden = await E("""(()=>{const c=document.querySelector('.attgrid').getBoundingClientRect();return [...document.querySelectorAll('#gsres .gsitem')].filter(it=>{const q=it.getBoundingClientRect();if(q.bottom<c.top||q.top>c.bottom)return false;const e=document.elementFromPoint(q.left+q.width/2,q.top+q.height/2);return !(e&&e.closest('#gsres'));}).length})()""")
            over = await E("(()=>{const c=document.querySelector('.attgrid').getBoundingClientRect();return [...document.querySelectorAll('#gsres .gsitem')].filter(it=>{const q=it.getBoundingClientRect();return q.bottom>c.top&&q.top<c.bottom}).length})()")
            ok(over > 0 and hidden == 0, f"{w}px: search results drawn over the Attention cards {when} ({over} overlap, {hidden} hidden)")
            await pg.wait_for_timeout(500)
        await pg.keyboard.press("Escape")
        ok(await E("document.getElementById('gsres').innerHTML") == "", f"{w}px: Escape closes the results")
    await pg.set_viewport_size({"width": 1366, "height": 860})

    # ---- price book: remove a wrong price; warn on a price that looks off ----
    await E("go('prices')")
    grp = await E("[...document.querySelectorAll('#prows .pgrp')].map(g=>[g.querySelector('h4').textContent.replace(/\\s*\\d+$/,''),[...g.querySelectorAll('thead th.pcol')].map(t=>t.textContent).slice(0,-1)])")
    ok(len(grp) > 10 and all(h == sorted(h) for _, h in grp), "price book: one table per category, supplier columns A→Z")
    gd = dict(grp)
    ok(gd.get("Angle") == ["Supplier A", "Supplier B"] and gd.get("Paint & Coatings") == ["Coatings Distributor"] and "Abrasives" not in gd, f"each category shows only its own suppliers (Paint & Coatings: {gd.get('Paint & Coatings')}); demo has no Abrasives")
    await E("DB.meta.priceCategories=(DB.meta.priceCategories||[]).concat(['Empty cat']);save();removePriceCat('Empty cat')")
    ok(await E("!priceCats().includes('Empty cat')"), "empty category removes straight away")
    await E("['T-1','T-2'].forEach((c,i)=>{const it={id:'tmp'+i,code:c,category:'Temp cat',description:'Temp item '+i,tags:'',stockLength:'',grade:'',uom:'Each',notes:'',synonyms:''};DB.priceItems.push(it);DB.priceQuotes.push({id:'tq'+i,itemRef:it.id,supplier:'Supplier A',date:todayISO(),price:10,response:'Quoted',note:'',seq:9999+i});});save()")
    nh = await E("DB.priceItems.filter(i=>i.category==='Temp cat').length"); nq0 = await E("DB.priceQuotes.length")
    await E("removePriceCat('Temp cat')")
    ok(await E("document.getElementById('askscrim').classList.contains('show')") and f"{nh} item" in await pg.inner_text("#askbody"), "category with items: asks first, says how many")
    await E("document.getElementById('askok').onclick()")
    ok(await E("!priceCats().includes('Temp cat')&&!DB.priceItems.some(i=>i.category==='Temp cat')") and await E("DB.priceQuotes.length") == nq0 - 2, "category, its items and their prices deleted")
    cats = await E("priceCats()")
    ok("Miscellaneous" in cats and not {"Abrasives", "Hoses", "Consumables"} & set(cats) and cats == sorted(cats), "demo: Abrasives & Hoses gone, Consumables → Miscellaneous, categories A→Z")
    ok(await E("!DB.priceItems.some(i=>/^Masking tape|^Poly sheeting/.test(i.description))"), "demo: masking tape and poly sheeting items removed")
    ok(await E("DB.priceItems.every(i=>bestPrice(i))"), "demo: every price-book item has a price")
    ok(await E("DB.priceQuotes.filter(q=>q.response==='Estimate').every(q=>/estimate/i.test(q.note))") and await E("!DB.priceItems.some(i=>i.code==='PL-10')"), "drafted prices are labelled estimates; 1-inch A572 cut-pieces item removed")
    ok(await E("(()=>{go('prices');priceCat='Pipe Fittings';render();const n=document.querySelectorAll('#prows .estflag').length;priceCat='';render();return n>0})()"), "estimates show est. in the price book")
    did = await E("DB.priceItems.find(i=>i.category==='Miscellaneous').id")
    await E(f"openPriceItem('{did}')"); await pg.locator("#mbody button", has_text="Delete item").click(); await E("document.getElementById('askok').onclick()")
    ok(await E(f"!priceItem('{did}')&&!DB.priceQuotes.some(q=>q.itemRef==='{did}')"), "Delete item removes it and its prices")
    await E("go('prices')")
    ok(await E("[...document.querySelectorAll('#prows tbody tr')].every(r=>r.children.length===r.closest('table').querySelectorAll('thead th').length)"), "every row lines up with its headings")
    it9 = await E("DB.priceItems.find(i=>i.code==='RHS-09').id")
    await E(f"openQuoteForm('{it9}')"); await pg.fill("#mbody [data-k=supplier]", "Supplier B"); await pg.fill("#mbody [data-k=price]", "45")
    n0 = await E("DB.priceQuotes.length"); await E("saveForm()"); await pg.wait_for_timeout(50)
    ok(await E("document.getElementById('askscrim').classList.contains('show')") and "98% lower" in await pg.inner_text("#askbody"), "typo price ($45 vs $2,000) → Check this price")
    ok(await E("DB.priceQuotes.length") == n0, "nothing saved until you decide")
    await pg.click("#askcancel")
    ok(await E("document.getElementById('scrim').classList.contains('show')") and await E("DB.priceQuotes.length") == n0, "Fix → back to the form, nothing saved")
    await pg.fill("#mbody [data-k=price]", "2100"); await E("saveForm()"); await pg.wait_for_timeout(50)
    ok(await E("DB.priceQuotes.length") == n0 + 1 and not await E("document.getElementById('askscrim').classList.contains('show')"), "a sensible price saves without a warning")
    await E(f"openQuoteForm('{it9}')"); await pg.fill("#mbody [data-k=supplier]", "Supplier B"); await pg.fill("#mbody [data-k=price]", "45"); await E("saveForm()"); await pg.wait_for_timeout(50)
    await pg.click("#askok"); await pg.wait_for_timeout(50)
    ok(await E("DB.priceQuotes.length") == n0 + 2 and await E(f"bestPrice(priceItem('{it9}')).price") == 45, "Keep → saved as typed")
    await E(f"openPriceItem('{it9}')")
    await pg.locator("#mbody tr", has_text="$45").locator("button[title='Remove this price']").click()
    ok("$45" in await pg.inner_text("#askbody"), "✕ asks before removing")
    await pg.click("#askok"); await pg.wait_for_timeout(50)
    ok(await E("DB.priceQuotes.length") == n0 + 1 and await E(f"bestPrice(priceItem('{it9}')).price") == 2100 and "$45" not in await pg.inner_text("#mbody"), "wrong price removed; best price back to the real one ($2,100 logged above)")
    await E("closeForm()")
    # RFQ reply: an off price warns, and removing it also clears it from the reply
    rid = await E("(()=>{const r=DB.procurement.find(r=>rfqMats(r).some(m=>m.priceItemRef)&&(r.suppliers||[]).length);return r&&r.id})()")
    if rid:
        lid = await E(f"DB.procurement.find(r=>r.id==='{rid}').suppliers[0].id")
        mid = await E(f"rfqMats(DB.procurement.find(r=>r.id==='{rid}')).find(m=>m.priceItemRef&&lastPrice(m.priceItemRef)).id")
        lastp = await E(f"+lastPrice(DB.materials.find(m=>m.id==='{mid}').priceItemRef).price")
        await E(f"openQuote('{rid}','{lid}')"); await pg.fill(f"#mbody [data-mp='{mid}']", str(round(lastp / 40, 2))); await E("saveForm()"); await pg.wait_for_timeout(50)
        ok(await E("document.getElementById('askscrim').classList.contains('show')"), "Enter quote on an RFQ: off price → Check this price")
        await pg.click("#askok"); await pg.wait_for_timeout(50)
        qid = await E(f"(DB.priceQuotes.find(q=>q.srcLine==='{lid}'&&q.itemRef===DB.materials.find(m=>m.id==='{mid}').priceItemRef)||{{}}).id")
        ok(qid, "kept price logged from the RFQ reply")
        await E(f"delPriceQuote('{qid}')"); await E("document.getElementById('askok').onclick()")
        ok(await E(f"!(DB.procurement.find(r=>r.id==='{rid}').suppliers[0].prices||{{}})['{mid}']"), "removing it clears that item on the RFQ reply too")
        await E("closeForm()")

    # ---- calendar: 7 equal columns even with long names; weeks start Monday; today marked ----
    await E("DB.jobs[0].jobName='A very long project name that used to stretch its calendar column across the page';save();go('jobs');setView('calendar')"); await pg.wait_for_timeout(100)
    cols = await E("getComputedStyle(document.querySelector('.calgrid')).gridTemplateColumns.split(' ').map(parseFloat)")
    ok(len(cols) == 7 and max(cols) - min(cols) < 1.5, f"calendar: 7 equal columns ({[round(x) for x in cols]})")
    ok(await E("document.querySelector('.calgrid').getBoundingClientRect().right<=document.querySelector('.cal').getBoundingClientRect().right+1"), "calendar fits its card (Sunday column visible)")
    ok(await E("(()=>{const c=[...document.querySelectorAll('.calcell')];const i=c.findIndex(x=>x.dataset.date===todayISO());return i>=0&&c[i].classList.contains('today')&&((new Date(todayISO()+'T00:00:00').getDay()+6)%7)===i%7})()"), "today sits under the right weekday and is highlighted")
    ok(await E("(()=>{const c=[...document.querySelectorAll('.calcell')];return c.every((x,i)=>((new Date(x.dataset.date+'T00:00:00').getDay()+6)%7)===i%7)})()"), "every date sits under its weekday (Mon-first)")
    ok("Today is" in await pg.inner_text(".todaypill"), "calendar states today's date")
    await E("calNav(1)"); await E("calNav(-1)"); await E("calToday()")

    # ---- every text field matches the theme (no square white browser-default boxes, e.g. the quick reminder) ----
    await E("setTheme('dark')")
    bad = []
    for code in ["go('dashboard')", "go('reminders')", "go('settings');setTab='lists';render()", "go('settings');setTab='qc';render()", "go('settings');setTab='workflow';render()", "go('prices')", "go('purchasing')"]:
        await E(code); await pg.wait_for_timeout(60)
        bad += await E("[...document.querySelectorAll('#content input:not([type=checkbox]):not([type=radio]):not([type=hidden]),#content select,#content textarea')].filter(e=>e.offsetParent).filter(e=>{const c=getComputedStyle(e);return c.backgroundColor==='rgb(255, 255, 255)'||parseFloat(c.borderTopLeftRadius)<4}).map(e=>e.id||e.getAttribute('placeholder')||e.tagName)")
    ok(not bad, f"all fields styled for the theme in dark mode {bad[:5]}")
    await E("setTheme('light')")

    # ---- scrollbars ----
    await E("go('prices')")
    ok(await E("getComputedStyle(document.querySelector('.tablewrap')).scrollbarWidth") == "thin", "desktop scrollbars are thin")
    await pg.mouse.move(5, 5)
    ok((await E("getComputedStyle(document.querySelector('.tablewrap')).scrollbarColor")).startswith("rgba(0, 0, 0, 0)"), "desktop scrollbar hidden until hover / scroll")
    ok(not errs, "no page errors (desktop): " + "; ".join(errs[:3]))
    await ctx.close()


async def phone(b):
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); E = pg.evaluate
    await pg.goto(APP); await pg.wait_for_timeout(400)
    await E("go('jobs');openForm(null,'jobs')"); await pg.wait_for_timeout(200)
    ok(await E("document.querySelector('#mainmodal footer').getBoundingClientRect().bottom<=innerHeight"), "phone: new-job form fits one screen (Save visible)")
    await E("closeForm()")
    for name, code in [("jobs", "go('jobs')"), ("job", "openJob(DB.jobs.find(j=>j.jobId==='006').id)"), ("jobmat", "openJob(DB.jobs.find(j=>j.jobId==='006').id,'materials')"),
                       ("board", "go('jobs');setView('kanban')"), ("settings", "go('settings');setTab='workflow';render()")]:
        await E(code); await pg.wait_for_timeout(200)
        ok(await E("document.documentElement.scrollWidth<=390"), f"phone {name}: no horizontal page scroll")
    await E("go('jobs');setView('calendar')"); await pg.wait_for_timeout(150)
    ok(await E("document.documentElement.scrollWidth<=390") and await E("(()=>{const c=getComputedStyle(document.querySelector('.calgrid')).gridTemplateColumns.split(' ').map(parseFloat);return c.length===7&&Math.max(...c)-Math.min(...c)<1.5})()"), "phone calendar: 7 equal columns, no sideways scroll")
    ok(await E("getComputedStyle(document.querySelector('.calagenda')).display") != "none", "phone calendar: dated list under the grid")
    await E("openJob(DB.jobs.find(j=>j.jobId==='006').id)")
    ok(await E("(()=>{const t=document.querySelector('.jtabs');return t.scrollWidth<=t.clientWidth+1})()"), "phone: 4 job tabs fit without scrolling")
    ok(await E("getComputedStyle(document.documentElement).scrollbarWidth") == "none", "phone: no visible scrollbars")
    # touch drag: press-and-hold a card, drag it onto the next lane
    await E("go('jobs');setView('kanban')"); await pg.wait_for_timeout(200)
    ok(await E("getComputedStyle(document.querySelector('.barrow.r')).display") == "none", "phone: no arrows (swipe)")
    cdp = await ctx.new_cdp_session(pg)
    card = await pg.locator(".lane[data-status='RFQ Received'] .kcard").first.bounding_box()
    x0, y0 = card["x"] + 40, card["y"] + 30
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
    await pg.wait_for_timeout(450)
    ok(await E("!!document.querySelector('.kghost')"), "phone: press-and-hold picks the card up")
    x1, y1 = 368, y0 + 40   # near the right edge: the board auto-scrolls the next lane in
    for i in range(1, 13):
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / 12, "y": y0 + (y1 - y0) * i / 12}]})
        await pg.wait_for_timeout(30)
    await pg.wait_for_timeout(250)
    lane = await E("(()=>{const l=document.querySelector('.lane.drop');return l?l.dataset.status:''})()")
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); await pg.wait_for_timeout(200)
    ok(lane and lane != "RFQ Received" and await E("formMode") == "phase", f"phone: touch drag to another lane opens the phase dialog ({lane})")
    await E("closeForm()")
    # a quick swipe (no hold) scrolls the board instead of dragging
    await E("render()"); await pg.wait_for_timeout(150)
    card = await pg.locator(".lane[data-status='RFQ Received'] .kcard").first.bounding_box()
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": card["x"] + 200, "y": card["y"] + 30}]})
    for i in range(1, 8):
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": card["x"] + 200 - 25 * i, "y": card["y"] + 30}]}); await pg.wait_for_timeout(16)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); await pg.wait_for_timeout(400)
    ok(await E("!document.querySelector('.kghost')") and await E("formMode") != "phase" and await E("!detailJob"), "phone: a quick swipe doesn't pick a card up")
    # finger swipes: all the way right, then all the way back left, starting on a card
    async def swipe(x0, x1, y):
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y}]})
        for i in range(1, 11):
            await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / 10, "y": y}]}); await pg.wait_for_timeout(16)
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); await pg.wait_for_timeout(450)
    await E("go('jobs');setView('kanban');document.getElementById('boardscroll').scrollLeft=0"); await pg.wait_for_timeout(250)
    bx = await E("(()=>{const r=document.getElementById('boardscroll').getBoundingClientRect();return [r.left,r.right]})()")
    yc = (await pg.locator(".lane .kcard").first.bounding_box())["y"] + 30
    for _ in range(8): await swipe(bx[1] - 25, bx[0] + 25, yc)
    right = await E("document.getElementById('boardscroll').scrollLeft")
    for _ in range(9): await swipe(bx[0] + 25, bx[1] - 25, yc)
    ok(right > 800 and await E("document.getElementById('boardscroll').scrollLeft") < 3 and await E("!detailJob"), f"phone: swipe all the way right ({round(right)}) and all the way back left")
    await pg.screenshot(path=os.path.join(OUT, "v6_phone_board.png"))
    ok(not errs, "no page errors (phone): " + "; ".join(errs[:3]))
    await ctx.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await desktop(b)
        await phone(b)
        await b.close()
    for c, m in res: print(("PASS " if c else "FAIL ") + m)
    f = sum(1 for c, _ in res if not c); print(f"\n{len(res)-f} passed, {f} failed"); raise SystemExit(1 if f else 0)

asyncio.run(main())
