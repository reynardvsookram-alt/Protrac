"""Dashboard v3: every card / row navigates, the five agreed fixes, phone order, light + dark, no forced theme.
Run: python3 tests/browser_dash.py"""
import os, asyncio
from playwright.async_api import async_playwright
APP = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); os.makedirs(OUT, exist_ok=True)
res = []
def ok(c, m): res.append((bool(c), m))

ORDER = ["o-att", "o-dl", "o-act", "o-risk", "o-fin", "o-pipe", "o-month", "o-recent"]


async def open_dash(pg):
    await pg.evaluate("DB.meta.hideGuide=true;save();go('dashboard')"); await pg.wait_for_timeout(60)


async def desktop(b):
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); E = pg.evaluate
    await pg.goto(APP); await pg.wait_for_timeout(400)
    ok(await E("document.documentElement.getAttribute('data-theme')") == "light", "light system theme → app opens light (no forced dark)")
    await open_dash(pg)
    ok(await E("[...document.querySelectorAll('.dash3 > .dcard, .dash3 .dg3 > .dcard')].length") == 8, "8 dashboard cards")
    tops = await E("['o-fin','o-pipe','o-dl'].map(c=>Math.round(document.querySelector('.'+c).getBoundingClientRect().top))")
    ok(len(set(tops)) == 1, f"desktop: Financial · Pipeline · Deadlines side by side ({tops})")

    # every Attention card goes where it says
    n = await pg.locator(".attcard").count()
    ok(n >= 4, f"demo shows {n} attention cards")
    for i in range(n):
        await open_dash(pg)
        label = (await pg.locator(".attcard").nth(i).inner_text()).replace("\n", " ")
        await pg.locator(".attcard").nth(i).click(); await pg.wait_for_timeout(40)
        st = await E("({current,jobFilter,qcFilter:typeof qcFilter!=='undefined'?qcFilter:null,rows:current==='jobs'?filteredRows().length:-1})")
        ok(st["current"] != "dashboard" and (st["current"] != "jobs" or st["rows"] > 0), f"attention card '{label}' → {st['current']} {st['jobFilter'] or st['qcFilter'] or ''} ({st['rows']} rows)")

    # fix 3: View all = only the projects behind the cards
    await open_dash(pg); await pg.locator(".o-att .dlink").click(); await pg.wait_for_timeout(40)
    ok(await E("jobFilter") == "attention" and await E("filteredRows().length===attentionJobIds().size&&filteredRows().length<DB.jobs.length"), "fix 3: Attention 'View all' opens only those projects")
    ok("Needs your attention" in await pg.inner_text(".filterbanner"), "fix 3: filter banner names it")

    # rows open the project
    for sel in [".drow", ".rrow", ".frow"]:
        await open_dash(pg); cnt = await pg.locator(sel).count(); good = 0
        for i in range(cnt):
            await open_dash(pg); jid = await E(f"(document.querySelectorAll('{sel}')[{i}].getAttribute('onclick')||'').match(/openJob\\('([^']+)'/)?.[1]")
            await pg.locator(sel).nth(i).click(); await pg.wait_for_timeout(30)
            good += (await E("detailJob")) == jid and jid is not None
        ok(cnt > 0 and good == cnt, f"every {sel} opens its project ({good}/{cnt})")
    # pipeline rows, legend + mini cards, this-month tiles, links
    await open_dash(pg); np = await pg.locator(".prow").count(); good = 0
    for i in range(np):
        await open_dash(pg); ph = await E(f"PHASES[{i}]"); await pg.locator(".prow").nth(i).click(); await pg.wait_for_timeout(30)
        good += await E(f"current==='jobs'&&gridFilters.phase===PHASES[{i}]")
    ok(np == 7 and good == np, f"every pipeline row opens its phase ({good}/{np})")
    for sel in [".fmini", ".flegend button", ".qtile"]:
        await open_dash(pg); cnt = await pg.locator(sel).count(); good = 0
        for i in range(cnt):
            await open_dash(pg); f = await E(f"(document.querySelectorAll('{sel}')[{i}].getAttribute('onclick')||'').match(/dashFilter\\('([^']+)'/)?.[1]")
            await pg.locator(sel).nth(i).click(); await pg.wait_for_timeout(30)
            good += f is not None and await E("jobFilter") == f and await E("current") == "jobs"
        ok(cnt > 0 and good == cnt, f"every {sel} opens its filtered list ({good}/{cnt})")
    for txt, want in [("Calendar", "current==='jobs'&&currentView==='calendar'"), ("All", "current==='reminders'")]:
        await open_dash(pg); sel = ".o-dl .dlink" if txt == "Calendar" else ".o-act .dlink"
        await pg.locator(sel).click(); await pg.wait_for_timeout(30)
        ok(await E(want), f"'{txt}' link goes to its page")
    # Recent activity = project updates and changes, newest first (replaced the Recent projects table, which repeated the Projects page)
    await open_dash(pg)
    ok(await pg.locator(".rtab").count() == 0 and "Recent activity" in await pg.inner_text(".o-recent"), "Recent activity replaces the Recent projects table")
    want = await E("(()=>{const f=[];DB.jobs.forEach(j=>(j.updates||[]).forEach((u,idx)=>f.push({u,idx})));f.sort((a,b)=>(b.u.date||'').localeCompare(a.u.date||'')||((b.u.ts||0)-(a.u.ts||0))||(b.idx-a.idx));return f.slice(0,3).map(x=>x.u.text.replace(/\\n/g,' '))})()")
    got = await E("[...document.querySelectorAll('.frow .fmsg')].slice(0,3).map(e=>e.textContent)")
    ok(want == got and len(got) == 3, f"feed shows the newest updates first ({got[:1]})")
    ok(await E("document.querySelector('.fday').textContent.length>0"), "feed is grouped by day")
    total = await E("DB.jobs.reduce((a,j)=>a+(j.updates||[]).length,0)"); n0 = await pg.locator(".frow").count()
    if total > n0:
        await pg.locator(".fmore").click(); await pg.wait_for_timeout(40)
        ok(await pg.locator(".frow").count() == min(total, n0 + 20), "Show more loads 20 more updates")
    await E("DB.jobs[0].updates.push({id:uid(),date:todayISO(),ts:Date.now(),text:'Test update from the shop floor'});save();go('dashboard')")
    ok((await pg.locator(".frow .fmsg").first.inner_text()) == "Test update from the shop floor" and (await pg.locator(".fday").first.inner_text()).lower() == "today", "a new update appears at the top under Today")
    await E("DB.jobs[0].updates.pop();save()")
    await open_dash(pg); await pg.locator(".dnew").click(); await pg.wait_for_timeout(60)
    ok(await E("formMode") is not None and await E("!!document.querySelector('#mbody [data-k=jobName]')"), "New project opens the project form")
    await E("closeForm()")

    # fix 2: This month
    await open_dash(pg)
    mt = await pg.inner_text(".o-month")
    ok("This month" in mt and "Quick stats" not in await pg.inner_text("#content") and all(s in mt for s in ["Delivered", "Value won"]), "fix 2: 'This month' replaces Quick stats")
    exp = await E("['quoted','won','delivered'].map(k=>DB.jobs.filter(j=>inThisMonth(j,k)).length)")
    got = await E("[...document.querySelectorAll('.qtile b')].slice(0,3).map(b=>+b.textContent)")
    ok(exp == got, f"fix 2: counts match the phase log ({got})")
    # fix 1 + 4 on screen
    over = await E("DB.jobs.filter(j=>jobState(j).overdue).map(j=>j.id)")
    ok(over and await E(f"!{over}.some(id=>document.querySelector('.o-risk').innerHTML.includes(id))") and await E(f"{over}.every(id=>document.querySelector('.o-dl').innerHTML.includes(id))"), "fix 1: overdue only in Attention + Deadlines")
    ok(not await E("/TTD 0(?![\\d,])|\\b0%/.test(document.querySelector('.o-fin').textContent)"), "fix 4: no zero lines in the financial overview")
    await pg.screenshot(path=os.path.join(OUT, "dash_desk_light.png"), full_page=True)
    await E("setTheme('dark');go('dashboard')"); await pg.wait_for_timeout(200)
    await pg.screenshot(path=os.path.join(OUT, "dash_desk_dark.png"), full_page=True)
    ok(await E("getComputedStyle(document.querySelector('.dcard')).backgroundImage!=='none'&&document.documentElement.getAttribute('data-theme')==='dark'"), "dark theme renders the cards")
    ok(not errs, "no page errors (desktop): " + "; ".join(errs[:3]))
    await ctx.close()
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    pg = await ctx.new_page(); await pg.goto(APP); await pg.wait_for_timeout(300)
    ok(await pg.evaluate("document.documentElement.getAttribute('data-theme')") == "dark", "dark system theme → app opens dark (follows the device)")
    await ctx.close()


