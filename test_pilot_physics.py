"""Independent checks of powered Schwarzschild motion and event handling."""
import math
import unittest

import numpy as np
from scipy.integrate import solve_ivp

import pilot_physics as p


def coordinate_reference(state, action, duration):
    """Full coordinate four-velocity ODE; no reduced-engine derivatives."""
    r, ur, angular, phi, consumed = state
    f = 1-2/r
    ut = math.sqrt((1+ur*ur/f+angular*angular/r/r)/f)
    y = np.array([0., r, phi, ut, ur, angular/r/r, consumed])
    action = np.asarray(action, dtype=float)
    acceleration = p.MAX_ACCEL*action/max(1., np.linalg.norm(action))

    def derivative(t, y, acceleration):
        r, U = y[1], y[3:6]
        f = 1-2/r
        # Construct connection directly from metric partial derivatives.
        inverse = np.diag([-1/f, f, 1/r/r])
        partial = np.zeros((3, 3, 3))
        partial[1] = np.diag([-2/r/r, -2/r/r/f/f, 2*r])
        connection = np.zeros((3, 3, 3))
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    connection[i, j, k] = sum(
                        .5*inverse[i, l]*(partial[j, l, k]
                            + partial[k, l, j]-partial[l, j, k])
                        for l in range(3))
        h = math.sqrt(f)
        spatial = np.array([U[1]/h, r*U[2]])
        temporal = h*U[0]
        work = spatial @ acceleration
        boosted = acceleration+spatial*work/(temporal+1)
        force = np.array([work/h, h*boosted[0], boosted[1]/r])
        change = -np.einsum('ijk,j,k->i', connection, U, U)+force
        return np.r_[U, change, np.linalg.norm(acceleration)]

    burn = min(duration, max(0., p.Q_MAX-consumed)/np.linalg.norm(acceleration)) \
        if np.linalg.norm(acceleration) else 0.
    time = 0.
    normalization_error = 0.
    for interval, force in ((burn, acceleration), (duration-burn, np.zeros(2))):
        if interval == 0:
            continue
        def safety(t, y):
            return y[1]-p.SAFETY_RADIUS
        safety.terminal, safety.direction = True, -1
        sol = solve_ivp(lambda t, y: derivative(t, y, force), (0, interval), y,
                        method='DOP853', rtol=2e-12, atol=2e-13,
                        max_step=.1, events=safety)
        if not sol.success:
            raise AssertionError(sol.message)
        rr, U = sol.y[1], sol.y[3:6]
        ff = 1-2/rr
        norms = -ff*U[0]**2+U[1]**2/ff+rr**2*U[2]**2
        normalization_error = max(normalization_error, np.max(np.abs(norms+1)))
        y = sol.y[:, -1]
        time += sol.t[-1]
        if len(sol.t_events[0]):
            break
    reduced = np.array([y[1], y[4], y[1]**2*y[5], y[2], y[6]])
    return reduced, time, normalization_error


