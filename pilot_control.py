"""Closed-loop planning in the powered Schwarzschild flight experiment.

The planner searches normalized proper-acceleration commands, not coordinates.
All learned controllers observe the same six scalar state features.
"""
import time

import numpy as np

import pilot_physics as physics

HORIZON = 12
INTERVAL = 2.0
MISSION_TIME = 160.0
CONTEXT_NAMES = ['r/10', 'ur', 'L/5', 'q/q_max', 'E', '1/r']
CONTROLLERS = ('coast', 'radial', 'classical', 'learned', 'checked',
               'hybrid', 'random_checked')


def context(state):
    r, ur, momentum, _, q = np.asarray(state)
    return np.array([r / 10, ur, momentum / 5, q / physics.Q_MAX,
                     float(physics.energy(state)), 1 / r])


def limit_actions(actions):
    actions = np.asarray(actions, dtype=float)
    return actions / np.maximum(1, np.linalg.norm(actions, axis=-1, keepdims=True))


def mission_states(seed, count, stress=False):
    """Generate launches independently of any fitted model or observed outcome."""
    rng = np.random.default_rng(seed)
    radii = rng.uniform(6.0, 8.0, count) if stress else rng.uniform(8.0, 12.0, count)
    energies = rng.uniform(0.995, 1.04, count)
    momenta = rng.uniform(2.8, 4.2, count)
    return np.array([physics.initial_state(r, e, ell)
                     for r, e, ell in zip(radii, energies, momenta)])


def score_plans(state, plans, substeps=4):
    """Score candidate burns followed by a coast, using the physical engine.

    Numerical look-ahead is a runtime check, not a proof of future safety.
    """
    plans = limit_actions(plans)
    states = np.broadcast_to(state, (len(plans), 5)).copy()
    min_radius = states[:, 0].copy()
    finish_time = np.full(len(plans), 120.0)
    finished = np.zeros(len(plans), dtype=bool)
    for i in range(HORIZON + 48):
        action = plans[:, i] if i < HORIZON else np.zeros((len(plans), 2))
        states = physics.step(states, action, INTERVAL, substeps=substeps)
        min_radius = np.minimum(min_radius, states[:, 0])
        escaped = ((states[:, 0] >= physics.ESCAPE_RADIUS) & (states[:, 1] > 0)
                   & (physics.energy(states) >= 1 + 1e-6))
        cutoff = states[:, 0] <= physics.SAFETY_RADIUS + 1e-8
        done = escaped | cutoff
        finish_time[done & ~finished] = (i + 1) * INTERVAL
        finished |= done
        if np.all(finished):
            break
    escaped = ((states[:, 0] >= physics.ESCAPE_RADIUS) & (states[:, 1] > 0)
               & (physics.energy(states) >= 1 + 1e-6))
    cutoff = states[:, 0] <= physics.SAFETY_RADIUS + 1e-8
    fuel_cost = 70 * (states[:, 4] - state[4])
    score = (states[:, 0] + 12 * states[:, 1]
             + 25 * (physics.energy(states) - 1) - fuel_cost)
    score = np.where(escaped, 200 - fuel_cost - .04 * finish_time, score)
    score = np.where(cutoff, -1000 + min_radius, score)
    score -= 4 * np.maximum(0, 3.0 - min_radius) ** 2
    return score, {'escaped': escaped, 'cutoff': cutoff,
                   'minimum_radius': min_radius, 'terminal': states}


def basic_plans():
    """Deterministic burn/coast candidates shared by classical and checked modes."""
    plans = [np.zeros((HORIZON, 2))]
    for angle in np.linspace(-np.pi / 2, np.pi / 2, 7):
        for duration in (2, 5, 9, 12):
            plan = np.zeros((HORIZON, 2))
            plan[:duration] = [np.cos(angle), np.sin(angle)]
            plans.append(plan)
    return np.array(plans)


def random_plans(rng, count):
    """Smooth random plans for a candidate-count-matched search baseline."""
    anchors = rng.normal(0, .65, (count, 3, 2))
    x = np.linspace(0, 2, HORIZON)
    random = np.array([[np.interp(x, [0, 1, 2], row[:, j]) for j in range(2)]
                       for row in anchors]).transpose(0, 2, 1)
    return limit_actions(random)


