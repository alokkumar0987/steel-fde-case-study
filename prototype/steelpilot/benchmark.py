"""Manual vs automatic nesting benchmark (case study Section 5.1, Test 2) and stock-length study.

Protocol, as in the case study:
  - 30 past profile nests, sampled at random (in the real pilot: chosen by the client, not by us)
  - each re-run with the stock that existed at the time, offcuts included, rebuilt
    from the offcut register
  - paired comparison, tonnage-weighted, thresholds fixed in config before the run
  - every nest written to a blind review file with random ids and no method label;
    the key is kept in a separate file

Three methods per nest: manual, automatic with default settings, and automatic
configured with the saw's minimum clamp length. The verdict uses the configured run,
because the pilot sets the optimiser up properly in week 1; the default run shows why
that matters ("automatic wastes more" may be a settings problem).

In this prototype "manual" is a replay (drawing order, first fit, clamp respected) and
the blind reviewer is a rule (remnant too short to clamp = not cuttable). In the pilot,
manual is the real historical nest from the client's software and the reviewer is the nesting lead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .cutting import auto_nest, best_length_nest, manual_nest, summarise


def _stock_at(offcuts: pd.DataFrame, project: str, section: str, when: str) -> list[tuple[str, int]]:
    """Offcuts that physically existed for this project/section on the nest date."""
    o = offcuts[(offcuts["project"] == project) & (offcuts["section"] == section) &
                (offcuts["created_date"] < when) &
                ((offcuts["used_date"] == "") | (offcuts["used_date"] >= when))]
    return list(zip(o["offcut_id"], o["length_mm"].astype(int)))


def decide(weighted_gain_pts: float, cuttable_share: float) -> tuple[str, list[str]]:
    """Apply the pre-registered thresholds (config.THRESHOLDS) to a benchmark result."""
    th = C.THRESHOLDS
    reasons = []
    if weighted_gain_pts < th["profile_gain_pts"]:
        reasons.append(f"gain {weighted_gain_pts:.2f} pts < {th['profile_gain_pts']} pts")
    if cuttable_share < th["cuttable_min"]:
        reasons.append(f"cuttable {cuttable_share:.0%} < {th['cuttable_min']:.0%}")
    return ("GO" if not reasons else "STOP"), reasons


def run(t: dict[str, pd.DataFrame], seed: int = C.SEED) -> dict:
    rng = np.random.default_rng(seed + 1)
    parts, nests, offcuts = t["parts"], t["nests"], t["offcut_register"]
    linked = parts[parts["nest_id"] != ""]
    nest_meta = nests.groupby("nest_id")[["project", "section", "nest_date"]].first()
    sample = rng.choice(nest_meta.index.to_numpy(), size=C.N_BENCHMARK_NESTS, replace=False)

    rows, blind = [], []
    for nest_id in sorted(sample):
        meta = nest_meta.loc[nest_id]
        p = linked[linked["nest_id"] == nest_id]
        part_list = list(zip(p["part_id"], p["length_mm"].astype(int)))
        stock = _stock_at(offcuts, meta["project"], meta["section"], meta["nest_date"])
        kg_m = C.SECTIONS[meta["section"]]
        results = {"manual": summarise(manual_nest(part_list, stock)),
                   "auto": summarise(auto_nest(part_list, stock, configured=True)),
                   "auto_default": summarise(auto_nest(part_list, stock, configured=False))}
        rows.append({
            "nest_id": nest_id, "project": meta["project"], "section": meta["section"],
            "parts": len(part_list), "parts_t": p["weight_kg"].sum() / 1000,
            "yield_manual": results["manual"]["yield"], "yield_auto": results["auto"]["yield"],
            "yield_auto_default": results["auto_default"]["yield"],
            "new_bars_manual": results["manual"]["new_bars"], "new_bars_auto": results["auto"]["new_bars"],
            "cuttable_manual": results["manual"]["cuttable"], "cuttable_auto": results["auto"]["cuttable"],
            "cuttable_auto_default": results["auto_default"]["cuttable"],
            "steel_saved_t": (results["manual"]["consumed_mm"] - results["manual"]["offcut_mm"]
                              - results["auto"]["consumed_mm"] + results["auto"]["offcut_mm"]) * kg_m / 1e6,
        })
        for method, r in results.items():
            blind.append({"method": method, "nest_id": nest_id, "bars": r["new_bars"] + r["offcuts_used"],
                          "scrap_mm": r["scrap_mm"], "cuttable": r["cuttable"]})

    df = pd.DataFrame(rows)
    df["gain_pts"] = (df["yield_auto"] - df["yield_manual"]) * 100
    df["gain_default_pts"] = (df["yield_auto_default"] - df["yield_manual"]) * 100
    weighted_gain = float(np.average(df["gain_pts"], weights=df["parts_t"]))
    cuttable_auto = float(df["cuttable_auto"].mean())

    # Blind review file: shuffled, random ids, no method; the key goes in a separate file
    blind_df = pd.DataFrame(blind).sample(frac=1, random_state=seed).reset_index(drop=True)
    blind_df["blind_id"] = [f"B{n:03d}" for n in rng.permutation(len(blind_df)) + 1]
    key = blind_df[["blind_id", "nest_id", "method"]]
    review = blind_df[["blind_id", "bars", "scrap_mm"]].assign(
        reviewer_cuttable=blind_df["cuttable"].map({True: "yes", False: "no"}))

    verdict, reasons = decide(weighted_gain, cuttable_auto)
    metrics = {
        "nests": len(df),
        "weighted_gain_pts": weighted_gain,
        "median_gain_pts": float(df["gain_pts"].median()),
        "nests_auto_better": int((df["gain_pts"] > 0).sum()),
        "cuttable_auto": cuttable_auto,
        "cuttable_manual": float(df["cuttable_manual"].mean()),
        "weighted_gain_default_pts": float(np.average(df["gain_default_pts"], weights=df["parts_t"])),
        "cuttable_auto_default": float(df["cuttable_auto_default"].mean()),
        "blind_nests": len(blind),
        "steel_saved_t": float(df["steel_saved_t"].sum()),
        "verdict": verdict,
        "reasons": reasons,
    }
    return {"nests": df, "blind_review": review, "blind_key": key, "metrics": metrics}


def stock_length_study(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Same cut lists, different stock lengths: how much is scrap, how much becomes offcut.

    Shows that part of profile waste is decided at purchasing (which length to buy),
    before any nesting happens (case study Option G).
    """
    parts = t["parts"]
    rows = []
    options = [(f"{L // 1000} m only", L) for L in C.STOCK_LENGTH_OPTIONS_MM] + [("Best length per bar", None)]
    for label, length in options:
        tot = {"consumed_mm": 0, "scrap_mm": 0, "kerf_mm": 0, "offcut_mm": 0, "parts_mm": 0}
        for (_, _), g in parts.groupby(["project", "section"]):
            plist = list(zip(g["part_id"], g["length_mm"].astype(int)))
            bars = auto_nest(plist, [], length) if length else best_length_nest(plist)
            s = summarise(bars)
            for k in tot:
                tot[k] += s[k]
        rows.append({
            "stock": label,
            "scrap_pct": (tot["scrap_mm"] + tot["kerf_mm"]) / tot["consumed_mm"] * 100,
            "offcut_pct": tot["offcut_mm"] / tot["consumed_mm"] * 100,
            "yield": tot["parts_mm"] / (tot["consumed_mm"] - tot["offcut_mm"]) * 100,
        })
    return pd.DataFrame(rows)
