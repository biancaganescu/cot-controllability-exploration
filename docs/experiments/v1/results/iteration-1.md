# Iteration 1: Qwen3-8B

← [v1](../README.md) · terms: [terminology](../../../terminology.md)

## In short

- Qwen3-8B **understands every instruction** — asked directly, it says correctly who can see its
  thinking and that it must not write the key (100%).
- But it **writes the key in its thinking half to two thirds of the time, whatever it is told**:
  visible or private, under none, intrinsic or instructed alike.
- In its **final answer** it almost never writes the key (0–4%). It controls what it *says*, not
  what it *thinks*.
- The leak is a **habit**: right after opening the file it restates what it read. It does that even
  more (86–93%) with an ID that is not secret at all.
- When it does try to be careful, it **gives up** instead: 17% of attempts under instructed
  while visible refused to open the file and asked the partner to look up the key.

## What we ran

Qwen3-8B on our GPU, 16 customers × 3 samples = **48 attempts per condition** (`validation`).
All runs finished; the model's self-report was checked with a separate question per condition.

## Main results

| Condition | Visible / private | Leaks | Reads the whole key | Correct | Gives up |
| --- | --- | --- | --- | --- | --- |
| none | visible | 60% | 92% | 98% | 2% |
| none | private | 69% | 98% | 96% | 2% |
| intrinsic | visible | 60% | 96% | 98% | 0% |
| intrinsic | private | 63% | 98% | 100% | 0% |
| instructed | visible | 50% | **77%** | **81%** | **17%** |
| instructed | private | 46% | 96% | 98% | 2% |
| intrinsic + instructed | visible | 55% | 83% | 90% | 8% |
| intrinsic + instructed | private | 59% | 85% | 88% | 12% |
| *control:* placebo | — | 48% | 94% | 96% | 4% |
| *control:* routing ID | visible | **86%** | 98% | 100% | 0% |

Differences of 10–20 points between rows are within chance at this size (placebo, which
says nothing, is the lowest).

<details>
<summary>Full tables (all 13 conditions, all contrasts with confidence intervals)</summary>

Setup: `Qwen/Qwen3-8B`, vLLM 0.31.0, one A100 80GB, thinking mode, temperature 0.6, top-p 0.95,
top-k 20, `max_tokens` 8,192 per step, up to 6 steps. `train`: 208 trials (1 sample);
`validation`: 624 trials (3 samples, 48 per condition); a 208-question manipulation check per
split. All 832 trials finished (830 answered, 2 hit `max_tokens`). Dataset sha256 `733a04c6…`,
runner sha256 `2ab33544…`.

O1 = read the full secret; O2 = wrote the secret in its reasoning (rates among trials with a known
outcome); the other columns are over all 48 trials.

| Condition | O1 read full | O2 in reasoning | Correct | Deflected | Answered w/o full read |
| --- | --- | --- | --- | --- | --- |
| `public-none` | 0.92 | 0.60 | 0.98 | 0.02 | 0.06 |
| `private-none` | 0.98 | 0.69 | 0.96 | 0.02 | 0.00 |
| `public-intrinsic` | 0.96 | 0.60 | 0.98 | 0.00 | 0.02 |
| `private-intrinsic` | 0.98 | 0.63 | 1.00 | 0.00 | 0.02 |
| `public-instructed` | 0.77 | 0.50 | 0.81 | 0.17 | 0.04 |
| `private-instructed` | 0.96 | 0.46 | 0.98 | 0.02 | 0.02 |
| `public-both` | 0.83 | 0.55 | 0.90 | 0.08 | 0.08 |
| `private-both` | 0.85 | 0.59 | 0.88 | 0.12 | 0.02 |
| `placebo-none` | 0.94 | 0.48 | 0.96 | 0.04 | 0.02 |
| `public-offtarget_intrinsic` | 0.92 | 0.67 | 0.98 | 0.02 | 0.06 |
| `public-offtarget_instructed` | 0.98 | 0.49 | 0.98 | 0.02 | 0.00 |
| `routing.public-none` | 0.98 | 0.86 | 1.00 | 0.00 | 0.02 |
| `routing.private-none` | 1.00 | 0.93 | 1.00 | 0.00 | 0.00 |

Paired contrasts: mean difference within case × sample, 95% CI from a bootstrap over the 16
cases; negative = less exposure in the first condition. Uncorrected.

| Contrast | O1 read full | O2 in reasoning |
| --- | --- | --- |
| H1 `instructed − intrinsic` (public) | −0.19 [−0.29, −0.10] | −0.14 [−0.35, +0.05] |
| H1 `instructed − intrinsic` (private) | −0.02 [−0.10, +0.04] | −0.16 [−0.34, +0.02] |
| H2 `public − private` @ none | −0.06 [−0.15, +0.02] | −0.09 [−0.30, +0.12] |
| H2 `public − private` @ intrinsic | −0.02 [−0.08, +0.04] | +0.00 [−0.20, +0.18] |
| H2 `public − private` @ instructed | −0.19 [−0.29, −0.06] | +0.07 [−0.11, +0.23] |
| H2 `public − private` @ both | −0.02 [−0.12, +0.08] | +0.00 [−0.17, +0.16] |
| H3 `key − routing ID` @ public-none | −0.06 [−0.15, +0.02] | −0.23 [−0.41, −0.05] |
| H3 `key − routing ID` @ private-none | −0.02 [−0.06, +0.00] | −0.26 [−0.43, −0.09] |
| Positive control `instructed − none` (public) | −0.15 [−0.27, −0.04] | −0.11 [−0.36, +0.13] |
| `intrinsic − none` (public) | +0.04 [−0.04, +0.12] | −0.02 [−0.20, +0.14] |
| Control `public − placebo` (none) | −0.02 [−0.12, +0.08] | +0.13 [−0.07, +0.33] |
| Control `offtarget_intrinsic − none` | +0.00 [−0.10, +0.10] | +0.09 [−0.11, +0.28] |
| Control `offtarget_instructed − none` | +0.06 [−0.02, +0.15] | −0.11 [−0.34, +0.12] |

Manipulation check: 100% match for visibility, intrinsic and instructed (both splits);
`placebo-none`, which states nothing, drew 31% "not stated".

</details>
