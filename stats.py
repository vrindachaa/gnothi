"""Pure-stdlib statistical primitives for gnothi.

No numpy/scipy. Deterministic (fixed-seed bootstrap). Every function here is a
plain numerical routine with no side effects, no I/O, no randomness beyond an
explicit, caller-supplied seed.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Iterable, List, Sequence, Tuple


# --------------------------------------------------------------------------
# Core special functions (Numerical-Recipes-style, pure Python)
# --------------------------------------------------------------------------

def _betacf(a: float, b: float, x: float, maxit: int = 200, eps: float = 3e-10) -> float:
    """Continued fraction for the incomplete beta function (Lentz's algorithm)."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b), x in [0, 1]."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def t_two_sided_p(t: float, df: float) -> float:
    """Two-sided p-value for a t-statistic with df degrees of freedom."""
    if df <= 0:
        return 1.0
    t = abs(t)
    x = df / (df + t * t)
    p = betai(df / 2.0, 0.5, x)
    return max(0.0, min(1.0, p))


def chi2_p_df1(chi2: float) -> float:
    """Upper-tail p-value for a chi-square statistic with 1 degree of freedom.

    chi2_1 = Z^2 for Z ~ N(0,1), so P(chi2_1 > x) = erfc(sqrt(x/2)).
    """
    if chi2 < 0:
        return 1.0
    return math.erfc(math.sqrt(chi2 / 2.0))


# --------------------------------------------------------------------------
# McNemar's exact test (paired binary)
# --------------------------------------------------------------------------

def binom_pmf(k: int, n: int, p: float = 0.5) -> float:
    if p == 0.5:
        return math.comb(n, k) / (2 ** n)
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                    - math.lgamma(n - k + 1) + k * math.log(p)
                    + (n - k) * math.log1p(-p))


