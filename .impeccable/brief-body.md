# PitchVision application shell and nine sections

Scope: the whole web app (frontend/src). Visitor mode: Operate.
Audience: school cricket coach on a laptop or tablet; players on phones for their own profile.
Job: enter data (scores, speeds, deliveries, fielding), review video measurements, compare players, pick the XI.
Constraints: starts empty; every figure traceable; estimates carry confidence and limits; dark and light themes.
Unresolved: team name, logo and colours (a setting the coach fills in).

## Direction contract

THESIS: The app is the ground's scoreboard put to work. Every statistic lives in a labelled window holding a number plate. It refuses the rounded-card dashboard with stat tiles and soft shadows.

OWN-WORLD: Board black-green #0D1310, whitewash #F4F6F1, numeral yellow #F2C230, outfield green #1F6B45, ball red #B3261E, crease white for lines. Number plates are always dark windows with light numerals, in both themes; the light theme is a whitewashed pavilion wall carrying dark plates. Structure is one-pixel ruled lines, never shadow. Barlow Condensed for painted labels and plate numerals (tabular), Barlow for text. Three type sizes only: 12, 15, 32. Rank comes from weight, case and rule. An over is six fixed cells.

STORY: The coach opens the board, sees what the team has recorded and what is missing, goes to a lab, enters or uploads, and reads a result that states its method.

FIRST VIEWPORT: Overview. Left rail of painted section names with the active one on a yellow plate. Top band: team name, season, theme switch, account. Below, one continuous board row of labelled plate windows (played, won, lost, players, speed readings, deliveries logged); empty windows show a dash and the action that fills them. Under a rule: two ruled columns, leading batters and bowlers left, next fixture and recent sessions right. Primary action in the top band: Add match / Add player when empty.

FORM: The ground scoreboard, candidate 3 of 7 on the grounded list; seed key 496b1e98. Signature interaction: plates slot. When a figure changes the old numeral drops out and the new one slides in from above (140 ms); calculators recompute live with no Calculate button; hovering a table row lights its mark on the pitch or ground drawing and the reverse. Reduced motion: instant swap.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
