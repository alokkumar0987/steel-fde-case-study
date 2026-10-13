"""Write output/results.md from the computed results. All findings are worded from the
numbers, so a different seed or assumption gives an honest, different report."""
from __future__ import annotations

import pandas as pd

from . import config as C


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.2f}") -> str:
    def fmt(v):
        if isinstance(v, bool):
            return "yes" if v else "no"
        if isinstance(v, float):
            return floatfmt.format(v)
        return str(v)
    head = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])


def _pct(x: float) -> str:
    return f"{x:.1%}"


def build(ledger: dict, bench: dict, stock: pd.DataFrame, offcut: dict, sens: dict, charts: dict) -> str:
    L, B, O, S = ledger["metrics"], bench["metrics"], offcut["metrics"], sens["metrics"]
    th = C.THRESHOLDS
    best = stock.loc[stock["scrap_pct"].idxmin()]
    current = stock[stock["stock"] == f"{C.STOCK_LENGTH_MM // 1000} m only"].iloc[0]

    claim_rows = pd.DataFrame([
        ["Ledger + cause tagging can be built from ERP-like exports", "4.3, 5.1 Test 1",
         f"{L['verdict']}: {_pct(L['tagged_share'])} of waste tagged, scrap within {_pct(L['max_recon_gap'])}"],
        ["Benchmark protocol runs end to end (paired, weighted, blind, pre-set thresholds)", "5.1 Test 2, 5.2",
         f"{B['verdict']} on this data: {B['weighted_gain_pts']:+.2f} pts, {_pct(B['cuttable_auto'])} cuttable"],
        ["Default optimiser settings can make automatic nesting look worse in practice", "2 (Q4), 3.1 A",
         f"default settings: {B['weighted_gain_default_pts']:+.2f} pts but only {_pct(B['cuttable_auto_default'])} cuttable"],
        ["Profile waste depends on the stock length bought, before nesting", "3.1 G",
         f"scrap {current['scrap_pct']:.2f}% on {C.STOCK_LENGTH_MM // 1000} m vs {best['scrap_pct']:.2f}% with {best['stock'].lower()}"],
        ["Simple offcut matching works, and its stop rule can be measured", "4.3, 5.2",
         f"{O['verdict']}: {_pct(O['accept_rate'])} accepted (stop below {_pct(th['offcut_accept_min'])})"],
        ["Plate vs profile split is uncertain within the client's ranges", "1.2",
         f"plate share {S['p_low']:.0%}–{S['p_high']:.0%}; equal waste at {S['crossover_mid']:.0%}"],
    ], columns=["Claim in the case study", "Section", "Result"])

    ledger_metrics = pd.DataFrame([
        ["Steel bought", f"{L['bought_t']:.1f} t"],
        ["Good parts", f"{L['good_parts_t']:.1f} t"],
        ["Waste (all causes)", f"{L['waste_t']:.1f} t ({_pct(L['waste_rate'])} of bought)"],
        ["Offcuts in stock, active / idle", f"{L['offcut_active_t']:.1f} t / {L['offcut_idle_t']:.1f} t"],
        ["Yield (parts / steel consumed net of offcuts)", _pct(L["yield"])],
        ["Waste tagged with a cause", f"{_pct(L['tagged_share'])} (pass ≥ {_pct(th['ledger_tagged_min'])}, "
                                      f"stop < {_pct(th['ledger_stop_below'])})"],
        ["Largest scrap gap vs scrap sold", f"{_pct(L['max_recon_gap'])} (pass ≤ {_pct(th['scrap_tolerance'])})"],
        ["Parts cut but on no nest record", f"{L['unlinked_parts']} parts, {L['unlinked_t']:.2f} t"],
        ["Verdict", f"**{L['verdict']}**"],
    ], columns=["Measure", "Value"])
    unexplained_t = ledger["by_cause"].loc["Total", "Unexplained"]
    if abs(unexplained_t - L["unlinked_t"]) < 0.05:
        unexplained_text = ("The two match: the ledger finds the planted record gaps instead of hiding them, "
                            "which is what Test 1 is for.")
    else:
        unexplained_text = "They do not fully match, so part of the unexplained waste has another cause to investigate."

    n = bench["nests"]
    methods = pd.DataFrame([
        ["Manual (replay)", _pct(n["yield_manual"].mean()), "—", _pct(B["cuttable_manual"])],
        ["Automatic, default settings", _pct(n["yield_auto_default"].mean()),
         f"{B['weighted_gain_default_pts']:+.2f}", _pct(B["cuttable_auto_default"])],
        ["Automatic, configured (clamp length set)", _pct(n["yield_auto"].mean()),
         f"{B['weighted_gain_pts']:+.2f}", _pct(B["cuttable_auto"])],
    ], columns=["Method", "Mean yield", "Weighted gain vs manual (pts)", "Judged cuttable (blind)"])
    reasons = "; ".join(B["reasons"]) if B["reasons"] else "all thresholds met"

    by_cause = ledger["by_cause"].reset_index().rename(columns={"project": "Project"})
    recon = ledger["recon"].rename(columns={"project": "Project", "scrap_sold_kg": "Scrap sold (kg)",
                                            "ledger_scrap_kg": "Ledger scrap (kg)", "difference": "Difference"})
    recon["Difference"] = recon["Difference"].map(_pct)
    reject = ", ".join(f"{k}: {v}" for k, v in O["reject_reasons"].items()) or "none"

    if B["cuttable_auto_default"] < th["cuttable_min"]:
        default_finding = (
            f"With default settings the optimiser scores {B['weighted_gain_default_pts']:+.2f} pts on paper, "
            f"but only {_pct(B['cuttable_auto_default'])} of its nests can be cut, because it leaves remnants "
            "too short for the saw to clamp. A nesting team that tried the automatic option with default "
            "settings would conclude \"automatic wastes more\". The pilot therefore configures the optimiser in "
            "week 1, before any comparison.")
    else:
        default_finding = (f"Default settings keep {_pct(B['cuttable_auto_default'])} of nests cuttable, "
                           "so settings are not the issue on this data.")

    top_reason = max(O["reject_reasons"], key=O["reject_reasons"].get) if O["reject_reasons"] else None
    if top_reason == "cannot locate in yard":
        offcut_finding = ("Most rejections are offcuts too old to find in the yard. The matcher's value depends "
                          "on knowing where offcuts are, which links nesting to the yard problem the client raised.")
    elif top_reason:
        offcut_finding = f"The most common rejection is \"{top_reason}\"; that rule is the first thing to fix."
    else:
        offcut_finding = "No suggestions were rejected."

    p_mid_share_profile_more = sens["scenarios"].iloc[0]["profile_waste_t"] > sens["scenarios"].iloc[0]["plate_waste_t"]
    mid_word = "profiles waste more tonnes" if p_mid_share_profile_more else "plates waste more tonnes"
    scen = sens["scenarios"][["scenario", "plate_rate", "profile_rate", "overall_rate", "plate_share",
                              "plate_waste_t", "profile_waste_t"]].copy()
    for col in ["plate_rate", "profile_rate", "overall_rate", "plate_share"]:
        scen[col] = scen[col].map(lambda v: f"{v:.1%}")
    scen = scen.rename(columns={"scenario": "Scenario", "plate_rate": "Plate waste", "profile_rate": "Profile waste",
                                "overall_rate": "Overall", "plate_share": "Plate share",
                                "plate_waste_t": "Plate waste (t)", "profile_waste_t": "Profile waste (t)"})
    stock_tbl = stock.rename(columns={"stock": "Stock bought", "scrap_pct": "Scrap + kerf (%)",
                                      "offcut_pct": "Offcut (%)", "yield": "Yield (%)"})

    return f"""# Steel Waste Pilot: prototype results

> **Synthetic data.** Every number below comes from generated data (`steelpilot/config.py`,
> seed {C.SEED}). It shows that the **method** in the case study works end to end. It says
> nothing about how much this client will save. The only section built on the client's
> own figures is section 5.

## What this prototype checks

{md_table(claim_rows)}

## 1. Waste ledger and cause tagging (Test 1)

Every bar bought is followed through every cut, including later cuts of its offcuts,
and each kilogram is put into one bucket: good parts, revision scrap (client or
internal), offcuts still in stock (active or idle), short-remnant scrap, kerf, or
unexplained.

{md_table(ledger_metrics)}

![Waste by cause]({charts['waste']})

Waste by cause, tonnes:

{md_table(by_cause)}

Scrap reconciliation (kerf is dust and is not sold):

{md_table(recon, floatfmt="{:,.0f}")}

**Finding.** The unexplained bucket is {unexplained_t:.2f} t. Parts cut but missing from any
nest record weigh {L['unlinked_t']:.2f} t. {unexplained_text}

## 2. Manual vs automatic nesting (Test 2)

{B['nests']} past profile nests, each re-run with the stock that existed on the nest date
(offcuts included, rebuilt from the offcut register). The gain is weighted by the
tonnes in each nest. All {B['blind_nests']} nests went to a blind review file
(`output/blind_review.csv`, no method column); the key is in `output/blind_key.csv`.

{md_table(methods)}

![Paired benchmark]({charts['bench']})

**Verdict on this data: {B['verdict']}** ({reasons}). Automatic nesting did better on
{B['nests_auto_better']} of {B['nests']} nests (median {B['median_gain_pts']:+.2f} pts).

**Finding.** {default_finding}

## 3. Stock length (Option G)

The same cut lists, nested automatically from different stock lengths:

{md_table(stock_tbl)}

![Stock length]({charts['stock']})

**Finding.** Buying only {C.STOCK_LENGTH_MM // 1000} m bars gives {current['scrap_pct']:.2f}% scrap; choosing
the length per bar gives {best['scrap_pct']:.2f}%. Part of profile waste is decided at
purchasing, before nesting.

## 4. Offcut matching

Next drawing release: {O['new_parts']} parts. Same-project offcuts only, as in the pilot.

| Measure | Value |
|---|---|
| Suggestions made | {O['suggestions']} |
| Accepted by the (simulated) nester | {O['accepted']} ({_pct(O['accept_rate'])}) |
| Rejected, by reason | {reject} |
| Blocked: fit exists only on another project | {O['blocked_cross_project']} |
| No offcut fits | {O['no_fit']} |
| New steel avoided | {O['new_steel_avoided_t']:.2f} t (≈ ${O['value_usd']:,.0f} at $500/t) |
| Verdict (stop below {_pct(th['offcut_accept_min'])}) | **{O['verdict']}** |

**Finding.** {offcut_finding}

## 5. Plate vs profile split (client's own ranges, not synthetic)

{md_table(scen, floatfmt="{:,.0f}")}

![Plate vs profile]({charts['range']})

**Finding.** At the midpoints plates are {S['p_mid']:.0%} of tonnage and {mid_word}. Within the stated ranges the plate share can be anywhere from {S['p_low']:.0%} to
{S['p_high']:.0%}, and plates waste more once they pass {S['crossover_mid']:.0%}. The pilot cannot be
scoped to plates only; the ledger settles the split.

The case study rounds the midpoint plate share to 7%, which gives ~1,260 t plate and
~5,580 t profile waste; the exact share ({S['p_mid']:.2%}) gives the figures above.

## How to reproduce

```
cd prototype
.venv\\Scripts\\activate          (Windows)   |   source .venv/bin/activate   (macOS/Linux)
python run.py
python -m unittest discover -s tests
```
"""


def write(text: str) -> None:
    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (C.OUTPUT_DIR / "results.md").write_text(text, encoding="utf-8")
