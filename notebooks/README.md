# PitchVision notebooks

Twelve Jupyter notebooks that do the calculations behind the application in plain Python. They import the same `pitchvision` package the backend uses, so a figure in a notebook matches the figure on screen.

| Notebook | What it does |
|---|---|
| 01_bowling_speed_analysis | Distance and time to speed, unit conversion, speed statistics, radar against stopwatch |
| 02_bowling_action_analysis | Video frames, MediaPipe landmarks, joint angles, comparing two deliveries |
| 03_cricket_ball_tracking | Detecting and tracking a ball with OpenCV, with tracking confidence |
| 04_drs_trajectory_simulation | Trajectory projection, stump intersection, uncertainty, LBW rules |
| 05_bowling_accuracy_analysis | Line and length bands, accuracy, heatmaps, session comparison |
| 06_swing_seam_analysis | Sideways movement from tracked paths, with a noise test |
| 07_batting_analysis | Averages, strike rates, pace and spin splits, wagon wheel |
| 08_fielding_analysis | Catching, run-outs and ground fielding, with confidence ranges |
| 09_team_match_analytics | Scorecards, run rates, partnerships, economy, team selection |
| 10_cricket_machine_learning | Cleaning, features, models against a baseline, importance, explanations |
| 11_ai_cricket_coach | Evidence-based answers and recommendations, with an optional language model |
| 12_complete_cricket_analytics_pipeline | Raw files to reports and CSV exports |

The data in `data/` is synthetic. See `data/DATA_DICTIONARY.md` for the columns. Every notebook was executed from the top and its saved outputs are in the files, so you can read the results without running anything.

## Run them on your computer

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r notebooks/requirements.txt
jupyter lab notebooks/
```

Open a notebook and choose Run All. The first cell of each one finds the project folder and adds it to the import path.

To rebuild and re-run all twelve from the command line:

```bash
python scripts/build_notebooks.py --execute
```

## Run them in Google Colab

1. Put the project folder somewhere Colab can reach: push it to GitHub, or zip it and upload the zip to Colab's file panel.
2. Open a new Colab notebook and run:

   ```python
   !git clone https://github.com/YOUR-ACCOUNT/pitchvision.git
   %cd pitchvision
   !pip install -q -r notebooks/requirements.txt
   ```

   For an uploaded zip, run `!unzip -q pitchvision.zip` and `%cd pitchvision` instead of the clone.
3. Use File, then Open notebook, then Upload, and choose one of the `.ipynb` files. Or open it from the cloned folder.
4. Run All.

## Using your own data

Replace the files in `notebooks/data/` with files that have the same columns. Notebook 12 checks each table and stops with a message if a column is missing or a ball breaks a scoring rule.

## Using your own video

Notebooks 02, 03 and 06 have a `VIDEO_PATH` setting near the top. In Colab, upload the clip with the file panel and set `VIDEO_PATH = "my_clip.mp4"`. With the setting left as `None` they use a synthetic demonstration instead.

Film from a fixed camera. Side-on suits pose analysis, and a camera behind the bowler suits swing. A frame rate of 120 fps or more helps ball tracking a lot.

## Where the results go

Notebooks write CSV files to `notebooks/exports/`. Notebook 12 writes its reports to `notebooks/exports/pipeline/`.
