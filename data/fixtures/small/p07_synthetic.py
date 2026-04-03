"""Synthetic fixture data for P07 analysis tests.

Generates a small (n=200) survey DataFrame with known structure
for deterministic testing of drivers, segmentation, and MaxDiff/TURF.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_survey_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic survey DataFrame for P07 testing.

    Columns:
    - ATT_01..ATT_20: 5-point Likert attitude items (IVs for drivers/clustering)
    - SAT_01, SAT_02: 5-point satisfaction DVs
    - NPS: 0-10 NPS score DV
    - BEH_01..BEH_03: behavioral binary DVs
    - GENDER: 1/2
    - AGE_GROUP: 1-4
    - SEGMENT: 1-3 (pre-assigned for testing, removable)
    - MD_TASK_01..MD_TASK_12: MaxDiff task responses (best=1, worst=-1, not_shown=0)
    - ACCEPT_01..ACCEPT_08: binary acceptance for TURF (0/1)
    """
    rng = np.random.RandomState(seed)

    data: dict[str, np.ndarray] = {}

    # 20 attitude items (5-point Likert)
    for i in range(1, 21):
        data[f"ATT_{i:02d}"] = rng.choice([1, 2, 3, 4, 5], size=n)

    # Satisfaction DVs
    data["SAT_01"] = rng.choice([1, 2, 3, 4, 5], size=n, p=[0.05, 0.1, 0.2, 0.35, 0.3])
    data["SAT_02"] = rng.choice([1, 2, 3, 4, 5], size=n, p=[0.05, 0.15, 0.25, 0.3, 0.25])
    data["NPS"] = rng.choice(range(11), size=n)

    # Binary behavioral DVs
    for i in range(1, 4):
        data[f"BEH_{i:02d}"] = rng.choice([0, 1], size=n, p=[0.4, 0.6])

    # Demographics
    data["GENDER"] = rng.choice([1, 2], size=n)
    data["AGE_GROUP"] = rng.choice([1, 2, 3, 4], size=n)

    # Pre-assigned segment (for profile testing)
    data["SEGMENT"] = rng.choice([1, 2, 3], size=n)

    # MaxDiff tasks: 12 tasks, each with best(1), worst(-1), not_shown(0)
    for i in range(1, 13):
        data[f"MD_TASK_{i:02d}"] = rng.choice([-1, 0, 1], size=n, p=[0.25, 0.5, 0.25])

    # TURF acceptance binary (8 items)
    for i in range(1, 9):
        data[f"ACCEPT_{i:02d}"] = rng.choice([0, 1], size=n, p=[0.4, 0.6])

    return pd.DataFrame(data)


def iv_columns() -> list[str]:
    """Return attitude IV column names."""
    return [f"ATT_{i:02d}" for i in range(1, 21)]


def dv_columns() -> list[str]:
    """Return DV column names for drivers analysis."""
    return ["SAT_01", "SAT_02", "NPS"]


def maxdiff_items() -> list[str]:
    """Return MaxDiff item column names."""
    return [f"MD_TASK_{i:02d}" for i in range(1, 13)]


def turf_acceptance_columns() -> list[str]:
    """Return TURF binary acceptance column names."""
    return [f"ACCEPT_{i:02d}" for i in range(1, 9)]
