"""KazProfTerm v1.0: does the reference language change LLM judge scores of Kazakh answers?"""
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parents[2]   # .../skillbridge
REPO = EXP_DIR.parent                           # repository root
ITEMS = EXP_DIR / "items" / "items_v0_1.json"
TERMS = REPO / "data" / "terms.csv"
PROMPT = EXP_DIR / "prompt" / "judge_prompt_v1_0.md"
BUILD = EXP_DIR / "build"
RUNS = EXP_DIR / "runs"
RESULTS = EXP_DIR / "results"

REF_CONDITIONS = ("R_EN", "R_KK", "R_KK_GLOSS")
TERM_FORMS = ("official", "teacher")
QUALITIES = ("full", "partial")
SEED = 20261124
