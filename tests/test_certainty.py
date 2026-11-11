import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import core, tools
import json


class CertaintyRegression(unittest.TestCase):
    def incomplete_prior(self, conclusion, prior):
        # Core rejects malformed input; the real public boundary abstains.
        with self.assertRaises(ValueError):
            core.qualify_conclusion_core(conclusion, prior_result=prior)
        result = json.loads(tools.qualify_conclusion(
            {'conclusion': conclusion, 'prior_result': prior}))
        self.assertIn('error', result)
        self.assertEqual(result['epistemic_status'], 'unverifiable')
        self.assertTrue(result['overclaim'])
        self.assertIsNone(result['supported_conclusion'])
        return result

    def test_unrelated_prior_verdict_cannot_support_conclusion(self):
        result = self.incomplete_prior('Dragons exist.', {'verdict': 'true'})
        self.assertEqual(result['epistemic_status'], 'unverifiable')
        self.assertTrue(result['overclaim'])

    def test_inconclusive_does_not_invent_observed_direction(self):
        result = self.incomplete_prior('Dragons exist.', {'verdict': 'inconclusive'})
        self.assertNotIn('data shows a difference', json.dumps(result))
        self.assertNotIn('B scored higher', json.dumps(result))
        self.assertNotIn('A scored higher', json.dumps(result))
        self.assertNotIn('observed difference is within noise', result['explanation'])

    def test_prior_verdict_explanation_does_not_claim_no_evidence(self):
        result = self.incomplete_prior('Dragons exist.', {'verdict': 'true'})
        self.assertNotIn('No usable evidence', result['explanation'])
        self.assertNotIn('no evidence exists', result['explanation'])

    def test_invalid_alpha_is_rejected(self):
        for alpha in (-0.1, 0, 1, 1.1, float('nan'), float('inf'), True):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                core.evaluate_difference_core([0, 1], [1, 1], alpha=alpha)

    def test_multi_part_claim_is_not_verified_by_one_number(self):
        result = core.verify_claim_core(
            'Revenue was 10 and the product is safe', 'count',
            {'count': 10, 'claimed_value': 10})
        self.assertEqual(result['verdict'], 'unverifiable')

    def test_hedge_does_not_excuse_certain_conclusion(self):
        result = self.incomplete_prior(
            'Maybe B helps, but B definitely cures everyone.',
            {'verdict': 'inconclusive'})
        self.assertTrue(result['overclaim'])
        self.assertNotEqual(result['supported_conclusion'], 'Maybe B helps, but B definitely cures everyone.')