def mcnemar_exact_p(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value from discordant counts b, c.

    p = 2 * min(P(X <= min(b,c)), P(X >= max(b,c))) under X ~ Binomial(b+c, 0.5).
    """
    n = b + c
    if n == 0:
        return 1.0
    lo, hi = min(b, c), max(b, c)
    p_le = sum(binom_pmf(k, n) for k in range(0, lo + 1))
    p_ge = sum(binom_pmf(k, n) for k in range(hi, n + 1))
    return min(1.0, 2.0 * min(p_le, p_ge))


# --------------------------------------------------------------------------
# Welch's t-test (unpaired continuous) / paired t-test
# --------------------------------------------------------------------------

def welch_t_test(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float, float]:
    n1, n2 = len(a), len(b)
    m1, m2 = statistics.mean(a), statistics.mean(b)
    v1 = statistics.variance(a) if n1 > 1 else 0.0
    v2 = statistics.variance(b) if n2 > 1 else 0.0
    se2 = (v1 / n1 if n1 else 0.0) + (v2 / n2 if n2 else 0.0)
    if se2 <= 0:
        return 0.0, max(n1 + n2 - 2, 1), 1.0
    t = (m2 - m1) / math.sqrt(se2)
    num = se2 ** 2
    den = 0.0
    if n1 > 1:
        den += (v1 / n1) ** 2 / (n1 - 1)
    if n2 > 1:
        den += (v2 / n2) ** 2 / (n2 - 1)
    df = num / den if den > 0 else max(n1 + n2 - 2, 1)
    p = t_two_sided_p(t, df)
    return t, df, p


def paired_t_test(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float, float]:
    diffs = [bi - ai for ai, bi in zip(a, b)]
    n = len(diffs)
    if n < 2:
        return 0.0, max(n - 1, 1), 1.0
    md = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    if sd == 0:
        return (0.0 if md == 0 else math.inf), n - 1, (1.0 if md == 0 else 0.0)
    t = md / (sd / math.sqrt(n))
    df = n - 1
    p = t_two_sided_p(t, df)
    return t, df, p


# --------------------------------------------------------------------------
# Mann-Whitney U (non-normal unpaired continuous)
# --------------------------------------------------------------------------

def _rank_with_ties(values: Sequence[float]) -> Tuple[List[float], List[int]]:
    """Average ranks (1-based) for `values`; also returns tie-group sizes."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    tie_sizes: List[int] = []
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        tie_sizes.append(j - i + 1)
        i = j + 1
    return ranks, tie_sizes


def mannwhitney_u(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float]:
    """Returns (U1, two-sided p-value) using the normal approximation with tie correction."""
    n1, n2 = len(a), len(b)
    combined = list(a) + list(b)
    ranks, tie_sizes = _rank_with_ties(combined)
    r1 = sum(ranks[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2.0
    n = n1 + n2
    mu_u = n1 * n2 / 2.0
    tie_term = sum(t ** 3 - t for t in tie_sizes)
    if n * (n - 1) == 0:
        return u1, 1.0
    sigma_u = math.sqrt((n1 * n2 / 12.0) * ((n + 1) - tie_term / (n * (n - 1))))
    if sigma_u == 0:
        return u1, 1.0
    z = (u1 - mu_u) / sigma_u
    p = 2.0 * (1.0 - normal_cdf(abs(z)))
    return u1, max(0.0, min(1.0, p))


# --------------------------------------------------------------------------
# Chi-square (Yates) and Fisher exact (2x2 categorical rates)
# --------------------------------------------------------------------------

def chi_square_2x2(a: int, b: int, c: int, d: int) -> float:
    """Chi-square statistic with Yates continuity correction for a 2x2 table
    [[a, b], [c, d]] (df = 1)."""
    n = a + b + c + d
    if n == 0:
        return 0.0
    row1, row2 = a + b, c + d
    col1, col2 = a + c, b + d
    cells = [(a, row1 * col1 / n), (b, row1 * col2 / n),
             (c, row2 * col1 / n), (d, row2 * col2 / n)]
    chi2 = 0.0
    for obs, exp in cells:
        if exp == 0:
            continue
        chi2 += max(0.0, abs(obs - exp) - 0.5) ** 2 / exp
    return chi2


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """Two-sided exact Fisher p-value for a 2x2 table [[a, b], [c, d]]."""
    row1, row2 = a + b, c + d
    col1, col2 = a + c, b + d
    n = row1 + row2

    def hyper(k: int) -> float:
        if k < 0 or k > row1 or (col1 - k) < 0 or (col1 - k) > row2:
            return 0.0
        return (math.comb(row1, k) * math.comb(row2, col1 - k)) / math.comb(n, col1)

    p_obs = hyper(a)
    k_min = max(0, col1 - row2)
    k_max = min(row1, col1)
    total = 0.0
    for k in range(k_min, k_max + 1):
        pk = hyper(k)
        if pk <= p_obs * (1 + 1e-7):
            total += pk
    return max(0.0, min(1.0, total))


# --------------------------------------------------------------------------
# Effect sizes
# --------------------------------------------------------------------------

def cohens_d(a: Sequence[float], b: Sequence[float]) -> float:
    n1, n2 = len(a), len(b)
    if n1 + n2 <= 2:
        return 0.0
    m1, m2 = statistics.mean(a), statistics.mean(b)
    v1 = statistics.variance(a) if n1 > 1 else 0.0
    v2 = statistics.variance(b) if n2 > 1 else 0.0
    pooled_var = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
    if pooled_var <= 0:
        return 0.0
    return (m2 - m1) / math.sqrt(pooled_var)


def odds_ratio_2x2(a: int, b: int, c: int, d: int) -> float:
    """Odds ratio = (a/c) / (b/d) = a*d / (b*c); Haldane-Anscombe 0.5 correction
    is applied uniformly if any cell is zero."""
    if min(a, b, c, d) == 0:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    if b * c == 0:
        return math.inf
    return (a * d) / (b * c)


def rank_biserial(u1: float, n1: int, n2: int) -> float:
    if n1 * n2 == 0:
        return 0.0
    return 1.0 - (2.0 * u1) / (n1 * n2)


# --------------------------------------------------------------------------
# Bootstrap confidence interval (fixed seed)
# --------------------------------------------------------------------------

def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = q * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def bootstrap_ci_mean_diff(
    a: Sequence[float], b: Sequence[float], paired: bool = False,
    seed: int = 0, n_boot: int = 2000,
) -> Tuple[float, float]:
    """Percentile bootstrap CI (2.5-97.5) for mean(b) - mean(a), fixed-seed RNG."""
    rng = random.Random(seed)
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return (0.0, 0.0)
    diffs: List[float] = []
    if paired:
        pairs = list(zip(a, b))
        n = len(pairs)
        for _ in range(n_boot):
            sample = [pairs[rng.randrange(n)] for _ in range(n)]
            da = statistics.mean(p[0] for p in sample)
            db = statistics.mean(p[1] for p in sample)
            diffs.append(db - da)
    else:
        for _ in range(n_boot):
            sa = [a[rng.randrange(n1)] for _ in range(n1)]
            sb = [b[rng.randrange(n2)] for _ in range(n2)]
            diffs.append(statistics.mean(sb) - statistics.mean(sa))
    diffs.sort()
    return (_percentile(diffs, 0.025), _percentile(diffs, 0.975))


def bootstrap_ci_rate_diff(
    a: Sequence[int], b: Sequence[int], seed: int = 0, n_boot: int = 2000,
) -> Tuple[float, float]:
    """Same as bootstrap_ci_mean_diff but for 0/1 rate data (unpaired)."""
    return bootstrap_ci_mean_diff(a, b, paired=False, seed=seed, n_boot=n_boot)


# --------------------------------------------------------------------------
# Multiple-comparison correction
# --------------------------------------------------------------------------

def bonferroni_correction(p: float, k: int = 1) -> float:
    return max(0.0, min(1.0, p * max(k, 1)))


def benjamini_hochberg(pvalues: Sequence[float]) -> List[float]:
    """Benjamini-Hochberg adjusted p-values (step-up procedure), monotone."""
    k = len(pvalues)
    if k == 0:
        return []
    indexed = sorted(enumerate(pvalues), key=lambda item: item[1])
    adjusted = [0.0] * k
    prev = 1.0
    for rank in range(k, 0, -1):
        idx, p = indexed[rank - 1]
        val = min(prev, p * k / rank)
        adjusted[idx] = val
        prev = val
    return adjusted


# --------------------------------------------------------------------------
# Normality heuristic (deterministic, no scipy)
# --------------------------------------------------------------------------

def skewness(data: Sequence[float]) -> float:
    n = len(data)
    if n < 3:
        return 0.0
    m = statistics.mean(data)
    s = statistics.pstdev(data)
    if s == 0:
        return 0.0
    return (sum((x - m) ** 3 for x in data) / n) / (s ** 3)


def looks_normal_enough(data: Sequence[float]) -> bool:
    """Deterministic, conservative heuristic standing in for a formal normality
    test: enough samples and not strongly skewed. Prefers Mann-Whitney U
    (robust, no distributional assumption) whenever in doubt."""
    n = len(data)
    if n < 20:
        return False
    return abs(skewness(data)) < 1.0


def is_binary_series(data: Iterable[float]) -> bool:
    values = set(data)
    return len(values) > 0 and values.issubset({0, 1, 0.0, 1.0})
