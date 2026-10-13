"""Plate vs profile split from the client's own ranges (case study Section 1.2).

This is arithmetic on the numbers in the discovery notes, not synthetic data.
If overall waste o = p * plate_rate + (1 - p) * profile_rate, the plate share is
p = (o - profile_rate) / (plate_rate - profile_rate). The ranges given allow a wide p.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from . import config as C


def plate_share(overall: float, plate: float, profile: float) -> float | None:
    p = (overall - profile) / (plate - profile)
    return p if 0 <= p <= 1 else None


def feasible_range() -> tuple[float, float]:
    """Smallest and largest plate share consistent with any combination of range ends."""
    shares = [plate_share(o, pl, pr) for o, pl, pr in itertools.product(
        C.OVERALL_WASTE_RANGE, C.PLATE_WASTE_RANGE, C.PROFILE_WASTE_RANGE)]
    valid = [s for s in shares if s is not None]
    low = 0.0 if any(s is None for s in shares) else min(valid)   # negative p clips to 0
    return low, max(valid)


def crossover(plate_rate: float, profile_rate: float) -> float:
    """Plate share at which plates and profiles waste the same tonnes."""
    return profile_rate / (plate_rate + profile_rate)


def run() -> dict:
    mid = {k: float(np.mean(v)) for k, v in
           {"plate": C.PLATE_WASTE_RANGE, "profile": C.PROFILE_WASTE_RANGE, "overall": C.OVERALL_WASTE_RANGE}.items()}
    p_mid = plate_share(mid["overall"], mid["plate"], mid["profile"])
    low, high = feasible_range()
    grid = pd.DataFrame({"plate_share": np.linspace(0, 0.40, 81)})
    grid["plate_waste_t"] = grid["plate_share"] * C.ANNUAL_TONNES * mid["plate"]
    grid["profile_waste_t"] = (1 - grid["plate_share"]) * C.ANNUAL_TONNES * mid["profile"]

    scenarios = []
    for name, o, pl, pr in [("Midpoints", mid["overall"], mid["plate"], mid["profile"]),
                            ("Plate-heavy end", 0.10, 0.20, 0.05),
                            ("Profile-heavy end", 0.07, 0.25, 0.065)]:
        p = plate_share(o, pl, pr)
        scenarios.append({"scenario": name, "plate_rate": pl, "profile_rate": pr, "overall_rate": o,
                          "plate_share": p,
                          "plate_waste_t": p * C.ANNUAL_TONNES * pl,
                          "profile_waste_t": (1 - p) * C.ANNUAL_TONNES * pr})
    return {
        "grid": grid,
        "scenarios": pd.DataFrame(scenarios),
        "metrics": {"p_mid": p_mid, "p_low": low, "p_high": high,
                    "crossover_mid": crossover(mid["plate"], mid["profile"])},
    }
