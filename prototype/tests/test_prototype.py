"""Tests for the prototype. Run from the prototype folder:
    python -m unittest discover -s tests
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from steelpilot import benchmark, generate_data, ledger, offcut_matcher, sensitivity  # noqa: E402
from steelpilot import config as C  # noqa: E402
from steelpilot.cutting import Bar, auto_nest, manual_nest, summarise  # noqa: E402


class CuttingTests(unittest.TestCase):
    def test_each_cut_uses_one_kerf(self):
        bar = Bar("S1", 1000)
        bar.add("a", 497)
        self.assertEqual(bar.used_mm, 500)
        self.assertTrue(bar.fits(497))          # leaves exactly 0
        self.assertFalse(bar.fits(498))

    def test_clamp_rule(self):
        bar = Bar("S1", 1000)
        self.assertTrue(bar.fits(900))                          # 97 mm left: physically fits
        self.assertFalse(bar.fits(900, respect_clamp=True))     # but cannot be clamped

    def test_bars_never_overfilled(self):
        rng = random.Random(1)
        parts = [(f"p{i}", rng.randint(800, 5800)) for i in range(200)]
        for nest in (manual_nest(parts, []), auto_nest(parts, []), auto_nest(parts, [], configured=False)):
            self.assertTrue(all(b.remnant_mm >= 0 for b in nest))
            self.assertEqual(sum(len(b.cuts) for b in nest), len(parts))

    def test_manual_and_configured_auto_are_cuttable(self):
        rng = random.Random(2)
        parts = [(f"p{i}", rng.randint(800, 5800)) for i in range(100)]
        self.assertTrue(summarise(manual_nest(parts, []))["cuttable"])
        self.assertTrue(summarise(auto_nest(parts, [], configured=True))["cuttable"])


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = generate_data.generate()
        cls.led = ledger.build(cls.t)
        cls.bench = benchmark.run(cls.t)

    def test_generation_is_deterministic(self):
        again = generate_data.generate()
        for name, df in self.t.items():
            self.assertTrue(df.equals(again[name]), f"{name} differs between runs")

    def test_ledger_balances(self):
        led = self.led["ledger"]
        cols = ["good_parts_kg", "client_rev_kg", "internal_rev_kg", "offcut_active_kg",
                "offcut_idle_kg", "drop_scrap_kg", "kerf_kg", "unexplained_kg"]
        self.assertLess((led["bought_kg"] - led[cols].sum(axis=1)).abs().max(), 1.0)

    def test_unexplained_equals_unrecorded_parts(self):
        m = self.led["metrics"]
        unexplained = self.led["by_cause"].loc["Total", "Unexplained"]
        self.assertAlmostEqual(unexplained, m["unlinked_t"], delta=0.05)

    def test_offcut_suggestions_stay_within_project(self):
        matches = offcut_matcher.run(self.t)["matches"]
        suggested = matches[matches["offcut_id"] != ""]
        owner = self.t["offcut_register"].set_index("offcut_id")["project"]
        self.assertTrue((suggested["offcut_id"].map(owner) == suggested["project"]).all())

    def test_blind_review_hides_method(self):
        self.assertNotIn("method", self.bench["blind_review"].columns)
        self.assertEqual(len(self.bench["blind_review"]), 3 * C.N_BENCHMARK_NESTS)


class DecisionTests(unittest.TestCase):
    def test_go_path(self):
        self.assertEqual(benchmark.decide(1.5, 0.9), ("GO", []))

    def test_stop_on_gain(self):
        verdict, reasons = benchmark.decide(0.4, 0.9)
        self.assertEqual(verdict, "STOP")
        self.assertIn("gain", reasons[0])

    def test_stop_on_cuttability(self):
        verdict, reasons = benchmark.decide(3.0, 0.5)
        self.assertEqual(verdict, "STOP")
        self.assertIn("cuttable", reasons[0])


class SensitivityTests(unittest.TestCase):
    def test_closed_forms(self):
        m = sensitivity.run()["metrics"]
        self.assertAlmostEqual(m["p_mid"], (0.085 - 0.075) / (0.225 - 0.075))
        self.assertAlmostEqual(m["p_high"], (0.10 - 0.05) / (0.20 - 0.05))
        self.assertEqual(m["p_low"], 0.0)
        self.assertAlmostEqual(m["crossover_mid"], 0.25)


if __name__ == "__main__":
    unittest.main()
