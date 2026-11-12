# Architecture

```
 Browser
 ┌──────────────────────────────────────────────────────────────┐
 │ React + TypeScript + Tailwind + Recharts                     │
 │ Overview · Bowling Lab · DRS Studio · Batting Lab ·          │
 │ Fielding Lab · Team Hub · Match Center · AI Coach · Settings │
 └───────────────┬──────────────────────────────────────────────┘
                 │ REST, JSON, multipart video upload  (/api)
                 ▼
 FastAPI (backend/app)
 ┌────────────────────────────┐        ┌──────────────────────────┐
 │ routers: core, bowling,    │ rows   │ SQLAlchemy models        │
 │ matches, labs              │◄──────►│ SQLite now, PostgreSQL / │
 │ auth (scrypt + JWT, roles) │        │ Supabase by changing one │
 │ services: rows to dicts    │        │ URL; Alembic migration   │
 └────────────┬───────────────┘        └──────────────────────────┘
              │ plain lists of dicts
              ▼
 pitchvision/  (shared analytics package, no web or database code)
 ┌──────────────┬────────────┬───────────┬──────────────┬─────────┐
 │ Analytics    │ Computer   │ Machine   │ Coaching     │ Sample  │
 │ speed        │ vision     │ learning  │ coach        │ data    │
 │ pitchmap     │ tracking   │ ml        │ (rules,      │ (labelled│
 │ scoring      │ (OpenCV)   │ (scikit-  │ optional LLM)│ synthetic)│
 │ stats        │ pose       │ learn)    │              │         │
 │ selection    │ (MediaPipe)│           │              │         │
 │ trajectory   │            │           │              │         │
 └──────▲───────┴─────▲──────┴─────▲─────┴──────▲───────┴────▲────┘
        │             │            │            │            │
        └─────────────┴────────────┴────────────┴────────────┘
                 imported directly by the 12 notebooks
```

## Why it is built this way

One package holds every calculation. The backend turns database rows into plain dictionaries (`backend/app/services.py`), calls the package, and returns the result. The notebooks read CSV files into the same kind of dictionaries and call the same functions. There is one definition of a batting average, one scoring engine and one set of line and length bands.

The front end repeats a single piece of logic: the speed calculator recomputes as you type, so it keeps its own copy of the unit conversion factors. A vitest suite checks that copy against the same known values the Python tests use.

## Data model

Players, matches, innings, balls, batting and bowling lines (for scorecards entered without ball-by-ball data), speed readings, bowling sessions and deliveries, fielding events, saved field setups, training logs, goals, video analyses (the measurements only; the video file is deleted after analysis), DRS reviews, accounts and one team-settings row. `backend/app/models.py` is the reference.

Every table that can hold demonstration data has an `is_sample` flag, which is how the Settings page removes synthetic data without touching real records.

## Video pipeline

1. The upload is checked for type and size and saved under a random name.
2. OpenCV opens it and rejects empty, truncated or unreadable files with a clear message.
3. Pose: frames are sampled and MediaPipe finds landmarks; `pose.frame_metrics` turns them into angles and indicators; `summarise_sequence` finds the key frame and writes observations, each with the measurement behind it.
4. Tracking: background subtraction finds moving round blobs; a Kalman filter links them; points are marked observed or predicted; bounce and sideways movement are tested against the track's own noise.
5. The measurements are stored. The video is deleted.

## Coordinates

All pitch positions use one system: `x` metres across from middle stump (positive is the off side), `y` metres from the striker's stumps toward the bowler, `z` height. The constants are in `pitchvision/constants.py`.
