"""Boundary and numerical regression cases found during contract review."""
import json
import math
import unittest
from _bootstrap import tools, stats


def evaluate(a, b, **kwargs):
    return json.loads(tools.evaluate_difference(dict(data_a=a, data_b=b, **kwargs)))


class Boundaries(unittest.TestCase):
    def test_every_handler_returns_strict_json_for_non_mapping(self):
        for handler in (tools.verify_claim, tools.evaluate_difference, tools.qualify_conclusion):
            for args in (None, [], 4, True, "bad"):
                with self.subTest(handler=handler.__name__, args=args):
                    out = json.loads(handler(args), parse_constant=lambda x: self.fail(x))
                    self.assertIn("error", out)
                    self.assertIn("explanation", out)

    def test_invalid_numeric_evidence_never_becomes_false(self):
        for bad in (math.nan, math.inf, -math.inf, True, "2", 10**400):
            out = json.loads(tools.verify_claim({"claim": "mean is 2", "metric": "mean",
                                                  "evidence": {"values": [bad, 2]}}))
            self.assertEqual(out["verdict"], "unverifiable")

    def test_invalid_parameters(self):
        for changes in ({"alpha": 0}, {"alpha": 1}, {"alpha": math.nan},
                        {"alpha": True}, {"paired": "false"}, {"data_a": [math.inf, 3]}):
            args = dict(data_a=[1, 2], data_b=[2, 3])
            args.update(changes)
            self.assertIn("error", json.loads(tools.evaluate_difference(args)))

    def test_negative_tolerance(self):
        out = json.loads(tools.verify_claim({"claim": "2", "metric": "count",
                                              "evidence": {"count": 2}, "tolerance": -1}))
        self.assertEqual(out["verdict"], "unverifiable")

    def test_explicit_value_cannot_certify_a_multi_number_claim(self):
        args = {"claim": "rose from 4 to 5", "metric": "mean", "evidence": {"values": [5]}}
        self.assertEqual(json.loads(tools.verify_claim(args))["verdict"], "unverifiable")
        args["evidence"]["claimed_value"] = 5
        self.assertEqual(json.loads(tools.verify_claim(args))["verdict"], "unverifiable")

    def test_empty_count_and_fractional_count(self):
        for ev, expected in (({"values": []}, "true"), ({"count": -1}, "unverifiable"),
                             ({"count": 0.5}, "unverifiable")):
            self.assertEqual(json.loads(tools.verify_claim({"claim": "0", "metric": "count",
                                                             "evidence": ev}))["verdict"], expected)

    def test_scientific_notation(self):
        out = json.loads(tools.verify_claim({"claim": "mean is 1e-3", "metric": "mean",
                                              "evidence": {"values": [0.001]}}))
        self.assertEqual(out["verdict"], "true")


