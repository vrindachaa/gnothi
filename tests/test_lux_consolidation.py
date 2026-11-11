"""Consolidated Lux relevance checks without broad prose/hedge heuristics."""
import json
import unittest
from _bootstrap import tools

class LuxConsolidation(unittest.TestCase):
    def test_unrelated_complete_numeric_results_do_not_label_conclusion(self):
        for verdict in ('true', 'false'):
            out = json.loads(tools.qualify_conclusion({'conclusion':'Dragons exist.',
                'prior_result':{'verdict':verdict,'metric':'count','claimed_value':10,'recomputed_value':10}}))
            self.assertEqual(out['epistemic_status'], 'unverifiable')
            self.assertTrue(out['overclaim'])
    def test_unrelated_statistical_result_does_not_invent_direction(self):
        out = json.loads(tools.qualify_conclusion({'conclusion':'Dragons exist.',
            'prior_result':{'verdict':'inconclusive','p_value':.625,'test_used':'mcnemar','observed_difference':.05}}))
        self.assertEqual(out['epistemic_status'], 'unverifiable')
        self.assertNotIn('scored higher', out['supported_conclusion'])
    def test_token_collisions_do_not_bind_prior_results(self):
        cases = [('Dragons have 10 wings', {'verdict':'true','metric':'count','claimed_value':10,'recomputed_value':10}),
                 ('Vitamin B prevents every disease', {'verdict':'supported','p_value':.01,'test_used':'mcnemar','observed_difference':.05})]
        for conclusion, prior in cases:
            out = json.loads(tools.qualify_conclusion({'conclusion':conclusion,'prior_result':prior}))
            self.assertEqual(out['epistemic_status'], 'unverifiable')
            self.assertTrue(out['overclaim'])

    def test_hedge_cannot_hide_later_nonkeyword_certainty(self):
        out = json.loads(tools.qualify_conclusion({'conclusion':'Cannot conclude B is better, but B eliminates every disease.',
            'prior_result':{'verdict':'inconclusive','p_value':.625,'test_used':'mcnemar','observed_difference':.05}}))
        self.assertTrue(out['overclaim'])