class PoweredPhysicsTests(unittest.TestCase):
    def test_zero_thrust_conserves_energy_and_angular_momentum(self):
        state = p.initial_state(9.48933112, 1.0256853698390396, 3.52593741)
        initial = p.energy(state)
        final, info = p.advance(state, [0, 0], dt=100, return_info=True)
        self.assertEqual(info['status'], 'safety_cutoff')
        self.assertAlmostEqual(p.energy(final), initial, delta=2e-9)
        self.assertEqual(final[2], state[2])

    def test_circular_geodesic(self):
        r = 8.
        state = np.array([r, 0., r/math.sqrt(r-3), 0., p.Q_MAX])
        final = p.advance(state, [1, 1], dt=60)
        np.testing.assert_allclose(final[:3], state[:3], atol=2e-12)
        self.assertAlmostEqual(final[3], 60*state[2]/r/r, places=11)

    def test_independent_full_coordinate_reference(self):
        for radius, E, L, action, duration in (
            (12., 1.03, 4.2, [.8, .3], 12.),
            (9., 1.06, 3.7, [-.4, .7], 16.),
            (6., 1.05, 1., [-.3, .2], 20.),
            (20., 1.015, 4.4, [.2, -.9], 12.)):
            with self.subTest(radius=radius):
                state = p.initial_state(radius, E, L)
                reference, elapsed, normalization = coordinate_reference(state, action, duration)
                actual, info = p.advance(state, action, duration, return_info=True)
                np.testing.assert_allclose(actual, reference, rtol=0, atol=2e-8)
                self.assertAlmostEqual(info['dt_used'], elapsed, delta=2e-8)
                self.assertLess(normalization, 2e-9)

    def test_proper_acceleration_and_work_identity(self):
        rng = np.random.default_rng(20261004)
        for _ in range(100):
            state = np.array([rng.uniform(2.11, 19), rng.uniform(-2, .2),
                              rng.uniform(-8, 8), 0., 0.])
            action = rng.uniform(-2, 2, 2)
            a = p.MAX_ACCEL*action/max(1., np.linalg.norm(action))
            r, ur, L = state[:3]
            h = math.sqrt(1-2/r)
            E = p.energy(state)
            w, gamma = np.array([ur/h, L/r]), E/h
            A0 = w @ a
            Avec = a+w*A0/(gamma+1)
            self.assertAlmostEqual(-gamma*A0+w @ Avec, 0., delta=3e-14)
            self.assertAlmostEqual(-A0*A0+Avec @ Avec, a @ a, delta=3e-14)
            rates = p.rhs(state, action)
            energy_rate = (ur*rates[1]+ur*(1+(L/r)**2)/r**2
                           +(1-2/r)*L*rates[2]/r**2
                           -(1-2/r)*L*L*ur/r**3)/E
            self.assertAlmostEqual(energy_rate, ur*a[0]+h*L/r*a[1], delta=2e-14)
            self.assertLessEqual(rates[4], p.MAX_ACCEL+1e-16)

    def test_fuel_exhaustion_matches_independent_split(self):
        state = p.initial_state(12, 1.03, 4.2)
        state[4] = p.Q_MAX-p.MAX_ACCEL*.37
        reference, _, _ = coordinate_reference(state, [1, 0], 2.)
        actual = p.advance(state, [1, 0], 2.)
        planned = p.step(state, [1, 0], 2., substeps=16)
        np.testing.assert_allclose(actual, reference, atol=2e-10, rtol=0)
        np.testing.assert_allclose(planned, reference, atol=2e-9, rtol=0)
        self.assertEqual(actual[4], p.Q_MAX)
        self.assertEqual(planned[4], p.Q_MAX)
        self.assertEqual(float(p.fuel_fraction(p.Q_MAX)), 0.)
        self.assertEqual(float(p.fuel_fraction(0)), 1.)
        self.assertTrue(np.all(np.diff(p.fuel_fraction(np.linspace(0, p.Q_MAX, 100))) < 0))

    def test_rk4_refinement(self):
        state = p.initial_state(6, 1.06, 3.7)
        action = [-.4, .7]
        reference = p.advance(state, action, 2., rtol=1e-12)
        errors = [np.max(np.abs(p.step(state, action, 2., substeps=n)-reference))
                  for n in (2, 4, 8, 16)]
        self.assertTrue(all(a > 10*b for a, b in zip(errors, errors[1:])), errors)
        self.assertLess(errors[-1], 1e-7)

    def test_terminal_events_freeze_and_track_elapsed_fuel(self):
        state = np.array([2.2, -2., 0., 0., 0.])
        final, info = p.advance(state, [1, 0], 2., return_info=True)
        self.assertEqual(info['status'], 'safety_cutoff')
        self.assertLess(info['dt_used'], .1)
        self.assertEqual(final[0], p.SAFETY_RADIUS)
        self.assertAlmostEqual(final[4], p.MAX_ACCEL*info['dt_used'], places=12)
        np.testing.assert_array_equal(p.step(final, [1, 0]), final)
        np.testing.assert_array_equal(p.advance(final, [1, 0]), final)
        planned = p.step(state, [1, 0], substeps=8)
        self.assertEqual(p.status(planned), 'safety_cutoff')
        self.assertGreaterEqual(planned[0], p.SAFETY_RADIUS)
        self.assertLess(abs(planned[4]-final[4]), 2e-7)

    def test_escape_event_and_terminal_freeze(self):
        state = np.array([19.9, .6, 4., 0., 0.])
        final, info = p.advance(state, [0, 0], return_info=True)
        self.assertEqual(info['status'], 'escaped')
        self.assertLess(info['dt_used'], 2)
        self.assertGreaterEqual(final[0], p.ESCAPE_RADIUS)
        np.testing.assert_array_equal(p.step(final, [-1, 1]), final)
        np.testing.assert_array_equal(p.advance(final, [-1, 1]), final)
        self.assertEqual(p.status([20.1, -.6, 4, 0, 0]), 'flying')
        self.assertEqual(p.status([20.1, .01, 4, 0, 0]), 'flying')

    def test_batch_broadcast_matches_scalar_and_handles_empty_fuel(self):
        state = p.initial_state(12, 1.03, 4.2)
        states = np.tile(state, (2, 3, 1))
        states[..., 4] = [[0., p.Q_MAX-.01295, p.Q_MAX]]
        actions = np.array([[1., 0.], [0., 1.], [-1., 1.]])
        actual = p.step(states, actions)
        self.assertEqual(actual.shape, (2, 3, 5))
        for i in range(2):
            for j in range(3):
                np.testing.assert_array_equal(actual[i, j], p.step(states[i, j], actions[j]))
        np.testing.assert_array_equal(p.step(state, actions)[0], p.step(state, actions[0]))
        np.testing.assert_array_equal(actual[0, 2], p.step(states[0, 2], [0, 0]))

    def test_escape_turnaround_cannot_stall_at_zero_time(self):
        final, info = p.advance([21., -.01, 10., 0., 0.], [0, 0], return_info=True)
        self.assertEqual(info['status'], 'escaped')
        self.assertGreater(info['dt_used'], 1.)
        self.assertGreater(final[1], 0.)
        repeated, repeated_info = p.advance(final, [0, 0], return_info=True)
        np.testing.assert_array_equal(repeated, final)
        self.assertEqual(repeated_info['status'], 'escaped')

    def test_invalid_inputs(self):
        state = p.initial_state(12, 1.03, 4.2)
        for bad in ([2, 0, 0, 0, 0], [3, 0, 0, 0, np.nan], [3, 0, 0, 0, 1]):
            with self.assertRaises(ValueError):
                p.energy(bad)
        for action in ([1, 2, 3], [np.inf, 0]):
            with self.assertRaises(ValueError):
                p.step(state, action)
        for dt in (0, -1, float('nan')):
            with self.assertRaises(ValueError):
                p.advance(state, [0, 0], dt)
        with self.assertRaises(ValueError):
            p.initial_state(12, .1, 4.2)


if __name__ == '__main__':
    unittest.main()
