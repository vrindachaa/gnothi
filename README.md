# gnothi — "Hermes, checked."

γνῶθι σεαυτόν ("know thyself") — a Hermes Agent plugin that lets the agent
test its own quantitative claims against evidence and recognize when a
conclusion goes beyond what the data supports.

Three on-demand tools, one engine:

- **`verify_claim`** — is this claim consistent with the evidence? → `true` / `false` / `unverifiable`
- **`evaluate_difference`** — is this difference statistically supported? → `supported` / `inconclusive` / `not_supported`
- **`qualify_conclusion`** — what may I actually conclude? → the conclusion + its epistemic status

The core distinction LLMs blur, that gnothi does not:

- **`unverifiable` ≠ `false`.** No evidence to recompute from is not the same
  as "wrong".
- **`inconclusive` ≠ `not_supported`.** A non-significant result means "this
  data doesn't establish it", not "there is no effect".

## Disclosure (per catalog rule 13)

- **Default-off integrations.** The core tools use no network, hooks, subprocesses,
  filesystem writes, credentials, or LLM calls. Optional automatic checking and
  Jev advisory support require explicit configuration.
- **Automatic checking is narrow.** It only matches labeled paired-binary
  correctness comparisons and never acts as general semantic verification.
- **Deterministic.** Same inputs → same outputs. The only randomness (the
  bootstrap confidence interval) uses a fixed seed (`random.Random(0)`), not
  wall-clock time.
- **Core is stateless.** Optional hooks keep bounded in-memory evidence and read
  plugin settings; neither integration writes durable storage.

## Install

```bash
hermes plugins validate /path/to/gnothi-submission --install-deps
hermes plugins install /path/to/gnothi-submission
hermes plugins enable gnothi
```

No Python dependencies beyond the standard library; `--install-deps` is a
no-op here by design (nothing to install).

## The three tools

### `verify_claim(claim, metric, evidence, calculation?, tolerance?)`

Recomputes a `percentage|mean|rate|count|difference` value from raw numbers
in `evidence` and compares it to a closed numeric claim grammar: a bare
number (for example `4.2`), or the selected metric followed by `=` or `is`
and a number (for example `percentage = 4.2` or `mean is 2`). Arbitrary
prose is `"unverifiable"`, even with a supplied `claimed_value`; numeric
consistency does not authenticate the supplied evidence. Missing or insufficient
evidence is also `"unverifiable"`, never `"false"`.

```json
{"verdict": "true", "claimed_value": 4.2, "recomputed_value": 4.2,
 "metric": "percentage", "explanation": "..."}
```

### `evaluate_difference(data_a, data_b, paired?, alpha?, correction?)`

Automatically selects McNemar's exact test (paired binary), a paired t-test
(paired continuous), chi-square/Fisher exact (unpaired binary rates), or
Welch's t-test/Mann-Whitney U (unpaired continuous, chosen by a normality
heuristic). Returns the raw p-value, an effect size, a fixed-seed bootstrap
confidence interval, and which test was used.

```json
{"verdict": "inconclusive", "p_value": 0.625, "effect_size": 3.0,
 "confidence_interval": [-0.05, 0.15], "test_used": "mcnemar", "explanation": "..."}
```

`verdict` is `"supported"`, `"inconclusive"`, or `"not_supported"` (reserved
for when the data is significant in the *opposite* direction of `data_b`
being the higher/better one).

### `qualify_conclusion(conclusion, evidence?, prior_result?)`

Given a conclusion sentence and either raw evidence or a prior
`verify_claim`/`evaluate_difference` result, returns the strongest conclusion
the evidence actually permits, its `epistemic_status`
(`supported|inconclusive|unverifiable|false`), and whether the asserted
conclusion `overclaim`s beyond that.

```json
{"supported_conclusion": "B scored higher, but this does not establish that B is better",
 "epistemic_status": "inconclusive", "overclaim": true, "explanation": "..."}
```

## Statistical methods (pure Python, no numpy/scipy)

| Method | Used for |
|---|---|
| McNemar's exact test (binomial) | paired binary outcomes |
| Paired t-test | paired continuous data |
| Welch's t-test (own incomplete-beta t-CDF) | unpaired continuous, normal-ish |
| Mann-Whitney U (normal approx, tie-corrected) | unpaired continuous, non-normal |
| Chi-square with Yates correction | unpaired binary rates, adequate counts |
| Fisher's exact test (hypergeometric) | unpaired binary rates, small counts |
| Cohen's d / odds ratio | effect sizes |
| Percentile bootstrap, fixed seed, B=2000 | confidence intervals |
| Bonferroni / Benjamini-Hochberg | multiple-comparison correction (`stats.py` helpers) |

See `stats.py` for the implementations (all pure stdlib: `math`, `statistics`,
`random`) and `core.py` for how each tool wires them together.

## Demo scenario

