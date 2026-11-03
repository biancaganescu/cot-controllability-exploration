# v1: does a model keep a secret out of its thinking?

← [project README](../../../README.md) · next version: [v2](../v2/README.md) · terms: [terminology](../../terminology.md)

One scenario (Parcelly), Qwen3-8B then Qwen3.6-27B, 25 conditions crossing visible / private with
none / intrinsic / instructed and several variants. Pre-registered, frozen at tag `experiment-v1`,
then run once on a held-out `test` split. **Closed.**

| Document | What is in it |
| --- | --- |
| [plan.md](plan.md) | design, hypotheses H1–H4, predictions P1–P3, analysis, deviations, recommendations for the next runs |
| [results/iteration-1.md](results/iteration-1.md) | Qwen3-8B: understands every instruction, follows none in its thinking |
| [results/iteration-2.md](results/iteration-2.md) | salient on 8B; first Qwen3.6-27B run; scoring checked against hand labels |
| [results/iteration-3.md](results/iteration-3.md) | Qwen3.6-27B, 25 conditions, 160 attempts each |
| [results/test.md](results/test.md) | **final results**: the held-out run, 320 attempts per condition, with figures |
| [examples.md](examples.md) | one real trajectory per main condition |
| [figures/test/](figures/test/) | the final figures, from the held-out `test` run, used in the results and the project README |

Code: dataset `scripts/secret_file/datasets/v1.py`, analysis `scripts/secret_file/analysis/v1.py`,
figures `scripts/secret_file/plots/v1.py`.
