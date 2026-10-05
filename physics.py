"""Equatorial timelike Schwarzschild geodesics, in units G=c=M=1.

Flights start inward at r0. Capture stops at r=2.001, outside the horizon.
The polynomial oracle and numerical integrator use separate calculations.
"""

import math

import numpy as np
from scipy.integrate import solve_ivp


CAPTURE_RADIUS = 2.001


def potential(r, L):
    """Return the effective potential; inputs support NumPy broadcasting."""
    r, L = np.asarray(r, dtype=float), np.asarray(L, dtype=float)
    return (1 - 2 / r) * (1 + L**2 / r**2)


def potential_derivative(r, L):
    """Return dV/dr, so radial acceleration is -dV/dr / 2."""
    r, L = np.asarray(r, dtype=float), np.asarray(L, dtype=float)
    return 2 / r**2 - 2 * L**2 / r**3 + 6 * L**2 / r**4


def critical_angular_momentum(E):
    """Return the positive capture boundary for finite energy E >= 1."""
    E = np.asarray(E, dtype=float)
    if np.any(~np.isfinite(E)) or np.any(E < 1):
        raise ValueError("energy must be finite and at least 1")
    delta = (E - 1) * (E + 1)
    root = np.hypot(1 - 3 * delta, 4 * np.sqrt(delta))
    # The second form avoids cancellation for large energies.
    radius = np.empty_like(delta)
    small = delta <= 1
    radius[small] = 8 / (root[small] + 1 - 3 * delta[small])
    radius[~small] = 1.5 + (root[~small] - 1) / (2 * delta[~small])
    # Equivalent to r/sqrt(r-3), without subtracting nearly equal numbers.
    return radius * np.sqrt((delta + 2 / radius) / (1 - 2 / radius))


def _initial_state(E, L, r0):
    E, L, r0 = float(E), float(L), float(r0)
    if not all(math.isfinite(value) for value in (E, L, r0)):
        raise ValueError("energy, angular momentum, and radius must be finite")
    if E < 1 or r0 <= 2:
        raise ValueError("energy must be at least 1 and launch radius must exceed 2")
    radial_squared = E * E - float(potential(r0, L))
    if not math.isfinite(radial_squared):
        raise ValueError("launch exceeds floating-point range")
    if radial_squared < 0:
        raise ValueError("launch is forbidden: E squared is below the initial potential")
    if radial_squared == 0:
        raise ValueError("launch must be strictly inward; initial radial speed is zero")
    return E, L, r0, -math.sqrt(radial_squared)


def outcome(E, L, r0=30):
    """Classify an inward launch using its radial turning polynomial.

    P(r) = (E^2 - 1)r^3 + 2r^2 - L^2 r + 2L^2.
    A negative minimum outside the horizon separates the two allowed branches.
    Equality within roundoff is unresolved, rather than a claim of escape.
    """
    E, L, r0, _ = _initial_state(E, L, r0)
    delta, momentum_squared = (E - 1) * (E + 1), L * L
    radius = 2 * momentum_squared / (math.sqrt(16 + 12 * delta * momentum_squared) + 4)
    if radius <= 2:
        return "capture"
    terms = (delta * radius**3, 2 * radius**2,
             -momentum_squared * radius, 2 * momentum_squared)
    minimum = math.fsum(terms)
    tolerance = 64 * np.finfo(float).eps * sum(abs(term) for term in terms)
    if abs(minimum) <= tolerance:
        return "unresolved"
    return "escape" if minimum < 0 and r0 > radius else "capture"


