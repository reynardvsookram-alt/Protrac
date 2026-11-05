// Before/after screenshots for phase-1 review. Usage: node tests/shots_phase1.js <before|after>
const {chromium}=require('playwright');const path=require('path');
const OUT=path.join(__dirname,'..','docs','phase1'),tag=process.argv[2]||'after';
(async()=>{
 const b=await chromium.launch();
 for(const [dev,vp] of [["desktop",{width:1366,height:860}],["phone",{width:390,height:844}]]){
  const p=await b.newPage({viewport:vp,deviceScaleFactor:dev==="phone"?2:1});
  await p.goto('file://'+path.join(__dirname,'..','index.html'));await p.waitForTimeout(500);
  await p.evaluate(()=>{DB.meta.hideGuide=true;save();});
  const shot=async n=>{await p.waitForTimeout(350);await p.screenshot({path:`${OUT}/${tag}-${dev}-${n}.png`});};
  await p.evaluate(()=>go('jobs'));await shot('jobs');
  await p.evaluate(()=>openForm(null,'jobs'));await shot('newjob');
  await p.evaluate(()=>closeForm());
  await p.evaluate(()=>{const j=DB.jobs.find(j=>j.phase==="In Production");openJob(j.id);});await shot('job');
  await p.evaluate(()=>{go('jobs');setView('kanban');});await shot('board');
  await p.close();
 }
 await b.close();
})();
