"""Paths and constants shared by every pipeline stage."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST_PATH = DATA_DIR / "manifest.json"
SITE_DATA_DIR = REPO_ROOT / "web" / "public" / "data"

# Identify the pipeline to data publishers; contact via the public repository.
USER_AGENT = "costmodel-data-pipeline/0.1 (+https://github.com/GYZ001/costmodel)"

# 1 troy ounce, exact by definition (International Yard and Pound Agreement, 1959).
GRAMS_PER_TROY_OUNCE = 31.1034768
