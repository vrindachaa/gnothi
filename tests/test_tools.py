import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import tools, core  # noqa: E402


class VerifyClaimUnverifiableVsFalse(unittest.TestCase):
    """The core epistemic distinction: missing evidence -> unverifiable, never false."""

    def test_missing_evidence_is_unverifiable_not_false(self):
        out = json.loads(tools.verify_claim({
            "claim": "conversion rose to 4.2%", "metric": "percentage", "evidence": {},
        }))
        self.assertEqual(out["verdict"], "unverifiable")

    def test_evidence_present_but_insufficient_is_unverifiable(self):
        out = json.loads(tools.verify_claim({
            "claim": "conversion rose to 4.2%", "metric": "percentage",
            "evidence": {"some_unrelated_field": 123},
        }))
        self.assertEqual(out["verdict"], "unverifiable")

    def test_evidence_contradicts_claim_is_false(self):
        out = json.loads(tools.verify_claim({
            "claim": "conversion rate", "metric": "percentage",
            "evidence": {"numerator": 42, "denominator": 1000, "claimed_value": 10.0},
        }))
        self.assertEqual(out["verdict"], "false")
        self.assertAlmostEqual(out["recomputed_value"], 4.2, places=6)

    def test_evidence_matches_claim_is_true(self):
        out = json.loads(tools.verify_claim({
            "claim": "conversion rate", "metric": "percentage",
            "evidence": {"numerator": 42, "denominator": 1000, "claimed_value": 4.2},
        }))
        self.assertEqual(out["verdict"], "true")

    def test_mean_metric(self):
        out = json.loads(tools.verify_claim({
            "claim": "average duration", "metric": "mean",
            "evidence": {"values": [10, 12, 14], "claimed_value": 12.0},
        }))
        self.assertEqual(out["verdict"], "true")
        self.assertAlmostEqual(out["recomputed_value"], 12.0, places=9)

    def test_difference_metric(self):
        out = json.loads(tools.verify_claim({
            "claim": "errors dropped", "metric": "difference",
            "evidence": {"a": 10, "b": 6, "claimed_value": -4},
        }))
        self.assertEqual(out["verdict"], "true")

    def test_unknown_metric_is_unverifiable_not_an_exception(self):
        out = json.loads(tools.verify_claim({
            "claim": "x", "metric": "nonsense", "evidence": {"foo": 1},
        }))
        self.assertEqual(out["verdict"], "unverifiable")

    def test_handler_never_raises_on_garbage_input(self):
        out = json.loads(tools.verify_claim({"claim": None, "metric": None, "evidence": None}))
        self.assertIn("verdict", out)


class EvaluateDifferenceInconclusiveVsNotSupported(unittest.TestCase):
    def test_non_significant_difference_is_inconclusive_not_not_supported(self):
        # small, noisy samples -> should not reach significance
        a = [5, 6, 4, 5, 6]
        b = [6, 5, 7, 5, 6]
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": False}))
        self.assertEqual(out["verdict"], "inconclusive")

    def test_significant_in_favor_of_a_is_not_supported(self):
        # data_b is clearly LOWER than data_a -> contradicts "b is better" direction
        a = [20, 21, 19, 22, 20, 21, 19, 22]
        b = [1, 2, 1, 2, 1, 2, 1, 2]
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": False}))
        self.assertEqual(out["verdict"], "not_supported")

    def test_significant_in_favor_of_b_is_supported(self):
        a = [1, 2, 1, 2, 1, 2, 1, 2]
        b = [20, 21, 19, 22, 20, 21, 19, 22]
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": False}))
        self.assertEqual(out["verdict"], "supported")

    def test_inconclusive_is_distinct_value_from_not_supported(self):
        self.assertNotEqual("inconclusive", "not_supported")  # sanity on the enum itself


