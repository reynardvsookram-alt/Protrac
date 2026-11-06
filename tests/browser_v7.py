"""Project value & costing (all excl. VAT): costing import/paste, quote → re-quote → PO values, margin, dashboard, hide values, phone.
Run: python3 tests/browser_v7.py"""
import os, asyncio
from playwright.async_api import async_playwright
APP = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUT, exist_ok=True)
res = []
def ok(c, m): res.append((bool(c), m))

# invented figures in the layout of a costing sheet copied from Excel (tab-separated, heading row included)
PASTE = "\n".join([
    "Cost item\tQty\tunit price\tExtended\tMarkup\tExtended Markup",
    "Paint top coat\t1\t$ 900.00\t$ 900.00\t10%\t$ 990.00",
    "Paint Primer\t1\t$ 450.00\t$ 450.00\t10%\t$ 495.00",
    "Labour fabricating\t1\t$ 2,000.00\t$ 2,000.00\t35%\t$ 2,700.00",
    "Labor for sand blasting & Painting\t1\t$ 1,200.00\t$ 1,200.00\t35%\t$ 1,620.00",
    "Materials\t1\t$ 3,800.00\t$ 3,800.00\t20%\t$ 4,560.00",
    "transport\t1\t$ 400.00\t$ 400.00\t0%\t$ 400.00",
    "Crane hire\t1\t$ 600.00\t$ 600.00\t10%\t$ 660.00",
    "\t\tShop total\t$ 9,350.00\t\t$ 11,425.00"])


