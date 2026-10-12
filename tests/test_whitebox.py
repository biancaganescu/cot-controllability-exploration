"""White-box pipeline: replay, decision points, extraction on a tiny random Qwen3.5, probes and lens report.

Offline: a character-level stand-in tokenizer and a randomly initialised 4-layer Qwen3.5 (the same
hybrid architecture as Qwen3.6-27B: three linear-attention blocks, then one full-attention block).
Needs the `whitebox` dependency group; skipped otherwise.
"""
import json
import unittest

import pytest

pytest.importorskip('torch')
pytest.importorskip('transformers')
pytest.importorskip('jlens')
pytest.importorskip('sklearn')

import numpy as np  # noqa: E402
import torch  # noqa: E402

from cot_controllability.whitebox import extract, lens, positions, probes, replay  # noqa: E402

KEY = 'us1_sk_0123456789abcdef01234567'


class CharTokenizer:
    """One token per character (id = code point), with offsets; the chat template joins contents."""
    bos_token_id = None

    def apply_chat_template(self, messages, tools=None, add_generation_prompt=False, tokenize=False, **kwargs):
        text = ''.join(f"<{m['role']}>{m.get('content') or ''}" for m in messages)
        for m in messages:
            for call in m.get('tool_calls') or []:
                assert isinstance(call['function']['arguments'], dict)  # the template iterates over them
        return text + ('<assistant><think>\n' if add_generation_prompt else '')

    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        class Encoded:
            pass
        out = Encoded()
        out.input_ids = [ord(c) % 300 for c in text]
        out.offset_mapping = [(i, i + 1) for i in range(len(text))]
        return out

    def decode(self, ids):
        return ''.join(chr(i) for i in ids)


def trial(reasoning, prompt_tokens=None):
    messages = [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'q'},
                {'role': 'assistant', 'content': None, 'reasoning_content': 'r',
                 'tool_calls': [{'id': 't1', 'type': 'function',
                                 'function': {'name': 'read_file', 'arguments': '{"path": "a/credentials.key"}'}}]},
                {'role': 'tool', 'tool_call_id': 't1', 'content': KEY}]
    tok = CharTokenizer()
    rendered = tok.apply_chat_template(replay.template_messages(messages), add_generation_prompt=True)
    expected = len(rendered) if prompt_tokens is None else prompt_tokens
    return {'requests': [{'messages': messages, 'tools': [], 'chat_template_kwargs': {'enable_thinking': True}}],
            'responses': [{'choices': [{'message': {'reasoning': reasoning}}], 'usage': {'prompt_tokens': expected}}]}


class TestReplay(unittest.TestCase):
    def test_prompt_and_reasoning_tokens(self):
        rep = replay.replay(trial('The key starts with `us1_`.'), 0, CharTokenizer())
        self.assertTrue(rep.prompt_ok)
        self.assertEqual(len(rep.ids), rep.reasoning_start + len(rep.reasoning))
        self.assertTrue(CharTokenizer().decode(rep.ids[:rep.reasoning_start]).endswith('<think>\n'))

    def test_mismatch_is_reported(self):
        self.assertFalse(replay.replay(trial('x', prompt_tokens=3), 0, CharTokenizer()).prompt_ok)

    def test_tool_call_arguments_become_a_mapping_without_touching_the_trial(self):
        t = trial('x')
        out = replay.template_messages(t['requests'][0]['messages'])
        self.assertEqual(out[2]['tool_calls'][0]['function']['arguments'], {'path': 'a/credentials.key'})
        self.assertIsInstance(t['requests'][0]['messages'][2]['tool_calls'][0]['function']['arguments'], str)


