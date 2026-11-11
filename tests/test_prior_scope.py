"""Prior results must bind the exact numeric assertion, not just its metric."""
import json
import unittest
from _bootstrap import core, tools


class PriorScope(unittest.TestCase):
    def test_opposite_canonical_comparison_is_not_supported(self):
        prior = core.evaluate_difference_core([0] * 10, [1] * 10, paired=True)
        out = core.qualify_conclusion_core('The supplied observations statistically support B < A under the selected test.', prior_result=prior)
        self.assertNotEqual(out['epistemic_status'], 'supported')

    def test_numeric_prior_binds_value(self):
        for claim, evidence in [('count = 10', {'count': 10}), ('count = 9', {'count': 10})]:
            prior = core.verify_claim_core(claim, 'count', evidence)
            self.assertEqual(core.qualify_conclusion_core(claim, prior_result=prior)['epistemic_status'],
                             'supported' if prior['verdict'] == 'true' else 'false')
            self.assertEqual(core.qualify_conclusion_core('count = 999', prior_result=prior)['epistemic_status'], 'unverifiable')

    def test_numeric_prior_does_not_certify_directional_prose(self):
        prior = core.verify_claim_core('percentage = 25%', 'percentage', {'numerator': 1, 'denominator': 4})
        self.assertEqual(core.qualify_conclusion_core('conversion rose to 25%', prior_result=prior)['epistemic_status'], 'unverifiable')

    def test_canonical_recomputed_value_is_supported_even_after_false_claim(self):
        prior = core.verify_claim_core('count = 9', 'count', {'count': 10})
        out = core.qualify_conclusion_core('The recomputed count is 10.0 in the supplied evidence.', prior_result=prior)
        self.assertEqual(out['epistemic_status'], 'supported')
        self.assertFalse(out['overclaim'])

    def test_malformed_prior_direction_is_strict_and_publicly_uncertain(self):
        for observed in (-1, float('nan'), True):
            prior = {'verdict': 'supported', 'p_value': .01, 'test_used': 'mcnemar', 'observed_difference': observed}
            with self.subTest(observed=observed):
                with self.assertRaises(ValueError):
                    core.qualify_conclusion_core('B is better', prior_result=prior)
                out = json.loads(tools.qualify_conclusion({'conclusion': 'B is better', 'prior_result': prior}))
                self.assertEqual(out['epistemic_status'], 'unverifiable')
                self.assertIn('error', out)