def classical_plan(state, rng, previous=None, count=64, rounds=2):
    """Cross-entropy shooting with smooth random plans and burn/coast seeds."""
    fixed = basic_plans()
    if previous is not None:
        fixed = np.concatenate((fixed, np.r_[previous[1:], [[0., 0.]]][None]))
    plans = np.concatenate((fixed, random_plans(rng, count)))
    best_plan, best_score, best_info = None, -np.inf, None
    for iteration in range(rounds):
        scores, info = score_plans(state, plans)
        best = int(np.argmax(scores))
        if scores[best] > best_score:
            best_plan, best_score = plans[best].copy(), float(scores[best])
            best_info = {key: value[best] for key, value in info.items()}
        if iteration + 1 < rounds:
            elite = plans[np.argsort(scores)[-12:]]
            samples = rng.normal(elite.mean(0), elite.std(0) + .08,
                                 (count, HORIZON, 2))
            plans = np.concatenate((fixed, best_plan[None], limit_actions(samples)))
    return best_plan, {'score': best_score, **best_info}


def flight(initial, controller='classical', model=None, seed=0,
           collect=False, candidate_count=16, max_time=MISSION_TIME):
    """Run actual feedback: observe, plan, execute one burn, then observe again."""
    if controller not in CONTROLLERS:
        raise ValueError('Unknown controller')
    if controller in ('learned', 'checked', 'hybrid') and model is None:
        raise ValueError('Learned controller requires trained weights')
    rng = np.random.default_rng(seed)
    state = np.asarray(initial, dtype=float).copy()
    previous = None
    points, decisions, examples = [], [], []
    tau = 0.0
    points.append([tau, *state.tolist(), float(physics.energy(state)),
                   float(physics.fuel_fraction(state[4]))])
    times = []
    while tau < max_time and physics.status(state) == 'flying':
        started = time.perf_counter()
        intervention = False
        if state[4] >= physics.Q_MAX - 1e-10 or controller == 'coast':
            plan = np.zeros((HORIZON, 2))
        elif controller == 'radial':
            plan = np.tile([1., 0.], (HORIZON, 1))
        elif controller == 'classical':
            plan, _ = classical_plan(state, rng, previous)
        else:
            proposal_seed = int(rng.integers(2**31))
            proposals = (random_plans(np.random.default_rng(proposal_seed), candidate_count)
                         if controller == 'random_checked'
                         else model.sample(context(state), count=candidate_count,
                                           seed=proposal_seed))
            if controller == 'learned':
                plan = proposals[0]
            else:
                candidates = (np.concatenate((proposals, basic_plans()))
                              if controller == 'hybrid' else proposals)
                scores, _ = score_plans(state, candidates)
                selected = int(np.argmax(scores))
                plan = candidates[selected]
                intervention = selected != 0
        elapsed = time.perf_counter() - started
        times.append(elapsed)
        if collect and state[4] < physics.Q_MAX - 1e-10:
            examples.append((context(state).copy(), plan.copy()))
        decisions.append({'tau': tau, 'action': plan[0].tolist(),
                          'seconds': elapsed, 'intervention': intervention})
        previous = plan
        # The executed path uses an adaptive solver independent of planner RK4.
        state, integration = physics.advance(state, plan[0], INTERVAL, return_info=True)
        tau += integration['dt_used']
        points.append([tau, *state.tolist(), float(physics.energy(state)),
                       float(physics.fuel_fraction(state[4]))])
    status = physics.status(state)
    result = {'controller': controller, 'seed': seed,
              'outcome': 'timeout' if status == 'flying' else status,
              'points': points, 'decisions': decisions,
              'point_columns': ['tau', 'r', 'ur', 'L', 'phi', 'q', 'E', 'fuel'],
              'minimum_radius': min(p[1] for p in points),
              'fuel_used': 1 - float(physics.fuel_fraction(state[4])),
              'impulse_used': float(state[4]), 'proper_time': tau,
              'decision_count': len(decisions),
              'decision_seconds': float(sum(times)),
              'interventions': sum(d['intervention'] for d in decisions)}
    if collect:
        return result, examples
    return result
