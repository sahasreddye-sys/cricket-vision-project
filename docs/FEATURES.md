# Feature completion report

Status key: **Complete** means it computes correctly and was exercised by a test or by running it. **Partial** means it works but a stated part was not tested or is missing. **Needs data** and **Needs hardware** mean the code is there and the result depends on material I did not have.

What I could and could not check is stated plainly. No real video of a person bowling, batting or catching was available, so every video feature was tested on synthetic clips or on clips with nobody in them.

## Bowling Lab

| Feature | Status | Notes |
|---|---|---|
| Speed calculator (m, ft, yd; s, ms; m/s, km/h, mph) | Complete | Python and browser versions checked against the same known values. The result is labelled an average speed, never a release speed. |
| Saved readings, history, average, fastest, slowest, recent, chart | Complete | |
| Radar entry and comparison with calculated speed | Complete | The difference is shown with the reason radar reads higher. |
| Line and length pitch map | Complete | Click to record, five length bands, five line bands, heatmap, distribution, target box, session comparison, accuracy trend. |
| Bowling action analyzer | Partial | Landmark angles, key frame, run-up steadiness, observations and A/B comparison are implemented. Tested on synthetic landmarks and on a clip with no person (returns "insufficient"). Not tested on real footage of a bowler. |
| Ball tracking | Partial | Detection, Kalman tracking, observed and predicted points, confidence, bounce and ground-plane calibration work on synthetic clips (mean error about half a pixel). Real footage will be much harder; the limits are shown on screen. |
| Swing and seam | Partial | Noise-aware test implemented and measured (about 2% false alarms with no movement, high detection at 3 times the noise). Values are in pixels from one camera. Needs real clips from a fixed camera to say how useful it is in practice. |

## DRS Studio

| Feature | Status | Notes |
|---|---|---|
| Interactive pitch, stump and ball-path views | Complete | Observed and predicted parts drawn differently. |
| Pitching, impact, projected point, 95% range, hit probability | Complete | 4,000-run Monte Carlo over input uncertainty. |
| LBW conditions (Law 36) | Complete | Each condition is listed with its result. |
| Hitting, missing or inconclusive, with assumptions and limitations | Complete | Inconclusive when data is missing, when travel after the bounce is under 40 cm, or when the answer changes within the uncertainty. |
| Manual entry | Complete | |
| Positions from video | Partial | The bounce point can be placed on the pitch from video with four marked corners. Impact point and height must be entered by hand because one camera cannot measure them. |
| Calibrated, multi-camera accuracy | Needs hardware | Not claimed anywhere. |

## Batting Lab

| Feature | Status | Notes |
|---|---|---|
| Batting action analyzer | Partial | Same status as the bowling analyzer: stance, head position, weight transfer, follow-through and clip comparison are implemented; not tested on real footage. |
| Shot selection (pace, spin, length, line, shot type, dismissals, scoring patterns) | Complete | Each finding states its balls and numbers; small groups are not interpreted. |
| Wagon wheel | Complete | Eight zones, boundaries, off and leg split, strong zones, two-innings comparison, direction picked on the ground while scoring. |
| Structured import | Partial | Ball-by-ball CSV import is checked against the scoring rules before saving. A scorecard-only CSV import is not built; scorecards are typed in. |

## Fielding Lab

| Feature | Status | Notes |
|---|---|---|
| Drag-and-drop field, saved setups | Complete | Attacking, balanced and defensive presets. |
| Field recommendation from a batter's scoring areas | Complete | The method is written out. Needs at least 12 plotted scoring shots. It ignores the bowler, pitch and match situation, and says so. |
| Fielding tracker and player statistics | Complete | Catches, drops, run-outs, direct hits, stumpings, ground fielding and opportunities. |
| Catching technique analyzer | Partial | Hands-together frame, hand height, balance, knee flexion and movement. Not tested on real footage. |

## Team Hub and Match Center

| Feature | Status | Notes |
|---|---|---|
| Player profiles | Complete | Batting, bowling, fielding, speeds, practice accuracy, goals, training, recommendations. |
| Team selection assistant | Complete | Every pick lists its statistics and the rule that put it there; alternatives are compared; no composite rating. |
| Opposition scouting | Complete | Reports built from balls recorded against a player. |
| Match scorecards, partnerships, run rates, required rate, over-by-over, bowling figures | Complete | |
| Live scoring | Complete | Checked against the Laws by a dedicated set of tests: wides, no-balls, byes, leg-byes, maidens, strike rotation, wickets and who they are credited to, impossible combinations rejected. Corrections are by undoing the last ball only; editing an earlier ball is not built. |
| Leaderboards with season and format filters | Complete | Qualification rules shown under each table. "Improvement" covers batting only. |

## AI Coach and progress

| Feature | Status | Notes |
|---|---|---|
| Questions answered from stored data | Complete | Rules cover the eight suggested question types and variants. Anything else gets a plain list of what it can answer. |
| Recommendations with evidence | Complete | Each has the trigger figure and threshold. |
| Optional language model | Partial | Wired to the Claude API with the facts passed in. Not run against the live API because no key was available; the no-key path is tested. |
| Training log, goals, weekly and monthly charts, milestones | Complete | Goals can be measured automatically from recorded data. |

## Platform

| Item | Status | Notes |
|---|---|---|
| React, TypeScript, Tailwind, Recharts | Complete | Interactive maps are hand-drawn SVG rather than a charting library. |
| FastAPI REST with generated docs | Complete | `/docs` and `/redoc`. |
| Relational schema and migration | Complete | Alembic migration. Tested on SQLite. |
| PostgreSQL and Supabase | Needs data | Models are written for both; I could not run either here. |
| Accounts | Complete, different from the brief | Built-in email and password accounts with roles, not Supabase Auth. This was your choice during setup. |
| FFmpeg | Not used | Video is decoded with OpenCV, which was enough and avoids an install. |
| PyTorch | Not used | Nothing in the project needed it. scikit-learn covers the models. |
| Responsive layout | Partial | Checked in the built-in browser at desktop and phone width on all ten pages, with no sideways overflow. Not tried on physical devices or tablets. |
| Light and dark themes | Complete | |
| Tests | Complete | 74 backend tests and 5 frontend unit tests pass, including corrupted, empty, oversized and wrong-type uploads and a clip with no moving ball. |

## Notebooks

All twelve exist as `.ipynb` files in `notebooks/`, each with markdown explanation, executable code, charts, sample data, a summary of findings, limitations and its link to the application. Each was executed from the top with no errors and its outputs are saved. I did not open them in Google Colab itself; the setup cell and instructions are written for it.

## Design

The interface follows the committed "ground scoreboard" direction: number plates in labelled windows, one-pixel rules, three type sizes. After you named further design skills I added the Apple reference's system-font text and control behaviour (hover lift, press, drawn link underlines, 44 px touch targets) and rewrote interface wording to remove stock phrasing. Not run: the Impeccable finish-reviewer subagent and the documenter subagent, so `DESIGN.md` was written by hand from the built interface. The mechanical design detector found nothing.
