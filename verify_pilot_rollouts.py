"""Compare fixed planner candidates with finer RK4 and adaptive execution."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import scipy

import pilot_control as control
import pilot_physics as physics


def source_hash(name):
    return hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()


def label(info, index):
    return 'escaped' if info['escaped'][index] else (
        'safety_cutoff' if info['cutoff'][index] else 'flying')


def execute(state, plan):
    state = state.copy()
    initial_impulse = state[4]
    minimum = state[0]
    finish = 120.
    for i in range(control.HORIZON+48):
        action = plan[i] if i < control.HORIZON else [0., 0.]
        state = physics.advance(state, action, control.INTERVAL)
        minimum = min(minimum, state[0])
        if physics.status(state) != 'flying':
            finish = (i+1)*control.INTERVAL
            break
    status = physics.status(state)
    cost = 70*(state[4]-initial_impulse)
    score = state[0]+12*state[1]+25*(physics.energy(state)-1)-cost
    if status == 'escaped':
        score = 200-cost-.04*finish
    if status == 'safety_cutoff':
        score = -1000+minimum
    score -= 4*max(0, 3-minimum)**2
    return state, status, float(score), float(minimum)


def validate(seed=40217):
    started = time.perf_counter()
    launches = control.mission_states(seed, 16)
    plans = control.basic_plans()
    comparisons = []
    cached = []
    selected = set()
    closest = None
    for i, launch in enumerate(launches):
        coarse = control.score_plans(launch, plans, substeps=4)
        fine = control.score_plans(launch, plans, substeps=8)
        cached.append((coarse, fine))
        # Coast, sustained radial, sustained negative tangential, and mixed burn.
        selected.update((i, j) for j in (0, 16, 4, (8, 12, 20, 24)[i % 4]))
        for j in range(len(plans)):
            s4, s8 = label(coarse[1], j), label(fine[1], j)
            minimum = float(fine[1]['minimum_radius'][j])
            comparisons.append({'launch': i, 'plan': j, 'rk4_status': s4,
                'rk8_status': s8, 'minimum_radius': minimum,
                'score_difference': float(abs(coarse[0][j]-fine[0][j])),
                'terminal_state_difference': float(np.max(np.abs(
                    coarse[1]['terminal'][j]-fine[1]['terminal'][j])))})
            if s4 != s8:
                selected.add((i, j))
            if minimum > physics.SAFETY_RADIUS+1e-8:
                if closest is None or minimum < closest[0]:
                    closest = (minimum, i, j)
    if closest:
        selected.add(closest[1:])
    references = []
    for i, j in sorted(selected):
        state, status, score, minimum = execute(launches[i], plans[j])
        row = {'launch': i, 'plan': j, 'status': status,
               'terminal': state.tolist(), 'score': score, 'minimum_radius': minimum}
        for substeps, (scores, info) in zip((4, 8), cached[i]):
            row[str(substeps)] = {'status': label(info, j),
                'terminal_state_error': float(np.max(np.abs(info['terminal'][j]-state))),
                'score_error': float(abs(scores[j]-score)),
                'minimum_radius_error': float(abs(info['minimum_radius'][j]-minimum))}
        references.append(row)
    summary = {
        'fixed_candidates': len(comparisons),
        'refinement_classification_disagreements': sum(
            x['rk4_status'] != x['rk8_status'] for x in comparisons),
        'adaptive_reference_cases': len(references),
        'adaptive_outcomes': {s: sum(x['status'] == s for x in references)
                             for s in ('escaped', 'safety_cutoff', 'flying')},
        'closest_surviving_candidate': list(closest) if closest else None}
    for n in ('4', '8'):
        summary['substeps_'+n] = {
            'adaptive_classification_disagreements': sum(
                x[n]['status'] != x['status'] for x in references),
            'max_terminal_state_error': max(x[n]['terminal_state_error'] for x in references),
            'max_score_error': max(x[n]['score_error'] for x in references),
            'max_minimum_radius_error': max(x[n]['minimum_radius_error'] for x in references)}
    return {'seed': seed, 'launches': launches.tolist(),
        'source_sha256': {name: source_hash(name)
                          for name in ('pilot_physics.py', 'pilot_control.py',
                                       'verify_pilot_rollouts.py')},
        'versions': {'python': platform.python_version(), 'numpy': np.__version__,
                     'scipy': scipy.__version__},
        'method': 'All 29 fixed plans on 16 launches; 64 diverse plans plus disagreements and closest surviving candidate use scalar DOP853. Scores and minimum radius use planner interval endpoints.',
        'summary': summary, 'fixed_comparisons': comparisons,
        'adaptive_references': references, 'elapsed_seconds': time.perf_counter()-started}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=40217)
    parser.add_argument('--output', type=Path, default=Path('results/pilot/physics-validation.json'))
    args = parser.parse_args()
    result = validate(args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['summary'], indent=2))
    print('Elapsed seconds:', round(result['elapsed_seconds'], 3), flush=True)
