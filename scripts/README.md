# Scripts

One folder per task; inside it one folder per kind of script (`datasets/`, `analysis/`, `plots/`) and
one file per version. Post-hoc additions go into that version's file behind a flag, not into new files. Each script has a docstring (what, why, usage)
and `--help`; run from the repo root. The task runners themselves are entry points
(`cot-secret-file`, `cot-secret-token`, `cot-judge`, `cot-label`); see [DEVELOPER.md](../DEVELOPER.md).

## `secret_file/`

| Script | What it does | When to run | Writes |
| --- | --- | --- | --- |
| `datasets/v1.py`, `datasets/v2.py`, `datasets/v3.py` | build one dataset version: all wording, conditions, files, tools, customers | after changing that version's wording (a released version is never edited: make a new one) | `src/cot_controllability/data/secret_file/<version>.json.gz` |
| `analysis/v1.py` | v1's pre-registered analysis (frozen at `experiment-v1`): rates, H1–H4, P1–P3, manipulation check | once per finished v1 run | report on stdout (`logs/analyze-test.txt` for `test`) |
| `analysis/v2.py` | v2's pre-registered analysis (A1–A3); `--wording-split` adds the post-hoc look at A2 per wording | once per finished v2 run | report on stdout |
| `analysis/v3.py` | v3's pre-registered analysis (B1–B4); reuses v2's helpers | once per finished v3 run | report on stdout |
| `plots/v1.py` | the v1 result figures and the "rule only after the leak" table (descriptive) | after a run, to refresh the docs | `docs/experiments/v1/figures/test/*.png` |
| `plots/v2.py` | the v2 figures, per environment: leaks, A1/A2 contrasts, knows vs does, rule timing, reading | after a v2 run | `docs/experiments/v2/figures/<stage>/*.png` |
| `plots/v3.py` | the same figures for v3's conditions and B1–B4 (v2's code with v3's rows and text) | after a v3 run | `docs/experiments/v3/figures/<stage>/*.png` |
| `build_golden_positives.py` | one-off: the judge's golden set of positives (observer, eval awareness) | only to rebuild that file | `data/golden/observer-eval-positives.jsonl.gz` |

The `secret_token` demo has no scripts.
