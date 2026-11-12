# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

User-specified: React + TypeScript + Tailwind CSS + Recharts (frontend); Python + FastAPI REST (backend); OpenCV + MediaPipe (computer vision); NumPy / Pandas / scikit-learn (ML).
Confirmed by the user: SQLite locally with the same SQLAlchemy models and Alembic migrations Postgres/Supabase-ready through one `DATABASE_URL` variable; built-in email + password accounts (hashed, role-based) rather than a third-party auth service.

## Users

Primary: the coach or team administrator of a school cricket team, working on a laptop or tablet. They enter scores, review bowling/batting/catching video, compare players, and pick the playing XI.
Secondary: players, who check their own profile, speeds, goals and coaching notes, mostly on phones.

## Product Purpose

PitchVision is a cricket performance and analytics platform for one school team. It turns what the team already produces (scorebooks, stopwatch or radar timings, phone video of the nets) into statistics, visualisations and coaching observations the team can act on in training, selection and match preparation. Success means the coach trusts the numbers enough to use them for a decision, and every number can be traced back to data the team entered.

## Positioning

Every figure on screen comes from the team's own stored data and says how it was derived; video-based estimates carry their confidence and their limits. It is a training and education tool, not a broadcast-grade tracking system.

## Operating Context

Six working areas: Bowling Lab, DRS Studio and ball tracking, Batting Lab, Fielding Lab, Team Intelligence and Match analytics, AI Coaching and player development. Nine navigation sections: Overview, Bowling Lab, DRS Studio, Batting Lab, Fielding Lab, Team Hub, Match Center, AI Coach, Settings.
Inputs are manual entry, ball-by-ball scoring during a match, structured CSV import, and uploaded phone video (single, uncalibrated camera).
A companion set of twelve Jupyter notebooks shares the same Python analytics modules as the application.

## Capabilities and Constraints

- The application starts empty: no seeded players, matches or statistics. Empty states direct the user to the first action. (User decision.)
- Synthetic sample data exists only for the notebooks and as an optional, clearly labelled import; it is never presented as real team performance.
- A distance/time speed reading is an average speed over the measured distance, never a release speed.
- Pose estimation yields measurable angles and movement indicators only. It does not diagnose injury, medical safety, or the legality of a bowling action.
- Ball tracking and the DRS simulation are educational. Observed positions are shown separately from predicted ones, with confidence and uncertainty; insufficient tracking returns "inconclusive".
- Tracking noise is never labelled as swing or seam movement.
- Team-selection recommendations explain the statistics and assumptions behind them; no arbitrary scores.
- The AI coach answers from stored data and works without an external LLM (rule-based); an LLM is optional.
- Scoring follows the Laws of Cricket for runs, extras, overs, wickets, batter and bowler figures and partnerships.
- No FFmpeg binary is assumed on the host; video decoding goes through OpenCV.

## Brand Commitments

Name: PitchVision. Team name is not yet decided; it is a setting the coach fills in.
User-stated interface constraints: inspired by professional cricket broadcast graphics and modern sports analytics; clean typography, strong hierarchy, subtle animation, professional dark and light themes. Avoid generic AI dashboard layouts, excessive gradients, unnecessary glassmorphism, oversized cards, excessive empty space, and fake graphs or sample statistics presented as real.

## Evidence on Hand

No real team data, video, logo or colours have been supplied. Nothing may be fabricated to fill that gap in the application.

## Product Principles

1. Every number is traceable to entered data and states its method.
2. Say what a measurement is not, as plainly as what it is.
3. A feature is complete when it computes correctly, not when its screen exists.
4. The coach's task comes first; expression never hides state or controls.
5. The application and the notebooks compute through the same code.

## Accessibility & Inclusion

Responsive across desktop, tablet and phone; keyboard-operable controls with visible focus; reduced-motion respected; light and dark themes both meet readable contrast.
