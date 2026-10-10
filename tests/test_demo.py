"""Offline checks for the small demo; all API responses are synthetic mocks."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cot_controllability import demo

DUMMY_KEY = 'offline-demo-test-key-not-a-credential'


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = demo.load_demo()
        cls.case = cls.data['cases'][0]
        cls.profile = cls.data['model_profile']

    def response(self, *, case=None, reasoning='Use the supplied prefix.', content=None,
                 finish='stop', **extra_message):
        case = case or self.case
        message = {'role': 'assistant', 'content': content if content is not None else json.dumps({'region': case['region']})}
        if reasoning is not None:
            message['reasoning'] = reasoning
        message.update(extra_message)
        return {'model': self.profile['model'], 'provider': self.profile['provider_name'],
                'choices': [{'message': message, 'finish_reason': finish}],
                'usage': {'cost': .00001, 'completion_tokens_details': {'reasoning_tokens': 8}}}

    def metadata(self):
        return {'model': {}, 'endpoint': {}, 'estimated_max_usd': .4,
                'price_caps_per_million': {'prompt': .5, 'completion': 2.}}

    def test_ten_balanced_examples_and_fresh_requests(self):
        self.assertEqual(len(self.data['cases']), 10)
        self.assertEqual([c['region'] for c in self.data['cases']], ['Europe', 'America'] * 5)
        bodies = [demo.request_for(self.data, c) for c in self.data['cases']]
        for case, body in zip(self.data['cases'], bodies):
            self.assertEqual([m['role'] for m in body['messages']], ['user'])
            self.assertEqual(body['messages'][0]['content'].count(case['token']), 1)
            for other in self.data['cases']:
                if other['id'] != case['id']:
                    self.assertNotIn(other['token'], body['messages'][0]['content'])
            self.assertFalse(body['provider']['allow_fallbacks'])
        bodies[0]['messages'].append({'role': 'assistant', 'content': 'test-only mutation'})
        self.assertEqual(len(bodies[1]['messages']), 1)
        self.assertEqual(len(demo.request_for(self.data, self.case)['messages']), 1)

    def test_missing_truncated_encrypted_and_conflicting_negatives_unknown(self):
        scenarios = [self.response(reasoning=None), self.response(finish='length'),
                     self.response(reasoning=None, reasoning_details=[{'type': 'reasoning.encrypted', 'data': 'opaque'}]),
                     self.response(reasoning_content='A different native representation.')]
        for raw in scenarios:
            with self.subTest(raw=raw):
                score = demo.score_response(raw, self.case, self.profile)
                self.assertIsNone(score['token_in_reasoning'])
                self.assertIsNone(score['literal_absence_and_correct'])
                self.assertFalse(score['reasoning_eligible_for_absence'])

    def test_observed_positives_survive_truncation_and_alternative_native_fields(self):
        token = self.case['token']
        for raw in [self.response(reasoning=token, finish='length'),
                    self.response(reasoning_content=token),
                    self.response(reasoning=None, reasoning_details=[{'type': 'reasoning.text', 'text': token}])]:
            with self.subTest(raw=raw):
                result = demo.score_response(raw, self.case, self.profile)
                self.assertIs(result['token_in_reasoning'], True)
                self.assertIs(result['literal_absence_and_correct'], False)
        wrong = self.response(reasoning=token)
        wrong['provider'] = 'a different provider'
        self.assertIsNone(demo.score_response(wrong, self.case, self.profile)['token_in_reasoning'])

    def test_malformed_response_envelopes_are_unknown(self):
        scenarios = [None, [], 'not an object', {}, {'choices': []},
                     self.response(tool_calls={}), self.response(tool_calls=''),
                     self.response(tool_calls=[{'id': 'unexpected'}]),
                     self.response(role='user')]
        for raw in scenarios:
            with self.subTest(raw=raw):
                score = demo.score_response(raw, self.case, self.profile)
                self.assertFalse(score['complete'])
                self.assertIsNone(score['token_in_reasoning'])
                self.assertIsNone(score['answer_correct'])

    def test_accuracy_strict_json_duplicates_and_visible_final_leak(self):
        answer = json.dumps({'region': self.case['region']})
        good = demo.score_response(self.response(content=answer), self.case, self.profile)
        self.assertTrue(good['answer_correct']); self.assertTrue(good['strict_json'])
        prose = demo.score_response(self.response(content='The result is ' + answer), self.case, self.profile)
        self.assertTrue(prose['answer_correct']); self.assertFalse(prose['strict_json'])
        duplicate = '{"region":"' + self.case['region'] + '","region":"' + self.case['region'] + '"}'
        for content in [duplicate, answer + ' ' + answer, 'unparseable response']:
            result = demo.score_response(self.response(content=content), self.case, self.profile)
            self.assertIsNone(result['answer_correct'])
            self.assertFalse(result['strict_json'])
        leaked = demo.score_response(self.response(content=self.case['token'] + ' ' + answer), self.case, self.profile)
        self.assertTrue(leaked['answer_correct']); self.assertTrue(leaked['token_in_final'])
        self.assertFalse(leaked['literal_absence_and_correct'])

    def test_missing_trials_remain_in_planned_denominator(self):
        row = demo.score_response(self.response(), self.case, self.profile)
        summary = demo.summarize([row], 2)
        self.assertEqual(summary['not_received'], 1)
        self.assertEqual(summary['answer_correct'], {'yes': 1, 'no': 0, 'unknown': 1, 'rate_among_known': 1.})
        self.assertEqual(summary['token_in_reasoning']['unknown'], 1)
        self.assertEqual(summary['token_in_reasoning']['no'], 1)

    def test_show_is_offline_and_run_requires_explicit_budget(self):
        with patch.object(demo, 'api_json', side_effect=AssertionError('show must be offline')), redirect_stdout(io.StringIO()):
            self.assertEqual(demo.main(['show']), 0)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                demo.main(['run', '--out', 'unused'])

    def test_budget_rejection_precedes_inference_and_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as parent, patch.dict(demo.os.environ, {'OPENROUTER_API_KEY': DUMMY_KEY}), patch.object(demo, 'preflight', return_value=self.metadata()), patch.object(demo, 'api_json', side_effect=AssertionError('inference forbidden')):
            output = Path(parent) / 'new'
            args = argparse.Namespace(limit=2, budget_usd=.1, out=output)
            with self.assertRaisesRegex(ValueError, 'estimate exceeds'):
                demo.run(args)
            self.assertFalse(output.exists())
            output.mkdir()
            args.budget_usd = 1.
            with self.assertRaisesRegex(ValueError, 'already exists'):
                demo.run(args)

    def test_successful_run_has_exact_case_requests_dynamic_price_cap_and_no_key_logs(self):
        sent = []
        def api(path, body=None, key=None):
            self.assertEqual(path, 'chat/completions')
            self.assertEqual(key, DUMMY_KEY)
            index = len(sent); sent.append(deepcopy(body))
            return self.response(case=self.data['cases'][index])
        with tempfile.TemporaryDirectory() as parent, patch.dict(demo.os.environ, {'OPENROUTER_API_KEY': DUMMY_KEY}), patch.object(demo, 'preflight', return_value=self.metadata()), patch.object(demo, 'api_json', side_effect=api), redirect_stdout(io.StringIO()):
            output = Path(parent) / 'run'
            demo.run(argparse.Namespace(limit=2, budget_usd=1., out=output))
            self.assertEqual(len(sent), 2)
            for index, body in enumerate(sent):
                expected = demo.request_for(self.data, self.data['cases'][index])
                expected['provider']['max_price'] = self.metadata()['price_caps_per_million']
                self.assertEqual(body, expected)
                self.assertEqual([m['role'] for m in body['messages']], ['user'])
            scores = demo.score_run(output)
            self.assertEqual(scores['summary']['received'], 2)
            for path in output.glob('*.json.gz'):
                self.assertNotIn(DUMMY_KEY, json.dumps(demo.read_data(path)))

    def test_transport_failure_is_recorded_as_attempt_without_retry_or_next_case(self):
        with tempfile.TemporaryDirectory() as parent, patch.dict(demo.os.environ, {'OPENROUTER_API_KEY': DUMMY_KEY}), patch.object(demo, 'preflight', return_value=self.metadata()), patch.object(demo, 'api_json', side_effect=RuntimeError('mock unavailable')) as api, redirect_stdout(io.StringIO()):
            output = Path(parent) / 'run'
            with self.assertRaises(RuntimeError):
                demo.run(argparse.Namespace(limit=2, budget_usd=1., out=output))
            self.assertEqual(api.call_count, 1)
            self.assertEqual(len(list(output.glob('*.request.json.gz'))), 1)
            self.assertFalse(list(output.glob('*.response.json.gz')))
            summary = demo.score_run(output)['summary']
            self.assertEqual(summary['not_received'], 2)
            self.assertEqual(summary['token_in_reasoning']['unknown'], 2)

    def test_truncated_response_stops_before_next_case_but_preserves_positive(self):
        raw = self.response(reasoning=self.case['token'], finish='length')
        with tempfile.TemporaryDirectory() as parent, patch.dict(demo.os.environ, {'OPENROUTER_API_KEY': DUMMY_KEY}), patch.object(demo, 'preflight', return_value=self.metadata()), patch.object(demo, 'api_json', return_value=raw) as api, redirect_stdout(io.StringIO()):
            output = Path(parent) / 'run'
            with self.assertRaisesRegex(RuntimeError, 'incomplete response'):
                demo.run(argparse.Namespace(limit=2, budget_usd=1., out=output))
            self.assertEqual(api.call_count, 1)
            summary = demo.score_run(output)['summary']
            self.assertEqual(summary['received'], 1)
            self.assertEqual(summary['token_in_reasoning']['yes'], 1)
            self.assertEqual(summary['token_in_reasoning']['unknown'], 1)

    def test_unpack_writes_readable_copies_of_file_and_directory(self):
        with tempfile.TemporaryDirectory() as parent:
            parent = Path(parent)
            demo.save(parent / 'a.json.gz', {'value': 'é'})
            demo.save(parent / 'b.json.gz', {'value': 2})
            self.assertEqual(demo.unpack(parent / 'a.json.gz'), [(parent / 'a.json', True)])
            self.assertIn('é', (parent / 'a.json').read_text(encoding='utf-8'))
            # Existing up-to-date copy is kept; only the missing one is written.
            self.assertEqual(demo.unpack(parent), [(parent / 'a.json', False), (parent / 'b.json', True)])
            self.assertEqual(json.loads((parent / 'b.json').read_text())['value'], 2)
            self.assertTrue((parent / 'a.json.gz').exists())
            # A newer source (e.g. after a pull) refreshes the stale copy.
            demo.os.utime(parent / 'b.json', (0, 0))
            self.assertEqual(demo.unpack(parent / 'b.json.gz'), [(parent / 'b.json', True)])
            self.assertGreater((parent / 'b.json').stat().st_mtime, 0)
            with self.assertRaises(ValueError):
                demo.unpack(parent / 'a.json')
            (parent / 'missing-canary.json.gz').write_bytes(demo.gzip.compress(b'{}'))
            with self.assertRaisesRegex(ValueError, 'canary'):
                demo.unpack(parent / 'missing-canary.json.gz')
            (parent / 'empty').mkdir()
            with self.assertRaisesRegex(ValueError, 'No .json.gz'):
                demo.unpack(parent / 'empty')

    def test_preflight_validates_pin_effort_prices_and_completion_limit(self):
        profile = self.profile
        model = {'id': profile['model'], 'canonical_slug': profile['canonical_slug'], 'reasoning': {'supported_efforts': [profile['effort']]}}
        endpoint = {'tag': profile['provider_tag'], 'provider_name': profile['provider_name'], 'status': 0,
                    'quantization': profile['quantisation'], 'supported_parameters': ['reasoning', 'reasoning_effort', 'max_tokens'],
                    'max_completion_tokens': profile['max_tokens'], 'pricing': {'prompt': '.000001', 'completion': '.000002'}}
        def check(m, e):
            with patch.object(demo, 'api_json', side_effect=[{'data': [m]}, {'data': {'endpoints': [e]}}]):
                return demo.preflight(self.data, self.data['cases'][:2])
        self.assertGreater(check(model, endpoint)['estimated_max_usd'], 0)
        changes = [('provider_name', 'different'), ('quantization', 'bf16'), ('max_completion_tokens', 1), ('supported_parameters', ['max_tokens'])]
        for key, value in changes:
            changed = deepcopy(endpoint); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                check(model, changed)
        changed = deepcopy(model); changed['canonical_slug'] = 'different'
        with self.assertRaises(ValueError): check(changed, endpoint)
        changed = deepcopy(model); changed['reasoning']['supported_efforts'] = []
        with self.assertRaises(ValueError): check(changed, endpoint)
        changed = deepcopy(endpoint); changed['pricing']['completion'] = 'NaN'
        with self.assertRaises(ValueError): check(model, changed)


if __name__ == '__main__':
    unittest.main()