40 paired tasks, models A and B agree on 36 (17 both-right, 19 both-wrong),
disagree on 4 (B right/A wrong ×3, A right/B wrong ×1). Aggregate: A=18/40,
B=20/40 — looks like B wins. `evaluate_difference(paired=true)` runs
McNemar's exact test on the 4 discordant pairs and gets p=0.625 (computed,
not hardcoded) → `"inconclusive"`. `qualify_conclusion("Model B is better
than Model A.", prior_result=<that result>)` returns `overclaim: true` and a
corrected statement: aggregate wins don't establish superiority. See
`tests/test_demo_scenario.py` and `tests/test_regressions.py`.

## Optional automatic check

The hook is disabled unless `automatic_check: true` is configured. It holds the
response stream, verifies a narrow paired-binary comparison locally, and adds a
warning when an exact superiority claim outruns the result. `jev_remote: true`
is a separate opt-in that sends the claim text, decision question, and bounded
aggregate evidence to OpenRouter and its model provider. Remote calls may incur
charges and add latency while streaming is held. Scores are non-authoritative
model judgments, not calibrated truth, and never override the local verdict.
Credentials are resolved at call time using Hermes `agent.secret_scope.get_secret`;
missing credentials or an unavailable Hermes API fail closed without an environ
fallback.

Settings live under `plugins.entries.gnothi.settings`: `automatic_check` (bool,
default false), `jev_remote` (bool, default false), and `decision_model` (str,
default `typesafe/jev-1.14`). The manifest declares `post_tool_call` and
`transform_llm_output`; registration is intentionally inactive by default. A
validator warning about declared-but-unregistered hooks in default configuration
is expected, not evidence that the opt-in path has been exercised.

General automatic free-text verification, calibrated-confidence oracles, and UI
remain out of scope.

## Interpretation and limits

This submission includes the strict verification core, regression coverage,
and separately opt-in automatic hook and Jev integrations. It includes repairs to
paired and independent odds-ratio reporting, Yates correction near zero,
sparse-table routing, invalid-input handling, and overly permissive conclusion
qualification.

- Paired binary effect: matched odds ratio B-only/A-only; add 0.5 to both
  discordant counts if either is zero (0/0 yields 1). Independent binary:
  B/A odds ratio, adding 0.5 to all four cells if any is zero.
- Continuous effects: Cohen's d (unpaired) or dz (paired); null if undefined.
  `effect_size_measure` labels the scale. `observed_difference` is mean(B)-mean(A).
- The CI is a fixed 95% percentile bootstrap interval for mean(B)-mean(A),
  **not** an interval for the odds ratio or standardized effect. It uses 2,000
  resamples with seed 0 and preserves pairing when requested.
- Welch routing requires both sample sizes ≥20 and absolute skewness <1.
  Otherwise continuous independent samples use tie-corrected Mann–Whitney
  normal approximation without continuity correction. Small samples may have
  poor approximation accuracy; this is not a formal normality test. Mann–Whitney
  direction follows rank ordering, which can differ from the sample mean.
- Fisher is used if any expected 2×2 count is below 5; otherwise Yates chi-square.
- `bonferroni`/`bh` requests add an explicit warning: the tool has no comparison
  family, so **p-values and verdicts remain unadjusted**. Helpers alone do not
  correct a tool call.
- Inputs must be finite numbers (not booleans/strings), magnitude ≤1e100;
  alpha must be in (0,1), tolerance ≥0, and each comparison sample needs ≥2
  observations. Zero-standard-error nonzero t comparisons return an explained
  inconclusive error. Missing or invalid verification data is unverifiable.
- Numeric claims use only the closed grammar above (including scientific
  notation); arbitrary prose is not parsed or verified. A supplied `claimed_value`
  does not relax that grammar. `percentage` uses percent units; `rate` uses
  fractions. `calculation` is documentation only and is never executed.
- Qualification is deterministic pattern matching, not semantic entailment.
  Unknown wording, causation, and broad superiority flag `overclaim: true`.
  Its status describes the evidence result. A positive arithmetic check does
  not validate unrelated prose, provenance, representativeness, or causality.
  Prior results are caller-supplied and unauthenticated.

Known safe inconclusive phrases (case-insensitive, optional final period):
“The result is inconclusive”; “B may be slightly better, but this is not
conclusive”; “There is insufficient evidence to establish that B is better”.
The generated canonical conclusion also avoids an overclaim flag on reuse.
For supported results, use the generated canonical statement exactly.

The public API is the three registered tools. Each handler accepts an argument
mapping and returns a JSON string, including structured errors. Core Python
functions may raise validation exceptions; registered wrappers convert these to
structured error responses. No runtime tools read
or write files; registration only references the bundled skill path.

## Running the tests

```bash
cd /path/to/gnothi-submission
python -B -m unittest discover -s tests -v
python -m compileall -q .
```

The repository root is the installable plugin. See [PITCH.md](PITCH.md) for
the worked demonstration and [SUBMISSION.md](SUBMISSION.md) for verification
scope and remaining publication requirements.
