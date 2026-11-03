"""What the residual is disposed to make the model say, at each decision point: Jacobian-lens top-k
tokens, split into attempts that leak and attempts that do not.

For each layer, the tokens that appear in the top-k most often in one group relative to the other
(counts per 100 attempts, add-one smoothed ratio). A readout, not a causal claim: J-lens shows an
average linear disposition; whether a token's direction matters needs an intervention.
"""
from __future__ import annotations

from collections import Counter

from cot_controllability.whitebox.probes import load


def counts(topk, rows):
    c = Counter()
    for i in rows:
        c.update({int(t) for t in topk[i] if t >= 0})
    return c


def report(path, tokenizer, point='after_read', conditions=None, layers=None, kind='jlens', top=8):
    tensors, info = load(path)
    p = info['points'].index(point)
    keep = [i for i, r in enumerate(info['rows']) if (not conditions or r['condition'] in conditions)
            and point in r['points']]
    leak = [i for i in keep if info['rows'][i]['leak']]
    kept = [i for i in keep if not info['rows'][i]['leak']]
    topk = tensors[f'{kind}_topk']
    if (topk[keep] < 0).all():
        print(f'no {kind} readouts in {path}')
        return
    print(f"{path}: {kind} top-{info['topk']} at {point}; {len(leak)} leak, {len(kept)} kept "
          f"({', '.join(conditions) if conditions else 'all conditions'})")
    dec = lambda t: repr(tokenizer.decode([t]))  # noqa: E731
    for li, layer in enumerate(info['layers']):
        if layers and layer not in layers:
            continue
        a, b = counts(topk[:, p, li], leak), counts(topk[:, p, li], kept)
        na, nb = max(1, len(leak)), max(1, len(kept))
        ratio = {t: ((a[t] + 1) / (na + 1)) / ((b[t] + 1) / (nb + 1)) for t in set(a) | set(b)}
        more_leak = sorted(ratio, key=lambda t: -ratio[t])[:top]
        more_kept = sorted(ratio, key=lambda t: ratio[t])[:top]
        common = [t for t, _ in (a + b).most_common(top)]
        print(f'\n  layer {layer}')
        print('    most common: ' + ', '.join(dec(t) for t in common))
        print('    more in leak: ' + ', '.join(f'{dec(t)} {100 * a[t] / na:.0f}/{100 * b[t] / nb:.0f}' for t in more_leak))
        print('    more in kept: ' + ', '.join(f'{dec(t)} {100 * a[t] / na:.0f}/{100 * b[t] / nb:.0f}' for t in more_kept))
