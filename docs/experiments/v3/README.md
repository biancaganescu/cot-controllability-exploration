# v3: what makes the one sentence work (B1–B4)

← [project README](../../../README.md) · previous version: [v2](../v2/README.md) · terms: [terminology](../../terminology.md)

Four follow-ups to v2, on new customers in the same four environments: does v2's sentence about the
reasoning work because it is about the reasoning (B1, an emphasis control)? does it help an instruction
too (B2)? does framing the instruction around the model's own output protect better (B3)? does a
concrete instruction about what to *write* work like the one about what to read (B4)? Stages smoke →
small → main. **In progress.**

| Document | What is in it |
| --- | --- |
| [plan.md](plan.md) | why v3, conditions, stages, predictions B1–B4, deviations |
| [results/smoke.md](results/smoke.md) | stage 1: the pipeline works and every new sentence passes the check; first signals |
| [results/small.md](results/small.md) | stage 2: gate passed on new customers; which smoke signals held |
| results/main.md | stage 3, confirmatory — *pending* |
| [examples.md](examples.md) | base prompts and one real trajectory per condition (from smoke) |
| [figures/](figures/) | per-environment figures, one folder per stage (`smoke/`, `small/` so far) |

Code: dataset `scripts/secret_file/datasets/v3.py`, analysis `scripts/secret_file/analysis/v3.py`,
figures `scripts/secret_file/plots/v3.py`, stage runner `infra/run_stage.sh` (`DATA=v3`).
