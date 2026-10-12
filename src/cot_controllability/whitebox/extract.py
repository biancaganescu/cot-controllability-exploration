"""Residual-stream activations and lens readouts at the decision points of a black-box run.

For every scored trial whose key file was read: replay the step after the read, run one forward pass
up to the last decision point, and keep, at each point and each chosen layer,
- the residual (block output), for probes;
- the top-k tokens of the Jacobian lens (J_l @ h, then the model's final norm and unembedding) and
  of the plain logit lens, for reading what the activation is disposed to make the model say.

jlens.HFLensModel finds the decoder blocks, final norm and unembedding; jlens' own `apply()` is not
used because it re-tokenizes a string and truncates at 512 tokens.

Output (`save`): <out>.safetensors (residual [N, P, L, d] float16 with NaN where a point is missing; jlens_topk
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


def collect(lm, items, layers, lens=None, topk=20):
    """Run each (row, Replay, points) of `items` through `lm` (a jlens LensModel) and read the residual and
    the lens top-k at every point and layer. Returns (rows, tensors) as `save` writes them."""
    import torch
    from jlens.hooks import ActivationRecorder

    if lens is not None:
        missing = set(layers) - set(lens.source_layers)
        if missing:
            raise ValueError(f'lens has no layers {sorted(missing)}')
        # transport() moves J to the residual's device on every call; move the used layers once
        lens.jacobians = {layer: lens.jacobians[layer].to(lm.input_device) for layer in layers}
    rows, residuals, jl, ll = [], [], [], []
    nan = torch.full((lm.d_model,), float('nan'), dtype=torch.float16)
    none = torch.full((topk,), -1, dtype=torch.int32)

    def top(h):
        return lm.unembed(h).topk(topk).indices[0].int().cpu()

    for row, rep, points in items:
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
                hs = {layer: acts[layer][p.index:p.index + 1].float() for layer in layers} if p else {}
                res.append([hs[layer][0].half().cpu() if p else nan for layer in layers])
                ltop.append([top(hs[layer]) if p else none for layer in layers])
                jtop.append([top(lens.transport(hs[layer], layer)) if p and lens else none for layer in layers])
        residuals.append(torch.stack([torch.stack(r) for r in res]))
        ll.append(torch.stack([torch.stack(t) for t in ltop]))
        jl.append(torch.stack([torch.stack(t) for t in jtop]))
        rows.append(meta(row, rep, points, key_step(row)))
        if len(rows) % 50 == 0:
            print(f'[{len(rows)}] {row["condition"]} {row["case_id"]} s{row["sample"]}', flush=True)
    if not rows:
        raise ValueError('no trials to extract')
    return rows, {'residual': torch.stack(residuals), 'jlens_topk': torch.stack(jl), 'logit_topk': torch.stack(ll)}


def save(out, rows, tensors, **info):
    from safetensors.torch import save_file

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_file(tensors, str(out) + '.safetensors')
    Path(str(out) + '.json').write_text(json.dumps({'canary': sf.CANARY, **info, 'points': list(POINTS), 'rows': rows}, indent=1))
    print(f"wrote {len(rows)} examples x {len(POINTS)} points x {len(info['layers'])} layers to {out}.{{safetensors,json}}")


def extract(run, model_name, out, layers=None, lens_path=None, conditions=None, limit=None, topk=20,
            dtype='bfloat16', tokenizer_name=None):
    """`tokenizer_name` (default: the model's) renders the chat template: it must be the one vLLM used for
    the run, e.g. Qwen3.6-27B's when a smaller model of the family replays Qwen3.6-27B's trajectories."""
    import jlens
    import torch
    import transformers

    tokenizer = transformers.AutoTokenizer.from_pretrained(tokenizer_name or model_name)
    # device_map='auto' spreads the model over the GPUs; on a laptop it picks MPS, where loading segfaults
    device_map = 'auto' if torch.cuda.is_available() else 'cpu'
    hf = transformers.AutoModelForCausalLM.from_pretrained(model_name, dtype=getattr(torch, dtype), device_map=device_map)
    lm = jlens.from_hf(hf, tokenizer, force_bos=False)  # chat-template ids already carry what the model saw
    layers = sorted(layers) if layers else sorted(set(range(0, lm.n_layers, 4)) | {lm.n_layers - 1})
    lens = load_lens(lens_path, jlens) if lens_path else None
    rows, tensors = collect(lm, examples(run, tokenizer, conditions, limit), layers, lens, topk)
    save(out, rows, tensors, run=str(run), model=model_name, tokenizer=tokenizer_name or model_name,
         lens=lens_path, layers=layers, topk=topk)
