"""Independent derivative, barrier, launch, and fitted-basis cross-checks."""
import json
import unittest

import numpy as np

import physics
from run_controls import (ENERGY, EPSILONS, ROOT, WIDTH, basis_control,
                          bump, controlled_world, selective_policy_control)
from world_model import analytic_margin


class ControlTests(unittest.TestCase):
    def test_bump_derivative_support_and_exact_suprema(self):
        center = 3.7
        radius = center + WIDTH * np.array([-1.1, -1., -.8, -.3, 0., .3, .8, 1., 1.1])
        value, derivative = bump(radius, center)
        step = 1e-6
        finite_difference = (bump(radius + step, center)[0]
                             - bump(radius - step, center)[0]) / (2 * step)
        np.testing.assert_allclose(derivative, finite_difference, rtol=1e-8, atol=2e-10)
        self.assertEqual(bump(center, center)[0], 1.)
        self.assertEqual(bump(30., center)[0], 0.)
        np.testing.assert_array_equal(value[[0, 1, 7, 8]], 0.)
        np.testing.assert_array_equal(derivative[[0, 1, 7, 8]], 0.)
        # Critical points of |q'| occur at |z|=1/sqrt(5), by differentiation.
        peak = center + WIDTH / np.sqrt(5)
        self.assertAlmostEqual(abs(bump(peak, center)[1]) / 2,
                               48 / (25 * np.sqrt(5) * WIDTH), places=13)
        # q, q', q'' vanish at either support endpoint, so the zero extension is C2.
        for z in (-1., 1.):
            self.assertEqual(-6 * (1 - z*z) * (1 - 5*z*z) / WIDTH**2, 0.)

    def test_constructive_barrier_and_polynomial_oracle(self):
        for epsilon in EPSILONS:
            momentum, center, potential, derivative = controlled_world(float(epsilon))
            self.assertAlmostEqual(float(analytic_margin(ENERGY, momentum)), -epsilon / 2, delta=3e-15)
            self.assertAlmostEqual(float(potential(center, momentum) - ENERGY**2), epsilon / 2, delta=3e-15)
            self.assertAlmostEqual(float(derivative(center, momentum)), 0., delta=1e-15)
            self.assertEqual(float(potential(30., momentum)), float(physics.potential(30., momentum)))
            self.assertEqual(physics.outcome(ENERGY, momentum), 'capture')
            self.assertLess(center + WIDTH, 30.)
            self.assertGreater(center - WIDTH, physics.CAPTURE_RADIUS)
            # A dense check supplements the analytic maximum proof; it is not a certificate.
            radii = np.r_[np.linspace(physics.CAPTURE_RADIUS, 30., 3000), center]
            self.assertLessEqual(float(np.max(potential(radii, momentum))),
                                 float(potential(center, momentum)) + 1e-14)
        momentum, _, potential, derivative = controlled_world(1e-5)
        exact = physics.trace(ENERGY, momentum, rtol=1e-13, max_points=300)
        model = physics.trace(ENERGY, momentum, potential_fn=potential,
                              derivative_fn=derivative, rtol=1e-13, max_points=300)
        self.assertEqual(exact['outcome'], 'capture')
        self.assertEqual(model['outcome'], 'escape')
        self.assertLess(model['energy_drift'], 1e-5 / 200)

    def test_privileged_basis_on_all_frozen_launches(self):
        result = basis_control()
        self.assertEqual(result['rank'], 4)
        np.testing.assert_allclose(result['coefficients'], [1., -2., 1., -2.], rtol=0, atol=2e-14)
        self.assertLess(result['validation_max_error'], 1e-13)
        for distribution in result['distributions'].values():
            self.assertEqual(distribution['count'], 2000)
            self.assertEqual(distribution['agreements'], 2000)
            self.assertEqual(distribution['false_escapes'], 0)
            self.assertEqual(distribution['false_captures'], 0)

    def test_saved_gauge_and_tolerance_controls(self):
        source = ROOT / 'results/controls.json'
        if not source.exists():
            self.skipTest('Run run_controls.py to generate control artifacts.')
        data = json.loads(source.read_text())
        self.assertEqual(data['protocol_status'], 'posthoc after frozen neural experiment')
        self.assertEqual(len(data['perturbation']), 6)
        for row in data['perturbation']:
            self.assertEqual(row['numerical_status'], 'confirmed')
            self.assertEqual([run['rtol'] for run in row['traces']], [1e-11, 1e-13])
            for run in row['traces']:
                self.assertEqual(run['physical']['outcome'], 'capture')
                self.assertEqual(run['perturbed']['outcome'], 'escape')
                self.assertLess(run['physical']['energy_drift'], row['epsilon'] / 200)
                self.assertLess(run['perturbed']['energy_drift'], row['epsilon'] / 200)
        for row in data['gauge']:
            self.assertAlmostEqual(row['physical_margin'], row['shifted_margin'], places=14)
            self.assertEqual(row['physical']['outcome'], row['shifted']['outcome'])
            self.assertEqual(row['acceleration_sup_error'], 0.)
            self.assertEqual(row['max_point_difference'], 0.)

    def test_selective_policy_has_measured_cost_and_rejects_showcase(self):
        result = selective_policy_control()
        self.assertFalse(result['certificate'])
        self.assertTrue(result['showcase']['flagged_uncertain'])
        self.assertFalse(result['showcase']['accepted_by_selective_policy'])
        self.assertEqual(len(result['models']), 10)
        for groups in result['models'].values():
            for score in groups.values():
                self.assertEqual(score['false_escapes'], 0)
                self.assertEqual(score['accepted_unresolved_truth'], 0)
                self.assertEqual(score['accepted'], score['accepted_true_escapes'])
                self.assertLessEqual(score['accepted'], score['true_escapes'])
            self.assertGreater(groups['stress']['missed_true_escapes'], 0)
        self.assertAlmostEqual(result['mean_coverage_by_architecture']['small']['stress'], .1676)
        self.assertAlmostEqual(result['mean_coverage_by_architecture']['large']['stress'], .1576)


if __name__ == '__main__':
    unittest.main()