class PairedVsUnpairedTestSelection(unittest.TestCase):
    def test_paired_binary_selects_mcnemar(self):
        a = [1] * 17 + [0] * 19 + [0] * 3 + [1] * 1
        b = [1] * 17 + [0] * 19 + [1] * 3 + [0] * 1
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": True}))
        self.assertEqual(out["test_used"], "mcnemar")

    def test_unpaired_binary_selects_chi_square_or_fisher(self):
        a = [1] * 15 + [0] * 15
        b = [1] * 20 + [0] * 10
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": False}))
        self.assertIn(out["test_used"], ("chi_square", "fisher_exact"))

    def test_paired_continuous_selects_paired_t(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        b = [1.5, 2.3, 3.1, 4.4, 5.2, 6.6]
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": True}))
        self.assertEqual(out["test_used"], "paired_t")

    def test_unpaired_continuous_normal_selects_welch(self):
        a = [float(x) for x in range(1, 26)]
        b = [float(x) + 2 for x in range(1, 26)]
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": False}))
        self.assertEqual(out["test_used"], "welch_t")

    def test_unpaired_continuous_nonnormal_small_selects_mann_whitney(self):
        a = [1.0, 1.1, 1.2, 1.3, 100.0]  # heavily skewed, n<20
        b = [2.0, 2.1, 2.2, 2.3, 200.0]
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": False}))
        self.assertEqual(out["test_used"], "mann_whitney")

    def test_paired_vs_unpaired_choose_different_tests_for_same_binary_data(self):
        a = [1, 0, 1, 0, 1, 0, 1, 0]
        b = [1, 1, 0, 0, 1, 1, 0, 1]
        paired_out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": True}))
        unpaired_out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": False}))
        self.assertEqual(paired_out["test_used"], "mcnemar")
        self.assertIn(unpaired_out["test_used"], ("chi_square", "fisher_exact"))
        self.assertNotEqual(paired_out["test_used"], unpaired_out["test_used"])

    def test_mismatched_paired_lengths_handled_without_exception(self):
        out = json.loads(tools.evaluate_difference({"data_a": [1, 2], "data_b": [1, 2, 3], "paired": True}))
        self.assertIn("error", out)
        self.assertIn("verdict", out)  # still returns the full error-shaped contract


class McNemarWorkedExample(unittest.TestCase):
    def test_b3_c1_gives_p_0_625_through_the_tool(self):
        a = [1] * 17 + [0] * 19 + [0] * 3 + [1] * 1  # A correct = 18
        b = [1] * 17 + [0] * 19 + [1] * 3 + [0] * 1  # B correct = 20
        self.assertEqual(sum(a), 18)
        self.assertEqual(sum(b), 20)
        out = json.loads(tools.evaluate_difference({"data_a": a, "data_b": b, "paired": True}))
        self.assertEqual(out["test_used"], "mcnemar")
        self.assertAlmostEqual(out["p_value"], 0.625, places=9)
        self.assertEqual(out["verdict"], "inconclusive")


class QualifyConclusion(unittest.TestCase):
    def test_overclaim_true_when_inconclusive(self):
        eval_result = {"verdict": "inconclusive", "p_value": 0.625, "effect_size": 0.05,
                       "confidence_interval": [-0.05, 0.15], "test_used": "mcnemar", "explanation": "x"}
        out = json.loads(tools.qualify_conclusion({
            "conclusion": "Model B is better than Model A.", "prior_result": eval_result,
        }))
        self.assertEqual(out["epistemic_status"], "inconclusive")
        self.assertTrue(out["overclaim"])
        self.assertIn("inconclusive", out["supported_conclusion"])

    def test_general_superiority_overclaims_even_when_comparison_supported(self):
        eval_result = {"verdict": "supported", "p_value": 0.001, "effect_size": 1.2,
                       "confidence_interval": [0.5, 1.9], "observed_difference": 1.2, "test_used": "welch_t", "explanation": "x"}
        out = json.loads(tools.qualify_conclusion({
            "conclusion": "Model B is better than Model A.", "prior_result": eval_result,
        }))
        self.assertEqual(out["epistemic_status"], "supported")
        self.assertTrue(out["overclaim"])

    def test_false_verdict_from_verify_claim_maps_to_false_status(self):
        verify_result = {"verdict": "false", "claimed_value": 10.0, "recomputed_value": 4.2,
                         "metric": "percentage", "explanation": "x"}
        out = json.loads(tools.qualify_conclusion({
            "conclusion": "percentage = 10%", "prior_result": verify_result,
        }))
        self.assertEqual(out["epistemic_status"], "false")
        self.assertTrue(out["overclaim"])

    def test_unverifiable_without_any_evidence(self):
        out = json.loads(tools.qualify_conclusion({"conclusion": "Something happened."}))
        self.assertEqual(out["epistemic_status"], "unverifiable")

    def test_already_hedged_conclusion_is_not_flagged_as_overclaim(self):
        eval_result = {"verdict": "inconclusive", "p_value": 0.625, "effect_size": 0.05,
                       "confidence_interval": [-0.05, 0.15], "test_used": "mcnemar", "explanation": "x"}
        out = json.loads(tools.qualify_conclusion({
            "conclusion": "B may be slightly better, but this is not conclusive.",
            "prior_result": eval_result,
        }))
        self.assertFalse(out["overclaim"])

    def test_handler_never_raises_on_garbage_input(self):
        out = json.loads(tools.qualify_conclusion({"conclusion": None}))
        self.assertIn("epistemic_status", out)


if __name__ == "__main__":
    unittest.main()
