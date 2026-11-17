"""Light theme readability: every piece of text on every main page reads at WCAG AA contrast
(>= 4.5:1, or 3:1 for large text) against its real background. His request: "some things are very hard
to see in light mode". Dark mode he signed off as is, so it isn't checked here.
Run: python3 tests/browser_contrast.py"""
import os, asyncio
from playwright.async_api import async_playwright
APP = "file://" + os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
PAGES = [
 [
  "dashboard",
  "go('dashboard')"
 ],
 [
  "jobs",
  "go('jobs')"
 ],
 [
  "board",
  "go('jobs');setView('kanban')"
 ],
 [
  "calendar",
  "go('jobs');setView('calendar')"
 ],
 [
  "job-overview",
  "openJob(DB.jobs.find(j=>j.jobId==='004').id)"
 ],
 [
  "job-schedule",
  "openJob(DB.jobs.find(j=>j.jobId==='004').id,'schedule')"
 ],
 [
  "job-materials",
  "openJob(DB.jobs.find(j=>j.jobId==='007').id,'materials')"
 ],
 [
  "job-qc",
  "openJob(DB.jobs.find(j=>j.jobId==='004').id,'checklist')"
 ],
 [
  "purchasing",
  "go('purchasing')"
 ],
 [
  "prices",
  "go('prices')"
 ],
 [
  "qc",
  "go('qc')"
 ],
 [
  "suppliers",
  "go('suppliers')"
 ],
 [
  "reminders",
  "go('reminders')"
 ],
 [
  "settings",
  "go('settings')"
 ]
]
AUDIT = "()=>{\n  const parse=c=>{const m=c.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;const a=m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number);return {r:a[0],g:a[1],b:a[2],a:a.length>3?a[3]:1};};\n  const lum=c=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(c.r)+.7152*f(c.g)+.0722*f(c.b)};\n  const blend=(top,bot)=>({r:top.r*top.a+bot.r*(1-top.a),g:top.g*top.a+bot.g*(1-top.a),b:top.b*top.a+bot.b*(1-top.a),a:1});\n  const bgOf=el=>{let stack=[];for(let e=el;e;e=e.parentElement){const cs=getComputedStyle(e);const c=parse(cs.backgroundColor);if(cs.backgroundImage&&cs.backgroundImage.includes('gradient')){const m=cs.backgroundImage.match(/rgba?\\([^)]+\\)/);if(m){stack.push(parse(m[0]));}}if(c&&c.a>0)stack.push(c);if(stack.length&&stack[stack.length-1].a>=1)break;}\n   let col={r:255,g:255,b:255,a:1};for(let i=stack.length-1;i>=0;i--)col=blend(stack[i],col);return col;};\n  const out=[];const seen=new Set();\n  document.querySelectorAll('#content *, .topbar *').forEach(el=>{\n   if(!el.childNodes.length)return;const txt=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join(' ').trim();if(!txt)return;\n   const rect=el.getBoundingClientRect();if(!rect.width||!rect.height)return;const cs=getComputedStyle(el);if(cs.visibility==='hidden'||+cs.opacity===0)return;\n   let fg=parse(cs.color);const bg=bgOf(el);if(fg.a<1)fg=blend(fg,bg);\n   const L1=lum(fg),L2=lum(bg);const cr=(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);\n   const size=parseFloat(cs.fontSize),bold=+cs.fontWeight>=600;const large=size>=24||(size>=18.6&&bold);const need=large?3:4.5;\n   if(cr<need){const key=cs.color+'|'+`rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`;out.push({key,cr:Math.round(cr*100)/100,txt:txt.slice(0,28),cls:(el.className&&el.className.baseVal===undefined?el.className:'').toString().slice(0,30),size});}\n  });return out;}"
res = []
def ok(c, m): res.append((bool(c), m))

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1440, "height": 900}); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(APP); await pg.wait_for_timeout(400)
        await pg.evaluate("DB.meta.hideGuide=true;setTheme('light')")
        for name, code in PAGES:
            await pg.evaluate(code); await pg.wait_for_timeout(450)
            bad = await pg.evaluate(AUDIT)
            ok(not bad, f"light {name}: all text readable" + ("" if not bad else " — " + "; ".join(f'{x["cr"]}:1 "{x["txt"]}" .{x["cls"]}' for x in bad[:4])))
        # checkboxes (his request): light = transparent inside + dark outline, ticked = orange; dark keeps the native look
        await pg.evaluate("go('purchasing')"); await pg.wait_for_timeout(400)
        st = await pg.evaluate("(()=>{const c=document.querySelector('#purbody input[type=checkbox]');const s=getComputedStyle(c);return [s.backgroundColor,s.borderTopColor,s.borderTopWidth]})()")
        ok(st[0] == "rgba(0, 0, 0, 0)" and st[1] == "rgb(61, 71, 86)", f"light checkbox: transparent inside, dark outline ({st})")
        await pg.locator("#purbody input[type=checkbox]").nth(1).check(); await pg.wait_for_timeout(200)
        ok(await pg.evaluate("getComputedStyle(document.querySelectorAll('#purbody input[type=checkbox]')[1]).backgroundColor") == "rgb(181, 73, 10)", "light checkbox ticked: orange fill")
        await pg.evaluate("setTheme('dark');go('purchasing')"); await pg.wait_for_timeout(300)
        ok(await pg.evaluate("getComputedStyle(document.querySelector('#purbody input[type=checkbox]')).appearance") == "auto", "dark theme keeps the native checkbox")
        await pg.evaluate("setTheme('light')")
        ok(not errs, "no page errors: " + "; ".join(errs[:3]))
        await b.close()
    for c, m in res: print(("PASS " if c else "FAIL ") + m)
    f = sum(1 for c, _ in res if not c); print(f"\n{len(res) - f} passed, {f} failed")
    raise SystemExit(1 if f else 0)

asyncio.run(main())
