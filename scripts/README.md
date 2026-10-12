# Scripts

One folder per task, one file per version inside it. Each script has a docstring (what, why, usage)
and `--help`; run from the repo root. The task runners themselves are entry points
(`cot-secret-file`, `cot-secret-token`, `cot-judge`, `cot-label`); see [DEVELOPER.md](../DEVELOPER.md).

## `secret_file/`

| Script | What it does | When to run | Writes |
| --- | --- | --- | --- |
| `datasets/v1.py`, `datasets/v2.py` | build one dataset version: all wording, conditions, files, tools, customers | after changing that version's wording (a released version is never edited: make a new one) | `src/cot_controllability/data/secret_file/<version>.json.gz` |
| `analysis/v1.py` | v1's pre-registered analysis (frozen at `experiment-v1`): rates, H1–H4, P1–P3, manipulation check | once per finished v1 run | report on stdout (`logs/analyze-test.txt` for `test`) |
| `analysis/v2.py` | v2's pre-registered analysis (A1–A3) | once per finished v2 run | report on stdout |
| `plot.py` | the v1 result figures and the "rule only after the leak" table (descriptive) | after a run, to refresh the docs | `docs/experiments/v1/figures/*.png` |
| `build_golden_positives.py` | one-off: the judge's golden set of positives (observer, eval awareness) | only to rebuild that file | `data/golden/observer-eval-positives.jsonl.gz` |

The `secret_token` demo has no scripts.