def trace(E, L, potential_fn=None, derivative_fn=None, r0=30,
          rtol=1e-9, max_time=2000, max_points=700):
    """Integrate the same physical launch through an exact or learned potential.

    energy_drift is the maximum absolute error in v^2 + V, relative to launch.
    For a learned world, exact_energy_drift separately measures physical error.
    A timeout or ambiguous exact boundary always remains unresolved.
    """
    E, L, r0, velocity = _initial_state(E, L, r0)
    if not math.isfinite(rtol) or rtol < 100 * np.finfo(float).eps:
        raise ValueError("rtol must be finite and at least 100 times machine epsilon")
    if not math.isfinite(max_time) or max_time <= 0:
        raise ValueError("max_time must be finite and positive")
    if not isinstance(max_points, (int, np.integer)) or max_points < 2:
        raise ValueError("max_points must be an integer of at least 2")
    exact_world = potential_fn is None and derivative_fn is None
    selected_potential = potential_fn or potential
    selected_derivative = derivative_fn or potential_derivative
    conserved_energy = velocity**2 + float(selected_potential(r0, L))
    if not math.isfinite(conserved_energy):
        raise ValueError("initial model potential must be finite")

    def equations(tau, state):
        radius, radial_velocity, _ = state
        acceleration = -0.5 * float(selected_derivative(radius, L))
        if not math.isfinite(acceleration):
            raise ValueError("model derivative must be finite")
        return radial_velocity, acceleration, L / radius**2

    def capture(tau, state):
        return state[0] - CAPTURE_RADIUS

    def escape(tau, state):
        return state[0] - r0

    def turning(tau, state):
        return state[1]

    capture.terminal, capture.direction = True, -1
    escape.terminal, escape.direction = True, 1
    turning.direction = 1
    if r0 <= CAPTURE_RADIUS:
        return {"outcome": "capture", "points": [[0.0, r0, 0.0]],
                "energy_drift": 0.0,
                "diagnostics": {"exact_energy_drift": 0.0, "turning_radius": None,
                                "steps": 0, "cutoff": CAPTURE_RADIUS,
                                "escape_radius": r0, "terminal_time": 0.0,
                                "conserved_energy": conserved_energy,
                                "initial_radial_velocity": velocity,
                                "message": "launch is inside the numerical capture surface"}}
    solution = solve_ivp(equations, (0, max_time), [r0, velocity, 0.0],
                         method="DOP853", rtol=rtol, atol=rtol * 0.01,
                         max_step=2.0, dense_output=True,
                         events=(capture, escape, turning))
    label = "unresolved"
    if solution.success:
        if len(solution.t_events[0]):
            label = "capture"
        elif len(solution.t_events[1]):
            label = "escape"
    if exact_world and outcome(E, L, r0) == "unresolved":
        label = "unresolved"
    sample_times = np.linspace(0, solution.t[-1], max_points)
    turning_radius = None
    if len(solution.t_events[2]):
        turning_time = solution.t_events[2][0]
        turning_radius = float(solution.y_events[2][0][0])
        if max_points > 2:
            nearest = np.argmin(abs(sample_times[1:-1] - turning_time)) + 1
            sample_times[nearest] = turning_time
            sample_times.sort()
    states = solution.sol(sample_times)
    check_states = np.concatenate((solution.y, states), axis=1)
    radii, velocities = check_states[:2]
    model_energy = velocities**2 + selected_potential(radii, L)
    exact_energy = velocities**2 + potential(radii, L)
    drift = float(np.max(np.abs(model_energy - conserved_energy)))
    exact_drift = float(np.max(np.abs(exact_energy - E * E)))
    if not math.isfinite(drift) or not math.isfinite(exact_drift):
        raise ValueError("model trajectory produced nonfinite energy")
    return {"outcome": label,
            "points": np.column_stack((sample_times, states[0], states[2])).tolist(),
            "energy_drift": drift,
            "diagnostics": {"exact_energy_drift": exact_drift,
                            "turning_radius": turning_radius,
                            "steps": int(len(solution.t) - 1), "cutoff": CAPTURE_RADIUS,
                            "escape_radius": r0, "terminal_time": float(solution.t[-1]),
                            "conserved_energy": conserved_energy,
                            "initial_radial_velocity": velocity,
                            "evaluations": int(solution.nfev),
                            "integration_success": bool(solution.success),
                            "message": solution.message}}
