"""End-to-end demo scenario from spec.md: 40 paired tasks, models A and B.
Verifies the full gnothi flow and that the McNemar p-value is genuinely
*computed* from the data, not hardcoded anywhere in the pipeline."""

import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import tools, stats  # noqa: E402


def _independent_mcnemar_reference(b: int, c: int) -> float:
    """A from-scratch reimplementation of the exact McNemar formula, written
    independently of stats.mcnemar_exact_p, to cross-check the tool's output
    rather than comparing it against a literal constant."""
    n = b + c

    def binom_pmf(k, n, p=0.5):
        return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))

    lo, hi = min(b, c), max(b, c)
    p_le = sum(binom_pmf(k, n) for k in range(lo + 1))
    p_ge = sum(binom_pmf(k, n) for k in range(hi, n + 1))
    return 2 * min(p_le, p_ge)


class DemoScenarioEndToEnd(unittest.TestCase):
    def setUp(self):
        # 40 paired tasks: both right 17, both wrong 19, B-right/A-wrong 3, A-right/B-wrong 1.
        self.data_a = [1] * 17 + [0] * 19 + [0] * 3 + [1] * 1
        self.data_b = [1] * 17 + [0] * 19 + [1] * 3 + [0] * 1
        self.assertEqual(len(self.data_a), 40)
        self.assertEqual(len(self.data_b), 40)
        # Sanity on the aggregate "B wins by 2" framing from the spec.
        self.assertEqual(sum(self.data_a), 18)
        self.assertEqual(sum(self.data_b), 20)

    def test_step1_aggregate_looks_like_a_b_win(self):
        self.assertGreater(sum(self.data_b), sum(self.data_a))

    def test_step2_mcnemar_p_value_is_computed_not_hardcoded(self):
        b_wins = sum(1 for a, b in zip(self.data_a, self.data_b) if a == 0 and b == 1)
        a_wins = sum(1 for a, b in zip(self.data_a, self.data_b) if a == 1 and b == 0)
        self.assertEqual(b_wins, 3)
        self.assertEqual(a_wins, 1)

        reference_p = _independent_mcnemar_reference(b_wins, a_wins)
        engine_p = stats.mcnemar_exact_p(b_wins, a_wins)
        self.assertAlmostEqual(engine_p, reference_p, places=12)
        self.assertAlmostEqual(engine_p, 0.625, places=9)

    def test_step3_evaluate_difference_returns_inconclusive(self):
        result = json.loads(tools.evaluate_difference({
            "data_a": self.data_a, "data_b": self.data_b, "paired": True,
        }))
        self.assertEqual(result["test_used"], "mcnemar")
        self.assertAlmostEqual(result["p_value"], 0.625, places=9)
        self.assertEqual(result["verdict"], "inconclusive")
        self.eval_result = result

    def test_step4_qualify_conclusion_flags_overclaim(self):
        eval_result = json.loads(tools.evaluate_difference({
            "data_a": self.data_a, "data_b": self.data_b, "paired": True,
        }))
        qualify_result = json.loads(tools.qualify_conclusion({
            "conclusion": "Model B is better than Model A.",
            "prior_result": eval_result,
        }))
        self.assertEqual(qualify_result["epistemic_status"], "inconclusive")
        self.assertTrue(qualify_result["overclaim"])
        self.assertIn("does not establish", qualify_result["supported_conclusion"])

    def test_full_pipeline_matches_spec_narrative(self):
        """The complete demo beat, start to finish, through the public tool API only."""
        eval_json = tools.evaluate_difference({"data_a": self.data_a, "data_b": self.data_b, "paired": True})
        eval_result = json.loads(eval_json)
        self.assertEqual(eval_result["verdict"], "inconclusive")

        qualify_json = tools.qualify_conclusion({
            "conclusion": "Model B is better than Model A.",
            "prior_result": eval_result,
        })
        qualify_result = json.loads(qualify_json)
        self.assertEqual(qualify_result["epistemic_status"], "inconclusive")
        self.assertTrue(qualify_result["overclaim"])
        # "B scored higher" preserved, "better" claim retracted — the exact beat from spec.md.
        self.assertIn("scored higher", qualify_result["supported_conclusion"])
        self.assertIn("does not establish", qualify_result["supported_conclusion"])


if __name__ == "__main__":
    unittest.main()
