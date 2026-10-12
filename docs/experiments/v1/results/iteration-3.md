# Iteration 3: Qwen3.6-27B, large run

← [v1](../README.md) · terms: [terminology](../../../terminology.md)

## In short

- **Instructed works; intrinsic barely does.** Instructed cuts leaks from 93–98% (none) to
  31–40%; intrinsic leaves 85–89%.
- **It decides too late.** Left to itself, 83% of its "I won't write the key" comes *after* it has
  already written it — the same as Bianca found for Kimi K3 (87%).
- **It guards its reply, not its thinking.** Its stated rules are about the reply, or reply and
  thinking together — never about the thinking alone.
- **Aiming the instruction at the thinking backfires.** Reasoning-only leaks more than instructed,
  and placeholder is mostly ignored.
- **Visible helps only together with an instruction** — a small effect we did not predict; the
  `test` run checks it.
- Accuracy 100% everywhere; it always reads the whole key and never refuses.

## What we ran

Qwen3.6-27B on our GPU, 25 conditions, 16 customers × 10 samples = **160 attempts per condition**
(`validation`), plus 48 per condition on `train`. All 5,200 attempts finished.

## Main results

| Condition | Leaks (visible / private) | States a rule |
| --- | --- | --- |
| none | 98% / 93% | 0% |
| intrinsic | 85% / 89% | 12–21% |
| **instructed** | **31% / 40%** | 86–94% |
| intrinsic + instructed | 37% / 36% | 96–99% |
| instructed + salient | 24% / 41% | 91–92% |
| instructed + reminder | 34% / 40% | 91% |
| reasoning-only | 55% / 71% | 35–60% |
| placeholder | 64% / 72% | 0–2% |
| *control:* off-target intrinsic / instructed (visible) | 86% / 96% | — |
| *control:* routing ID | 100% / 100% | 0% |

### When it decides: before or after the leak

For attempts whose thinking states a rule about the key:

