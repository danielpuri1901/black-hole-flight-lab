"""Powered equatorial Schwarzschild motion, G=c=M=1.

State: [r, u_r, L, phi, consumed proper impulse].
Actions: radial/tangential components in rotationless-boosted rest axes.
The safety surface is a mission cutoff, not the event horizon.
"""
import math

import numpy as np
from scipy.integrate import solve_ivp

MAX_ACCEL = .035
Q_MAX = .7
EXHAUST_SPEED = .7
SAFETY_RADIUS = 2.1
ESCAPE_RADIUS = 20.
ESCAPE_MARGIN = 1e-6


def _state(state):
    state = np.asarray(state, dtype=float)
    if state.ndim < 1 or state.shape[-1] != 5 or not np.all(np.isfinite(state)):
        raise ValueError("state must have five finite components")
    if np.any(state[..., 0] <= 2) or np.any(state[..., 4] < -1e-12) or np.any(state[..., 4] > Q_MAX + 1e-12):
        raise ValueError("state radius must exceed two and impulse must be within budget")
    return state


def energy(state):
    """Return positive Killing energy per instantaneous ship rest mass."""
    s = _state(state)
    r, u, L = s[..., 0], s[..., 1], s[..., 2]
    return np.hypot(u, np.sqrt(1-2/r)*np.hypot(1, L/r))


def fuel_fraction(q):
    """Return remaining propellant fraction, excluding the inferred dry mass."""
    q = np.asarray(q, dtype=float)
    if not np.all(np.isfinite(q)):
        raise ValueError("consumed impulse must be finite")
    # expm1 avoids subtracting almost equal wet and dry masses near exhaustion.
    return np.clip(np.expm1((Q_MAX-np.clip(q, 0, Q_MAX))/EXHAUST_SPEED)
                   / np.expm1(Q_MAX/EXHAUST_SPEED), 0, 1)


def initial_state(r, E, L):
    """Construct an inward launch, including zero radial speed when allowed."""
    r, E, L = float(r), float(E), float(L)
    if not all(math.isfinite(x) for x in (r, E, L)) or r <= SAFETY_RADIUS or E <= 0:
        raise ValueError("launch must be finite, outside the safety radius, with positive energy")
    rest = math.sqrt(1-2/r)*math.hypot(1, L/r)
    squared = (E-rest)*(E+rest)
    if squared < -1e-14 or not math.isfinite(squared):
        raise ValueError("launch energy is below its potential or exceeds numerical range")
    return np.array([r, -math.sqrt(max(0, squared)), L, 0., 0.])


def status(state):
    s = _state(state)
    labels = np.full(s.shape[:-1], "flying", dtype="<U13")
    escaped = (s[..., 0] >= ESCAPE_RADIUS) & (s[..., 1] > 0) & (energy(s) >= 1+ESCAPE_MARGIN)
    labels = np.where(escaped, "escaped", labels)
    labels = np.where(s[..., 0] <= SAFETY_RADIUS+1e-12, "safety_cutoff", labels)
    return str(labels.item()) if labels.ndim == 0 else labels


def _inputs(state, action):
    s, a = _state(state), np.asarray(action, dtype=float)
    if a.ndim < 1 or a.shape[-1] != 2 or not np.all(np.isfinite(a)):
        raise ValueError("action must have two finite components")
    shape = np.broadcast_shapes(s.shape[:-1], a.shape[:-1])
    s, a = np.broadcast_to(s, shape+(5,)), np.broadcast_to(a, shape+(2,))
    norm = np.hypot(a[..., 0], a[..., 1])
    if not np.all(np.isfinite(norm)):
        raise ValueError("action exceeds numerical range")
    a = MAX_ACCEL*a/np.maximum(1, norm)[..., None]
    return s, a


def _rates(s, a):
    # Intermediate RK stages can cross the mission boundary before event location.
    # Evaluate a bounded exterior continuation, then stop the accepted trajectory.
    r = np.maximum(s[..., 0], SAFETY_RADIUS)
    u, L = s[..., 1], s[..., 2]
    h, p = np.sqrt(1-2/r), L/r
    E = np.hypot(u, h*np.hypot(1, p))
    work = u*a[..., 0]+h*p*a[..., 1]
    radial_force = h*a[..., 0]+(u/(E+h))*work
    torque = r*a[..., 1]+(L/(E+h))*work
    with np.errstate(over="ignore", invalid="ignore"):
        radial = ((r-3)*p*p-1)/r**2+radial_force
    result = np.stack((u, radial, torque, L/r**2, np.hypot(a[..., 0], a[..., 1])), axis=-1)
    if not np.all(np.isfinite(result)):
        raise ValueError("state exceeds numerical range")
    return result


def rhs(state, action):
    """Return bounded controlled derivatives, with no thrust after exhaustion."""
    s, a = _inputs(state, action)
    active = np.asarray(status(s)) == "flying"
    a = np.where((active & (s[..., 4] < Q_MAX))[..., None], a, 0.)
    return np.where(active[..., None], _rates(s, a), 0.)


def _rk4(s, a, dt):
    dt = np.asarray(dt)[..., None]
    k1 = _rates(s, a)
    k2 = _rates(s+.5*dt*k1, a)
    k3 = _rates(s+.5*dt*k2, a)
    k4 = _rates(s+dt*k3, a)
    return s+dt*(k1+2*k2+2*k3+k4)/6