class Statistics(unittest.TestCase):
    def test_degenerate_t_comparisons_are_inconclusive_errors(self):
        for a, b, paired in (([2, 3, 4], [3, 4, 5], True),
                             ([2] * 20, [3] * 20, False)):
            out = evaluate(a, b, paired=paired)
            self.assertEqual(out["verdict"], "inconclusive")
            self.assertIsNone(out["p_value"])
            self.assertIn("error", out)

    def test_matched_odds_ratio_and_reverse(self):
        a, b = [0, 0, 0, 1], [1, 1, 1, 0]
        forward, reverse = evaluate(a, b, paired=True), evaluate(b, a, paired=True)
        self.assertEqual(forward["effect_size"], 3)
        self.assertAlmostEqual(reverse["effect_size"], 1 / 3)
        self.assertEqual(forward["p_value"], reverse["p_value"])
        self.assertEqual(forward["effect_size_measure"], "matched_odds_ratio_b_over_a")

    def test_zero_discordance_convention(self):
        out = evaluate([0, 0, 0], [1, 1, 1], paired=True)
        self.assertEqual(out["effect_size"], 7)
        out = evaluate([0, 1], [0, 1], paired=True)
        self.assertEqual(out["effect_size"], 1)
        self.assertEqual(out["p_value"], 1)

    def test_independent_odds_ratio_orientation(self):
        out = evaluate([1] * 2 + [0] * 8, [1] * 8 + [0] * 2)
        self.assertEqual(out["effect_size"], 16)

    def test_fisher_selected_for_sparse_failures(self):
        out = evaluate([1] * 29 + [0], [1] * 28 + [0] * 2)
        self.assertEqual(out["test_used"], "fisher_exact")

    def test_yates_equal_table_has_no_statistic(self):
        self.assertEqual(stats.chi_square_2x2(10, 10, 10, 10), 0)

    def test_fisher_known_value(self):
        self.assertAlmostEqual(stats.fisher_exact_2x2(1, 9, 11, 3), 0.0027594561852200836, places=12)

    def test_student_cauchy_identity(self):
        self.assertAlmostEqual(stats.t_two_sided_p(1, 1), 0.5, places=9)
        self.assertAlmostEqual(stats.t_two_sided_p(math.sqrt(2), 2), 1 - 1 / math.sqrt(2), places=9)

    def test_large_mcnemar_no_overflow(self):
        self.assertAlmostEqual(stats.mcnemar_exact_p(600, 600), 1, places=12)

    def test_correction_does_not_claim_adjustment(self):
        out = evaluate([0, 0, 0, 1], [1, 1, 1, 0], paired=True, correction="bh")
        self.assertEqual(out["p_value"], 0.625)
        self.assertIn("no family-wise adjustment", out["explanation"])


class Qualification(unittest.TestCase):
    def test_incomplete_prior_is_unverifiable(self):
        for prior in ({"verdict": "true"}, {"verdict": "supported"},
                      {"verdict": "inconclusive", "p_value": math.nan, "test_used": "mcnemar"}):
            out = json.loads(tools.qualify_conclusion({"conclusion": "B is better", "prior_result": prior}))
            self.assertEqual(out["epistemic_status"], "unverifiable")
            self.assertTrue(out["overclaim"])

    def test_reverse_demo_never_claims_b_scored_higher(self):
        result = evaluate([1, 1, 1, 0], [0, 0, 0, 1], paired=True)
        out = json.loads(tools.qualify_conclusion({"conclusion": "B is better", "prior_result": result}))
        self.assertTrue(out["supported_conclusion"].startswith("A scored higher"))

    def test_positive_verification_cannot_support_unrelated_claim(self):
        result = json.loads(tools.verify_claim({"claim": "2", "metric": "mean", "evidence": {"values": [2]}}))
        out = json.loads(tools.qualify_conclusion({"conclusion": "This proves causation", "evidence": result}))
        self.assertTrue(out["overclaim"])
        self.assertNotIn("causation", out["supported_conclusion"])

    def test_hedge_substrings_do_not_excuse_claims(self):
        for text in ("May sales prove B is best", "B may help and definitely causes recovery"):
            out = json.loads(tools.qualify_conclusion({"conclusion": text, "prior_result": {"verdict": "inconclusive", "p_value": 0.625, "test_used": "mcnemar"}}))
            self.assertTrue(out["overclaim"])

    def test_canonical_supported_statement(self):
        result = evaluate([0] * 12, [1] * 12, paired=True)
        args = {"conclusion": "B is better", "prior_result": result}
        first = json.loads(tools.qualify_conclusion(args))
        args["conclusion"] = first["supported_conclusion"]
        self.assertFalse(json.loads(tools.qualify_conclusion(args))["overclaim"])

    def test_demo_exact_sentence_and_repeatability(self):
        args = {"data_a": [1]*17 + [0]*19 + [0]*3 + [1],
                "data_b": [1]*17 + [0]*19 + [1]*3 + [0], "paired": True}
        result = tools.evaluate_difference(args)
        self.assertEqual(result, tools.evaluate_difference(args))
        out = json.loads(tools.qualify_conclusion({"conclusion": "B is better", "prior_result": json.loads(result)}))
        self.assertEqual(out["supported_conclusion"], "B scored higher, but this does not establish that B is better")

