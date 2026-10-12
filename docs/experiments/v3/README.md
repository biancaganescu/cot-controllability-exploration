# v3: what makes the one sentence work (B1–B4)

← [project README](../../../README.md) · previous version: [v2](../v2/README.md) · terms: [terminology](../../terminology.md)

Four follow-ups to v2, on new customers in the same four environments: does v2's sentence about the
reasoning work because it is about the reasoning (B1, an emphasis control)? does it help an instruction
too (B2)? does framing the instruction around the model's own output protect better (B3)? does a
concrete instruction about what to *write* work like the one about what to read (B4)? Stages smoke →
small → main. **Done.** Emphasis does a little (−8 points), the reasoning sentence much more
(−30); adding it to an instruction barely helps (−6); "keep it out of everything you write" beats "do
not share with the partner" (56% vs 71%); "write only the first 4 characters" is ignored (84%).

| Document | What is in it |
| --- | --- |
| [plan.md](plan.md) | why v3, conditions, stages, predictions B1–B4, outcome on main, deviations |
| [results/smoke.md](results/smoke.md) | stage 1: the pipeline works and every new sentence passes the check; first signals |
| [results/small.md](results/small.md) | stage 2: gate passed on new customers; which smoke signals held |
| [results/main.md](results/main.md) | stage 3, confirmatory: B1–B4, per environment, the v2 wording split on new customers |
| [examples.md](examples.md) | base prompts and real trajectories per condition (from main), with the less common outcome for five conditions |
| [figures/](figures/) | per-environment figures, one folder per stage (`smoke/`, `small/`, `main/`) |

Code: dataset `scripts/secret_file/datasets/v3.py`, analysis `scripts/secret_file/analysis/v3.py`,
figures `scripts/secret_file/plots/v3.py`, stage runner `infra/run_stage.sh` (`DATA=v3`).