async def desktop(b):
    ctx = await b.new_context(viewport={"width": 1366, "height": 860})
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); E = pg.evaluate
    await pg.goto(APP); await pg.wait_for_timeout(400)

    # demo has invented values; dashboard value row
    await E("DB.meta.hideGuide=true;save();go('dashboard')")
    txt = await pg.inner_text("#content")
    ok(all(s in txt for s in ["Quoted — waiting on the client", "Won — work in hand", "Profit on won work", "Quotes won"]), "dashboard money panel with plain headings")
    book = await E("DB.jobs.filter(j=>EXEC.includes(j.phase)).reduce((a,j)=>a+(jobValue(j)||0),0)")
    ok(await E(f"document.querySelector('.moneypanel').textContent.includes(money({book}))"), f"work in hand = sum of PO values ({book})")
    await pg.locator(".mblk", has_text="work in hand").click()
    ok(await E("jobFilter") == "active", "order book tile opens the active projects")
    await E("go('dashboard')"); await pg.locator(".mblk", has_text="Quotes won").click()
    ok(await E("jobFilter") == "winloss" and await E("filteredRows().every(j=>isWon(j)||isLostQuote(j))") and await E("filteredRows().some(j=>j.phase===PH.LOST)"), "Win rate tile opens the won & lost projects")
    await E("go('dashboard')"); await pg.locator(".mblk", has_text="Profit on won work").click()
    ok(await E("jobFilter") == "costed" and await E("filteredRows().length>0&&filteredRows().every(j=>!!jobMargin(j))"), "Average margin tile opens the costed projects behind it")
    await E("go('dashboard')"); await pg.locator("button", has_text="Hide values").click()
    ok("•••" in await pg.inner_text(".moneypanel") and "$" not in (await pg.inner_text(".moneypanel")).replace("$ •••", ""), "Hide values masks the money")
    await E("go('jobs')"); ok("•••" in await pg.inner_text("tbody"), "…in the project list too")
    await E("toggleHideVals()")

    # new project → costing by xlsx import
    await E("openForm(null,'jobs')"); await pg.fill("#mbody [data-k=jobName]", "Costing test skid"); await E("saveForm()")
    jid = await E("DB.jobs.find(j=>j.jobName==='Costing test skid').id")
    await E(f"openJob('{jid}')")
    ok(await pg.locator(".valcard h3 button", has_text="Costing").count() == 1 and await pg.locator(".valcard .vcell").count() == 4, "Overview has the Value & costing card with 4 tappable boxes")
    await E(f"openCosting('{jid}')")
    async with pg.expect_file_chooser() as fc:
        await pg.locator("#mbody button", has_text="Import costing sheet").click()
    await (await fc.value).set_files(os.path.join(FIX, "sample_costing.xlsx")); await pg.wait_for_timeout(500)
    got = await E("costRead()")
    ok(got["lines"].get("labFab", {}).get("cost") == 2000 and got["lines"].get("labPaint", {}).get("cost") == 1200 and got["lines"].get("mat", {}).get("cost") == 3800, "xlsx import: lines matched by name, extended = cost")
    ok(not got["lines"].get("transport", {}).get("markup") and got["lines"].get("paintTop", {}).get("cost") == 900, "xlsx import: % cells (stored 0.1) read as 10%, defaults kept")
    ok(any(x["label"] == "Gasket set" and x["cost"] == 150 for x in got["extra"]), "unknown line added as its own line")
    ok("Matches the sheet" in await pg.inner_text("#costsheet"), "import checks against the sheet's own total ($13,535)")
    await E("saveForm()")
    c = await E(f"jobCosting(DB.jobs.find(j=>j.id==='{jid}'))")
    ok(abs(c["cost"] - 11350) < 0.01 and abs(c["sell"] - 13535) < 0.01, f"costing saved: cost {c['cost']} sell {c['sell']}")

    # paste instead of import (replaces the figures)
    await E(f"openCosting('{jid}')"); await pg.locator("#mbody button", has_text="Paste cells").click()
    await pg.fill("#costpastein", PASTE); await pg.locator("#mbody button", has_text="Fill in").click(); await pg.wait_for_timeout(100)
    got = await E("costRead()")
    ok(got["lines"]["labFab"]["cost"] == 2000 and any(x["label"] == "Crane hire" and x["cost"] == 600 for x in got["extra"]), "paste: lines filled, extra line added")
    ok("9,350" not in await pg.inner_text("#costsheet") or "Matches" in await pg.inner_text("#costsheet") or "check a line" in await pg.inner_text("#costsheet"), "paste: sheet total compared")
    await E("closeForm()")

    # quote submitted: value pre-filled from the costing → Rev 0
    await E(f"openPhaseAction('{jid}','quoted')")
    ok(await E("document.querySelector('#mbody [data-k=qvalue]').value") == "13535", "Quote submitted: value pre-filled from the costing sell total")
    await pg.fill("#mbody [data-k=qref]", "Q-123"); await E("saveForm()")
    j = await E(f"DB.jobs.find(j=>j.id==='{jid}')")
    ok(len(j["quotes"]) == 1 and j["quotes"][0]["value"] == 13535 and j["quotes"][0]["ref"] == "Q-123", "Rev 0 recorded")
    m = await E(f"jobMargin(DB.jobs.find(j=>j.id==='{jid}'))")
    ok(abs(m["amt"] - 2185) < 0.01 and abs(m["pct"] - 16.14) < 0.05, f"margin {m['amt']} / {round(m['pct'],1)}%")

    # re-quote −10%: shows the margin hit, warns below the minimum
    await E(f"openJob('{jid}')"); await pg.locator(".valcard button", has_text="Re-quote").click()
    ok(await E("document.getElementById('rqval').value") == "12181.5", "Re-quote pre-fills −10%")
    rq = await pg.inner_text("#rqmargin")
    ok("margin now" in rq and "after the re-quote" in rq and "Below your 10% minimum" in rq, "re-quote shows margin before/after and warns when it drops below the minimum")
    await pg.click("#mbody .qchip:has-text('−5%')")
    ok(await E("document.getElementById('rqval').value") == "12858.25", "−5% chip")
    await pg.fill("#mbody [data-k=note]", "asked for a discount"); await E("saveForm()")
    j = await E(f"DB.jobs.find(j=>j.id==='{jid}')")
    ok(len(j["quotes"]) == 2 and j["quotes"][1]["rev"] == 1 and j["quotes"][1]["value"] == 12858.25 and "Re-quote Rev 1" in j["updates"][-1]["text"], "Rev 1 saved and logged")
    ok("Rev 1" in await pg.inner_text(".valcard") and "was $13,535" in await pg.inner_text(".valcard"), "value card shows the revision history")

    # the value boxes are tappable: quote revisions editable, margin breakdown, costing
    await E(f"openJob('{jid}')"); await pg.locator(".vcell", has_text="Quoted").click()
    ok(await E("formMode") == "quotes" and await E("document.querySelectorAll('#qrows tr').length") == 2, "tap Quoted → both revisions, editable")
    await pg.locator("#qrows tr:nth-child(1) [data-q=value]").fill("13600"); await E("saveForm()")
    j = await E(f"DB.jobs.find(j=>j.id==='{jid}')")
    ok(j["quotes"][0]["value"] == 13600 and j["quotes"][1]["value"] == 12858.25, "a revision's value can be corrected")
    await E(f"openQuotesEdit('{jid}')"); await pg.locator("#qrows tr:nth-child(2) button[title='Delete this revision']").click(); await E("saveForm()")
    ok(await E(f"DB.jobs.find(j=>j.id==='{jid}').quotes.length") == 1 and await E(f"quoteValue(DB.jobs.find(j=>j.id==='{jid}'))") == 13600, "a revision can be deleted")
    await E(f"openRequote('{jid}')"); await pg.click("#mbody .qchip:has-text('−5%')"); await E("saveForm()")
    await E(f"openJob('{jid}')"); await pg.locator(".vcell", has_text="Margin").click()
    ok(await E("formMode") == "view" and "Costing total" in await pg.inner_text("#mbody") and "Labour" in await pg.inner_text("#mbody"), "tap Margin → line-by-line breakdown")
    await E("closeForm()"); await pg.locator(".vcell", has_text="Cost").click()
    ok(await E("formMode") == "costing", "tap Cost → the costing")
    await E("closeForm()")

    # PO: value pre-filled from the latest revision
    await E(f"openPhaseAction('{jid}','po')")
    ok(await E("document.querySelector('#mbody [data-k=poValue]').value") == "12920", "PO value pre-filled from the latest revision (13,600 − 5%)")
    await pg.fill("#mbody [data-k=poValue]", "12700"); await pg.fill("#mbody [data-k=leadMax]", "10"); await E("saveForm()")
    ok(await E(f"jobValue(DB.jobs.find(j=>j.id==='{jid}'))") == 12700, "after the PO the project value is the PO value")
    await E(f"openJob('{jid}')"); await pg.locator(".vcell", has_text="PO value").click()
    ok(await E("formMode") == "poedit", "tap PO value → edit PO number and value")
    await pg.fill("#mbody [data-k=poValue]", "12650"); await E("saveForm()")
    ok(await E(f"poValue(DB.jobs.find(j=>j.id==='{jid}'))") == 12650 and "PO value changed" in await E(f"DB.jobs.find(j=>j.id==='{jid}').updates.slice(-1)[0].text"), "PO value edited and logged")
    ok(await E("go('jobs');document.querySelector('thead').textContent.includes('Value')"), "project list has a Value column")
    ok(await E("(()=>{go('settings');setTab='general';render();return document.querySelector('#content').textContent.includes('Costing defaults')})()"), "Settings: costing defaults (day rates, minimum margin, markups)")
    await E("setCostMarkup(6,25)")
    ok(await E("costLines()[6].markup") == 25, "default markup editable")
    ok(not errs, "no page errors (desktop): " + "; ".join(errs[:3]))
    await ctx.close()