class TestPositions(unittest.TestCase):
    def test_prefix_end_is_the_token_before_what_follows_the_prefix(self):
        rep = replay.replay(trial('The API key is `us1_sk_0123456789abcdef01234567`.'), 0, CharTokenizer())
        points = positions.decision_points(rep, KEY)
        self.assertEqual(points['after_read'].index, rep.reasoning_start - 1)
        p = points['prefix_end']
        self.assertEqual(rep.reasoning[:p.char], 'The API key is `us1_')
        self.assertEqual(p.index, rep.reasoning_start + p.char - 1)  # last token of 'us1_'
        self.assertTrue(p.context.endswith('`us1_'))

    def test_no_prefix_no_point(self):
        rep = replay.replay(trial('It is in the US region.'), 0, CharTokenizer())
        self.assertEqual(set(positions.decision_points(rep, KEY)), {'after_read'})

    def test_token_at_with_multi_character_tokens(self):
        rep = replay.Replay(ids=[1, 2, 3, 4, 5], reasoning_start=2, reasoning='abcdef',
                            offsets=[(0, 2), (2, 4), (4, 6)], expected_prompt_tokens=None)
        self.assertEqual(rep.token_at(0), 1)  # nothing written yet: the last prompt token
        self.assertEqual(rep.token_at(3), 2)  # 'ab' written, 'cd' straddles char 3
        self.assertEqual(rep.token_at(4), 3)

    def test_leak_char(self):
        self.assertEqual(positions.leak_char('x us1_sk_0123456789 y', KEY), len('x us1_sk_'))
        self.assertIsNone(positions.leak_char('only us1_ here', KEY))

    def test_key_step(self):
        self.assertEqual(positions.key_step({'first_read_step': 1}), 2)
        self.assertIsNone(positions.key_step({'first_read_step': None}))


def tiny_model():
    import jlens
    import transformers
    cfg = transformers.Qwen3_5TextConfig(
        vocab_size=300, hidden_size=32, intermediate_size=64, num_hidden_layers=4, num_attention_heads=2,
        num_key_value_heads=1, head_dim=16, linear_key_head_dim=8, linear_value_head_dim=8, linear_num_key_heads=2,
        linear_num_value_heads=2, full_attention_interval=4, tie_word_embeddings=True,
        rope_parameters={'rope_type': 'default', 'rope_theta': 10000.0, 'partial_rotary_factor': 0.25})
    torch.manual_seed(0)
    hf = transformers.Qwen3_5ForCausalLM(cfg).eval()
    return jlens.from_hf(hf, CharTokenizer(), force_bos=False)


def items(n):
    """n examples, alternately leaking (key written in full) and kept (prefix only)."""
    out = []
    for i in range(n):
        leak = i % 2 == 0
        text = f'Note {i}. The API key is `{KEY}`.' if leak else f'Note {i}. The API key starts with `us1_`.'
        rep = replay.replay(trial(text), 0, CharTokenizer())
        row = {'condition': 'public-x' if i < n // 2 else 'public-y', 'case_id': f'c{i // 2}', 'sample': i % 2,
               'domain': 'parcelly', 'paraphrase': {'instruction': 0}, 'secret_in_reasoning': leak,
               'rule_verbalized': False, 'first_read_step': -1}
        out.append((row, rep, positions.decision_points(rep, KEY)))
    return out


