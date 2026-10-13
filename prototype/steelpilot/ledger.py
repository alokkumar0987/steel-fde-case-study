"""Waste ledger and cause tagging (case study Sections 4.3 and 5.1, Test 1).

For every bar bought, follow it through every cut, including later cuts of its
offcuts (the "lineage", keyed by root_stock_id), and account for each kilogram:

  bought = good parts + revision scrap (client / internal) + offcuts still in stock
           (active / idle) + short-remnant scrap + kerf + unexplained

Cause rules, in priority order:
  1. a part cut and later superseded            -> revision waste, client or internal
  2. an unused offcut older than IDLE_DAYS      -> idle stock (not waste, reported apart)
  3. short remnants and saw kerf                -> nesting / process waste
  4. whatever does not balance                  -> unexplained (its size is itself a finding)
"""
from __future__ import annotations

import pandas as pd

from . import config as C

CAUSES = ["Nesting / process", "Client revision", "Internal revision", "Unexplained"]


def build(t: dict[str, pd.DataFrame]) -> dict:
    stock, parts, nests = t["stock_items"], t["parts"], t["nests"]
    offcuts, revisions, sales = t["offcut_register"], t["revisions"], t["scrap_sales"]
    kg_per_mm = nests["section"].map(C.SECTIONS) / 1000

    # One row per (cut event, part) actually recorded on a nest
    cuts = nests.assign(part_id=nests["part_ids"].str.split(";")).explode("part_id")
    cuts = cuts[cuts["part_id"].fillna("") != ""]
    cuts = cuts.merge(parts[["part_id", "weight_kg", "status"]], on="part_id", how="left")
    cuts = cuts.merge(revisions[["part_id", "reason"]], on="part_id", how="left")

    def by_root(df: pd.DataFrame, col: str) -> pd.Series:
        return df.groupby("root_stock_id")[col].sum()

    good = by_root(cuts[cuts["status"] == "cut"], "weight_kg")
    rev_client = by_root(cuts[(cuts["status"] == "superseded") & (cuts["reason"] == "client")], "weight_kg")
    rev_internal = by_root(cuts[(cuts["status"] == "superseded") & (cuts["reason"] == "internal")], "weight_kg")

    nests = nests.assign(
        scrap_kg=(nests["remnant_type"] == "scrap") * nests["remnant_mm"] * kg_per_mm,
        kerf_kg=nests["n_cuts"] * C.KERF_MM * kg_per_mm,
    )
    drop_scrap = by_root(nests, "scrap_kg")
    kerf = by_root(nests, "kerf_kg")

    in_stock = offcuts[offcuts["used_date"] == ""]
    idle_mask = in_stock["age_days"] > C.IDLE_DAYS
    off_active = by_root(in_stock[~idle_mask], "weight_kg")
    off_idle = by_root(in_stock[idle_mask], "weight_kg")

    led = stock[["stock_id", "project", "section", "weight_kg"]].rename(
        columns={"stock_id": "root_stock_id", "weight_kg": "bought_kg"}).set_index("root_stock_id")
    for name, s in [("good_parts_kg", good), ("client_rev_kg", rev_client), ("internal_rev_kg", rev_internal),
                    ("offcut_active_kg", off_active), ("offcut_idle_kg", off_idle),
                    ("drop_scrap_kg", drop_scrap), ("kerf_kg", kerf)]:
        led[name] = s.reindex(led.index).fillna(0.0)

    accounted = led[["good_parts_kg", "client_rev_kg", "internal_rev_kg", "offcut_active_kg",
                     "offcut_idle_kg", "drop_scrap_kg", "kerf_kg"]].sum(axis=1)
    led["unexplained_kg"] = (led["bought_kg"] - accounted).where(lambda x: x.abs() >= 1.0, 0.0)
    led = led.reset_index()

    # Waste by cause, tonnes, per project
    cause_cols = {"Nesting / process": ["drop_scrap_kg", "kerf_kg"], "Client revision": ["client_rev_kg"],
                  "Internal revision": ["internal_rev_kg"], "Unexplained": ["unexplained_kg"]}
    by_cause = pd.DataFrame({cause: led.groupby("project")[cols].sum().sum(axis=1) / 1000
                             for cause, cols in cause_cols.items()})
    by_cause.loc["Total"] = by_cause.sum()

    total_waste = by_cause.loc["Total"].sum()
    tagged_share = 1 - by_cause.loc["Total", "Unexplained"] / total_waste

    # Scrap reconciliation: ledger's physical scrap vs scrap sold (kerf is dust, not sold)
    ledger_scrap = led.groupby("project")[["drop_scrap_kg", "client_rev_kg", "internal_rev_kg"]].sum().sum(axis=1)
    recon = sales.set_index("project").assign(ledger_scrap_kg=ledger_scrap.round(0))
    recon["difference"] = recon["scrap_sold_kg"] / recon["ledger_scrap_kg"] - 1

    th = C.THRESHOLDS
    unlinked = parts[(parts["nest_id"] == "")]
    bought_t = led["bought_kg"].sum() / 1000
    offcut_t = (led["offcut_active_kg"].sum() + led["offcut_idle_kg"].sum()) / 1000
    metrics = {
        "bought_t": bought_t,
        "good_parts_t": led["good_parts_kg"].sum() / 1000,
        "waste_t": total_waste,
        "waste_rate": total_waste / bought_t,
        "offcut_active_t": led["offcut_active_kg"].sum() / 1000,
        "offcut_idle_t": led["offcut_idle_kg"].sum() / 1000,
        "yield": (led["good_parts_kg"].sum() / 1000) / (bought_t - offcut_t),
        "tagged_share": tagged_share,
        "max_recon_gap": recon["difference"].abs().max(),
        "unlinked_parts": len(unlinked),
        "unlinked_t": unlinked["weight_kg"].sum() / 1000,
    }
    if tagged_share < th["ledger_stop_below"]:
        verdict = "STOP"
    elif tagged_share >= th["ledger_tagged_min"] and metrics["max_recon_gap"] <= th["scrap_tolerance"]:
        verdict = "PASS"
    else:
        verdict = "CONTINUE WITH GAPS"
    metrics["verdict"] = verdict
    return {"ledger": led, "by_cause": by_cause, "recon": recon.reset_index(), "metrics": metrics}
