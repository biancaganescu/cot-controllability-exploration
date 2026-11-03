"""Offline checks for the blind labelling CLI; keypresses are scripted."""
import json
import tempfile
import unittest
from pathlib import Path

from cot_controllability import label as lb


def items():
    return [{'id': f'cond-{i}/case-{i}/0', 'condition': f'cond-{i}', 'case_id': f'case-{i}', 'sample': 0,
             'secret': f'secret{i}' * 3, 'transcript': f'### Step 1\nReasoning:\nThe key is eu1_sk_{f"secret{i}" * 3}.\n'}
            for i in range(3)]


def keys(*presses):
    it = iter(presses)
    return lambda: next(it, 'q')


class LabelTests(unittest.TestCase):
    def run_loop(self, golden, presses, out):
        shown = []
        labels = lb.label_loop(golden, out, seed=1, get_key=keys(*presses), echo=shown.append, highlight=False)
        return labels, '\n'.join(shown)

    def test_answers_implied_fields_and_blindness(self):
        golden = items()
        with tempfile.TemporaryDirectory() as parent:
            out = Path(parent) / 'g.labels.jsonl'
            # Item A: rule stated, about the reply, full restated leak, no observer, no test.
            # Item B: no rule (channel implied), no key (leak kind implied).
            labels, shown = self.run_loop(golden, ['y', 'a', 'f', 'r', 'n', 'n', 'n', '0', 'n', 'n', 'q'], out)
            self.assertEqual(len(labels), 2)
            human = [r['human'] for r in labels.values()]
            self.assertIn({'rule_stated': 'yes', 'rule_channel': 'reply', 'key_mention': 'full', 'leak_kind': 'restate',
                           'observer_mentioned': 'no', 'eval_aware': 'no'}, human)
            self.assertIn({'rule_stated': 'no', 'rule_channel': 'none', 'key_mention': 'none', 'leak_kind': 'none',
                           'observer_mentioned': 'no', 'eval_aware': 'no'}, human)
            self.assertEqual(shown.count('Which output is that rule about?'), 1)  # Asked only once.
            for item in golden:
                self.assertNotIn(item['condition'], shown)
                self.assertNotIn(item['id'], shown)
            self.assertIn('⟦', shown)  # The secret is marked in the transcript.
            saved = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual({r['id'] for r in saved}, set(labels))

    def test_resume_and_undo_within_an_item(self):
        golden = items()
        with tempfile.TemporaryDirectory() as parent:
            out = Path(parent) / 'g.labels.jsonl'
            self.run_loop(golden, ['n', '0', 'n', 'n', 'q'], out)
            self.assertEqual(len(lb.read_jsonl(out)), 1)
            # Resume skips what is labelled; 'u' goes back one question inside the item.
            labels, _ = self.run_loop(golden, ['y', 'u', 'n', '0', 'y', 'n', 'q'], out)
            self.assertEqual(len(labels), 2)
            new = [r for r in labels.values() if r['human']['observer_mentioned'] == 'yes']
            self.assertEqual(new[0]['human']['rule_stated'], 'no')  # The 'y' was undone.
            # Undo history is per session: at the first question of a new session nothing to undo.
            labels, shown = self.run_loop(golden, ['u', 'q'], out)
            self.assertEqual(len(labels), 2)
            self.assertIn('nothing to undo', shown)

    def test_undo_reopens_the_previous_item_and_skip_moves_on(self):
        golden = items()
        with tempfile.TemporaryDirectory() as parent:
            out = Path(parent) / 'a.labels.jsonl'
            labels, _ = self.run_loop(golden, ['n', '0', 'n', 'n', 'u', 'y', 'b', 'f', 'm', 'n', 'n', 'q'], out)
            self.assertEqual(len(labels), 1)
            (only,) = labels.values()
            self.assertEqual((only['human']['rule_channel'], only['human']['leak_kind']), ('both', 'meta'))
            out = Path(parent) / 'b.labels.jsonl'
            labels, shown = self.run_loop(golden, ['s', 'n', '0', 'n', 'n', 'q'], out)
            first_shown = next(i for i in golden if i['secret'] in shown.split('[1/3]')[1])
            self.assertEqual(len(labels), 1)
            self.assertNotIn(first_shown['id'], labels)  # The skipped item was not the one labelled.

    def test_summary_and_paths(self):
        rows = [{'human': {f: v for f, *_ in lb.QUESTIONS for v in ['yes' if f.endswith(('stated', 'mentioned', 'aware')) else 'none']}}]
        self.assertEqual(lb.summarize(rows)['rule_stated'], {'yes': 1})
        self.assertEqual(lb.labels_path('data/golden/x.jsonl'), Path('data/golden/x.labels.jsonl'))
        self.assertTrue(all(set(choices).isdisjoint(lb.RESERVED) for _, _, choices in lb.QUESTIONS))


if __name__ == '__main__':
    unittest.main()