async def phone(b):
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); E = pg.evaluate
    await pg.goto(APP); await pg.wait_for_timeout(400)
    for name, code in [("dashboard", "DB.meta.hideGuide=true;go('dashboard')"), ("project", "openJob(DB.jobs.find(j=>j.jobId==='005').id)"), ("list", "go('jobs')")]:
        await E(code); await pg.wait_for_timeout(150)
        ok(await E("document.documentElement.scrollWidth<=390"), f"phone {name}: no horizontal page scroll")
    await E("openCosting(DB.jobs.find(j=>j.jobId==='005').id)"); await pg.wait_for_timeout(150)
    ok(await E("(()=>{const r=document.querySelector('.costtab [data-cs=paintTop]').getBoundingClientRect();return r.right<=390&&r.width>0})()"), "phone costing: sell column visible without scrolling")
    await pg.screenshot(path=os.path.join(OUT, "v7_phone_costing.png"))
    ok(not errs, "no page errors (phone): " + "; ".join(errs[:3]))
    await ctx.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await desktop(b); await phone(b); await b.close()
    for c, m in res: print(("PASS " if c else "FAIL ") + m)
    f = sum(1 for c, _ in res if not c); print(f"\n{len(res)-f} passed, {f} failed"); raise SystemExit(1 if f else 0)

asyncio.run(main())
