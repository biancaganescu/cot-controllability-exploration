"""Residual-stream activations and lens readouts at the decision points of a black-box run.

For every scored trial whose key file was read: replay the step after the read, run one forward pass
up to the last decision point, and keep, at each point and each chosen layer,
- the residual (block output), for probes;
- the top-k tokens of the Jacobian lens (J_l @ h, then the model's final norm and unembedding) and
  of the plain logit lens, for reading what the activation is disposed to make the model say.

jlens.HFLensModel finds the decoder blocks, final norm and unembedding; jlens' own `apply()` is not
used because it re-tokenizes a string and truncates at 512 tokens.

Output: <out>.safetensors (residual [N, P, L, d] float16 with NaN where a point is missing; jlens_topk
and logit_topk [N, P, L, k] int32, -1 where missing) and <out>.json (one row per trial: condition,
case, labels, points with their context; plus layers, points and the model).
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from cot_controllability.blackbox import secret_file as sf
from cot_controllability.whitebox.positions import decision_points, key_step
from cot_controllability.whitebox.replay import replay

POINTS = ('after_read', 'prefix_end')


def load_trial(run, row):
    with gzip.open(sf.trial_path(Path(run), row['condition'], row['case_id'], row['sample'])) as f:
        return json.load(f)


def keys_by_case(run):
    with gzip.open(Path(run) / 'run.json.gz') as f:
        return {c['id']: c['key'] for c in json.load(f)['cases']}


def examples(run, tokenizer, conditions=None, limit=None):
    """Yield (row, Replay, points) for the trials of `run` with a key read, in score order."""
    keys = keys_by_case(run)
    rows = [r for r in sf.score_run(run)['trials'] if r['item'] == 'secret'
            and (not conditions or r['condition'] in conditions) and key_step(r) is not None]
    for row in rows[:limit]:
        trial = load_trial(run, row)
        step = key_step(row)
        if step >= len(trial['requests']):
            continue  # answered right after the read without another reasoning step
        rep = replay(trial, step, tokenizer)
        yield row, rep, decision_points(rep, keys[row['case_id']])


def meta(row, rep, points, step):
    return {
        'condition': row['condition'], 'case_id': row['case_id'], 'sample': row['sample'],
        'domain': row.get('domain'), 'wording': row['paraphrase']['instruction'],
        'leak': bool(row['secret_in_reasoning']), 'rule': bool(row['rule_verbalized']),
        'step': step, 'prompt_ok': rep.prompt_ok, 'n_tokens': len(rep.ids),
        'points': {name: {'index': p.index, 'char': p.char, 'context': p.context,
                          'text_before': rep.reasoning[:p.char or 0]} for name, p in points.items()},
    }


def load_lens(spec, jlens):
    """A local lens file, or 'repo_id:path/in/repo/lens.pt' on the HF Hub."""
    if Path(spec).is_file():
        return jlens.JacobianLens.load(spec)
    repo, filename = spec.split(':', 1)
    return jlens.JacobianLens.from_pretrained(repo, filename=filename)


def extract(run, model_name, out, layers=None, lens_path=None, conditions=None, limit=None, topk=20,
            dtype='bfloat16'):
    import jlens
    import torch
    import transformers
    from jlens.hooks import ActivationRecorder
    from safetensors.torch import save_file

    tokenizer = transformers.AutoTokenizer.from_pretrained(model_name)
    hf = transformers.AutoModelForCausalLM.from_pretrained(model_name, dtype=getattr(torch, dtype), device_map='auto')
    lm = jlens.from_hf(hf, tokenizer, force_bos=False)  # chat-template ids already carry what the model saw
    layers = sorted(layers) if layers else list(range(0, lm.n_layers, 4)) + [lm.n_layers - 1]
    lens = load_lens(lens_path, jlens) if lens_path else None
    if lens is not None:
        missing = set(layers) - set(lens.source_layers)
        if missing:
            raise ValueError(f'lens has no layers {sorted(missing)}')

    rows, residuals, jl, ll = [], [], [], []
    nan = torch.full((lm.d_model,), float('nan'), dtype=torch.float16)
    none = torch.full((topk,), -1, dtype=torch.int32)
    for row, rep, points in examples(run, tokenizer, conditions, limit):
        if not rep.prompt_ok:
            raise ValueError(f"{row['condition']} {row['case_id']} s{row['sample']}: replayed prompt has "
                             f'{rep.reasoning_start} tokens, vLLM saw {rep.expected_prompt_tokens}')
        last = max(p.index for p in points.values())
        ids = torch.tensor([rep.ids[:last + 1]], device=lm.input_device)
        with torch.no_grad(), ActivationRecorder(lm.layers, at=layers) as rec:
            lm.forward(ids)
            acts = {layer: rec.activations[layer][0].detach() for layer in layers}
        res, jtop, ltop = [], [], []
        for name in POINTS:
            p = points.get(name)
            res.append([acts[layer][p.index].half().cpu() if p else nan for layer in layers])
            with torch.no_grad():
                ltop.append([lm.unembed(acts[layer][p.index:p.index + 1].float()).topk(topk).indices[0].int().cpu()
                             if p else none for layer in layers])
                jtop.append([lm.unembed(lens.transport(acts[layer][p.index:p.index + 1].float(), layer)).topk(topk)
                             .indices[0].int().cpu() if p and lens else none for layer in layers])
        residuals.append(torch.stack([torch.stack(r) for r in res]))
        ll.append(torch.stack([torch.stack(t) for t in ltop]))
        jl.append(torch.stack([torch.stack(t) for t in jtop]))
        rows.append(meta(row, rep, points, key_step(row)))
        if len(rows) % 50 == 0:
            print(f'[{len(rows)}] {row["condition"]} {row["case_id"]} s{row["sample"]}', flush=True)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_file({'residual': torch.stack(residuals), 'jlens_topk': torch.stack(jl), 'logit_topk': torch.stack(ll)},
              str(out.with_suffix('.safetensors')))
    out.with_suffix('.json').write_text(json.dumps({
        'canary': sf.CANARY, 'run': str(run), 'model': model_name, 'lens': lens_path, 'layers': layers,
        'points': list(POINTS), 'topk': topk, 'rows': rows}, indent=1))
    print(f'wrote {len(rows)} examples x {len(POINTS)} points x {len(layers)} layers to {out}.{{safetensors,json}}')