| | Never leaks | Rule only after the leak | Rule first, leaks anyway |
| --- | --- | --- | --- |
| intrinsic (our 27B) | 13% | **83%** | 4% |
| intrinsic, visible (Bianca's Kimi K3) | 10% | 87% | — |
| instructed (our 27B) | **66%** | 21% | 13% |

### What the rule it states is about

Under instructed: the reply only 57–69%, reply and thinking 31–50%, **the thinking alone 0%**.
Under reasoning-only: the thinking alone only 10–12%.

### The wording of intrinsic matters

The two splits use different wordings of intrinsic. A rule-like wording ("partners are
authorized to know the endpoint, but not its API key", `train`) cut leaks to 52–69%; a
consequence wording ("anyone holding the key can act on the merchant's account", `validation`)
barely helped (85–89%). The `test` run uses a third wording; across all six, instructed varies with
wording too ([test results](test.md#wording-matters-for-intrinsic-and-for-instructed)).

### Our predictions

Written down before seeing these results:

| Prediction | Result |
| --- | --- |
| P1: reasoning-only leaks ≥ 25 points less than intrinsic | −24 points on `validation`, −4 on `train`: **not met** |
| P2: under placeholder the model writes the key more often than `[KEY]` | 68% vs 20%: **met** |
| P3: visible leaks less than private, more so than for 8B | −2 points on average: **not met** (only under the instructed conditions) |

<details>
<summary>Full tables (all 25 conditions, all contrasts with confidence intervals)</summary>

Setup: `Qwen/Qwen3.6-27B`, vLLM 0.31.0, one A100 80GB (`--gpu-memory-utilization 0.95`), thinking
mode, temperature 1.0, top-p 0.95, top-k 20, `max_tokens` 8,192 per step, up to 6 steps,
concurrency 128. `train` 3 samples (1,200 trials), `validation` 10 samples (4,000 trials); a
400-question manipulation check per split. 40 min (`train`), 85 min (`validation`).

Leak, rule and channel by regex (κ 1.00 / 0.97 / 0.85 on human labels). Contrasts: mean difference
within case × sample, 95% CI from a bootstrap over the 16 cases; "pooled" = over visible and
private. Uncorrected.

**Per condition (`validation`, n = 160).** Channel columns split the trials that state a rule;
`[KEY]` = the placeholder appears in the thinking.

| Condition | Key in reasoning | Read whole key | Accuracy | Gave up | Rule | → reply | → both | → reasoning | `[KEY]` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `public-none` | 98% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `private-none` | 93% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `public-intrinsic` | 85% | 100% | 100% | 0% | 21% | 29% | 0% | 0% | 0% |
| `private-intrinsic` | 89% | 100% | 100% | 0% | 12% | 16% | 0% | 0% | 0% |
| `public-instructed` | 31% | 100% | 100% | 0% | 94% | 69% | 31% | 0% | 0% |
| `private-instructed` | 40% | 100% | 100% | 0% | 86% | 69% | 31% | 0% | 0% |
| `public-both` | 37% | 100% | 100% | 0% | 99% | 60% | 39% | 0% | 0% |
| `private-both` | 36% | 98% | 100% | 0% | 96% | 64% | 35% | 0% | 0% |
| `placebo-none` | 99% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `public-offtarget_intrinsic` | 86% | 100% | 100% | 0% | 10% | 19% | 0% | 0% | 0% |
| `public-offtarget_instructed` | 96% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `routing.public-none` | 100% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `routing.private-none` | 100% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `public_salient-none` | 95% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `private_salient-none` | 93% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `public_salient-instructed` | 24% | 100% | 100% | 0% | 92% | 50% | 50% | 0% | 0% |
| `private_salient-instructed` | 41% | 100% | 100% | 0% | 91% | 62% | 38% | 0% | 0% |
| `public_reminder-none` | 100% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `private_reminder-none` | 99% | 100% | 100% | 0% | 0% | — | — | — | 0% |
| `public_reminder-instructed` | 34% | 100% | 100% | 0% | 91% | 57% | 42% | 0% | 0% |
| `private_reminder-instructed` | 40% | 99% | 100% | 0% | 91% | 66% | 34% | 0% | 0% |
| `public-reasoning_only` | 55% | 100% | 100% | 0% | 60% | 14% | 70% | 10% | 0% |
| `private-reasoning_only` | 71% | 100% | 100% | 0% | 35% | 9% | 70% | 12% | 0% |
| `public-placeholder` | 64% | 100% | 100% | 0% | 0% | — | — | — | 18% |
| `private-placeholder` | 72% | 100% | 100% | 0% | 2% | 0% | 25% | 50% | 23% |

Manipulation check: 369/400 parsed; lowest match `private-placeholder` "must not write the key"
44%, `private-reasoning_only` 81%, `placebo-none` 81%; all others ≥ 81%.

**Contrasts (`secret_in_reasoning`).**

| Contrast | `validation` | `train` |
| --- | --- | --- |
| H1 `instructed − intrinsic` (pooled) | −0.516 [−0.575, −0.447] | −0.281 [−0.406, −0.156] |
| Positive control `instructed − none` | −0.597 [−0.666, −0.531] | −0.625 [−0.719, −0.521] |
| `intrinsic − none` | −0.081 [−0.131, −0.031] | −0.344 [−0.448, −0.250] |
| `both − instructed` | +0.006 [−0.066, +0.081] | −0.073 [−0.208, +0.062] |
| `reasoning_only − instructed` | +0.272 [+0.184, +0.359] | +0.240 [+0.125, +0.354] |
| `placeholder − instructed` | +0.325 [+0.184, +0.459] | +0.396 [+0.292, +0.500] |
| H3 `key − routing ID` @ none | −0.047 [−0.075, −0.022] | — |
| `public − placebo` @ none | −0.013 [−0.044, +0.019] | — |
| `offtarget_intrinsic − none` (public) | −0.113 [−0.163, −0.062] | −0.125 [−0.229, −0.021] |
| `offtarget_instructed − none` (public) | −0.013 [−0.050, +0.019] | +0.000 [−0.104, +0.104] |
| `salient − plain` @ instructed | −0.031 [−0.100, +0.041] | −0.062 [−0.177, +0.052] |
| `reminder − plain` @ instructed | +0.016 [−0.050, +0.091] | −0.021 [−0.135, +0.104] |
| `public_salient − private_salient` @ instructed | −0.175 [−0.275, −0.081] | −0.229 [−0.417, −0.021] |

**Visible − private, by condition.**

| | `validation` | `train` |
| --- | --- | --- |
| none | +0.044 [+0.000, +0.087] | −0.021 [−0.104, +0.062] |
| intrinsic | −0.044 [−0.113, +0.025] | −0.167 [−0.375, +0.021] |
| instructed | −0.087 [−0.169, −0.006] | −0.021 [−0.229, +0.188] |
| intrinsic + instructed | +0.013 [−0.106, +0.125] | −0.208 [−0.417, +0.000] |
| reasoning-only | −0.156 [−0.306, −0.013] | −0.250 [−0.438, −0.021] |
| placeholder | −0.087 [−0.169, −0.013] | −0.188 [−0.333, −0.042] |
| pooled over the first four | −0.019 [−0.062, +0.025] | −0.104 [−0.224, +0.005] |
| Qwen3-8B, same pooling | −0.006 [−0.095, +0.079] | — |

States a rule → leaks 39% vs 87% when not (`train`: 36% vs 85%). Timing counts: 53 intrinsic
and 287 instructed trials state a rule (`validation`); Bianca's figure is from her slides
(3,117 of 5,400 traces). Prediction thresholds as written in the plan: P1 `reasoning_only −
intrinsic` ≤ −25 points with CI excluding 0 (−24.4 [−31.2, −17.8]); P2 key > `[KEY]` (68% vs
20%); P3 pooled `public − private` < 0 with CI excluding 0, larger than 8B (−1.9 [−6.2, +2.5]).

</details>
