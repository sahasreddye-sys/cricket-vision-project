# Data dictionary

Every file in this folder is synthetic. `pitchvision/sample_data.py` generated it with a fixed random seed, so the players, matches and numbers are invented. Each file has a `synthetic` column set to `True`. Replace the files with your own using the same column names and the notebooks will run on your data.

Pitch coordinates are in metres. `x` is the distance across the pitch from middle stump (positive is the off side; left-handers are mirrored). `y` is the distance from the striker's stumps toward the bowler. The pitch is 20.12 m long.

## players.csv

| Column | Meaning |
|---|---|
| name | Player's name. Must match the name used in the other files. |
| role | batter, bowler, all_rounder or wicket_keeper |
| bowl_style | pace_fast, pace_medium, spin_off or spin_leg. Empty for players who do not bowl. |
| batting_hand | right or left |
| synthetic | True for generated rows |

## matches.csv

| Column | Meaning |
|---|---|
| match_id | Whole number that links to `balls.csv` and `fielding.csv` |
| date, season, format, overs | When it was played, the season label, the format (for example T20) and overs per side |
| opponent, venue | Opposition name and Home or Away |
| batted_first | Which side batted first |
| our_score, our_overs, their_score, their_overs | Final totals as runs/wickets and overs.balls (3.4 means 3 overs and 4 balls) |
| result | won, lost or tied, from our side's point of view |

## balls.csv

One row per ball bowled, in order within each innings.

| Column | Meaning |
|---|---|
| match_id, innings, ball_no | Which match and innings, and the ball's position in it. Wides and no-balls take a ball_no too. |
| batting_team | Name of the batting side |
| over | Over number, starting at 0 |
| striker, non_striker, bowler | Player names |
| bowl_type | pace or spin |
| x, y | Where the ball pitched. Empty if not recorded. |
| runs_bat | Runs off the bat, 0 to 6 |
| wides | Total wides on this ball (the penalty plus any runs run). 0 if not a wide. |
| no_balls | 1 if the ball was a no-ball |
| byes, leg_byes | Runs taken as byes or leg-byes |
| wicket_kind | bowled, caught, lbw, stumped, run_out, hit_wicket and so on. Empty if no wicket. |
| player_out, fielder | Who was out and who took the catch or effected the run-out. Empty if none. |
| shot_type | drive, cut, pull, flick, sweep, glance, loft or defence. Empty if not recorded. |
| shot_angle | Direction the ball was hit, in degrees. 0 is straight back past the bowler and angles grow clockwise toward the off side. Empty if the batter did not score or it was not recorded. |
| date, season, format | Copied from the match |

## deliveries.csv

Net-session deliveries used for line and length.

| Column | Meaning |
|---|---|
| player | Bowler's name |
| session, session_no, date | Session label, its number for that bowler, and its date |
| x, y | Where the ball pitched. A few rows are empty on purpose so the notebooks have to handle missing values. |
| bowl_type | pace or spin |

## speeds.csv

| Column | Meaning |
|---|---|
| player, date | Bowler and day |
| source | stopwatch (distance and time) or radar |
| distance_m, time_s | The measurement behind a stopwatch speed. Empty for radar rows, and for a few stopwatch rows with a missing time. |
| kmh | Speed in km/h. For a stopwatch row it is the average speed over the distance, not the release speed. |

## fielding.csv

| Column | Meaning |
|---|---|
| player, match_id, date | Fielder and when |
| kind | catch, drop, run_out, direct_hit, missed_run_out, stumping, missed_stumping, clean_stop or misfield |
| count | How many times it happened (always 1 in the sample) |