async def phone(b):
    for theme in ("light", "dark"):
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, color_scheme=theme)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); E = pg.evaluate
        await pg.goto(APP); await pg.wait_for_timeout(400); await open_dash(pg)
        tops = await E(f"{ORDER}.map(c=>document.querySelector('.'+c).getBoundingClientRect().top)")
        ok(all(tops[i] < tops[i + 1] for i in range(len(tops) - 1)), f"fix 5 ({theme}): phone order Attention → Deadlines → Actions → At-risk → Financial → Pipeline → This month → Recent")
        ok(await E("document.documentElement.scrollWidth<=390"), f"phone {theme}: no horizontal page scroll")
        ok(await E("[...document.querySelectorAll('.dcard')].every(c=>c.getBoundingClientRect().right<=391)"), f"phone {theme}: every card fits the width")
        await pg.locator(".attcard").first.tap(); await pg.wait_for_timeout(40)
        ok(await E("current") != "dashboard", f"phone {theme}: attention card responds to a tap")
        await open_dash(pg)
        await pg.screenshot(path=os.path.join(OUT, f"dash_phone_{theme}.png"), full_page=True)
        ok(not errs, f"no page errors (phone {theme}): " + "; ".join(errs[:3]))
        await ctx.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await desktop(b); await phone(b); await b.close()
    for c, m in res: print(("PASS " if c else "FAIL ") + m)
    f = sum(1 for c, _ in res if not c); print(f"\n{len(res) - f} passed, {f} failed")
    raise SystemExit(1 if f else 0)

asyncio.run(main())
