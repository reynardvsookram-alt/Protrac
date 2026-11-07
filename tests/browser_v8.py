"""v8 flow (desktop): no Procurement phase, Start production, client requirements, MPI → load test → MPI order,
Delivered / Collected → Documents & handover, in-stock material lines, costing warnings, board / dashboard / calendar.
Run: python3 tests/browser_v8.py"""
import os, asyncio
from playwright.async_api import async_playwright
APP = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUT, exist_ok=True)
res = []
def ok(c, m): res.append((bool(c), m))


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); E = pg.evaluate
        await pg.goto(APP); await pg.wait_for_timeout(400)
        await E("DB.meta.hideGuide=true;save()")

        # ---- board: no Procurement lane, Documents & handover before Complete ----
        await E("go('jobs');setView('kanban')"); await pg.wait_for_timeout(100)
        lanes = await E("[...document.querySelectorAll('.lane .ln')].map(e=>e.textContent)")
        ok(lanes == ["RFQ Received", "Quoted – Awaiting PO", "PO Received", "In Production", "Documents & handover", "Complete", "Lost / Declined"], f"board lanes ({lanes})")
        ok(await pg.locator(".kcard .matbadge").count() >= 2, "board cards show the materials badge")

        # ---- new project: requirement ticks + delivery, pre-ticked by project type ----
        await E("openForm(null,'jobs')")
        ok(await E("document.querySelector('#mbody [data-k=reqMPI]').checked") and not await E("document.querySelector('#mbody [data-k=reqLoad]').checked"), "Build to client drawing → MPI ticked, load test not")
        await pg.locator("#mbody .segbtn", has_text="Repair / blast & paint").click()
        ok(not await E("document.querySelector('#mbody [data-k=reqMPI]').checked"), "Repair / blast & paint → MPI unticked")
        await pg.locator("#mbody .segbtn", has_text="Design & build").click()
        await pg.fill("#mbody [data-k=jobName]", "Pad-eye test frame")
        await pg.locator("#mbody .optchk", has_text="Load test").click()
        await pg.locator("#mbody .dvbtns .segbtn", has_text="Client collects").click()
        await E("saveForm()"); await pg.wait_for_timeout(100)
        jid = await E("DB.jobs.find(j=>j.jobName==='Pad-eye test frame').id")
        ok(await E(f"(()=>{{const j=DB.jobs.find(x=>x.id==='{jid}');return j.reqMPI&&j.reqLoad&&!j.reqWeldMap&&j.delivery==='client'}})()"), "ticks and 'Client collects' saved on the project")
        keys = await E(f"DB.tasks.filter(t=>t.jobRef==='{jid}'&&t.stepKey).map(t=>t.stepKey)")
        ok(all(k in keys for k in ["mpi", "loadtest", "mpi2", "docs"]) and "weldmaps" not in keys, "schedule gets MPI → load test → MPI after → documents (no weld maps)")
        order = [k for k in keys if k in ("fab", "mpi", "loadtest", "mpi2", "blast", "coat")]
        ok(order == ["fab", "mpi", "loadtest", "mpi2", "blast", "coat"], f"steps in his order ({order})")

        # ---- quote: warnings for uncosted requirements ----
        await E(f"openPhaseAction('{jid}','quoted')")
        txt = await pg.inner_text("#mbody")
        ok("MPI is required but not costed" in txt and "Load test is required but not costed" in txt and "Transport" not in txt, "quote dialog warns: MPI + load test not costed (client collects → no transport warning)")
        await E("saveForm()")
        # ---- PO: confirm requirements (add weld maps) ----
        await E(f"openPhaseAction('{jid}','po')")
        ok(await pg.locator("#mbody", has_text="Confirm client requirements").count() == 1, "PO dialog asks to confirm client requirements")
        await pg.fill("#mbody [data-k=leadMax]", "15"); await pg.locator("#mbody .optchk", has_text="Weld maps").click()
        await E("saveForm()"); await pg.wait_for_timeout(100)
        ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').reqWeldMap") and await E(f"DB.tasks.some(t=>t.jobRef==='{jid}'&&t.stepKey==='weldmaps')"), "weld maps added at the PO → step added to the schedule")
        await E(f"openJob('{jid}')")
        ok(await pg.locator(".phacts button", has_text="Start production").count() == 1, "PO Received → Start production button")
        ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').phase") == "PO Received", "still PO Received until he starts production")
        await pg.locator(".phacts button", has_text="Start production").click(); await E("saveForm()"); await pg.wait_for_timeout(100)
        ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').phase") == "In Production", "Start production → In Production")

        # ---- QC tab: inspection order is enforced ----
        await E(f"openJob('{jid}','checklist')")
        names = await E("[...document.querySelectorAll('.qcname')].map(e=>e.textContent)")
        ok(names[:4] == ["Welding / Fabrication", "MPI — welds", "Load test — pad eyes", "MPI — pad eyes after load test"], f"QC rows in order ({names[:4]})")
        await E(f"qcSet('{jid}','mpi','Fail')"); await pg.fill("#askin", "linear indication on pad eye weld"); await pg.click("#askok"); await pg.wait_for_timeout(60)
        await E(f"qcSet('{jid}','load','Pass')"); await pg.wait_for_timeout(60)
        ok(await E("document.getElementById('askscrim').classList.contains('show')") and "failed" in (await pg.inner_text("#askbody")), "load test blocked while MPI has failed")
        await pg.click("#askcancel")
        ok(not await E(f"(DB.jobs.find(j=>j.id==='{jid}').qc.load||{{}}).s"), "…and not recorded")
        await E(f"qcSet('{jid}','mpi','Pass');qcSet('{jid}','load','Pass')"); await pg.wait_for_timeout(60)
        await E(f"qcSet('{jid}','blast','Pass')"); await pg.wait_for_timeout(60)
        ok("isn't recorded yet" in await pg.inner_text("#askbody"), "blast before the pad-eye MPI asks first")
        await pg.click("#askcancel")
        await E(f"qcSet('{jid}','mpi2','Pass');qcSet('{jid}','blast','Pass')"); await pg.wait_for_timeout(60)
        ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').qc.blast.s") == "Pass", "all inspections passed → blast records")
        ok(await E(f"DB.tasks.find(t=>t.jobRef==='{jid}'&&t.stepKey==='mpi2').status") == "Done", "schedule ticks the after-load-test MPI itself")

        # ---- collected → documents & handover → closed ----
        await E(f"openJob('{jid}')"); await pg.locator(".phacts button", has_text="Collected by client").click()
        ok("Documents & handover" in await pg.inner_text("#mbody"), "collect dialog says the documents phase comes next")
        await E("saveForm()"); await pg.wait_for_timeout(80)
        ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').phase") == "Documents & handover", "collected → Documents & handover")
        steps = await E("[...document.querySelectorAll('.stepper .slbl')].map(e=>e.textContent)")
        ok(steps == ["RFQ", "Quoted", "PO", "Production", "Documents", "Complete"], f"stepper matches the board: … Production → Documents → Complete ({steps})")
        ok((await E("document.querySelectorAll('.stepper .sdate')[4].textContent")).startswith("Collected "), "the Documents step is dated by the collection")
        ok("Documents due" in await pg.inner_text(".dmeta"), "documents due date shown")
        await E("go('dashboard')")
        ok(await pg.locator(".attcard", has_text="Documents to hand over").count() == 1, "dashboard: Documents to hand over card")
        ok("Hand over documents" in await pg.inner_text(".o-dl"), "upcoming deadlines: hand over documents")
        await E(f"openJob('{jid}')"); await pg.locator(".phacts button", has_text="Documents handed over").click(); await E("saveForm()"); await pg.wait_for_timeout(80)
        ok(await E(f"(()=>{{const j=DB.jobs.find(x=>x.id==='{jid}');return j.phase==='Delivered'&&!!j.docsSentDate&&isClosed(j)}})()"), "documents handed over → closed")
        ok("Collected" in await pg.inner_text(".dmeta"), "closed project reads 'Collected'")

        # ---- in-stock material lines ----
        await E(f"DB.materials.push({{id:'is1',jobRef:'{jid}',description:'Off-cut 3/8 plate',qtyReq:1}},{{id:'is2',jobRef:'{jid}',description:'Angle 2x2x1/4',qtyReq:2}});save();openJob('{jid}','materials')")
        await pg.locator("tr", has_text="Off-cut 3/8 plate").locator("button", has_text="In stock").click()
        ok(await E("DB.materials.find(m=>m.id==='is1').inStock") and await pg.locator("tr", has_text="Off-cut 3/8 plate").locator(".mchip", has_text="In stock").count() >= 1, "In stock toggle on the material row")
        await E(f"matSel=new Set(['is1','is2']);renderDetail()"); await pg.locator(".bulkbar button", has_text="Send supplier RFQ").click(); await pg.wait_for_timeout(60)
        ok(await E("impCtx&&impCtx.ids.join()") == "is2", "supplier RFQ leaves the in-stock line out")
        await E("closeForm()")

        # ---- calendar legend + settings text ----
        await E("go('jobs');setView('calendar')")
        ok("Documents due" in await pg.inner_text(".callegend"), "calendar legend has Documents due")
        await E("go('settings');setTab='workflow';render()")
        st = await pg.inner_text("#content")
        ok("Procurement" not in st and "Documents handed over" in st, "Settings: flow text updated, documents target / overdue days editable")

        # ---- nothing anywhere still offers Procurement as a phase ----
        await E("go('jobs');setView('grid')")
        opts = await E("[...document.querySelectorAll('select')].flatMap(s=>[...s.options].map(o=>o.textContent))")
        ok("Procurement" not in opts, "no Procurement option in any phase filter")
        for theme in ("light", "dark"):
            await E(f"setTheme('{theme}');openJob('{jid}')"); await pg.wait_for_timeout(150)
            await pg.screenshot(path=os.path.join(OUT, f"v8_job_{theme}.png"))
        # ---- project list: one ⋯ per row, hover → floating menu with the 4 actions; wider Project column ----
        await E("go('jobs');setView('grid')"); await pg.wait_for_timeout(150)
        ok(await E("document.querySelectorAll('tbody tr .icobtn').length") == 0 and await E("document.querySelectorAll('tbody tr .kebab').length") == await E("filteredRows().length"), "one ⋯ button per row, no icon strip")
        ok(await E("document.querySelector('thead th.pcol').getBoundingClientRect().width") >= 260, "Project column gets the freed width (≥ 260 px)")
        await pg.locator("tbody tr").nth(1).locator(".kebab").hover(); await pg.wait_for_timeout(200)
        items = await E("[...document.querySelectorAll('#rowmenu.show button')].map(b=>b.textContent.trim())")
        ok(items == ["▸Open project", "📁Open file", "✏️Edit", "🗑Delete"], f"hover shows the floating menu ({items})")
        ok(await E("(()=>{const m=document.getElementById('rowmenu').getBoundingClientRect();return m.right<=innerWidth&&m.bottom<=innerHeight})()"), "menu stays inside the window")
        await pg.locator("#rowmenu button", has_text="Edit").click(); await pg.wait_for_timeout(100)
        ok(await E("document.getElementById('scrim').classList.contains('show')") and await E("!!editingId"), "Edit opens the project form")
        await E("closeForm()")
        await pg.locator("tbody tr").nth(0).locator(".kebab").click(); await pg.wait_for_timeout(150)
        await pg.locator("#rowmenu button", has_text="Open project").click(); await pg.wait_for_timeout(100)
        ok(await E("!!detailJob"), "click works too: Open project")
        await E("go('jobs')"); await pg.locator("tbody tr").nth(0).locator(".kebab").click(); await pg.wait_for_timeout(100)
        await pg.keyboard.press("Escape")
        ok(not await E("document.getElementById('rowmenu').classList.contains('show')"), "Escape closes the menu")
        # keyboard only (I3): Tab to the ⋯, Enter opens and focuses the first option, arrows move, Escape returns to the ⋯
        await E("go('jobs')"); await pg.wait_for_timeout(400); await E("document.querySelectorAll('tbody tr .kebab')[2].focus()")
        await pg.keyboard.press("Enter"); await pg.wait_for_timeout(80)
        ae = await E("[document.activeElement.tagName,document.activeElement.className,document.activeElement.textContent.slice(0,24),(document.getElementById('rowmenu')||{}).className]")
        ok(await E("!!(document.activeElement.closest('#rowmenu')&&document.activeElement.textContent.includes('Open project'))"), f"keyboard: Enter on ⋯ opens the menu with Open project focused ({ae})")
        await pg.keyboard.press("ArrowDown"); await pg.keyboard.press("ArrowDown")
        ok(await E("!!document.activeElement.closest('#rowmenu')&&document.activeElement.textContent.includes('Edit')"), "keyboard: arrow keys move through the options")
        await pg.keyboard.press("ArrowUp"); await pg.keyboard.press("ArrowUp"); await pg.keyboard.press("ArrowUp")
        ok(await E("!!document.activeElement.closest('#rowmenu')&&document.activeElement.textContent.includes('Delete')"), "keyboard: arrows wrap round")
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(50)
        ok(await E("document.activeElement.classList.contains('kebab')&&document.activeElement.getAttribute('aria-expanded')==='false'") and not await E("document.getElementById('rowmenu').classList.contains('show')"), "keyboard: Escape closes and returns to the ⋯")
        await pg.keyboard.press("Enter"); await pg.wait_for_timeout(60); await pg.keyboard.press("ArrowDown"); await pg.keyboard.press("ArrowDown"); await pg.keyboard.press("Enter"); await pg.wait_for_timeout(100)
        ok(await E("document.getElementById('scrim').classList.contains('show')&&!!editingId"), "keyboard: Enter on Edit opens the project form")
        await E("closeForm()")

        # ---- review fixes: list wording (B1), filter, 1366 px fit (I1), in-stock message (B4), delivery asked when unknown (I5) ----
        await E("go('jobs');setView('grid')"); await pg.wait_for_timeout(100)
        badge = await E(f"[...document.querySelectorAll('tbody tr')].find(tr=>tr.textContent.includes('Pad-eye test frame')).querySelector('.badge').textContent")
        ok(badge == "Complete", f"list: a project with documents handed over reads Complete ({badge})")
        await E("const j=DB.jobs.find(x=>x.jobId==='006');j.phase=PH.DONE;j.deliveredDate=todayISO();save();render()")
        badge = await E("[...document.querySelectorAll('tbody tr')].find(tr=>tr.textContent.includes('006'))?.querySelector('.badge')?.textContent")
        ok(badge == "Collected", f"list: client-collected project without documents reads Collected ({badge})")
        opts = await E("[...document.querySelector('select[data-filter=phase]').options].map(o=>o.textContent)")
        ok("Complete (delivered / collected)" in opts and "Delivered" not in opts, f"phase filter uses the same words ({opts[-2:]})")
        await pg.set_viewport_size({"width": 1366, "height": 768}); await E("render()"); await pg.wait_for_timeout(100)
        ok(await E("(()=>{const t=document.querySelector('.tablewrap');return t.scrollWidth<=t.clientWidth+1})()"), "project list fits at 1366 px without a sideways scroll")
        await pg.set_viewport_size({"width": 1440, "height": 900})
        await E(f"matAction('is1')"); await pg.wait_for_timeout(50)
        ok("From our stock" in await pg.inner_text("#toast"), "tapping an In stock chip explains it (not 'Already received')")
        oj = await E("(()=>{const j=DB.jobs.find(x=>x.jobId==='009');delete j.deliverySet;j.delivery='us';save();return j.id})()")
        await E(f"openPhaseAction('{oj}','quoted')")
        dlg = await pg.inner_text("#mbody"); lit = await pg.locator("#mbody .dvbtns .segbtn.on").count()
        ok(lit == 0 and "who moves the units" in dlg.lower() and "transport isn't costed" not in dlg.lower(), f"delivery never chosen → the quote dialog asks instead of warning about transport (lit {lit})")
        await pg.locator("#mbody .dvbtns .segbtn", has_text="Client collects").click(); await E("saveForm()")
        ok(await E(f"(()=>{{const j=DB.jobs.find(x=>x.id==='{oj}');return j.delivery==='client'&&j.deliverySet===true}})()"), "…and the answer is saved on the project")

        # ---- RFQ ready to send: supplier emails on their own lines, copy each or all (his request) ----
        rid = await E("(DB.procurement.find(r=>(r.suppliers||[]).filter(s=>((DB.suppliers.find(x=>x.id===s.supplierRef)||{}).email||'').trim()).length>=2)||{}).id")
        if rid:
            await E(f"showRfqText('{rid}')"); await pg.wait_for_timeout(100)
            n = await E(f"DB.procurement.find(r=>r.id==='{rid}').suppliers.length")
            ok(await pg.locator(".rfqto-row").count() == n, f"Send to: one line per supplier ({n})")
            mails = await E("[...document.querySelectorAll('.rfqto-mail')].map(e=>e.textContent)")
            ok(all("@" in m for m in mails) and await E("parseFloat(getComputedStyle(document.querySelector('.rfqto-mail')).fontSize)") >= 14, f"emails shown large and readable ({mails})")
            ok(await pg.locator(".rfqto button", has_text="Copy all").count() == 1 and await pg.locator(".rfqto-row button", has_text="Copy").count() == len(mails), "Copy all + a Copy button per email")
            await E("closeForm()")

        # ---- his icon sheet + logo: SVG nav icons, gear app icon, hover / press animation ----
        await E("go('dashboard')"); await pg.wait_for_timeout(100)
        ok(await E("document.querySelectorAll('.nav button svg.nic').length") == 8 and await E("![...document.querySelectorAll('.nav button .ic')].some(e=>/\\p{Extended_Pictographic}/u.test(e.textContent))"), "8 SVG nav icons, no emoji left in the sidebar")
        ok(await E("document.querySelectorAll('.nav svg.nic .ac, .nav svg.nic .acf').length") >= 8, "every icon has its orange accent")
        ok(await E("!!document.querySelector('#applogo svg .lg-gear')") and await E("document.querySelector('.brand h1').textContent") == "PROTRAC", "brand: gear app icon + PROTRAC")
        ok((await E("(document.querySelector('link[rel~=icon]')||{}).href||''")).startswith("data:image/svg+xml"), "favicon is the gear icon (inline, offline)")
        await pg.hover(".nav button:nth-child(5)"); await pg.wait_for_timeout(60)
        ok(await E("getComputedStyle(document.querySelector('.nav button:nth-child(5) .nic')).transform") != "none", "hover lifts the icon")
        await pg.locator(".nav button", has_text="Suppliers").click(); await pg.wait_for_timeout(30)
        ok(await E("current") == "suppliers" and await E("document.querySelector('.nav button.active').classList.contains('pop')"), "press opens the page and the icon pops")
        await pg.wait_for_timeout(500); await E("go('dashboard')")
        ok(await E("!document.querySelector('.nav button.pop')"), "the pop plays once (gone on the next page)")
        ok(not errs, "no page errors: " + "; ".join(errs[:3]))
        await b.close()
    for c, m in res: print(("PASS " if c else "FAIL ") + m)
    f = sum(1 for c, _ in res if not c); print(f"\n{len(res) - f} passed, {f} failed")
    raise SystemExit(1 if f else 0)

asyncio.run(main())
