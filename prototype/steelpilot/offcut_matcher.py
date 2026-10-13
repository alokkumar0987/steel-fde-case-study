"""Offcut matching for the next drawing release (case study Sections 4.3 and 5.2).

Rules on purpose, no optimiser: for each new part (longest first), list offcuts in
stock of the same section that are long enough (part + kerf), and suggest the one
that leaves the smallest remnant. Same-project offcuts only, as in the pilot.
A match that exists only on another project is counted as "blocked" because it
needs Finance's cost-loading rule first.

The nester's decision is simulated by rules standing in for real reasons:
  - offcut older than 180 days    -> reject, "cannot locate in yard"
  - remnant left too short to clamp -> reject, "cannot clamp"
  - otherwise                      -> accept
"""
from __future__ import annotations

import pandas as pd

from . import config as C

STALE_DAYS = 180


def run(t: dict[str, pd.DataFrame]) -> dict:
    stock = t["offcut_register"]
    stock = stock[stock["used_date"] == ""].copy()
    new_parts = t["new_parts"].sort_values("length_mm", ascending=False)
    taken: set[str] = set()
    rows = []

    for _, part in new_parts.iterrows():
        need = int(part["length_mm"]) + C.KERF_MM
        fits = stock[(stock["section"] == part["section"]) & (stock["length_mm"] >= need) &
                     (~stock["offcut_id"].isin(taken))]
        same = fits[fits["project"] == part["project"]]
        if same.empty:
            outcome = "blocked: other project" if not fits.empty else "no offcut fits"
            rows.append({"part_id": part["part_id"], "project": part["project"], "section": part["section"],
                         "length_mm": part["length_mm"], "weight_kg": part["weight_kg"],
                         "offcut_id": "", "leftover_mm": None, "decision": outcome, "reason": ""})
            continue
        best = same.assign(leftover=same["length_mm"] - need).sort_values("leftover").iloc[0]
        leftover = int(best["leftover"])
        if best["age_days"] > STALE_DAYS:
            decision, reason = "reject", "cannot locate in yard"
        elif 0 < leftover < C.CLAMP_MM:
            decision, reason = "reject", "cannot clamp"
        else:
            decision, reason = "accept", ""
            taken.add(best["offcut_id"])
        rows.append({"part_id": part["part_id"], "project": part["project"], "section": part["section"],
                     "length_mm": part["length_mm"], "weight_kg": part["weight_kg"],
                     "offcut_id": best["offcut_id"], "leftover_mm": leftover,
                     "decision": decision, "reason": reason})

    df = pd.DataFrame(rows)
    suggested = df[df["decision"].isin(["accept", "reject"])]
    accepted = df[df["decision"] == "accept"]
    accept_rate = len(accepted) / len(suggested) if len(suggested) else 0.0
    saved_t = accepted["weight_kg"].sum() / 1000
    metrics = {
        "new_parts": len(df),
        "suggestions": len(suggested),
        "accepted": len(accepted),
        "accept_rate": accept_rate,
        "blocked_cross_project": int((df["decision"] == "blocked: other project").sum()),
        "no_fit": int((df["decision"] == "no offcut fits").sum()),
        "reject_reasons": df[df["decision"] == "reject"]["reason"].value_counts().to_dict(),
        "new_steel_avoided_t": saved_t,
        "value_usd": saved_t * (C.STEEL_USD_PER_T - C.SCRAP_USD_PER_T),
        "verdict": "BUILD" if accept_rate >= C.THRESHOLDS["offcut_accept_min"] else "STOP",
    }
    return {"matches": df, "metrics": metrics}
