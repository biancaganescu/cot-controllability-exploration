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
| results/smoke.md | stage 1 — *running* |
| results/small.md | stage 2 — *pending* |
| results/main.md | stage 3, confirmatory — *pending* |
| examples.md | one real trajectory per condition — *after smoke* |
| figures/ | per-environment figures, one folder per stage — *after smoke* |

Code: dataset `scripts/secret_file/datasets/v3.py`, analysis `scripts/secret_file/analysis/v3.py`,
figures `scripts/secret_file/plots/v3.py`, stage runner `infra/run_stage.sh` (`DATA=v3`).
