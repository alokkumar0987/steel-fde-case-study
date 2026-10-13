"""Every assumption the prototype uses, in one place.

The data is synthetic. These values are chosen to be plausible for a structural
steel fabricator, not taken from the client. Change them here, never inline.
"""
from datetime import date
from pathlib import Path

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

# --- Reproducibility -------------------------------------------------------
SEED = 42
TODAY = date(2026, 10, 1)  # fixed "as of" date so offcut ages are deterministic

# --- Projects and material -------------------------------------------------
PROJECTS = ["P101", "P102", "P103"]
PARTS_PER_PROJECT = 360

# Profile sections and their weight in kg per metre
SECTIONS = {
    "UB305x165x40": 40.3,
    "UC254x254x73": 73.1,
    "PFC200x75x23": 23.4,
    "EA100x100x10": 15.0,
}

PART_LENGTH_MM = (800, 5800)        # uniform range of part lengths
NEST_SIZE = (12, 24)                # parts per nest (one section, one project)
STOCK_LENGTH_MM = 12000             # length the client buys today (assumed)
STOCK_LENGTH_OPTIONS_MM = [6000, 9000, 12000]  # standard mill lengths
KERF_MM = 3                         # saw cut width
MIN_USABLE_OFFCUT_MM = 1000         # shorter remnants are scrap
CLAMP_MM = 150                      # a remnant shorter than this (but > 0) cannot be clamped

# --- Ledger noise ----------------------------------------------------------
REVISION_RATE = 0.08                # share of cut parts later superseded by a revision
CLIENT_REVISION_SHARE = 0.60        # of those, share caused by the client
MISSING_RECORD_RATE = 0.03          # share of bars with one part not recorded on the nest
OFFCUT_UNUSED_RATE = 0.40           # share of offcuts never used again
IDLE_DAYS = 90                      # unused offcut older than this = idle stock
SCRAP_SALES_NOISE = 0.06            # weighbridge vs ledger difference (max, +/-)

# --- Money -------------------------------------------------------------------
STEEL_USD_PER_T = 800
SCRAP_USD_PER_T = 300

# --- Benchmark ---------------------------------------------------------------
N_BENCHMARK_NESTS = 30

# --- Pre-registered thresholds (case study, Section 5) --------------------------
THRESHOLDS = {
    "ledger_tagged_min": 0.90,      # Test 1: share of waste tagged with a cause
    "ledger_stop_below": 0.80,      # stop rule
    "scrap_tolerance": 0.10,        # ledger scrap vs scrap sold
    "profile_gain_pts": 1.0,        # Test 2: tonnage-weighted gain, percentage points
    "cuttable_min": 0.70,           # share of automatic nests judged cuttable
    "offcut_accept_min": 0.10,      # stop rule for the offcut matcher
}

# --- Client's stated ranges (discovery notes) for the sensitivity check ----------
ANNUAL_TONNES = 80_000
PLATE_WASTE_RANGE = (0.20, 0.25)
PROFILE_WASTE_RANGE = (0.05, 0.10)
OVERALL_WASTE_RANGE = (0.07, 0.10)