def _segment(s, a, dt):
    """Advance a held burn and locate terminal crossings within that burn."""
    result = s.copy()
    active = (np.asarray(status(s)) == "flying") & (dt > 0)
    if not np.any(active):
        return result
    start, force, duration = s[active], a[active], dt[active]
    candidate = _rk4(start, force, duration)
    candidate[..., 4] = np.clip(candidate[..., 4], 0, Q_MAX)
    # Inspect radius before status(), which requires an exterior valid state.
    cutoff = candidate[..., 0] <= SAFETY_RADIUS
    exterior = candidate.copy()
    exterior[..., 0] = np.maximum(exterior[..., 0], SAFETY_RADIUS)
    terminal = cutoff | (np.asarray(status(exterior)) == "escaped")
    if np.any(terminal):
        lo, hi = np.zeros(np.count_nonzero(terminal)), duration[terminal].copy()
        origin, burn = start[terminal], force[terminal]
        for _ in range(30):
            mid = (lo+hi)*.5
            trial = _rk4(origin, burn, mid)
            crossed_cutoff = trial[..., 0] <= SAFETY_RADIUS
            trial[..., 0] = np.maximum(trial[..., 0], SAFETY_RADIUS)
            trial[..., 4] = np.clip(trial[..., 4], 0, Q_MAX)
            crossed = crossed_cutoff | (np.asarray(status(trial)) == "escaped")
            hi, lo = np.where(crossed, mid, hi), np.where(crossed, lo, mid)
        endpoint = _rk4(origin, burn, hi)
        endpoint[..., 0] = np.maximum(endpoint[..., 0], SAFETY_RADIUS)
        endpoint[..., 4] = np.clip(endpoint[..., 4], 0, Q_MAX)
        candidate[terminal] = endpoint
    result[active] = candidate
    return result


def step(state, action, dt=2., substeps=8):
    """Vectorized RK4 planner step; split exhaustion exactly, then coast."""
    if not math.isfinite(dt) or dt <= 0 or not isinstance(substeps, int) or substeps < 1:
        raise ValueError("step duration must be positive and substeps a positive integer")
    s, requested = _inputs(state, action)
    scalar = s.ndim == 1
    shape = s.shape
    s, requested = s.reshape(-1, 5).copy(), requested.reshape(-1, 2)
    interval = dt/substeps
    for _ in range(substeps):
        active = np.asarray(status(s)) == "flying"
        a = np.where((active & (s[:, 4] < Q_MAX))[:, None], requested, 0.)
        norm = np.hypot(a[:, 0], a[:, 1])
        burn_time = np.full(len(s), interval)
        np.divide(Q_MAX-s[:, 4], norm, out=burn_time, where=norm > 0)
        burn_time = np.clip(burn_time, 0, interval)
        exhausted = (norm > 0) & (burn_time < interval)
        s = _segment(s, a, burn_time)
        s[exhausted, 4] = np.where(np.asarray(status(s[exhausted])) == "flying", Q_MAX, s[exhausted, 4])
        s = _segment(s, np.zeros_like(a), interval-burn_time)
    return s.reshape(shape) if not scalar else s[0]


def advance(state, action, dt=2., rtol=1e-10, return_info=False):
    """High-accuracy scalar execution with fuel and mission event locations."""
    if not math.isfinite(dt) or dt <= 0 or not math.isfinite(rtol) or rtol < 1e-13:
        raise ValueError("duration must be positive and tolerance at least 1e-13")
    s, requested = _inputs(state, action)
    if s.ndim != 1:
        raise ValueError("advance accepts one state and one action")
    s = s.copy()
    elapsed = 0.
    evaluations = 0
    while elapsed < dt and status(s) == "flying":
        a = requested if s[4] < Q_MAX else np.zeros(2)
        norm = math.hypot(*a)
        remaining = dt-elapsed
        fuel_time = (Q_MAX-s[4])/norm if norm else math.inf
        duration = min(remaining, fuel_time)

        def cutoff(tau, y):
            return y[0]-SAFETY_RADIUS

        def escaped(tau, y):
            r = max(y[0], SAFETY_RADIUS)
            E = math.hypot(y[1], math.sqrt(1-2/r)*math.hypot(1, y[2]/r))
            # Locate just inside the accepted region, avoiding a zero-time root
            # at ur=0 or a label reversal from floating-point boundary rounding.
            return min(y[0]-np.nextafter(ESCAPE_RADIUS, math.inf),
                       y[1]-1e-12, E-(1+ESCAPE_MARGIN+8*np.finfo(float).eps))

        cutoff.terminal, cutoff.direction = True, -1
        escaped.terminal, escaped.direction = True, 1
        solution = solve_ivp(lambda t, y: _rates(y, a), (0, duration), s,
            method="DOP853", rtol=rtol, atol=rtol*.01,
            max_step=min(.5, duration), events=(cutoff, escaped))
        if not solution.success:
            raise RuntimeError(solution.message)
        s, used = solution.y[:, -1], float(solution.t[-1])
        evaluations += solution.nfev
        elapsed += used
        s[0] = max(s[0], SAFETY_RADIUS)
        s[4] = min(Q_MAX, s[4])
        if len(solution.t_events[0]) or len(solution.t_events[1]):
            break
        if fuel_time <= remaining:
            s[4] = Q_MAX
        if used == 0:
            raise RuntimeError("integration made no progress")
    info = {"dt_used": elapsed, "status": status(s), "evaluations": evaluations}
    return (s, info) if return_info else s
