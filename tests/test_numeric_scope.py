"""Numeric verification is a bounded calculation, not a prose truth detector."""
import json
import unittest
from _bootstrap import core, tools


class NumericScope(unittest.TestCase):
    def test_arbitrary_prose_is_not_certified_by_matching_value(self):
        for claim in (
            'Revenue was 10 and the product is safe',
            'count is not 10',
            'count rose from 4 to 10',
            'count is 10 because treatment cures everyone',
            'count = 10; the product is safe',
            'count = 10 and mean = 10',
        ):
            with self.subTest(claim=claim):
                out = core.verify_claim_core(claim, 'count', {'count': 10, 'claimed_value': 10})
                self.assertEqual(out['verdict'], 'unverifiable')

    def test_canonical_count_match_and_mismatch(self):
        for claim, expected in (('count = 10', 'true'), ('count is 9', 'false'), ('10', 'true')):
            with self.subTest(claim=claim):
                self.assertEqual(core.verify_claim_core(claim, 'count', {'count': 10})['verdict'], expected)

    def test_supported_metrics_keep_scoped_matches_and_mismatches(self):
        fixtures = (
            ('percentage', {'numerator': 1, 'denominator': 4}, '25%', '20%'),
            ('rate', {'numerator': 1, 'denominator': 4}, '0.25', '0.2'),
            ('mean', {'values': [2, 4]}, '3', '4'),
            ('difference', {'a': 10, 'b': 6}, '-4', '4'),
        )
        for metric, evidence, match, mismatch in fixtures:
            for value, expected in ((match, 'true'), (mismatch, 'false')):
                with self.subTest(metric=metric, value=value):
                    out = core.verify_claim_core(f'{metric} = {value}', metric, evidence)
                    self.assertEqual(out['verdict'], expected)

    def test_legacy_labels_are_exact_aliases_not_prose_patterns(self):
        fixtures = (
            ('conversion rate', 'percentage', {'numerator': 1, 'denominator': 4, 'claimed_value': 25}),
            ('average duration', 'mean', {'values': [2, 4], 'claimed_value': 3}),
            ('x', 'mean', {'values': [2, 4], 'claimed_value': 3}),
            ('errors dropped', 'difference', {'a': 10, 'b': 6, 'claimed_value': -4}),
        )
        for label, metric, evidence in fixtures:
            with self.subTest(label=label):
                self.assertEqual(core.verify_claim_core(label, metric, evidence)['verdict'], 'true')
                self.assertEqual(core.verify_claim_core(label + ' and the product is safe', metric, evidence)['verdict'], 'unverifiable')
        out = core.verify_claim_core('errors dropped', 'difference', {'a': 6, 'b': 10, 'claimed_value': 4})
        self.assertEqual(out['verdict'], 'unverifiable')

    def test_directional_alias_cannot_use_tolerance_to_certify_an_increase(self):
        for after, claimed, tolerance in ((10, -1e-10, None), (11, -1, 2)):
            with self.subTest(after=after):
                out = core.verify_claim_core('errors dropped', 'difference',
                    {'a': 10, 'b': after, 'claimed_value': claimed}, tolerance=tolerance)
                self.assertNotEqual(out['verdict'], 'true')
        self.assertEqual(core.verify_claim_core('difference = -1', 'difference',
            {'a': 10, 'b': 11}, tolerance=2)['verdict'], 'true')

    def test_explicit_value_cannot_override_the_claim(self):
        out = core.verify_claim_core('count = 9', 'count', {'count': 10, 'claimed_value': 10})
        self.assertEqual(out['verdict'], 'unverifiable')

    def test_metric_in_claim_must_match_requested_metric(self):
        out = core.verify_claim_core('mean = 10', 'count', {'count': 10, 'claimed_value': 10})
        self.assertEqual(out['verdict'], 'unverifiable')

    def test_percentage_suffix_cannot_silently_change_units(self):
        out = core.verify_claim_core('rate = 50%', 'rate', {'numerator': 1, 'denominator': 2})
        self.assertEqual(out['verdict'], 'unverifiable')

    def test_result_discloses_unauthenticated_supplied_evidence(self):
        out = json.loads(tools.verify_claim({'claim': 'count = 10', 'metric': 'count', 'evidence': {'count': 10}}))
        self.assertEqual(out['verdict'], 'true')
        self.assertIn('not authenticated', out['explanation'])
