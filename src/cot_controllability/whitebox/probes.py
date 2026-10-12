"""W2: can a linear probe tell, before the key is written, that it will be?

Per decision point and layer: logistic regression on the residual, label = the trial leaks; 5-fold
cross-validation grouped by customer (no customer in both train and test), AUC from the held-out
predictions. Baselines on the same folds:
- shuffled labels (the probe's chance level with this many dimensions and examples);
- text: the same classifier on character n-grams of the reasoning written before the point (at
  `after_read` nothing is written yet, so it is chance). A probe is interesting only where it beats
  the text, i.e. where the activation holds more than what the model already wrote.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def load(path):
    from safetensors.numpy import load_file
    return load_file(f'{path}.safetensors'), json.loads(Path(f'{path}.json').read_text())


def cv_auc(X, y, groups, folds=5, seed=0, C=0.01):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if len(set(y)) < 2 or len(set(groups)) < folds:
        return None
    proba = np.zeros(len(y))
    for train, test in GroupKFold(n_splits=folds).split(X, y, groups):
        if len(set(y[train])) < 2:
            return None
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000, random_state=seed))
        clf.fit(X[train], y[train])
        proba[test] = clf.predict_proba(X[test])[:, 1]
    return roc_auc_score(y, proba)


def text_features(texts):
    from sklearn.feature_extraction.text import TfidfVectorizer
    if not any(texts):
        return None
    return TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 5), min_df=2).fit_transform(texts).toarray()


def probe(path, conditions=None, shuffles=3):
    """{(point, layer): {'n', 'leaks', 'probe', 'shuffled', 'text'}} for the rows of `conditions`."""
    tensors, info = load(path)
    keep = [i for i, r in enumerate(info['rows']) if not conditions or r['condition'] in conditions]
    out = {}
    for p, point in enumerate(info['points']):
        rows = [i for i in keep if point in info['rows'][i]['points']]
        if not rows:
            continue
        y = np.array([info['rows'][i]['leak'] for i in rows], dtype=int)
        groups = np.array([info['rows'][i]['case_id'] for i in rows])
        texts = [info['rows'][i]['points'][point]['text_before'] for i in rows]
        Xt = text_features(texts)
        text_auc = cv_auc(Xt, y, groups) if Xt is not None else 0.5
        rng = np.random.default_rng(0)
        for li, layer in enumerate(info['layers']):
            X = tensors['residual'][rows, p, li].astype(np.float32)
            shuffled = [cv_auc(X, rng.permutation(y), groups) for _ in range(shuffles)]
            shuffled = [s for s in shuffled if s is not None]
            out[(point, layer)] = {'n': len(rows), 'leaks': int(y.sum()), 'probe': cv_auc(X, y, groups),
                                   'shuffled': float(np.mean(shuffled)) if shuffled else None, 'text': text_auc}
    return out


def report(path, conditions=None):
    res = probe(path, conditions)
    print(f"{path}: {', '.join(conditions) if conditions else 'all conditions'}")
    print(f"{'point':<12} {'layer':>5} {'n':>5} {'leaks':>6} {'probe AUC':>10} {'shuffled':>9} {'text':>6}")
    fmt = lambda v: '-' if v is None else f'{v:.3f}'  # noqa: E731
    for (point, layer), r in res.items():
        print(f"{point:<12} {layer:>5} {r['n']:>5} {r['leaks']:>6} {fmt(r['probe']):>10} {fmt(r['shuffled']):>9} {fmt(r['text']):>6}")
    return res
