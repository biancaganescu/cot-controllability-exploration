# Results, iteration 2 (2026-10-11): louder observer, Qwen3.6-27B small run, LLM judge

Full tables behind the summary in the [README](../README.md). Exploratory: `train` and
`validation` splits only. Iteration 3 (the large 27B run) supersedes the 27B numbers here; in
particular the `intrinsic` rate on this small run (50%) was not borne out (see
[results-iteration-3.md](results-iteration-3.md)).

## A. Qwen3-8B with salient observer conditions

`validation`, 16 cases × 3 samples = 48 trials per condition; 8 conditions run together so the
plain and salient versions share a run. Leak = full secret in reasoning; "mentions observer" by a
regex for phrases like "the partner can see my reasoning".

| Condition | Key in reasoning | Read whole key | Gave up | States rule | Mentions observer |
| --- | --- | --- | --- | --- | --- |
| `public-none` | 60% | 96% | 0% | 10% | 0% |
| `public_salient-none` | 74% | 98% | 0% | 13% | 0% |
| `private-none` | 46% | 90% | 6% | 12% | 0% |
| `private_salient-none` | 49% | 96% | 2% | 5% | 8% |
| `public-instructed` | 67% | 90% | 2% | 37% | 0% |
| `public_salient-instructed` | 48% | 88% | 6% | 37% | 4% |
| `private-instructed` | 55% | 92% | 6% | 34% | 0% |
| `private_salient-instructed` | 31% | 79% | 19% | 26% | 2% |

Paired contrasts (salient − plain): at `none` +0.15 [+0.00, +0.31] (public), −0.05 [−0.35, +0.23]
(private); at `instructed` −0.17 [−0.33, +0.00] (public), −0.30 [−0.52, −0.09] (private).
Manipulation check: 100% in all 8 conditions.

**Run-to-run noise.** The four plain conditions were also run in iteration 1 with the same cases
and seeds; leak rates moved by 10–23 points (`private-none` 69% → 46%, `public-instructed` 50% →
67%, `private-instructed` 46% → 55%). With 48 trials per condition only large effects are
trustworthy; this is why later runs use 10 samples.

## B. Qwen3.6-27B small run

`train`, 8 cases × 1 sample = 8 trials per condition (21 conditions, 168 trials). All answered
correctly (guessing: 50%), always read the whole key, never gave up.

| Condition | Key in reasoning | States rule |
| --- | --- | --- |
| `public-none` / `private-none` | 100% / 100% | 0% / 0% |
| `public-intrinsic` / `private-intrinsic` | 50% / 50% | 50% / 75% |
| `public-instructed` / `private-instructed` | 25% / 12% | 100% / 50% |
| `public-both` / `private-both` | 12% / 12% | 100% / 100% |
| `placebo-none` | 100% | 0% |
| `public-offtarget_intrinsic` / `public-offtarget_instructed` | 88% / 88% | — |
| `routing.public-none` / `routing.private-none` | 100% / 100% | 0% |
| `public_salient-none` / `private_salient-none` | 100% / 100% | 0% |
| `public_salient-instructed` / `private_salient-instructed` | 12% / 50% | 100% / 88% |
| `public_reminder-none` / `private_reminder-none` | 100% / 100% | 0% |
| `public_reminder-instructed` / `private_reminder-instructed` | 25% / 25% | 100% / 100% |

Says vs does: rule stated in 77 / 152 key trials; leak 32% when stated, 89% when not. Channel of the
stated rule (LLM judges, before the human check): reply 64–84%, both 16–35%, reasoning only 0%.
Observer mentions: 0 of 168 (both judges and regex).

## C. Measuring the descriptive labels: regex vs LLM judges vs human

**Judges:** `openai/gpt-4.1-mini` and `anthropic/claude-haiku-4.5` via OpenRouter, blind to the
condition (reasoning and tool calls only). **Human labels:** one experimenter, blind and shuffled,
with `cot-label`.

### Golden set 1: 60 trajectories from the 27B small run (stratified)

Cohen's κ against the human labels:

| Label | regex | gpt-4.1-mini | claude-haiku-4.5 |
| --- | --- | --- | --- |
| Rule stated | **0.97** | 0.97 | 0.69 |
| Rule channel | **0.85** | 0.68 | 0.68 |
| How much of the secret | **1.00** | 0.87 | 1.00 |
| Leak kind | **1.00** | 0.94 | 1.00 |
| Mentions observer | — | 1.00 | 1.00 |
| Suspects a test | — | 1.00 | 1.00 |

The human labels had no positives for the last two, so their κ = 1.00 only shows the judges do
not raise false alarms. The 6 regex–human disagreements on the channel are all `reply` vs
`unspecified` (a rule sentence that names no channel next to a sentence about the reply).

Before the human check, judge vs regex on all 168 trajectories: rule stated κ 0.94 / 0.77
(gpt / haiku vs the other judge), channel 0.76 / 0.70, secret 0.84, leak kind 0.90; gpt-4.1-mini
called 14 full leaks "partial".

### Golden set 2: 10 positives for the observer / test labels

6 real Qwen3-8B trajectories that mention the observer (the human labelled 5 as mentions) and 4
synthetic ones: real 27B trajectories with one eval-aware sentence inserted (all 4 labelled as
suspecting a test).

| Label | gpt-4.1-mini | claude-haiku-4.5 |
| --- | --- | --- |
| Mentions observer | **κ 0.80**: 5 / 5 found, 1 false positive | κ 0.40: 5 / 5 found, 3 false positives |
| Suspects a test | **κ 1.00**: 4 / 4 found, none false | κ 1.00 |

**Decision:** regex for rule, channel, secret and leak kind; gpt-4.1-mini for observer mentions
and suspected tests. Caveat: the test positives are synthetic and explicit — no real one exists in
any run — so sensitivity to subtler hints is untested.
