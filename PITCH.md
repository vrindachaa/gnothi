# 20–18 isn’t a verdict.

## gnothi: the benchmark referee for AI claims

**A score is a fact. “The winner is better” is a claim. Make it show its work.**

When an AI agent compares two models, a tiny lead can turn into a confident
headline. gnothi checks the numbers against the supplied observations, runs
the appropriate statistical comparison, and flags conclusions that outrun
the evidence. It gives the agent a result it can explain and a sentence it
can stand behind.

### The demo: 20–18

Two models take the same 40 tasks. A gets 18 right. B gets 20 right.

**Hermes:** “B is the better model.”

**gnothi checks the matched results:**

- They agree on 36 tasks.
- On the four tasks where they disagree, B wins three and A wins one.
- Exact McNemar test: **p = 0.625**.
- Verdict: **inconclusive**.

**Hermes, corrected:** “B scored higher, but this test doesn’t establish that
B is better.”

**20–18 isn’t a verdict.** That’s the whole demo.

### Why this needs a plugin

“Be careful with statistics” is advice. gnothi takes the paired observations,
selects and computes the test, returns a structured verdict, and gives the
agent a qualified conclusion. The demo result is calculated from the input
data; the p-value is not a canned answer. The tools run on demand, with no
network, credentials, external statistical packages, or internal LLM calls in
the default core. Separately opt-in automatic hooks hold response streaming;
optional Jev advice sends claim text, a question, and aggregate evidence to
OpenRouter and its provider, may incur charges and latency, and never replaces
the deterministic verdict. Supplied evidence is not authenticated.

### What gnothi does

- Recomputes a supplied quantitative claim from supplied raw numbers.
- Tests whether a difference is supported by the sample, including paired
  binary model evaluations.
- Flags an overclaim and offers a more defensible conclusion.

### What gnothi does not claim

It does not verify where the data came from, prove the sample is representative,
or establish causation. “Inconclusive” does not mean “equal.” It means this
evidence does not settle the claim.

## 75-second demo script

**0–10s — The hook**  
Show two model scores: **A 18/40. B 20/40.** Say: “Two more wins. Is B
actually better?”

**10–25s — The confident claim**  
Ask Hermes to interpret the result. Let it state the tempting conclusion:
“B is better.”

**25–50s — The check**  
Show the 40 matched task outcomes being passed to `evaluate_difference` with
`paired=true`. Surface the discordant counts (**B-only 3, A-only 1**) and the
computed **p = 0.625**. Keep the raw observation that the models agree on 36
tasks visible; that is the twist behind the aggregate score.

**50–65s — The correction**  
Pass the result to `qualify_conclusion`. Show `inconclusive` and
`overclaim: true`, followed by: “B scored higher, but this does not establish
that B is better.”

**65–75s — The close**  
“A score is a fact. A winner is a claim. gnothi checks the difference.”

### One-line submission description

**gnothi is a benchmark referee for Hermes: it recomputes quantitative claims,
tests model comparisons against raw observations, and catches conclusions
that claim more than the evidence shows.**
