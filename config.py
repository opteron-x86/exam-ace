"""Application configuration for Project+ Quiz."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths
QUESTION_BANKS_DIR = os.path.join(BASE_DIR, "question_banks")
DATABASE_PATH = os.path.join(BASE_DIR, "data", "quiz_history.db")

# Quiz defaults
DEFAULT_TIME_LIMIT = 100  # minutes (Project+ exam is 100 min)
DEFAULT_QUESTION_COUNT = 90  # Project+ has ~90 scored questions
PASSING_SCORE = 710  # Out of 900 scale
SCORE_SCALE_MAX = 900
SCORE_SCALE_MIN = 100

# Exam domain weights (for scaled scoring)
DOMAIN_WEIGHTS = {
    "1": {"name": "Project Management Concepts", "weight": 0.33},
    "2": {"name": "Project Life Cycle Phases", "weight": 0.30},
    "3": {"name": "Tools and Documentation", "weight": 0.19},
    "4": {"name": "Basics of IT and Governance", "weight": 0.18},
}

# Question types
QUESTION_TYPES = {
    "multiple_choice": "Multiple Choice",
    "multiple_select": "Multiple Select",
    "matching": "Matching",
    "ordering": "Ordering / Sequencing",
    "drag_drop": "Drag and Drop",
    "fill_in": "Fill in the Blank",
    "scenario": "Scenario-Based",
}
