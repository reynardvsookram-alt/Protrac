# Hand-off: put Dashboard v3 into the app

Read `CLAUDE.md` first (hard rules, wording "Project" not "Job", test loop). Work on branch
`claude/tender-maxwell-hbckz5` (open PR reynardvsookram-alt/Protrac#1); push there when done.

## Task
Replace the current dashboard in `index.html` with the approved v3 layout in `docs/dashboard-v3/`
(`dashboard.js` replaces `renderDashboard` + adds the icon helpers; `dashboard.css` goes in the main `<style>`).
Do **not** copy the try-out's forced dark default. Then make these five agreed fixes:

1. **No triple-listing.** An overdue item shows in *Attention required* and *Upcoming deadlines* only.
   *At-risk projects* = projects about to slip: due soon, chase client, on hold, QC fail — not ones already overdue.
2. **Replace "Quick stats"** (it repeats the pipeline) with **"This month"**: quotes sent, POs won, projects
   delivered (counts, from `phaseLog` dates in the current month) and the value won (`jobValue` of POs received
   this month). Each tile opens the matching filtered project list (add `dashFilter` filters as needed).
3. **"View all" on Attention required** opens a filtered list of only the projects behind those cards
   (new `jobFilter`, e.g. `attention`), not every project.
4. **Hide zero lines** in the Financial overview (e.g. "RFQ (costed) TTD 0 · 0%" when no RFQ project has a costing),
   in the legend, the donut and the four mini cards.
5. **Phone order** (≤760 px): Attention required → Upcoming deadlines → My actions → At-risk → Financial →
   Pipeline → This month → Recent projects (CSS `order` on the grid items is fine).

## Then
- Remove the old dashboard CSS/markup that's no longer used (keep `valueRow`/Money only if still referenced).
- Update tests that read the old dashboard (`tests/browser_v6.py` search-layering check uses `.cards` —
  point it at `.attgrid`/`.dg3`; `tests/browser_v7.py` reads `.moneypanel` / `.mblk` — retarget to the new cards;
  `tests/node_harness.js` "dashboard content" smoke). Add checks for the five fixes and that every card/row
  navigates. Don't weaken tests.
- Run the full loop in `CLAUDE.md` (incl. `sweep.py` and `PHONE=1`), look at real desktop + phone screenshots
  (light and dark), update `docs/phase1` shots and the CLAUDE.md "UI shell" notes, commit, push.
- Tell the owner the PR link and that the live site updates only after he merges to `main`.
