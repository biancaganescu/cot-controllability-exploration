"""cot-whitebox: replay a black-box run through HF transformers and read the residual stream.

    cot-whitebox check   outputs/qwen3.6-27b/v2/main                  # tokenizer only: replay matches vLLM?
    cot-whitebox extract outputs/qwen3.6-27b/v2/main --out outputs/whitebox/v2-main \\
        --lens solarkyle/jspace-lenses:Qwen3.6-27B/lens.pt           # GPU: residuals + lens top-k
    cot-whitebox probe   outputs/whitebox/v2-main --conditions public-intrinsic_channel
    cot-whitebox lens    outputs/whitebox/v2-main --point prefix_end --conditions public-intrinsic_channel
"""
from __future__ import annotations

import argparse
from collections import Counter

MODEL = 'Qwen/Qwen3.6-27B'


def layer_list(spec):
    """'0:64:4' -> range, '3,7,63' -> list."""
    if ':' in spec:
        return list(range(*map(int, spec.split(':'))))
    return [int(x) for x in spec.split(',')]


def check(args):
    from transformers import AutoTokenizer

    from cot_controllability.whitebox.extract import examples
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    n, bad, points, leak_at = 0, [], Counter(), Counter()
    for row, rep, pts in examples(args.run, tokenizer, args.conditions, args.limit):
        n += 1
        if not rep.prompt_ok:
            bad.append(f"{row['condition']} {row['case_id']} s{row['sample']}: {rep.reasoning_start} vs {rep.expected_prompt_tokens}")
        points.update(pts.keys())
        if 'prefix_end' in pts:
            leak_at[(row['secret_in_reasoning'], 'quotes rule' if 'starting with' in pts['prefix_end'].context else 'key')] += 1
    print(f'{n} replays; prompt tokens match vLLM in {n - len(bad)}')
    for b in bad[:10]:
        print('  MISMATCH', b)
    print('points found: ' + ', '.join(f'{k} {v}' for k, v in points.items()))
    print('prefix_end by (leak, first mention): ' + ', '.join(f'{k} {v}' for k, v in sorted(leak_at.items())))
    return 1 if bad else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='cot-whitebox', description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'extract'):
        p = sub.add_parser(name)
        p.add_argument('run', help='black-box run directory (scored trials)')
        p.add_argument('--model', default=MODEL)
        p.add_argument('--conditions', nargs='*')
        p.add_argument('--limit', type=int)
    sub.choices['extract'].add_argument('--out', required=True, help='output path without suffix')
    sub.choices['extract'].add_argument('--layers', type=layer_list, help="e.g. '0:64:4' or '15,31,63' (default every 4th + last)")
    sub.choices['extract'].add_argument('--lens', help="lens file or 'repo_id:path/lens.pt'")
    sub.choices['extract'].add_argument('--topk', type=int, default=20)
    p = sub.add_parser('probe')
    p.add_argument('features', help='extract output path without suffix')
    p.add_argument('--conditions', nargs='*')
    p = sub.add_parser('lens')
    p.add_argument('features')
    p.add_argument('--model', default=MODEL, help='for the tokenizer')
    p.add_argument('--point', default='after_read')
    p.add_argument('--conditions', nargs='*')
    p.add_argument('--layers', type=layer_list)
    p.add_argument('--kind', choices=('jlens', 'logit'), default='jlens')
    args = parser.parse_args(argv)

    if args.command == 'check':
        return check(args)
    if args.command == 'extract':
        from cot_controllability.whitebox.extract import extract
        extract(args.run, args.model, args.out, args.layers, args.lens, args.conditions, args.limit, args.topk)
    elif args.command == 'probe':
        from cot_controllability.whitebox.probes import report
        report(args.features, args.conditions)
    elif args.command == 'lens':
        from transformers import AutoTokenizer

        from cot_controllability.whitebox.lens import report
        report(args.features, AutoTokenizer.from_pretrained(args.model), args.point, args.conditions, args.layers, args.kind)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
