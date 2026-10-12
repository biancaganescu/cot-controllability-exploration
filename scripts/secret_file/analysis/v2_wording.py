"""Post-hoc look at A2's wording split (docs/experiments/v2/results/main.md, "Why w4 and w6").

Under intrinsic + channel, per reason wording and per environment: how many attempts state a rule,
the rule timing (the rule-timing figure's categories) and how many rules are about the reply only.

    uv run --group plots python scripts/secret_file/analysis/v2_wording.py outputs/qwen3.6-27b/v2/main
"""
import argparse
import importlib.util
from collections import Counter
from pathlib import Path

from cot_controllability import secret_file as sf

_spec = importlib.util.spec_from_file_location('plots_v1', Path(__file__).parents[1] / 'plots' / 'v1.py')
plots_v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plots_v1)  # add_decisions: the rule timing used by the figures

CONDITION = 'public-intrinsic_channel'


def table(rows, group, label):
    keys = list(plots_v1.DECISIONS)
    print(f"\n{label:<10} {'n':>3} {'rule':>5} {'reply only':>11}  " + '  '.join(f'{k:>11}' for k in keys))
    for g in sorted({group(r) for r in rows}):
        sub = [r for r in rows if group(r) == g]
        decisions = Counter(r['decision'] for r in sub)
        reply_only = sum(bool(r['rule_about_reply']) and not r['rule_about_reasoning'] for r in sub)
        print(f"{g:<10} {len(sub):>3} {sum(bool(r['rule_verbalized']) for r in sub):>5} {reply_only:>11}  "
              + '  '.join(f'{decisions[k]:>11}' for k in keys))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('run', type=Path, help='v2 run directory')
    args = parser.parse_args()
    rows = [r for r in sf.score_run(args.run)['trials'] if r['condition'] == CONDITION]
    plots_v1.add_decisions(args.run, rows)
    print(f'{args.run}: {len(rows)} trials under {CONDITION}')
    table(rows, lambda r: f"w{r['paraphrase']['instruction'] + 1}", 'wording')
    table(rows, lambda r: r['domain'], 'env')


if __name__ == '__main__':
    main()
