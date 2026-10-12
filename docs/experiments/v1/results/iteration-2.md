# Iteration 2: salient on Qwen3-8B, first look at Qwen3.6-27B, checking our measurements

← [README](../../../../README.md) · condition names: [terminology](../../../terminology.md)

## In short

- **Salient did not help Qwen3-8B.** Even when the partner writes "I can read your
  reasoning in real time", it rarely mentions being watched (0–8%) and leaks as before.
- **Our numbers were noisy.** Rerunning the same conditions moved leak rates by 10–23 points, so
  later runs use more samples.
- **Qwen3.6-27B follows instructions.** On a small first run, instructed cut leaks from 100% (none)
  to 12–25%. (The 50% it showed for intrinsic did not hold up in the large run.)
- **Simple pattern matching measures our labels better than LLM judges.** Checked against 70
  hand-labelled trajectories, the regex was more accurate than two LLM judges for whether a rule is
  stated, which output it is about, and how much of the key appears. An LLM judge is used only for
  "mentions the observer" and "suspects a test".

## A. Qwen3-8B with salient

48 attempts per condition. *Salient* = the partner also says in their own message whether they
see the reasoning ([terminology](../../../terminology.md)).

| Condition | Leaks | Mentions the observer |
| --- | --- | --- |
| none, visible | 60% | 0% |
| none + salient, visible | 74% | 0% |
| none, private | 46% | 0% |
| none + salient, private | 49% | 8% |
| instructed, visible | 67% | 0% |
| instructed + salient, visible | 48% | 4% |
| instructed, private | 55% | 0% |
| instructed + salient, private | 31% | 2% |

The same four plain conditions had been run before: `private-none` 69% → 46%, `public-instructed`
50% → 67%, `private-instructed` 46% → 55%. That is the noise level at 48 attempts.

## B. Qwen3.6-27B, small run

8 attempts per condition — only big differences are meaningful.

| Condition | Leaks (visible / private) |
| --- | --- |
| none | 100% / 100% |
| intrinsic | 50% / 50% |
| instructed | 25% / 12% |
| intrinsic + instructed | 12% / 12% |
| *control:* routing ID | 100% / 100% |

All answers correct; the model never mentioned the observer (0 of 168). When it stated a rule,
it leaked in 32% of attempts, vs 89% when it did not.

## C. Checking the measurements

We labelled 60 + 10 trajectories by hand (blind to the condition) and compared.

| Label | Regex | gpt-4.1-mini | claude-haiku-4.5 | Used |
| --- | --- | --- | --- | --- |
| Is a rule stated? | **0.97** | 0.97 | 0.69 | regex |
| Which output is the rule about? | **0.85** | 0.68 | 0.68 | regex |
| How much of the key appears? | **1.00** | 0.87 | 1.00 | regex |
| How does the leak read? | **1.00** | 0.94 | 1.00 | regex |
| Mentions the observer? | — | **0.80** | 0.40 | gpt-4.1-mini |
| Suspects a test? | — | **1.00** | 1.00 | gpt-4.1-mini |

Numbers are Cohen's κ against the human labels (1 = perfect agreement). The "suspects a test"
check used 4 synthetic examples — no real one has appeared in any run.

<details>
<summary>Details</summary>

**A.** `validation`, 16 cases × 3 samples. Paired contrasts (salient − plain): at `none` +0.15
[+0.00, +0.31] (public), −0.05 [−0.35, +0.23] (private); at `instructed` −0.17 [−0.33, +0.00]
(public), −0.30 [−0.52, −0.09] (private). Manipulation check 100% in all 8 conditions. Full
per-condition rates (read whole key, gave up, states the rule):

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

**B.** `train`, 8 cases × 1 sample, 21 conditions (168 trials). Off-target 88% / 88%; placebo
100%; salient + instructed 12% / 50%; reminder + instructed 25% / 25%; salient / reminder without
an instruction 100%. The LLM judges put the channel of stated rules at reply 64–84%, reply and
reasoning 16–35%, reasoning only 0%.

**C.** Golden set 1: 60 stratified trajectories from the 27B small run; it had no positives for
the observer / test labels, so a second set of 10 was built: 6 real Qwen3-8B trajectories that
mention the observer (5 labelled as such) and 4 real 27B trajectories with one eval-aware
sentence inserted. On it gpt-4.1-mini found 5/5 observer mentions with 1 false alarm and 4/4
tests; claude-haiku-4.5 found 5/5 with 3 false alarms. The regex's 6 channel disagreements with
the human (of 60) are all "reply" vs "not specified". Judges see only the reasoning and tool
calls, never the condition.

</details>
