"""Numerical checks for unpowered Schwarzschild flight."""

import json
import unittest

import numpy as np

import physics


class PhysicsTests(unittest.TestCase):
    def test_potential_arrays_and_derivative(self):
        radius = np.array([2.01, 4.0, 10.0, 30.0])
        momentum = np.array([0.0, 4.0, -4.0, 6.0])
        expected = (1 - 2 / radius) * (1 + momentum**2 / radius**2)
        np.testing.assert_allclose(physics.potential(radius, momentum), expected)
        step = 1e-5
        difference = (physics.potential(radius + step, momentum)
                      - physics.potential(radius - step, momentum)) / (2 * step)
        np.testing.assert_allclose(physics.potential_derivative(radius, momentum),
                                   difference, rtol=1e-7, atol=1e-10)

    def test_polynomial_oracle_matches_critical_sides(self):
        self.assertEqual(physics.critical_angular_momentum(1.0), 4.0)
        # At large E the capture boundary approaches the photon impact parameter.
        high = physics.critical_angular_momentum(np.array([1e7, 1e8]))
        np.testing.assert_allclose(high / [1e7, 1e8], np.sqrt(27), rtol=1e-12)
        self.assertEqual(physics.outcome(1.0, 4.0), "unresolved")
        self.assertEqual(physics.outcome(1.1, 0), "capture")
        for energy in [1.0, 1.002, 1.03, 1.2, 2.0, 10.0]:
            boundary = float(physics.critical_angular_momentum(energy))
            self.assertEqual(physics.outcome(energy, boundary), "unresolved")
            for fraction, expected in [(0.9999, "capture"), (1.0001, "escape")]:
                self.assertEqual(physics.outcome(energy, boundary * fraction), expected)
                self.assertEqual(physics.outcome(energy, -boundary * fraction), expected)
        # The same forbidden barrier captures a launch on its inner allowed side.
        self.assertEqual(physics.outcome(1.0, 5.0, r0=2.1), "capture")

    def test_invalid_launch_and_controls(self):
        for energy, momentum, radius in [(0.9, 4, 30), (np.nan, 4, 30),
                                          (1, np.inf, 30), (1, 4, 2),
                                          (1, 10, 30), (1, 4, 4)]:
            with self.subTest(E=energy, L=momentum, r0=radius):
                with self.assertRaises(ValueError):
                    physics.outcome(energy, momentum, radius)
                with self.assertRaises(ValueError):
                    physics.trace(energy, momentum, r0=radius)
        with self.assertRaises(ValueError):
            physics.trace(1.1, 4, max_points=1)

    def test_integrated_outcomes_and_energy(self):
        for energy, momentum in [(1.0, 0), (1.002, 3.9), (1.02, 4.5),
                                  (1.2, 6.3), (1.2, -6.3)]:
            with self.subTest(E=energy, L=momentum):
                result = physics.trace(energy, momentum, max_points=250)
                self.assertEqual(result["outcome"], physics.outcome(energy, momentum))
                self.assertLess(result["energy_drift"], 1e-7)
                self.assertLessEqual(len(result["points"]), 250)
                self.assertEqual(result["points"][0], [0.0, 30.0, 0.0])
                self.assertGreater(result["points"][-1][0], 0)
                end_radius = 2.001 if result["outcome"] == "capture" else 30
                self.assertAlmostEqual(result["points"][-1][1], end_radius, places=8)
                json.dumps(result, allow_nan=False)
        self.assertEqual(physics.trace(1.0, 4.0)["outcome"], "unresolved")
        self.assertEqual(physics.trace(1.0, 0, max_time=0.01)["outcome"], "unresolved")

    def test_tolerance_convergence(self):
        for momentum in [4.2, 4.4]:
            loose = physics.trace(1.02, momentum, rtol=1e-7, max_points=200)
            tight = physics.trace(1.02, momentum, rtol=1e-11, max_points=200)
            self.assertEqual(loose["outcome"], tight["outcome"])
            np.testing.assert_allclose(loose["points"], tight["points"],
                                       rtol=1e-6, atol=1e-5)
            self.assertLess(tight["energy_drift"], 1e-9)

    def test_learned_world_uses_same_initial_velocity(self):
        # A constant shift changes conserved energy but cannot change the orbit.
        shifted = lambda r, L: physics.potential(r, L) + 0.2
        exact = physics.trace(1.02, 4.5, max_points=150)
        learned = physics.trace(1.02, 4.5, potential_fn=shifted,
                                derivative_fn=physics.potential_derivative,
                                max_points=150)
        self.assertEqual(learned["outcome"], exact["outcome"])
        np.testing.assert_allclose(learned["points"], exact["points"], atol=1e-10)
        self.assertAlmostEqual(learned["diagnostics"]["conserved_energy"], 1.02**2 + 0.2)
        self.assertLess(learned["energy_drift"], 1e-7)
        self.assertLess(learned["diagnostics"]["exact_energy_drift"], 1e-7)


if __name__ == "__main__":
    unittest.main()
