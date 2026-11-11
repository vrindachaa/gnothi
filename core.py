"""Core logic for gnothi's three tools: verify_claim, evaluate_difference,
qualify_conclusion.

These functions return plain Python dicts (JSON-serializable) and may raise
``ValueError`` on malformed input; the thin wrappers in ``tools.py`` catch
everything and always hand back a JSON string, per the handler contract.

Pure stdlib. No network, no subprocess, no filesystem writes, no LLM calls.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from typing import Any, Dict, List, Optional, Sequence, Union

try:
    from . import stats as st
except ImportError:  # pragma: no cover - direct (non-package) import path for tests/tools
    import stats as st  # type: ignore

ALLOWED_METRICS = {"percentage", "mean", "rate", "count", "difference"}
HEDGE_PATTERNS = (
    "may", "might", "could", "possibly", "not necessarily", "does not establish",
    "no evidence", "unclear", "inconclusive", "cannot conclude", "not conclusive",
    "insufficient evidence", "within noise",
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _numeric_list(ev: Dict[str, Any], key: str) -> Optional[List[float]]:
    v = ev.get(key)
    if isinstance(v, list) and len(v) > 0 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return [float(x) for x in v]
    return None


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a finite number, not a boolean or string.")
    value = float(value)
    if not math.isfinite(value) or abs(value) > 1e100:
        raise ValueError("Numbers must be finite with magnitude at most 1e100.")
    return value


def _scoped_claim_value(claim: str, metric: str, explicit: Any) -> Optional[float]:
    """Parse a closed calculation grammar, never arbitrary natural language.

    Accept a bare number or '<metric> (=|is) <number>', optionally ending
    in a period. '%' is allowed only for percentage (percentage-point units).
    Legacy labels below are exact aliases for an explicit numeric assertion,
    not a general heuristic for interpreting prose. No evidence is authenticated.
    """
    text = claim.strip().lower()
    aliases = {
        'percentage': {'percentage', 'conversion rate'},
        'mean': {'mean', 'average duration', 'x'},
        'rate': {'rate'},
        'count': {'count'},
        'difference': {'difference', 'errors dropped'},
    }
    if text in aliases[metric]:
        if explicit is None or (text == 'errors dropped' and explicit >= 0):
            return None
        return _finite(explicit)
    number = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?'
    match = re.fullmatch(
        rf'(?:{metric}\s*(?:=|is)\s*)?(?P<value>{number})(?P<percent>%?)\.?', text)
    if match is None or (match.group('percent') and metric != 'percentage'):
        return None
    value = _finite(float(match.group('value')))
    # Conflicting assertions are ambiguous, not a license to choose one.
    if explicit is not None and _finite(explicit) != value:
        return None
    return value


# --------------------------------------------------------------------------
# verify_claim
# --------------------------------------------------------------------------

def _recompute_metric(metric: str, evidence: Dict[str, Any]) -> Optional[float]:
    if metric in ("percentage", "rate"):
        num = evidence.get("numerator", evidence.get("count"))
        den = evidence.get("denominator", evidence.get("total"))
        if isinstance(num, (int, float)) and isinstance(den, (int, float)) and den != 0 and not isinstance(num, bool) and not isinstance(den, bool):
            value = num / den
            return value * 100.0 if metric == "percentage" else value
        return None

    if metric == "mean":
        values = _numeric_list(evidence, "values")
        if values:
            return statistics.mean(values)
        return None

    if metric == "count":
        if evidence.get("values") == []:
            return 0.0
        values = _numeric_list(evidence, "values")
        if values is not None:
            return float(len(values))
        c = evidence.get("count")
        if isinstance(c, (int, float)) and not isinstance(c, bool):
            if c < 0 or not float(c).is_integer():
                raise ValueError("count must be a non-negative integer.")
            return float(c)
        return None

    if metric == "difference":
        a, b = evidence.get("a"), evidence.get("b")
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
            return float(b) - float(a)
        before = _numeric_list(evidence, "before")
        after = _numeric_list(evidence, "after")
        if before and after:
            return statistics.mean(after) - statistics.mean(before)
        return None

    return None


def verify_claim_core(
    claim: str, metric: str, evidence: Any,
    calculation: Optional[str] = None, tolerance: Optional[float] = None,
) -> Dict[str, Any]:
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("claim must be a non-empty string.")
    tolerance = 1e-9 if tolerance is None else _finite(tolerance)
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative.")
    if calculation is not None and not isinstance(calculation, str):
        raise ValueError("calculation is a documentation string, never executable code.")
    ev = _as_dict(evidence)
    for key in ("numerator", "denominator", "count", "total", "a", "b", "claimed_value"):
        if key in ev:
            _finite(ev[key])
    for key in ("values", "before", "after"):
        if key in ev:
            if not isinstance(ev[key], list):
                raise ValueError(f"{key} must be a list of numbers.")
            for value in ev[key]:
                _finite(value)

    if metric not in ALLOWED_METRICS:
        return {
            "verdict": "unverifiable", "claimed_value": None, "recomputed_value": None,
            "metric": metric,
            "explanation": f"Unknown metric '{metric}'; expected one of {sorted(ALLOWED_METRICS)}.",
        }

    if not ev:
        return {
            "verdict": "unverifiable", "claimed_value": None, "recomputed_value": None,
            "metric": metric,
            "explanation": "No evidence supplied (or it was empty/unparseable); the claim cannot "
                           "be recomputed, so it is unverifiable — not false.",
        }

    recomputed = _recompute_metric(metric, ev)
    if recomputed is None:
        return {
            "verdict": "unverifiable", "claimed_value": ev.get("claimed_value"), "recomputed_value": None,
            "metric": metric,
            "explanation": f"Evidence is insufficient to recompute a '{metric}' value "
                           f"(missing the required raw numbers). Unverifiable, not false.",
        }

    claimed = _scoped_claim_value(claim, metric, ev.get("claimed_value"))
    if claim.strip().lower() == 'errors dropped' and recomputed >= 0:
        claimed = None  # Numeric tolerance cannot establish the asserted direction.
    if claimed is None:
        return {
            "verdict": "unverifiable", "claimed_value": None, "recomputed_value": recomputed,
            "metric": metric,
            "explanation": "The claim is outside the bounded numeric grammar or has conflicting "
                           "assertions. Use a bare number or '<metric> = <number>'; an explicit "
                           "claimed_value does not certify arbitrary prose. Supplied evidence is "
                           "not authenticated. Unverifiable, not false.",
        }

    claimed = _finite(claimed)
    recomputed = _finite(recomputed)
    diff = abs(claimed - recomputed)
    if diff <= tolerance:
        verdict = "true"
        explanation = (f"Recomputed {metric} = {recomputed} from the supplied evidence, matching "
                       f"the claimed value {claimed} within tolerance {tolerance}.")
    else:
        verdict = "false"
        explanation = (f"Recomputed {metric} = {recomputed} from the supplied evidence, which "
                       f"differs from the claimed value {claimed} by {diff} (tolerance {tolerance}).")

    return {
        "verdict": verdict, "claimed_value": claimed, "recomputed_value": recomputed,
        "metric": metric, "explanation": explanation + " This verifies only the supplied numeric calculation; evidence is not authenticated.",
    }


# --------------------------------------------------------------------------
# evaluate_difference
# --------------------------------------------------------------------------

def _validate_series(name: str, data: Any) -> List[float]:
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"'{name}' must be a non-empty list of numbers.")
    out = []
    for x in data:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise ValueError(f"'{name}' must contain only numbers, got {x!r}.")
        out.append(_finite(x))
    return out


def evaluate_difference_core(
    data_a: Any, data_b: Any, paired: bool = False,
    alpha: Optional[float] = None, correction: Optional[str] = None,
) -> Dict[str, Any]:
    a = _validate_series("data_a", data_a)
    b = _validate_series("data_b", data_b)
    alpha = 0.05 if alpha is None else _finite(alpha)
    if not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between 0 and 1.")
    if not isinstance(paired, bool):
        raise ValueError("paired must be a boolean.")
    if min(len(a), len(b)) < 2:
        raise ValueError("At least two observations per condition are required.")
    if correction not in (None, "bonferroni", "bh", "none"):
        raise ValueError("'correction' must be one of: bonferroni, bh, none, or omitted.")

    if paired and len(a) != len(b):
        raise ValueError("Paired data_a and data_b must have equal length.")

    binary_a, binary_b = st.is_binary_series(a), st.is_binary_series(b)

    if paired:
        if binary_a and binary_b:
            test_used = "mcnemar"
        else:
            test_used = "paired_t"
    else:
        if binary_a and binary_b:
            # 2x2 contingency table on success/failure counts per group
            succ_a, fail_a = sum(a), len(a) - sum(a)
            succ_b, fail_b = sum(b), len(b) - sum(b)
            n_a, n_b = len(a), len(b)
            row1, row2 = n_a, n_b
            col1 = succ_a + succ_b
            exp_min = min(row * col / (n_a + n_b)
                          for row in (row1, row2)
                          for col in (col1, fail_a + fail_b))
            test_used = "fisher_exact" if exp_min < 5 else "chi_square"
        else:
            test_used = "welch_t" if (st.looks_normal_enough(a) and st.looks_normal_enough(b)) else "mann_whitney"

    p_value: float
    effect_size: float
    direction_favors_b: bool
    ci: tuple

    if test_used == "mcnemar":
        n_pairs = len(a)
        b_wins = sum(1 for ai, bi in zip(a, b) if ai == 0 and bi == 1)   # B right, A wrong
        a_wins = sum(1 for ai, bi in zip(a, b) if ai == 1 and bi == 0)   # A right, B wrong
        p_value = st.mcnemar_exact_p(b_wins, a_wins)
        effect_size = ((b_wins + 0.5) / (a_wins + 0.5)
                       if min(b_wins, a_wins) == 0 else b_wins / a_wins)
        direction_favors_b = (b_wins - a_wins) >= 0
        ci = st.bootstrap_ci_mean_diff(a, b, paired=True)
        detail = f"discordant pairs: B-right/A-wrong={b_wins}, A-right/B-wrong={a_wins} (n={n_pairs})"

    elif test_used == "paired_t":
        diffs = [bi - ai for ai, bi in zip(a, b)]
        if statistics.variance(diffs) == 0 and statistics.mean(diffs) != 0:
            raise ValueError("Constant nonzero paired differences give zero estimated standard error; t inference is undefined.")
        t, df, p_value = st.paired_t_test(a, b)
        diffs = [bi - ai for ai, bi in zip(a, b)]
        sd = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
        effect_size = (statistics.mean(diffs) / sd) if sd else None
        direction_favors_b = statistics.mean(diffs) >= 0
        ci = st.bootstrap_ci_mean_diff(a, b, paired=True)
        detail = f"paired t={t:.4f}, df={df:.1f}"

    elif test_used in ("chi_square", "fisher_exact"):
        succ_a, fail_a = int(sum(a)), len(a) - int(sum(a))
        succ_b, fail_b = int(sum(b)), len(b) - int(sum(b))
        # table [[succ_a, fail_a], [succ_b, fail_b]]
        if test_used == "chi_square":
            chi2 = st.chi_square_2x2(succ_a, fail_a, succ_b, fail_b)
            p_value = st.chi2_p_df1(chi2)
            detail = f"chi2(Yates)={chi2:.4f}"
        else:
            p_value = st.fisher_exact_2x2(succ_a, fail_a, succ_b, fail_b)
            detail = "fisher exact 2x2"
        effect_size = st.odds_ratio_2x2(succ_b, fail_b, succ_a, fail_a)
        rate_a = succ_a / len(a) if len(a) else 0.0
        rate_b = succ_b / len(b) if len(b) else 0.0
        direction_favors_b = rate_b >= rate_a
        ci = st.bootstrap_ci_rate_diff(a, b)

    elif test_used == "welch_t":
        if statistics.variance(a) + statistics.variance(b) == 0 and statistics.mean(a) != statistics.mean(b):
            raise ValueError("Both groups are constant with different means; Welch inference is undefined.")
        t, df, p_value = st.welch_t_test(a, b)
        effect_size = st.cohens_d(a, b) if statistics.variance(a) + statistics.variance(b) else None
        direction_favors_b = statistics.mean(b) >= statistics.mean(a)
        ci = st.bootstrap_ci_mean_diff(a, b, paired=False)
        detail = f"Welch t={t:.4f}, df={df:.1f}"

    else:  # mann_whitney
        u1, p_value = st.mannwhitney_u(a, b)
        effect_size = st.cohens_d(a, b) if statistics.variance(a) + statistics.variance(b) else None
        direction_favors_b = u1 < len(a) * len(b) / 2
        ci = st.bootstrap_ci_mean_diff(a, b, paired=False)
        detail = f"Mann-Whitney U1={u1:.2f}"

    # Multiple-comparison correction: with a single evaluate_difference call
    # there is no implicit family of tests (k=1), so correction is a documented
    # no-op here. bonferroni_correction/benjamini_hochberg in stats.py are the
    # real, independently-tested implementations for callers comparing several
    # p-values at once.
    correction_note = ""
    if correction in ("bonferroni", "bh"):
        correction_note = (f" (correction='{correction}' requested, but evaluate_difference "
                           f"evaluates a single comparison — no family-wise adjustment to apply; "
                           f"use stats.bonferroni_correction/benjamini_hochberg across a list of "
                           f"p-values from multiple calls.)")

    if p_value < alpha:
        verdict = "supported" if direction_favors_b else "not_supported"
    else:
        verdict = "inconclusive"

    effect_name = ("matched_odds_ratio_b_over_a" if test_used == "mcnemar" else
                   "odds_ratio_b_over_a" if binary_a and binary_b else
                   "cohens_dz" if paired else "cohens_d")
    explanation = (
        f"test_used={test_used} ({detail}); p={p_value:.6g} vs alpha={alpha}. "
        + (
            f"The difference is statistically significant and favors data_b."
            if verdict == "supported" else
            f"The difference is statistically significant but in the OPPOSITE direction of "
            f"data_b (favors data_a) — this contradicts a claim that data_b is better/greater."
            if verdict == "not_supported" else
            f"Not statistically significant at alpha={alpha}: inconclusive, NOT evidence that "
            f"there is no difference — only that this data does not establish one."
        )
        + correction_note
        + f" Effect size: {effect_name}; zero binary cells receive +0.5."
        + " CI: fixed-seed 95% percentile bootstrap of mean(B)-mean(A), not the effect-size ratio."
        + " Significance does not establish causality or general superiority."
    )

    return {
        "verdict": verdict,
        "p_value": p_value,
        "effect_size": effect_size,
        "effect_size_measure": effect_name,
        "observed_difference": statistics.mean(b) - statistics.mean(a),
        "confidence_interval_measure": "mean_b_minus_mean_a",
        "confidence_interval": [ci[0], ci[1]],
        "test_used": test_used,
        "explanation": explanation,
    }


# --------------------------------------------------------------------------
# qualify_conclusion
# --------------------------------------------------------------------------

def _has_hedge(text: str) -> bool:
    return text.strip().lower().rstrip(".") in {
        "the result is inconclusive",
        "b may be slightly better, but this is not conclusive",
        "there is insufficient evidence to establish that b is better",
    }


def _hedge_for_inconclusive(conclusion: str, direction_favors_b: bool) -> str:
    m = re.search(
        r"^(.*?)\s+(?:is|was|are|were)\s+(?:better|greater|higher|stronger|more effective|superior)\s+than\s+(.*?)[\.\!\?]*$",
        conclusion.strip(), re.IGNORECASE,
    )
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        winner, loser = (left, right) if direction_favors_b else (right, left)
        return f"{winner} scored higher, but this does not establish that {winner} is better than {loser}."
    return (f"The data shows a difference in the observed direction, but this does not establish "
           f"the conclusion as stated (\"{conclusion.strip()}\"): the result is inconclusive.")


def _qualify_from_dict(conclusion: str, result: Dict[str, Any]) -> Dict[str, Any]:
    verdict = result.get("verdict")
    if "error" in result:
        verdict = "unverifiable"
    if verdict in ("true", "false"):
        if result.get("metric") not in ALLOWED_METRICS:
            raise ValueError("Prior verification result is missing a valid metric.")
        _finite(result.get("claimed_value"))
        _finite(result.get("recomputed_value"))
    if verdict in ("supported", "not_supported", "inconclusive"):
        p = _finite(result.get("p_value"))
        if not 0 <= p <= 1 or result.get("test_used") not in {
            "mcnemar", "paired_t", "welch_t", "mann_whitney", "chi_square", "fisher_exact"
        }:
            raise ValueError("Prior statistical result needs a valid p-value and test_used.")
        if 'observed_difference' in result:
            observed = _finite(result['observed_difference'])
            if (verdict == 'supported' and observed <= 0 or
                    verdict == 'not_supported' and observed >= 0):
                raise ValueError('Prior statistical verdict contradicts its observed direction.')
        elif verdict in ('supported', 'not_supported'):
            raise ValueError('Prior directional verdict requires observed_difference.')

    # A complete result is not evidence for an unrelated conclusion. These are
    # conservative relevance gates, not provenance authentication or endorsement.
    normalized = conclusion.strip().rstrip('.').lower()
    metric = result.get('metric')
    canonical_numeric = (f"The recomputed {metric} is {result.get('recomputed_value')} in the supplied evidence.").rstrip('.').lower()
    scoped_numeric = (_scoped_claim_value(conclusion, metric, None)
                      if metric in ALLOWED_METRICS else None)
    unrelated_numeric = verdict in ('true', 'false') and not (
        normalized == canonical_numeric or
        scoped_numeric is not None and scoped_numeric == result.get('claimed_value'))
    if verdict in ('true', 'false') and normalized == canonical_numeric:
        verdict = 'true'  # The recomputed value is not the rejected claimed value.
    comparison_forms = {
        'b is better', 'b is better than a', 'model b is better than model a',
        'b scored higher, but this does not establish that b is better',
        'a scored higher, but this does not establish that a is better',
        'the supplied observations statistically support b > a under the selected test',
        'the supplied observations statistically support b < a under the selected test',
        'the result is inconclusive; this does not establish a difference or equivalence',
    }
    unrelated_comparison = verdict in ('supported', 'not_supported', 'inconclusive') and not (
        normalized in comparison_forms or _has_hedge(conclusion))
    opposite_comparison = (
        verdict == 'supported' and normalized == 'the supplied observations statistically support b < a under the selected test' or
        verdict == 'not_supported' and normalized == 'the supplied observations statistically support b > a under the selected test')
    if unrelated_numeric or unrelated_comparison or opposite_comparison:
        return {
            'supported_conclusion': 'The prior result does not establish the conclusion as stated.',
            'epistemic_status': 'unverifiable', 'overclaim': True,
            'explanation': 'The supplied prior result does not identify a relationship to this conclusion; no direction or support is inferred.',
        }

    if verdict == "true":
        epistemic_status = "supported"
    elif verdict == "false":
        epistemic_status = "false"
    elif verdict == "unverifiable":
        epistemic_status = "unverifiable"
    elif verdict == "supported":
        epistemic_status = "supported"
    elif verdict == "inconclusive":
        epistemic_status = "inconclusive"
    elif verdict == "not_supported":
        epistemic_status = "false"
    else:
        epistemic_status = "unverifiable"

    observed = result.get("observed_difference")
    if observed is None and result.get("test_used") in ("paired_t", "welch_t"):
        observed = result.get("effect_size")
    direction_favors_b = isinstance(observed, (int, float)) and observed > 0

    hedge_already_present = _has_hedge(conclusion)

    if epistemic_status == "supported":
        if verdict == "true":
            supported_conclusion = (f"The recomputed {result.get('metric')} is "
                                    f"{result.get('recomputed_value')} in the supplied evidence.")
        else:
            supported_conclusion = "The supplied observations statistically support B > A under the selected test."
        overclaim = conclusion.strip().rstrip(".").lower() != supported_conclusion.rstrip(".").lower()
        explanation = "Only the stated calculation or statistical comparison is supported; arbitrary claims, causation, and general superiority are not established."

    elif epistemic_status == "inconclusive":
        overclaim = not hedge_already_present
        if direction_favors_b:
            supported_conclusion = "B scored higher, but this does not establish that B is better"
        elif isinstance(observed, (int, float)) and observed < 0:
            supported_conclusion = "A scored higher, but this does not establish that A is better"
        else:
            supported_conclusion = "The result is inconclusive; this does not establish a difference or equivalence."
        if conclusion.strip().rstrip(".").lower() == supported_conclusion.rstrip(".").lower():
            overclaim = False
        p_val = result.get("p_value")
        explanation = (f"The test did not establish a statistically significant difference"
                       f"{f' (p={p_val:.4g})' if isinstance(p_val, (int, float)) else ''}. "
                       f"Inconclusive, not false — more data could still show a real effect.")

    elif epistemic_status == "unverifiable":
        overclaim = not hedge_already_present
        supported_conclusion = (conclusion.strip() if hedge_already_present
                                else "There is insufficient empirical evidence to verify or refute: "
                                     f"\"{conclusion.strip()}\".")
        explanation = "No usable evidence was supplied to check this conclusion against."

    else:  # false
        overclaim = True
        supported_conclusion = ("The supplied observations statistically support B < A under the selected test."
                                if verdict == "not_supported" else
                                f"The recomputed {result.get('metric')} is {result.get('recomputed_value')}; "
                                f"the supplied claimed value {result.get('claimed_value')} does not match.")
        explanation = result.get("explanation") or "The evidence contradicts this conclusion."

    return {
        "supported_conclusion": supported_conclusion,
        "epistemic_status": epistemic_status,
        "overclaim": overclaim,
        "explanation": explanation,
    }


def qualify_conclusion_core(
    conclusion: str, evidence: Any = None, prior_result: Any = None,
) -> Dict[str, Any]:
    if not isinstance(conclusion, str) or not conclusion.strip():
        raise ValueError("'conclusion' must be a non-empty string.")

    prior = _as_dict(prior_result)
    if prior and "verdict" in prior:
        return _qualify_from_dict(conclusion, prior)

    ev = _as_dict(evidence)
    if ev:
        if "verdict" in ev:
            return _qualify_from_dict(conclusion, ev)
        if "data_a" in ev and "data_b" in ev:
            eval_result = evaluate_difference_core(
                ev.get("data_a"), ev.get("data_b"),
                paired=ev.get("paired", False),
                alpha=ev.get("alpha"), correction=ev.get("correction"),
            )
            return _qualify_from_dict(conclusion, eval_result)
        if "metric" in ev:
            verify_result = verify_claim_core(
                ev.get("claim", conclusion), ev.get("metric"), ev.get("evidence", ev),
                calculation=ev.get("calculation"), tolerance=ev.get("tolerance"),
            )
            return _qualify_from_dict(conclusion, verify_result)

    # No usable evidence or prior result at all.
    return {
        "supported_conclusion": f"There is insufficient empirical evidence to verify or refute: "
                                f"\"{conclusion.strip()}\".",
        "epistemic_status": "unverifiable",
        "overclaim": True,
        "explanation": "qualify_conclusion was called without evidence or a prior verify_claim/"
                       "evaluate_difference result to check the conclusion against.",
    }
