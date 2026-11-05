import os
APP="file://"+os.path.abspath(os.path.join(os.path.dirname(__file__),"..","index.html"))
FIX=os.path.join(os.path.dirname(os.path.abspath(__file__)),"fixtures")
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"out");os.makedirs(OUT,exist_ok=True)
import asyncio, json, sys
from playwright.async_api import async_playwright
RESET="""(()=>{try{closeForm()}catch(e){};document.getElementById('askscrim').classList.remove('show');
DB=seed();migrate();autoPriceMaterials(DB.materials);pbInvalidate();seedSchedules();save();supView=null;setTab='general';matGrid=null;listQ='';gridFilters={};purStage='';purQ='';purSel=new Set();matSel=new Set();priceQ='';priceCat='';qcFilter='';detailJob=null;jobFilter=null;sortKey=null;})()"""
def job(prefix,tab): return f"(()=>{{openJob(DB.jobs.find(j=>j.jobName.startsWith('{prefix}')).id,'{tab}')}})()"
STATES=[("dashboard","go('dashboard')"),("jobs-grid","go('jobs')"),("jobs-board","go('jobs');setView('kanban')"),("jobs-cal","go('jobs');setView('calendar')"),
 ("pur-toorder","go('purchasing');purStage='toorder';render()"),("pur-waiting","go('purchasing');purStage='waiting';render()"),("pur-ordered","go('purchasing');purStage='ordered';render()"),("pur-received","go('purchasing');purStage='received';render()"),
 ("prices","go('prices')"),("qc","go('qc')"),("suppliers","go('suppliers')"),("reminders","go('reminders')"),("settings","go('settings')"),
 ("sup-profile","go('suppliers');openSupplier(DB.suppliers.find(s=>s.company==='Coatings Distributor').id)"),("sup-profile-steel","go('suppliers');openSupplier(DB.suppliers[0].id)"),
 ("set-workflow","go('settings');setTab='workflow';render()"),("set-templates","go('settings');setTab='templates';render()"),("set-lists","go('settings');setTab='lists';render()"),("set-qc","go('settings');setTab='qc';render()"),("set-data","go('settings');setTab='data';render()"),
 ("vac-schedule","openJob(DB.jobs.find(j=>j.jobId==='Q-26-022').id,'schedule')"),
 ("grid-editor","startGrid(DB.jobs.find(j=>j.jobName.startsWith('200 BBL')).id)")]
for pre in ["200 BBL","Sand storage","Container box","DNV pump"]:
  for t in ["overview","checklist","schedule","materials","procurement","updates"]:
    STATES.append((f"{pre}/{t}",job(pre,t)))
SEL="button:visible, [onclick]:visible:not(button), select:visible, input[type=checkbox]:visible"
async def main():
  issues=[];total=0
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={"width":1400,"height":900})
    pg=await ctx.new_page();errs=[]
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.on("console",lambda m:errs.append("console: "+m.text) if m.type=="error" else None)
    pg.on("filechooser",lambda fc:None)
    await pg.goto(APP);await pg.wait_for_timeout(300)
    async def goto(code):
      await pg.evaluate(RESET);await pg.evaluate(code);await pg.wait_for_timeout(20)
    for name,code in ([] if __import__('os').environ.get('PHONE') else STATES):
      await goto(code)
      n=await pg.locator(SEL).count()
      for i in range(n):
        await goto(code)
        loc=pg.locator(SEL).nth(i)
        try:
          tag=await loc.evaluate("e=>e.tagName+(e.textContent||e.value||'').trim().slice(0,40)")
          href=await loc.evaluate("e=>e.getAttribute('href')||''")
          if href.startswith("mailto"):continue
        except Exception: continue
        errs.clear();total+=1
        try:
          if tag.startswith("SELECT"):
            opts=await loc.evaluate("e=>Array.from(e.options).map(o=>o.value)")
            v=[o for o in opts if o and o!="__add__" and o!="__new__"]
            if v: await loc.select_option(v[-1],timeout=1500)
          else: await loc.click(timeout=1500)
          await pg.wait_for_timeout(40)
          # confirm dialogs and saves
          for _ in range(3):
            if await pg.evaluate("document.getElementById('askscrim').classList.contains('show')"):
              if await pg.locator("#askin").count(): await pg.fill("#askin","Test")
              await pg.click("#askok",timeout=1500);await pg.wait_for_timeout(40)
            elif await pg.evaluate("document.getElementById('scrim').classList.contains('show')"):
              ov=await pg.evaluate("(()=>{const m=document.getElementById('mainmodal');const r=m.getBoundingClientRect();return Array.from(m.querySelectorAll('input:not([type=radio]):not([type=checkbox]),select,textarea')).filter(e=>e.offsetParent&&!e.closest('.tablewrap,.gridwrap')).filter(e=>e.getBoundingClientRect().right>r.right+1).map(e=>e.dataset.k||e.id||e.tagName)})()")
              if ov: issues.append((name,tag,"modal overflow: "+",".join(ov)))
              ft=await pg.evaluate("getComputedStyle(document.querySelector('#mainmodal footer')).display!=='none'")
              if ft: await pg.click("#mainsave",timeout=1500);await pg.wait_for_timeout(40)
              break
            else: break
        except Exception as e:
          s=str(e).split("\n")[0]
          if "Timeout" not in s and "not visible" not in s and "detached" not in s: issues.append((name,tag,"click failed: "+s[:120]))
        for er in errs: issues.append((name,tag,er[:200]))
    # phone layout per state
    m=await b.new_context(viewport={"width":390,"height":844});mp=await m.new_page()
    await mp.goto(APP);await mp.wait_for_timeout(300)
    for name,code in STATES:
      await mp.evaluate(RESET);await mp.evaluate(code);await mp.wait_for_timeout(30)
      sw=await mp.evaluate("document.documentElement.scrollWidth")
      wide=await mp.evaluate("Array.from(document.querySelectorAll('#content *')).filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.right>392&&!e.closest('.tablewrap,.gridwrap,.kanban,.cal,.gantt,.calgrid,.jtabs,.pchips,.settabs,.tlstrip')}).slice(0,3).map(e=>e.tagName+'.'+e.className)")
      if sw>392 or wide: issues.append((name,"phone",f"overflow scrollWidth={sw} {wide}"))
    await b.close()
  seen=set()
  for x in issues:
    k=(x[0].split('/')[-1],x[2][:80])
    if k in seen: continue
    seen.add(k);print("ISSUE",x)
  print("clicked",total,"elements;",len(issues),"issue hits;",len(seen),"unique")
asyncio.run(main())
