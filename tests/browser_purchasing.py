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
        for vw in [(1400,900),(390,844)]:
            ctx=await b.new_context(viewport={"width":vw[0],"height":vw[1]})
            pg=await ctx.new_page();errs=[];pg.on("pageerror",lambda e:errs.append(str(e)))
            await pg.goto(APP);await pg.wait_for_timeout(300)
            E=pg.evaluate; tag=f"[{vw[0]}] "
            # add material form overflow
            await E("go('purchasing');openForm(null,'materials',{jobRef:DB.jobs[0].id})")
            ov=await E("(()=>{const m=document.getElementById('mainmodal');const r=m.getBoundingClientRect();return Array.from(m.querySelectorAll('input,select,textarea')).filter(e=>e.offsetParent).some(e=>e.getBoundingClientRect().right>r.right+1)})()")
            ok(not ov,tag+"add-material fields stay inside dialog")
            await pg.fill('#mbody [data-k="description"]',"SHS"); await pg.fill('#mbody [data-k="size"]','4x4x1/4')
            hint=await pg.inner_text("#pricehint"); ok("Price book" in hint,tag+"live price hint: "+hint[:60])
            if vw[0]==1400: await pg.screenshot(path=os.path.join(OUT,"p_form.png"))
            await E("closeForm()")
            if vw[0]==1400:
                await E("go('purchasing')"); await pg.screenshot(path=os.path.join(OUT,"p_toorder.png"),full_page=True)
            # stage cards clickable
            for st in ["waiting","ordered","received","toorder"]:
                await E(f"document.querySelector('.stagecard.st-{st}').click()")
                ok(await E("purStage")==st,tag+"card click -> "+st)
            sw=await E("document.documentElement.scrollWidth"); ok(sw<=vw[0]+2,tag+f"no page h-scroll ({sw})")
            if vw[0]==390:
                await pg.screenshot(path=os.path.join(OUT,"pm_toorder.png")); await ctx.close(); continue
            # full flow on 200 BBL tank
            jid=await E("DB.jobs.find(j=>j.jobName.startsWith('200 BBL')).id")
            n0=await E(f"jobMats('{jid}').filter(m=>matStage(m)==='toorder').length")
            await E(f"purSelMany('{jid}',true)"); ok(await E("purSel.size")==n0,"select all job lines")
            await E("purRfq()")
            await E("document.querySelectorAll('#mbody [data-sup]').forEach(x=>x.checked=['Supplier A','Supplier B'].includes(DB.suppliers.find(s=>s.id===x.dataset.sup).company))")
            await E("saveForm()"); await E("closeForm()")
            ok(await E("purStage")=="waiting","after RFQ -> waiting stage")
            r=await E("DB.procurement[DB.procurement.length-1]"); rid=r["id"]
            ok(len(r["suppliers"])==2 and await E(f"jobMats('{jid}').every(m=>matStage(m)==='waiting')"),"lines now waiting")
            await E("render()"); await pg.screenshot(path=os.path.join(OUT,"p_waiting.png"),full_page=True)
            # quote from A: prices; from B: cheaper on some
            la,lb=r["suppliers"][0]["id"],r["suppliers"][1]["id"]
            mids=await E(f"rfqMats(DB.procurement.find(x=>x.id==='{rid}')).map(m=>m.id)")
            await E(f"openQuote('{rid}','{la}')")
            for i,m in enumerate(mids): await pg.fill(f'#mbody [data-mp="{m}"]',str(1000+i*100))
            await pg.fill('#mbody [data-k="lead"]',"ex stock")
            await pg.screenshot(path=os.path.join(OUT,"p_quote.png"))
            pq0=await E("DB.priceQuotes.length"); await E("saveForm()"); await E("(()=>{const s=document.getElementById('askscrim');if(s&&s.classList.contains('show'))document.getElementById('askok').onclick();})()")   # test prices are made up, so 'Check this price' may ask — Keep
            ok(await E("DB.priceQuotes.length")>pq0,"quote logged to price book")
            await E(f"openQuote('{rid}','{lb}')")
            for i,m in enumerate(mids):
                if i%2==0: await pg.fill(f'#mbody [data-mp="{m}"]',str(900+i*100))
            await E(f"document.querySelector('#mbody [data-mr=\"{mids[1]}\"]').value='No stock'")
            await E("saveForm()"); await E("(()=>{const s=document.getElementById('askscrim');if(s&&s.classList.contains('show'))document.getElementById('askok').onclick();})()")
            ok("2/2 replied" in await pg.inner_text("#purbody"),"card shows 2/2 replied")
            await E(f"openCompare('{rid}')"); await pg.screenshot(path=os.path.join(OUT,"p_compare.png"))
            tot=await pg.inner_text("#cmptot"); ok("Supplier B" in tot and "Supplier A" in tot,"compare totals split by supplier")
            await E("saveCompare()")
            ok(await E("purStage")=="ordered","after order -> ordered stage")
            sB=await E("DB.suppliers.find(s=>s.company==='Supplier B').id")
            m0=await E(f"DB.materials.find(m=>m.id==='{mids[0]}')"); m1=await E(f"DB.materials.find(m=>m.id==='{mids[1]}')")
            ok(m0["supplierRef"]==sB and m0["quotedPrice"]==900,"cheapest (B) picked for item 1")
            ok(m1["quotedPrice"]==1100,"item 2 from A (B no stock)")
            ok(await E(f"matPrice(DB.materials.find(m=>m.id==='{mids[0]}')).price")==900,"material uses chosen quote price")
            await pg.screenshot(path=os.path.join(OUT,"p_ordered.png"),full_page=True)
            await E(f"receiveMats({mids!r})".replace("'",'"'))
            ok(await E(f"jobMats('{jid}').every(m=>matStage(m)==='received')"),"received")
            ok(await E(f"DB.procurement.find(x=>x.id==='{rid}').suppliers.every(s=>s.status==='Received')"),"supplier lines -> Received")
            ok(not await E(f"rfqOpen(DB.procurement.find(x=>x.id==='{rid}'))"),"RFQ no longer open")
            await E("purStage='received';render()"); await E(f"toggleMTR('{mids[0]}')")
            ok(await E(f"DB.materials.find(m=>m.id==='{mids[0]}').mtr"),"MTR toggle")
            await pg.screenshot(path=os.path.join(OUT,"p_received.png"),full_page=True)
            # direct order + unlink + delete RFQ
            hid=await E("(()=>{const j=DB.jobs.find(j=>j.jobName.startsWith('Vacuum'));DB.materials.push({id:uid(),jobRef:j.id,lineNo:'1',description:'Plate',size:'1/4\"',grade:'A36',qtyReq:1,unit:'sheet',qtyOrdered:0,qtyReceived:0});save();return j.id})()")
            await E(f"purStage='toorder';render();purSelMany('{hid}',true);openOrderModal()")
            await E("document.querySelector('#mbody [data-k=supplierRef]').value=DB.suppliers[0].id"); await E("saveForm()")
            ok(await E(f"jobMats('{hid}').every(m=>matStage(m)==='ordered'&&m.supplierRef===DB.suppliers[0].id)"),"ordered direct")
            # job page procurement tab renders new cards
            await E(f"openJob('{jid}','procurement')"); ok("Compare" in await pg.inner_text("#content") or "replied" in await pg.inner_text("#content"),"job procurement tab uses new cards")
            # legacy: dashboard link
            await E("dashGo('procurement')"); ok(await E("current")=="purchasing" and await E("purStage")=="waiting","dashboard link -> waiting")
            ok(not errs,"no page errors: "+"; ".join(errs[:3]))
            await ctx.close()
        await b.close()
    for c,m in res: print(("PASS " if c else "FAIL ")+m)
    print(sum(c for c,_ in res),"/",len(res))
asyncio.run(main())
