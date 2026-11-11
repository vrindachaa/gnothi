---
name: gnothi
description: Use gnothi before asserting a number or a data-driven conclusion. Verifies claims, tests differences, qualifies conclusions.
version: 0.1.0
metadata:
  hermes:
    tags: [statistics, epistemics, self-check, verification]
---

# gnothi — "Hermes, checked."

gnothi (γνῶθι — "know thyself") gives you three on-demand tools to test your
own quantitative claims against evidence before you assert them. The product
is an epistemic distinction LLMs routinely blur:

- **`unverifiable` is not `false`.** If you don't have the evidence to recompute
  a number, say so — don't call it wrong, and don't call it right either.
- **`inconclusive` is not `not_supported`.** A non-significant difference means
  "this data doesn't establish it", not "there is no difference". Aggregate
  wins (20 vs 18) do not by themselves establish superiority — check the
  actual test.

## When to use each tool

| Situation | Tool |
|---|---|
| You're about to state a specific number ("conversion rose to 4.2%", "errors dropped to 40") and you have the raw numbers it rests on | `verify_claim` |
| You're about to say "A is better/worse/higher/different than B" from sample data | `evaluate_difference` |
| You have a verify/evaluate result (or raw evidence) and are about to state a conclusion from it | `qualify_conclusion` |

**Rule of thumb: before you assert a number, verify it. Before you assert a
comparison, evaluate it. Before you state the conclusion, qualify it.**

## verify_claim

Recompute the claim from `evidence` (raw numbers) and compare to the claimed
value. Use a bare number (`4.2`) or the selected metric with `=` or `is` and
a number (`percentage = 4.2`, `mean is 2`). Arbitrary prose is unverifiable,
even with `claimed_value`; supplied evidence is not authenticated. Core
validation exceptions become structured errors in registered tool wrappers.
Put the raw numbers in `evidence` using the metric-specific shape:

- `percentage`: `{"numerator": 42, "denominator": 1000, "claimed_value": 4.2}`
- `rate`: same numerator/denominator, but `claimed_value: 0.042` (fraction units)
- `mean`: `{"values": [1,2,3,...], "claimed_value": 12.0}`
- `count`: `{"values": [...]}` or `{"count": 40}`
- `difference`: `{"a": 10, "b": 14, "claimed_value": 4}` or `{"before": [...], "after": [...]}`

If `evidence` is missing or can't be recomputed from, the verdict is
`"unverifiable"` — never `"false"`. Only call it `"false"` when you actually
had enough evidence to recompute and the recomputed value disagrees with the
claimed value beyond `tolerance`.

## evaluate_difference

Pass `data_a` (baseline/control) and `data_b` (treatment/variant). Set
`paired=true` when `data_a[i]`/`data_b[i]` are matched observations (e.g. the
same task graded against both models) — this is what lets gnothi pick
McNemar's exact test for paired right/wrong outcomes instead of treating 40
paired judgments as 80 independent ones (the single biggest source of
falsely-confident A/B conclusions).

Test selection is automatic:

| Data shape | Test |
|---|---|
| paired, binary (0/1) | McNemar's exact test |
| paired, continuous | paired t-test |
| unpaired, binary rates | chi-square (Yates) or Fisher exact (small counts) |
| unpaired, continuous, looks normal-ish | Welch's t-test |
| unpaired, continuous, not normal-ish | Mann-Whitney U |

`verdict` is `"supported"` (significant, favors data_b), `"not_supported"`
(significant, but favors data_a — contradicts the implied "b is better"
direction), or `"inconclusive"` (not significant — need more data, this is
NOT proof there's no difference).

## qualify_conclusion

The final gate. Pass the `conclusion` you're about to state plus either
`prior_result` (the dict already returned by `verify_claim`/`evaluate_difference`)
or raw `evidence`. It returns `overclaim: true` whenever the conclusion asserts
more than the evidence supports — e.g. "Model B is better than Model A" when
`evaluate_difference` only found an inconclusive paired difference. Use
`supported_conclusion` as the corrected statement to actually say.

Qualification is conservative pattern matching, not semantic entailment.
A significant comparison still does not prove general superiority or causality.
Use the generated canonical statement; unknown phrasing is flagged for review.
Do not treat a caller-supplied prior result as authenticated. A requested
bonferroni/bh correction cannot be applied without the comparison family;
this tool reports unadjusted p-values and says so.

## Worked example (the whole point of gnothi)

40 paired tasks, models A and B. Both right on 17, both wrong on 19, B right
only on 3, A right only on 1. Aggregate: A=18/40, B=20/40 — "B is better"
*looks* true.

```
evaluate_difference(data_a=[...40 zeros/ones...], data_b=[...], paired=true)
  -> McNemar exact test on the 4 discordant pairs (b=3, c=1): p=0.625
  -> {"verdict": "inconclusive", "p_value": 0.625, "test_used": "mcnemar", ...}

qualify_conclusion(conclusion="Model B is better than Model A.", prior_result=<above>)
  -> {"epistemic_status": "inconclusive", "overclaim": true,
      "supported_conclusion": "B scored higher, but this does not establish that B is better"}
```

The aggregate win is real; the superiority claim is not supported. That's the
check gnothi exists to run.

## What gnothi will NOT do (by design)

- No calibrated-confidence percentage for an arbitrary claim — it refuses
  ("insufficient empirical evidence to quantify confidence") rather than
  inventing a number.
- No free-text claim extraction. You (the agent) supply the structured claim
  and its evidence; gnothi doesn't scan transcripts looking for numbers.
- Automatic checking is optional and default-off, not general semantic auditing.
  `automatic_check: true` enables narrow paired-binary checks and holds streaming.
  Separately opting into `jev_remote: true` sends claim text, a question, and
  bounded aggregate evidence to OpenRouter and its provider, with possible
  charges and latency. Jev scores are non-authoritative and never override local
  verdicts. Credentials use Hermes profile-safe `get_secret`; unavailable API
  or credentials fail closed. Default validation may warn that declared hooks
  are not registered; this is expected while automatic checking is off.
