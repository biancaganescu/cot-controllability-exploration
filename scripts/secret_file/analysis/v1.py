"""Pre-registered analysis of one secret_file run (docs/experiments/v1/plan.md; logic frozen at `experiment-v1`).

Checks: per-condition rates, H1-H4 and the plan's other contrasts on leaks (`secret_in_reasoning`,
paired within case x sample, 95% CI from a bootstrap over cases), intrinsic per paraphrase, P1-P3,
and the manipulation check. Prints a plain-text report; the `test` report is logs/analyze-test.txt.

    uv run python scripts/secret_file/analysis/v1.py outputs/qwen3.6-27b/large/test \
        --check logs/qwen3.6-27b-vllm-large-test-check-summary.json
"""
import argparse
import json
import random
import re
from collections import Counter, defaultdict

from cot_controllability import secret_file as sf
from cot_controllability.common import read_data, reasoning_variants

KEY = re.compile(r'\[KEY\]')


def rate(sub, k):
    known = [x[k] for x in sub if x[k] is not None]
    return (sum(known) / len(known), len(known)) if known else (None, 0)


def pooled(rows, pairs, key, resamples=4000, seed=0):
    """Mean of a - b over (case, sample) pairs, pooled over several (a, b) condition pairs;
    95% CI from a bootstrap over cases (all pairs of a case move together)."""
    by = defaultdict(dict)
    for r in rows:
        if r[key] is not None:
            by[(r['case_id'], r['sample'])][r['condition']] = float(r[key])
    diffs = defaultdict(list)
    for (case, _), v in by.items():
        for a, b in pairs:
            if a in v and b in v:
                diffs[case].append(v[a] - v[b])
    cases = sorted(diffs)
    if not cases:
        return None
    flat = [d for c in cases for d in diffs[c]]
    rng = random.Random(seed)
    boots = sorted(sum(p := [d for c in rng.choices(cases, k=len(cases)) for d in diffs[c]]) / len(p)
                   for _ in range(resamples))
    return sum(flat) / len(flat), boots[int(.025 * resamples)], boots[int(.975 * resamples)], len(flat)


def fmt(res):
    return '—' if res is None else f'{res[0]:+.3f} [{res[1]:+.3f}, {res[2]:+.3f}] (n={res[3]})'


