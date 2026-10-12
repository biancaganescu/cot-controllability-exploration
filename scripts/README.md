# Scripts

One folder per task. Each script has a docstring (what, why, usage) and `--help`; run from the
repo root. The task runners themselves are entry points (`cot-secret-file`, `cot-secret-token`,
`cot-judge`, `cot-label`); see [DEVELOPER.md](../DEVELOPER.md).

## `secret_file/`

| Script | What it does | When to run | Writes |
| --- | --- | --- | --- |
| `build_data.py` | builds the task data: all wording, conditions, files, tools, customers | after changing any wording (`--fresh` for new customers) | `src/cot_controllability/data/secret_file.json.gz` |
| `analyze.py` | the pre-registered analysis (frozen at `experiment-v1`): rates, H1–H4, P1–P3, manipulation check | once per finished run | report on stdout (`logs/analyze-test.txt` for `test`) |
| `plot.py` | the result figures and the "rule only after the leak" table (descriptive) | after a run, to refresh the docs | `docs/experiments/v1/figures/*.png` |
| `build_golden_positives.py` | one-off: the judge's golden set of positives (observer, eval awareness) | only to rebuild that file | `data/golden/observer-eval-positives.jsonl.gz` |

The `secret_token` demo has no scripts.