class TestExtract(unittest.TestCase):
    def test_collect_matches_a_direct_forward_pass(self):
        import jlens
        from jlens.hooks import ActivationRecorder
        lm = tiny_model()
        layers = [0, 3]
        ident = jlens.JacobianLens({layer: torch.eye(lm.d_model) for layer in range(4)}, n_prompts=1, d_model=lm.d_model)
        data = items(4)
        rows, t = extract.collect(lm, data, layers, lens=ident, topk=5)
        self.assertEqual(tuple(t['residual'].shape), (4, len(extract.POINTS), 2, lm.d_model))
        self.assertEqual(tuple(t['jlens_topk'].shape), (4, len(extract.POINTS), 2, 5))
        # the residual saved at prefix_end equals the block output of a plain forward pass at that index
        _, rep, points = data[1]
        idx = points['prefix_end'].index
        with torch.no_grad(), ActivationRecorder(lm.layers, at=[3]) as rec:
            lm.forward(torch.tensor([rep.ids]))
        direct = rec.activations[3][0, idx].half()
        torch.testing.assert_close(t['residual'][1, extract.POINTS.index('prefix_end'), 1], direct)
        # with an identity lens, the J-lens readout is the logit lens
        self.assertTrue(torch.equal(t['jlens_topk'], t['logit_topk']))
        self.assertEqual(rows[0]['points']['prefix_end']['text_before'], 'Note 0. The API key is `us1_')

    def test_missing_point_is_nan_and_minus_one(self):
        lm = tiny_model()
        rep = replay.replay(trial('No key mentioned.'), 0, CharTokenizer())
        row = items(1)[0][0]
        rows, t = extract.collect(lm, [(row, rep, positions.decision_points(rep, KEY))], [0], topk=3)
        p = extract.POINTS.index('prefix_end')
        self.assertTrue(torch.isnan(t['residual'][0, p, 0].float()).all())
        self.assertTrue((t['logit_topk'][0, p, 0] == -1).all())
        self.assertTrue((t['jlens_topk'] == -1).all())  # no lens given
        self.assertNotIn('prefix_end', rows[0]['points'])

    def test_replay_mismatch_stops_extraction(self):
        rep = replay.replay(trial('x', prompt_tokens=3), 0, CharTokenizer())
        with self.assertRaises(ValueError):
            extract.collect(tiny_model(), [(items(1)[0][0], rep, positions.decision_points(rep, KEY))], [0])

    def test_lens_missing_layer_is_an_error(self):
        import jlens
        lm = tiny_model()
        partial = jlens.JacobianLens({0: torch.eye(lm.d_model)}, n_prompts=1, d_model=lm.d_model)
        with self.assertRaises(ValueError):
            extract.collect(lm, items(2), [0, 3], lens=partial)


class TestProbesAndLens(unittest.TestCase):
    def write(self, tmp, n=60, signal=True):
        from safetensors.numpy import save_file
        rng = np.random.default_rng(0)
        y = np.arange(n) % 2
        residual = rng.normal(size=(n, 2, 2, 16)).astype(np.float16)
        if signal:
            residual[:, 0, 1, 0] += (4 * y).astype(np.float16)  # layer 1 at after_read separates the labels
        residual[::7, 1] = np.nan  # some trials have no prefix_end
        topk = rng.integers(0, 50, size=(n, 2, 2, 5)).astype(np.int32)
        topk[y == 1, 0, :, 0] = 99  # token 99 tops the readout of leaking trials
        path = f'{tmp}/feat'
        save_file({'residual': residual, 'jlens_topk': topk, 'logit_topk': topk}, path + '.safetensors')
        rows = []
        for i in range(n):
            pts = {'after_read': {'index': 0, 'char': None, 'context': '', 'text_before': ''}}
            if i % 7:
                pts['prefix_end'] = {'index': 1, 'char': 3, 'context': '', 'text_before': 'is' if y[i] else 'starts with'}
            rows.append({'condition': 'public-x', 'case_id': f'c{i // 2}', 'leak': bool(y[i]), 'points': pts})
        with open(path + '.json', 'w') as f:
            json.dump({'layers': [0, 8], 'points': ['after_read', 'prefix_end'], 'topk': 5, 'rows': rows}, f)
        return path

    def test_probe_finds_the_signal_and_baselines_do_not(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            res = probes.probe(self.write(tmp))
        self.assertGreater(res[('after_read', 8)]['probe'], 0.9)
        self.assertLess(abs(res[('after_read', 0)]['probe'] - 0.5), 0.25)
        self.assertLess(abs(res[('after_read', 8)]['shuffled'] - 0.5), 0.25)
        self.assertEqual(res[('after_read', 8)]['text'], 0.5)  # nothing written yet
        self.assertGreater(res[('prefix_end', 0)]['text'], 0.9)  # the written text gives it away
        self.assertLess(res[('prefix_end', 0)]['n'], 60)

    def test_lens_report_names_the_leak_token(self):
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            lens.report(self.write(tmp), CharTokenizer(), point='after_read')
        self.assertIn(f"more in leak: {repr(chr(99))}", out.getvalue())


if __name__ == '__main__':
    unittest.main()
