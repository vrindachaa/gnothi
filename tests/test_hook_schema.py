"""The model must be able to label comparisons that the opt-in hook binds."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import schemas

class HookSchema(unittest.TestCase):
    def test_comparison_labels_are_public_optional_arguments(self):
        params = schemas.EVALUATE_DIFFERENCE['parameters']
        for name in ('entity_a', 'entity_b', 'outcome'):
            self.assertIn(name, params['properties'])
            self.assertNotIn(name, params['required'])
        self.assertEqual(params['properties']['outcome']['enum'], ['correctness'])
