"""PitchVision shared analytics package.

Every calculation used by the FastAPI backend and by the Jupyter notebooks lives
here, so the application and the notebooks can never disagree about a formula.

Modules
-------
constants   Pitch geometry and thresholds (metres, SI units throughout).
speed       Unit conversion and average ball-speed statistics.
pitchmap    Line and length classification, accuracy, heatmaps.
scoring     Ball-by-ball innings engine that follows the Laws of Cricket.
stats       Batting, bowling and fielding statistics, leaderboards, wagon wheel.
selection   Explainable playing-XI analysis.
trajectory  Ball-flight fitting, swing/seam deviation, DRS/LBW simulation.
tracking    OpenCV ball detection and Kalman tracking from video.
pose        MediaPipe pose estimation, joint angles, movement indicators.
coach       Rule-based, evidence-backed coaching (optional LLM wrapper).
ml          scikit-learn models with honest evaluation.
sample_data Clearly labelled SYNTHETIC data generators for demos and notebooks.
"""

__version__ = "1.0.0"