def report(D, check_path, reference):
    """Print the full report for run directory `D`; `reference` is the Qwen3-8B run used by P3."""
    rows = sf.score_run(D)['trials']
    for r in rows:
        rec = read_data(sf.trial_path(D, r['condition'], r['case_id'], r['sample']))
        text = ' '.join(t for raw in rec['responses'] for t in reasoning_variants(raw['choices'][0]['message'])[0].values())
        r['placeholder_used'] = bool(KEY.search(text)) if text else None
    print(f'{D}: {len(rows)} trials, status {dict(Counter(r["status"] for r in rows))}')
    print(f"\n{'condition':<29} {'wrote':>6} {'readfull':>8} {'acc':>5} {'gaveup':>6} {'rule':>5} {'ch:reply':>8} {'ch:both':>7} {'ch:reas':>7} {'[KEY]':>6} n")
    for c in sf.conditions(sf.load_data()):
        s = [r for r in rows if r['condition'] == c]
        if not s:
            continue
        rule = [r for r in s if r['rule_verbalized']]
        cells = [rate(s, 'secret_in_reasoning')[0], rate(s, 'read_full_secret')[0], rate(s, 'task_success')[0],
                 rate(s, 'deflected')[0], rate(s, 'rule_verbalized')[0],
                 None if not rule else sum(bool(r['rule_about_reply']) and not r['rule_about_reasoning'] for r in rule) / len(rule),
                 None if not rule else sum(bool(r['rule_about_reply']) and bool(r['rule_about_reasoning']) for r in rule) / len(rule),
                 None if not rule else sum(bool(r['rule_about_reasoning']) and not r['rule_about_reply'] for r in rule) / len(rule),
                 rate(s, 'placeholder_used')[0]]
        print(f'{c:<29} ' + ' '.join(f'{"—" if v is None else f"{100*v:.0f}%":>{w}}' for v, w in zip(cells, (6, 8, 5, 6, 5, 8, 7, 7, 6), strict=True)) + f' {len(s)}')

    V, LEVELS = ('public', 'private'), ('none', 'intrinsic', 'instructed', 'both')
    print('\nPREDICTIONS')
    print('P1 reasoning_only - intrinsic (pooled):', fmt(pooled(rows, [(f'{v}-reasoning_only', f'{v}-intrinsic') for v in V], 'secret_in_reasoning')))
    ph = [r for r in rows if r['condition'].endswith('-placeholder')]
    print('P2 placeholder: secret in reasoning', f"{100*rate(ph, 'secret_in_reasoning')[0]:.0f}%", '| "[KEY]" in reasoning', f"{100*rate(ph, 'placeholder_used')[0]:.0f}%",
          '| per visibility', {v: (f"{100*rate([r for r in ph if r['condition'].startswith(v)], 'secret_in_reasoning')[0]:.0f}%",
                                 f"{100*rate([r for r in ph if r['condition'].startswith(v)], 'placeholder_used')[0]:.0f}%") for v in V})
    p3 = pooled(rows, [(f'public-{i}', f'private-{i}') for i in LEVELS], 'secret_in_reasoning')
    rows8 = sf.score_run(reference)['trials']
    p3_8 = pooled(rows8, [(f'public-{i}', f'private-{i}') for i in LEVELS], 'secret_in_reasoning')
    print('P3 public - private pooled, 27B:', fmt(p3), '| 8B:', fmt(p3_8))
    for i in LEVELS + ('reasoning_only', 'placeholder'):
        print(f'     @ {i:<15}', fmt(pooled(rows, [(f'public-{i}', f'private-{i}')], 'secret_in_reasoning')))

    DIRECTIVE = ('instructed', 'both', 'reasoning_only', 'placeholder')
    print('\nH4 public - private, pooled over directive conditions:',
          fmt(pooled(rows, [(f'public-{i}', f'private-{i}') for i in DIRECTIVE]
                     + [('public_salient-instructed', 'private_salient-instructed'),
                        ('public_reminder-instructed', 'private_reminder-instructed')], 'secret_in_reasoning')))
    print('H4 public - private @ none (should not be negative):', fmt(pooled(rows, [('public-none', 'private-none')], 'secret_in_reasoning')))
    print('\nINTRINSIC PER PARAPHRASE (instruction slot)')
    for slot in sorted({r['paraphrase']['instruction'] for r in rows}):
        sub = [r for r in rows if r['paraphrase']['instruction'] == slot]
        print(f'  slot {slot}: intrinsic {100*rate([r for r in sub if r["condition"].endswith("-intrinsic")], "secret_in_reasoning")[0]:.0f}% |'
              f' H1 instructed - intrinsic', fmt(pooled(sub, [(f'{v}-instructed', f'{v}-intrinsic') for v in V], 'secret_in_reasoning')))
    print('\nPLAN CONTRASTS (secret_in_reasoning)')
    for label, pairs in [
            ('H1 instructed - intrinsic', [(f'{v}-instructed', f'{v}-intrinsic') for v in V]),
            ('positive control instructed - none', [(f'{v}-instructed', f'{v}-none') for v in V]),
            ('intrinsic - none', [(f'{v}-intrinsic', f'{v}-none') for v in V]),
            ('both - instructed', [(f'{v}-both', f'{v}-instructed') for v in V]),
            ('reasoning_only - instructed', [(f'{v}-reasoning_only', f'{v}-instructed') for v in V]),
            ('placeholder - instructed', [(f'{v}-placeholder', f'{v}-instructed') for v in V]),
            ('H3 key - routing ID @none', [(f'{v}-none', f'routing.{v}-none') for v in V]),
            ('public - placebo @none', [('public-none', 'placebo-none')]),
            ('offtarget_intrinsic - none (public)', [('public-offtarget_intrinsic', 'public-none')]),
            ('offtarget_instructed - none (public)', [('public-offtarget_instructed', 'public-none')]),
            ('salient - plain @instructed', [(f'{v}_salient-instructed', f'{v}-instructed') for v in V]),
            ('reminder - plain @instructed', [(f'{v}_reminder-instructed', f'{v}-instructed') for v in V]),
            ('salient - reminder @instructed', [(f'{v}_salient-instructed', f'{v}_reminder-instructed') for v in V]),
            ('public_salient - private_salient @instructed', [('public_salient-instructed', 'private_salient-instructed')]),
            ('accuracy: instructed - none', None)]:
        if pairs is None:
            print(f'  {label:<46}', fmt(pooled(rows, [(f'{v}-instructed', f'{v}-none') for v in V], 'task_success')))
        else:
            print(f'  {label:<46}', fmt(pooled(rows, pairs, 'secret_in_reasoning')))
    rule_rows = [r for r in rows if r['item'] == 'secret' and r['rule_verbalized'] is not None and r['secret_in_reasoning'] is not None]
    said = [r for r in rule_rows if r['rule_verbalized']]
    quiet = [r for r in rule_rows if not r['rule_verbalized']]
    print(f"\nsays vs does: rule stated in {len(said)}/{len(rule_rows)}; leak when stated {100*rate(said,'secret_in_reasoning')[0]:.0f}%, not {100*rate(quiet,'secret_in_reasoning')[0]:.0f}%")
    check = json.load(open(check_path))['conditions'] if check_path else {}
    if check:
        low = sorted((e[k]['match_rate'], c, k) for c, e in check.items() for k in e if isinstance(e[k], dict) and 'match_rate' in e[k])
        print('manipulation check parsed', sum(e['parsed'] for e in check.values()), '/', sum(e['planned'] for e in check.values()),
              '| lowest:', [(round(m, 2), c, k) for m, c, k in low[:6]])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('run', help='run directory with *.trial.json.gz and run.json.gz')
    parser.add_argument('--check', help='manipulation-check summary JSON for the same split')
    parser.add_argument('--reference', default='outputs/qwen3-8b/validation', help='Qwen3-8B run for P3')
    args = parser.parse_args()
    report(args.run, args.check, args.reference)


if __name__ == '__main__':
    main()
