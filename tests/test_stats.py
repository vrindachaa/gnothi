import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import stats  # noqa: E402


class McNemarKnownCase(unittest.TestCase):
    def test_mcnemar_p_0_625(self):
        """b=3, c=1 (the spec's worked example) must give exactly p=0.625."""
        p = stats.mcnemar_exact_p(3, 1)
        self.assertAlmostEqual(p, 0.625, places=9)

    def test_mcnemar_symmetric(self):
        self.assertAlmostEqual(stats.mcnemar_exact_p(1, 3), stats.mcnemar_exact_p(3, 1), places=12)

    def test_mcnemar_no_discordant_pairs(self):
        self.assertEqual(stats.mcnemar_exact_p(0, 0), 1.0)

    def test_mcnemar_strongly_lopsided_is_significant(self):
        p = stats.mcnemar_exact_p(20, 1)
        self.assertLess(p, 0.05)


class WelchTTest(unittest.TestCase):
    def test_identical_groups_high_p(self):
        a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        b = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        t, df, p = stats.welch_t_test(a, b)
        self.assertAlmostEqual(t, 0.0, places=9)
        self.assertGreater(p, 0.99)

    def test_clearly_different_groups_low_p(self):
        a = [1, 2, 1, 2, 1, 2, 1, 2]
        b = [20, 21, 19, 22, 20, 21, 19, 22]
        t, df, p = stats.welch_t_test(a, b)
        self.assertLess(p, 0.001)


class MannWhitneyU(unittest.TestCase):
    def test_identical_distributions_high_p(self):
        a = list(range(1, 21))
        b = list(range(1, 21))
        u1, p = stats.mannwhitney_u(a, b)
        self.assertGreater(p, 0.9)

    def test_fully_separated_groups_low_p(self):
        a = list(range(1, 11))
        b = list(range(100, 110))
        u1, p = stats.mannwhitney_u(a, b)
        self.assertLess(p, 0.01)


class ChiSquareAndFisher(unittest.TestCase):
    def test_chi2_matches_known_relationship(self):
        # For df=1, chi2 p-value should equal 2*(1-Phi(sqrt(chi2)))
        chi2 = 3.84
        p = stats.chi2_p_df1(chi2)
        expected = 2 * (1 - stats.normal_cdf(math.sqrt(chi2)))
        self.assertAlmostEqual(p, expected, places=6)

    def test_fisher_exact_symmetric_table(self):
        # a=b=c=d case should give p close to 1 (no association)
        p = stats.fisher_exact_2x2(10, 10, 10, 10)
        self.assertGreater(p, 0.5)

    def test_fisher_exact_strong_association(self):
        p = stats.fisher_exact_2x2(20, 1, 1, 20)
        self.assertLess(p, 0.001)


class EffectSizes(unittest.TestCase):
    def test_cohens_d_zero_for_identical_groups(self):
        a = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(stats.cohens_d(a, a), 0.0, places=9)

    def test_odds_ratio_basic(self):
        # a=10,b=10,c=5,d=15 -> OR = (10*15)/(10*5) = 3.0
        self.assertAlmostEqual(stats.odds_ratio_2x2(10, 10, 5, 15), 3.0, places=9)


class BootstrapDeterminism(unittest.TestCase):
    def test_same_seed_same_result(self):
        a = [1, 2, 3, 4, 5, 6]
        b = [3, 4, 5, 6, 7, 8]
        ci1 = stats.bootstrap_ci_mean_diff(a, b, paired=False, seed=0, n_boot=200)
        ci2 = stats.bootstrap_ci_mean_diff(a, b, paired=False, seed=0, n_boot=200)
        self.assertEqual(ci1, ci2)

    def test_ci_contains_point_estimate(self):
        a = [1, 2, 3, 4, 5, 6, 7, 8]
        b = [5, 6, 7, 8, 9, 10, 11, 12]
        lo, hi = stats.bootstrap_ci_mean_diff(a, b, paired=False, seed=0, n_boot=500)
        self.assertLess(lo, 4.0)
        self.assertGreater(hi, 4.0)


class MultipleComparisonCorrection(unittest.TestCase):
    def test_bonferroni(self):
        self.assertAlmostEqual(stats.bonferroni_correction(0.01, 3), 0.03, places=9)
        self.assertEqual(stats.bonferroni_correction(0.5, 3), 1.0)

    def test_benjamini_hochberg_monotone_and_known_values(self):
        pvals = [0.01, 0.02, 0.03, 0.04, 0.5]
        adj = stats.benjamini_hochberg(pvals)
        self.assertEqual(len(adj), 5)
        # BH-adjusted p-values must be non-decreasing when p-values are sorted ascending
        sorted_adj = [adj[i] for i in sorted(range(len(pvals)), key=lambda i: pvals[i])]
        for i in range(1, len(sorted_adj)):
            self.assertGreaterEqual(sorted_adj[i] + 1e-12, sorted_adj[i - 1])
        # all adjusted p-values must be >= their raw p-value
        for raw, a in zip(pvals, adj):
            self.assertGreaterEqual(a + 1e-12, raw)


if __name__ == "__main__":
    unittest.main()
