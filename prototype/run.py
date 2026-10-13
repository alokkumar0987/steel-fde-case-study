"""Run the whole prototype: generate data, build the ledger, run the benchmark, the
stock-length study and the offcut matcher, check the client's ranges, then write
charts and output/results.md.

Usage (from the prototype folder, with the virtual environment active):
    python run.py
"""
from __future__ import annotations

import math

from steelpilot import benchmark, charts, generate_data, ledger, offcut_matcher, report, sensitivity
from steelpilot import config as C


def sanity_checks(t, led, bench, sens) -> None:
    """Fail loudly if the numbers break the accounting or the protocol."""
    # Every kilogram bought is accounted for (unexplained absorbs only real record gaps)
    parts_cols = ["good_parts_kg", "client_rev_kg", "internal_rev_kg", "offcut_active_kg",
                  "offcut_idle_kg", "drop_scrap_kg", "kerf_kg", "unexplained_kg"]
    gap = (led["ledger"]["bought_kg"] - led["ledger"][parts_cols].sum(axis=1)).abs().max()
    assert gap < 1.0, f"ledger does not balance: max gap {gap:.2f} kg"
    assert (led["ledger"]["unexplained_kg"] >= 0).all(), "negative unexplained waste"
    # Blind review hides the method
    assert "method" not in bench["blind_review"].columns, "blind review file leaks the method"
    assert bench["blind_review"]["blind_id"].is_unique, "blind ids are not unique"
    # Manual nests respect the saw (they were cut in reality)
    assert bench["metrics"]["cuttable_manual"] == 1.0, "manual replay produced uncuttable nests"
    # Sensitivity matches the closed form
    m = sens["metrics"]
    assert math.isclose(m["crossover_mid"], 0.075 / 0.30), "crossover differs from closed form"
    assert math.isclose(m["p_high"], 1 / 3), "upper plate share differs from (10-5)/(20-5)"


def main() -> None:
    tables = generate_data.generate()
    generate_data.write(tables)
    t = generate_data.load()   # work from the CSVs, as the pilot would from exports

    led = ledger.build(t)
    bench = benchmark.run(t)
    stock = benchmark.stock_length_study(t)
    offcut = offcut_matcher.run(t)
    sens = sensitivity.run()
    sanity_checks(t, led, bench, sens)

    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    led["ledger"].to_csv(C.OUTPUT_DIR / "ledger.csv", index=False)
    bench["nests"].to_csv(C.OUTPUT_DIR / "benchmark_nests.csv", index=False)
    bench["blind_review"].to_csv(C.OUTPUT_DIR / "blind_review.csv", index=False)
    bench["blind_key"].to_csv(C.OUTPUT_DIR / "blind_key.csv", index=False)
    stock.to_csv(C.OUTPUT_DIR / "stock_length_study.csv", index=False)
    offcut["matches"].to_csv(C.OUTPUT_DIR / "offcut_matches.csv", index=False)

    chart_files = {
        "waste": charts.waste_by_cause(led["by_cause"]),
        "bench": charts.benchmark_paired(bench["nests"], bench["metrics"]["weighted_gain_pts"]),
        "stock": charts.stock_length(stock),
        "range": charts.plate_profile_range(sens["grid"], sens["metrics"]),
    }
    report.write(report.build(led, bench, stock, offcut, sens, chart_files))

    L, B, O = led["metrics"], bench["metrics"], offcut["metrics"]
    print(f"Ledger     {L['verdict']:<20} {L['tagged_share']:.1%} of waste tagged, scrap gap {L['max_recon_gap']:.1%}")
    print(f"Benchmark  {B['verdict']:<20} {B['weighted_gain_pts']:+.2f} pts, {B['cuttable_auto']:.0%} cuttable "
          f"(default settings: {B['weighted_gain_default_pts']:+.2f} pts, {B['cuttable_auto_default']:.0%} cuttable)")
    print(f"Offcuts    {O['verdict']:<20} {O['accept_rate']:.1%} accepted, {O['blocked_cross_project']} blocked cross-project")
    print(f"Report     {C.OUTPUT_DIR / 'results.md'}")


if __name__ == "__main__":
    main()
