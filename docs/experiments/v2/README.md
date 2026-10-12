# v2: channel, motivation and reading (A1–A3)

← [project README](../../../README.md) · previous version: [v1](../v1/README.md) · terms: [terminology](../../terminology.md)

Follows up three questions v1 left open: does an instruction work because it names the reasoning (A1)? does
a reason work better if it names the reasoning as a channel (A2)? does "read only what you need" make
the model read less (A3)? Four environments, visible conditions only, run in three stages — smoke →
small → main. Frozen at tag `experiment-v2` before `main`. **Closed:** A1 not supported, A2 supported
(larger than predicted), A3 not supported — see [results/main.md](results/main.md).

| Document | What is in it |
| --- | --- |
| [plan.md](plan.md) | design, conditions, hypotheses A1–A3 with predictions, stages, deviations |
| [results/smoke.md](results/smoke.md) | stage 1: the pipeline works in four environments; three wording problems fixed |
| [results/small.md](results/small.md) | stage 2: the last check before the freeze; read_exact added as a separate case |
| [results/main.md](results/main.md) | **stage 3, confirmatory: the final results**, 240 attempts per condition |
| [examples.md](examples.md) | base prompts of the four environments and one real trajectory per condition |
| [figures/](figures/) | per-environment figures, one folder per stage (`smoke/`, `small/`, `main/` — the final ones) — `scripts/secret_file/plots/v2.py` |

Code: environments `src/cot_controllability/environments.py`, dataset
`scripts/secret_file/datasets/v2.py`, analysis `scripts/secret_file/analysis/v2.py`, stage runner
`infra/run_stage.sh`.

Regenerate every stage's figures:

```bash
O=outputs/qwen3.6-27b/v2; P="uv run --group plots python scripts/secret_file/plots/v2.py"
$P $O/smoke --check $O/smoke-check --out docs/experiments/v2/figures/smoke
$P $O/small $O/small-read_exact --check $O/small-check $O/small-read_exact-check --out docs/experiments/v2/figures/small
$P $O/main --check $O/main-check --out docs/experiments/v2/figures/main
```
