"""Tool schemas for gnothi. Each is a dict with a meaningful ``description``
(how the LLM decides when to call it) and a JSON-schema ``parameters`` block
matching the handler signature."""

from __future__ import annotations

VERIFY_CLAIM = {
    "name": "verify_claim",
    "description": (
        "Recompute a narrowly scoped numeric assertion from supplied, unauthenticated raw "
        "evidence. Use a bare number or '<metric> = <number>' / '<metric> is <number>', "
        "e.g. 'percentage = 4.2%' or 'count = 40'. Arbitrary prose, negation, causality, "
        "and compound claims are unverifiable even if one number matches. A true verdict "
        "checks only this numeric calculation, not data authenticity or broader conclusions. "
        "Missing or insufficient evidence is unverifiable, not false."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "claim": {"type": "string", "description": "A scoped calculation, e.g. 'percentage = 4.2%' or 'count = 10'; not arbitrary prose."},
            "metric": {"type": "string", "enum": ["percentage", "mean", "rate", "count", "difference"],
                       "description": "What kind of quantity the claim asserts."},
            "evidence": {
                "type": "object",
                "description": (
                    "The raw numbers to recompute from, and (ideally) the claimed value to check "
                    "against it: evidence['claimed_value'] plus metric-specific raw fields — "
                    "percentage/rate: {numerator, denominator}; mean: {values: [...]}; "
                    "count: {values: [...]} or {count}; difference: {a, b} or {before: [...], "
                    "after: [...]}. If claimed_value is omitted, the number is read only from "
                    "the closed numeric claim grammar. Supplied data is not authenticated."
                ),
            },
            "calculation": {"type": "string", "description": "Optional: how the claim was derived, if known."},
            "tolerance": {"type": "number", "minimum": 0, "description": "Absolute float comparison tolerance (default 1e-9)."},
        },
        "required": ["claim", "metric", "evidence"],
        "additionalProperties": False,
    },
}

EVALUATE_DIFFERENCE = {
    "name": "evaluate_difference",
    "description": (
        "Test whether an observed difference between two conditions (e.g. model A vs model B, "
        "control vs treatment, before vs after) is statistically supported by the data, or just "
        "noise. Use this BEFORE concluding 'X is better than Y' or 'X changed' from sample data. "
        "Automatically picks the right test: McNemar's exact test for paired binary (right/wrong) "
        "outcomes, paired t-test for paired continuous data, Welch's t-test or Mann-Whitney U for "
        "unpaired continuous data (chosen by a normality heuristic), and chi-square/Fisher exact "
        "for unpaired binary rates. A non-significant result is 'inconclusive' (need more data), "
        "never 'not_supported'; 'not_supported' is reserved for when the data significantly "
        "contradicts the implied direction (data_b being higher/better than data_a)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "data_a": {"type": "array", "items": {"type": "number"}, "description": "Control/baseline sample."},
            "data_b": {"type": "array", "items": {"type": "number"}, "description": "Treatment/variant sample."},
            "entity_a": {"type": "string", "description": "Optional baseline name for opt-in automatic audit; use with entity_b and outcome."},
            "entity_b": {"type": "string", "description": "Optional variant name for opt-in automatic audit."},
            "outcome": {"type": "string", "enum": ["correctness"], "description": "Optional binding for the narrow paired-binary correctness audit; does not change the statistical computation."},
            "paired": {"type": "boolean", "description": "True if data_a[i] and data_b[i] are matched "
                       "observations (e.g. the same task judged by both models). Default false."},
            "alpha": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "description": "Significance threshold. Default 0.05."},
            "correction": {"type": "string", "enum": ["bonferroni", "bh", "none"],
                           "description": "No family is supplied by this API: bonferroni/bh only add a warning; "
                                          "p_value and verdict remain unadjusted. Default none."},
        },
        "required": ["data_a", "data_b"],
        "additionalProperties": False,
    },
}

QUALIFY_CONCLUSION = {
    "name": "qualify_conclusion",
    "description": (
        "Given a conclusion you (or the user) are about to assert, and either raw evidence or a "
        "prior verify_claim/evaluate_difference result, return the strongest conclusion the "
        "evidence actually permits plus whether the asserted conclusion overclaims beyond it. "
        "Use this as the last check before stating a definitive conclusion drawn from data — "
        "especially after evaluate_difference comes back 'inconclusive', where an aggregate-looking "
        "win ('B scored higher') does not by itself establish the stronger claim ('B is better')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "conclusion": {"type": "string", "description": "The conclusion being asserted, e.g. "
                           "\"Model B is better than Model A.\""},
            "evidence": {
                "type": "object",
                "description": "Optional raw evidence to evaluate directly: either "
                               "{data_a, data_b, paired?, alpha?, correction?} (routed through "
                               "evaluate_difference) or {metric, evidence, calculation?, tolerance?} "
                               "(routed through verify_claim). Omit if passing prior_result instead.",
            },
            "prior_result": {
                "type": "object",
                "description": "Optional: the JSON result object already returned by verify_claim or "
                               "evaluate_difference, to avoid recomputing.",
            },
        },
        "required": ["conclusion"],
        "additionalProperties": False,
    },
}
