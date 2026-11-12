# PitchVision

Cricket analytics for a school team. A coach scores matches ball by ball, times deliveries, maps line and length, and reviews bowling, batting and catching from phone video. Players log their own sessions and goals. A rule-based coach answers questions from the recorded data.

The application starts empty. Nothing on screen is real until your team records it. A set of clearly labelled synthetic sample data can be loaded from Settings to see every screen with data in it, and removed again in one step.

## What is in the box

| Folder | Contents |
|---|---|
| `pitchvision/` | The shared Python package: speed, line and length, scoring, statistics, selection, trajectory and DRS, tracking, pose, coach, machine learning |
| `backend/` | FastAPI REST API, SQLAlchemy models, Alembic migration, tests |
| `frontend/` | React, TypeScript, Tailwind and Recharts interface |
| `notebooks/` | Twelve executed Jupyter notebooks, synthetic sample data and a data dictionary |
| `docs/` | Architecture, feature report |
| `scripts/` | The notebook builder |

The notebooks and the backend import the same `pitchvision` package, so a number in a notebook is the number the application shows.

## Run it

You need Python 3.10 or newer and Node 20 or newer. Nothing else is required: the database is a local SQLite file, and video is read with OpenCV, so FFmpeg is not needed.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

```bash
cd backend && uvicorn app.main:app --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The first account you create becomes the team admin. API documentation is at http://localhost:8000/docs.

The pose model (about 6 MB) is in `pitchvision/models/`. If you delete it, the backend downloads it again the first time a pose analysis runs.

### One process instead of two

```bash
cd frontend && npm run build && cd ../backend && uvicorn app.main:app --port 8000
```

The API then also serves the built interface at http://localhost:8000.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Every setting has a default, so this is optional.

| Variable | Purpose |
|---|---|
| `PITCHVISION_DATABASE_URL` | Database. Defaults to SQLite. See below for PostgreSQL and Supabase. |
| `PITCHVISION_SECRET_KEY` | Signs login tokens. If empty, a random key is generated and stored in `backend/.secret_key`. |
| `PITCHVISION_MAX_UPLOAD_MB` | Largest video accepted. Default 200. |
| `ANTHROPIC_API_KEY` | Optional. Lets the AI Coach phrase answers with Claude. Without it the built-in coach is used. |

Secrets are read from the environment and never sent to the browser.

### PostgreSQL or Supabase

Install a driver (`pip install "psycopg[binary]"`) and set the connection string:

```bash
export PITCHVISION_DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/pitchvision"
```

The models and the migration in `backend/alembic/versions/` are written for both databases. The migration runs when the server starts. I tested on SQLite only; the PostgreSQL path has not been run here.

## Tests

```bash
cd backend && pytest                 # 74 tests: calculators, conversions, scoring rules, statistics, DRS, API, video uploads
cd frontend && npx vitest run        # unit conversion checked against the same known values
```

Notebooks:

```bash
python scripts/build_notebooks.py --execute
```

See `notebooks/README.md` for running them in Jupyter or Google Colab.

## Accounts and roles

Accounts use an email and password, stored as scrypt hashes, with signed tokens. There are three roles.

| Role | Can do |
|---|---|
| Admin | Everything, including giving coaches access and linking accounts to players |
| Coach | Manage players, matches and scoring; add records for anyone |
| Player | View everything; add speed readings, sessions, fielding records, training and goals for their own player profile |

## Honest limits

- A speed worked out from distance and time is an average over that distance, not the release speed.
- Pose estimation gives 2-D angles from one camera. It does not diagnose injury, medical safety or the legality of an action.
- Ball tracking from one ordinary camera is an estimate with a confidence level. Positions are in pixels unless you mark the four pitch corners, which lets the bounce point be placed on the pitch.
- DRS Studio is a training simulation. It is not Hawk-Eye and not an umpiring tool.
- Movement is reported as swing or seam only when it is at least three times its own tracking error.
- Models in the notebooks are compared with a baseline and tested on held-out data. Scores on the synthetic data show the code works, not how well a model would predict real cricket.

`docs/FEATURES.md` lists what is complete, what is partial and what is waiting on data or hardware.
