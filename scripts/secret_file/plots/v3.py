"""Draw the v3 figures (docs/experiments/v3/figures/<stage>/*.png): plots/v2.py with v3's conditions.

The same six figures as v2 — leaks by condition, the contrasts against their predictions, leaks per
environment, knows vs does, rule timing and reading — over v3's nine conditions; B1-B4 replace A1-A2.

    uv run --group plots python scripts/secret_file/plots/v3.py outputs/qwen3.6-27b/v3/main \\
        --check outputs/qwen3.6-27b/v3/main-check --out docs/experiments/v3/figures/main
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location('plots_v2', Path(__file__).with_name('v2.py'))
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)

v2.ROWS = [('none', 'public-none'), ('intrinsic', 'public-intrinsic'), ('intrinsic + channel', 'public-intrinsic_channel'),
           ('intrinsic + emphasis', 'public-intrinsic_emphasis'), ('instructed', 'public-directive_reply'),
           ('instructed + consequence', 'public-directive_consequence'), ('instructed (output frame)', 'public-directive_output'),
           ('write_exact', 'public-write_exact'), ('read_exact', 'public-read_exact')]
v2.LABEL = {c: label for label, c in v2.ROWS}
v2.GROUPS = [('baseline', ['public-none']),
             ('intrinsic', ['public-intrinsic', 'public-intrinsic_channel', 'public-intrinsic_emphasis']),
             ('instructed', ['public-directive_reply', 'public-directive_consequence', 'public-directive_output']),
             ('concrete', ['public-write_exact', 'public-read_exact'])]
v2.CONTRASTS = [  # (label, a, b, predicted range of a - b); predictions as in docs/experiments/v3/plan.md
    ('B1: intrinsic + emphasis − intrinsic', 'public-intrinsic_emphasis', 'public-intrinsic', (0.0, 0.0)),
    ('    intrinsic + channel − intrinsic', 'public-intrinsic_channel', 'public-intrinsic', (0.0, 0.0)),
    ('B2: instructed + consequence − instructed', 'public-directive_consequence', 'public-directive_reply', (0.0, 0.0)),
    ('B3: output frame − instructed', 'public-directive_output', 'public-directive_reply', (0.0, 0.0)),
    ('B4: write_exact − instructed', 'public-write_exact', 'public-directive_reply', (0.0, 0.0)),
]
v2.READING = ('public-none', 'public-write_exact', 'public-read_exact')

if __name__ == '__main__':
    v2.main()
