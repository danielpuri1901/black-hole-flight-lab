"""Post hoc coast-support and fixed-library controls for powered flight."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform

import numpy as np

from pilot_control import HORIZON, basic_plans, flight, mission_states, random_plans
from run_pilot_experiment import wilson

CONTROLLERS = ('random_with_coast', 'fixed_checked')
DECLARATION = ('These post hoc controls were introduced after inspecting the first '
    'three held-out test cases, where random_checked spent all fuel. They test '
    'proposal support and fixed-library search. No model weights or parameters '
    'were tuned, and the original benchmark results are preserved.')
FIELDS = ('split', 'mission', 'controller', 'outcome', 'minimum_radius',
          'fuel_used', 'impulse_used', 'proper_time', 'decision_count',
          'decision_seconds', 'interventions')


class ProposalControl:
    """A proposal sampler with no learned weights or context dependence."""
    def __init__(self, controller):
        if controller not in CONTROLLERS:
            raise ValueError('Unknown supplemental control')
        self.controller = controller

    def sample(self, context, count, seed):
        if count != 16:
            raise ValueError('The supplemental protocol fixes count=16')
        if self.controller == 'fixed_checked':
            return basic_plans()
        coast = np.zeros((1, HORIZON, 2))
        return np.concatenate((coast, random_plans(np.random.default_rng(seed), 15)))


def atomic_json(path, value):
    temporary = path.with_suffix('.partial')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def evaluate(task):
    root, split, index, initial, controller = task
    path = root/'control-flights'/f'{split}-{index:03d}-{controller}.json'
    if path.exists():
        result = json.loads(path.read_text())
        if (result['initial_state'] != initial or result['controller'] != controller
                or result['split'] != split or result['mission'] != index):
            raise ValueError('Checkpoint does not match the declared mission')
    else:
        result = flight(initial, 'checked', ProposalControl(controller), seed=91000+index)
        result.update(controller=controller, split=split, mission=index, initial_state=initial)
        atomic_json(path, result)
        print(json.dumps({'split': split, 'mission': index, 'controller': controller,
                          'outcome': result['outcome'], 'fuel': round(result['fuel_used'], 4)}),
              flush=True)
    return {key: result[key] for key in FIELDS}


def summarize(rows):
    groups = []
    for split in ('test', 'stress'):
        for controller in CONTROLLERS:
            group = [r for r in rows if r['split'] == split and r['controller'] == controller]
            count = len(group)
            successes = sum(r['outcome'] == 'escaped' for r in group)
            groups.append({'split': split, 'controller': controller, 'flights': count,
                'escaped': successes, 'safety_cutoff': sum(r['outcome'] == 'safety_cutoff' for r in group),
                'timeout': sum(r['outcome'] == 'timeout' for r in group),
                'success_fraction': successes/count, 'wilson_95': wilson(successes, count),
                'mean_fuel_used': float(np.mean([r['fuel_used'] for r in group])),
                'median_minimum_radius': float(np.median([r['minimum_radius'] for r in group])),
                'mean_decision_seconds': sum(r['decision_seconds'] for r in group)
                                         /sum(r['decision_count'] for r in group),
                'mean_flight_compute_seconds': float(np.mean([r['decision_seconds'] for r in group]))})
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('results/pilot'))
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--smoke', action='store_true', help='One development launch; no held-out evaluation')
    args = parser.parse_args()
    if args.smoke:
        initial = mission_states(40217, 1)[0]
        rows = []
        for controller in CONTROLLERS:
            result = flight(initial, 'checked', ProposalControl(controller), seed=71000)
            rows.append({**{key: result[key] for key in FIELDS if key not in
                          ('split', 'mission', 'controller')}, 'controller': controller})
        print(json.dumps({'development_seed': 40217, 'results': rows}, indent=2))
        return
    root = args.root
    missions_path = root/'missions.json'
    missions = json.loads(missions_path.read_text())
    source_root = Path(__file__).resolve().parent
    sources = ('pilot_physics.py', 'pilot_control.py', 'run_pilot_controls.py',
               'run_pilot_experiment.py')
    hashes = {name: hashlib.sha256((source_root/name).read_bytes()).hexdigest()
              for name in sources}
    for name, expected in missions['source_sha256'].items():
        if hashes[name] != expected:
            raise ValueError('Frozen mission source does not match the current engine')
    hashes['missions'] = hashlib.sha256(missions_path.read_bytes()).hexdigest()
    manifest = {'sha256': hashes, 'python': platform.python_version(), 'numpy': np.__version__,
        'workers': args.workers, 'machine': platform.machine(), 'post_hoc': True,
        'declaration': DECLARATION, 'controller_seed': '91000 + mission index',
        'test_splits': ['test', 'stress'],
        'candidate_counts': {'random_with_coast': 16, 'fixed_checked': 29},
        'learned_weights_used': False,
        'blas_thread_limit': os.environ.get('OPENBLAS_NUM_THREADS', 'unspecified'),
        'timing_note': 'Observed wall time on a shared computer, not an isolated latency benchmark.'}
    manifest_path = root/'controls-manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError('Supplemental inputs changed. Do not reuse existing checkpoints.')
    (root/'control-flights').mkdir(parents=True, exist_ok=True)
    atomic_json(manifest_path, manifest)
    tasks = [(root, split, index, initial, controller)
             for split in ('test', 'stress')
             for index, initial in enumerate(missions['missions'][split])
             for controller in CONTROLLERS]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(evaluate, tasks))
    summary = {'manifest': manifest, 'groups': summarize(rows), 'trials': rows,
        'limitations': [DECLARATION, 'Small fixed mission samples; supplemental comparisons are exploratory.',
            'Fixed checked scores 29 proposals; random with coast scores 16.',
            'Interventions count selection away from the first coast proposal, not repair of a learned action.',
            'Fuel averages include failures; compare fuel and success together.',
            'Candidate ranking is numerical look-ahead, not a rigorous safety shield.']}
    atomic_json(root/'controls-summary.json', summary)
    print(json.dumps(summary['groups'], indent=2))


if __name__ == '__main__':
    main()
