"""Checks for exported inference, analytical derivatives, and launch predictions."""
import csv
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from world_model import WorldModel, export_model, load_model, analytic_prediction


class WorldModelTests(unittest.TestCase):
    def test_export_and_derivative(self):
        rng = np.random.default_rng(7)
        radius = rng.uniform(2.02, 30, 200)
        momentum = rng.uniform(3.5, 6.3, 200)
        x = np.column_stack((1 / radius, momentum))
        y = (1 - 2 / radius) * (1 + momentum**2 / radius**2)
        sx, sy = StandardScaler().fit(x), StandardScaler().fit(y[:, None])
        estimator = MLPRegressor(hidden_layer_sizes=(8, 8), activation='tanh',
                                 solver='lbfgs', max_iter=2000, random_state=7)
        estimator.fit(sx.transform(x), sy.transform(y[:, None]).ravel())
        payload = export_model(estimator, sx, sy, {'model_id': 'test'})
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'model.json'
            path.write_text(json.dumps(payload, allow_nan=False))
            model = load_model(path)
        expected = sy.inverse_transform(estimator.predict(sx.transform(x))[:, None]).ravel()
        np.testing.assert_allclose(model.potential(radius, momentum), expected, atol=1e-12)
        step = radius * 1e-5
        finite_difference = (model.potential(radius + step, momentum)
                             - model.potential(radius - step, momentum)) / (2 * step)
        np.testing.assert_allclose(model.derivative(radius, momentum), finite_difference,
                                   rtol=2e-6, atol=2e-8)
        self.assertIsInstance(model.potential(10., 4.), float)
        with self.assertRaises(ValueError):
            model.predict_outcome(1., 100.)

    def test_analytic_barrier(self):
        self.assertEqual(analytic_prediction(1.01, 3.5), 'capture')
        self.assertEqual(analytic_prediction(1.01, 6.3), 'escape')
        self.assertEqual(analytic_prediction(1., 4.), 'unresolved')
        from physics import outcome
        for energy in [1.002, 1.05, 1.2]:
            for momentum in np.linspace(3.5, 6.3, 11):
                self.assertEqual(analytic_prediction(energy, float(momentum)),
                                 outcome(energy, float(momentum)))

    def test_barrier_search(self):
        # This monotone tanh model has its maximum at the inner endpoint.
        model = WorldModel({'weights': [[[1., 0.], [0., 1.]], [[1.], [0.]]],
                            'biases': [[0., 0.], [0.]],
                            'feature_mean': [0., 0.], 'feature_scale': [1., 1.],
                            'target_mean': 0., 'target_scale': 1., 'metadata': {}})
        barrier = model.barrier(np.array([4., 5.]))
        np.testing.assert_allclose(barrier, model.potential(2.001, np.array([4., 5.])), atol=1e-9)
        from physics import potential
        from world_model import analytic_margin
        model.potential = potential
        momentum = np.linspace(3.5, 6.3, 101)
        np.testing.assert_allclose(model.barrier(momentum), analytic_margin(1., momentum) + 1, atol=1e-10)

    def test_saved_experiment_artifacts(self):
        root = Path(__file__).parent / 'results'
        if not (root / 'summary.json').exists():
            self.skipTest('Run the frozen experiment to create result artifacts.')
        summary = json.loads((root / 'summary.json').read_text())
        self.assertEqual(len(summary['model_metrics']), 10)
        self.assertEqual(len(summary['model_files']), 10)
        self.assertEqual(summary['protocol']['seeds'], [11, 22, 33, 44, 55])
        digest = hashlib.sha256((root / 'test_inputs.json').read_bytes()).hexdigest()
        self.assertEqual(summary['protocol']['test_sha256'], digest)
        def finite(value):
            if isinstance(value, dict):
                for item in value.values(): finite(item)
            elif isinstance(value, list):
                for item in value: finite(item)
            elif isinstance(value, float):
                self.assertTrue(math.isfinite(value))
        for path in root.rglob('*.json'):
            finite(json.loads(path.read_text()))
        with (root / 'trials.csv').open() as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 44000)
        for model_id in [*summary['model_files'], 'analytic']:
            model_rows = [row for row in rows if row['model_id'] == model_id]
            self.assertEqual(len(model_rows), 4000)
            for distribution in ('nominal', 'stress'):
                group = [row for row in model_rows if row['distribution'] == distribution]
                self.assertEqual(len(group), 2000)
                recorded = (summary['baseline'] if model_id == 'analytic' else
                            next(metric for metric in summary['model_metrics']
                                 if metric['model_id'] == model_id))['distributions'][distribution]
                self.assertEqual(recorded['false_escapes'], sum(row['prediction'] == 'escape'
                                                              and row['actual'] == 'capture' for row in group))
                self.assertEqual(recorded['gate_rejected'], sum(row['gate'] == 'rejected' for row in group))
                self.assertEqual(recorded['gate_accepted'], sum(row['gate'] == 'accepted' for row in group))
                self.assertFalse(any(row['gate'] == 'accepted' and row['actual'] != 'escape' for row in group))
        for seed in summary['protocol']['seeds']:
            with np.load(root / 'observations' / f'small-{seed}.npz') as small:
                with np.load(root / 'observations' / f'large-{seed}.npz') as large:
                    for key in small.files:
                        np.testing.assert_array_equal(small[key], large[key])
        witness = json.loads((root / 'showcase.json').read_text())
        self.assertEqual(witness['prediction'], witness['model_trace']['outcome'])
        self.assertEqual(witness['actual'], witness['true_trace']['outcome'])


if __name__ == '__main__':
    unittest.main()
