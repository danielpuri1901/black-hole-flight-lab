"""Evaluate fixed held-out missions with real closed-loop control.

Each completed flight is a checkpoint. No test flight trains the model.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import platform
import os

import numpy as np

from pilot_control import CONTROLLERS, flight
from pilot_model import load_model


def wilson(successes, total):
    z = 1.959963984540054
    p = successes / total
    center = (p + z*z/(2*total)) / (1 + z*z/total)
    half = z*np.sqrt(p*(1-p)/total + z*z/(4*total*total)) / (1 + z*z/total)
    return [float(center-half), float(center+half)]


def evaluate(task):
    root, split, index, initial, controller = task
    path = root / 'flights' / f'{split}-{index:03d}-{controller}.json'
    if path.exists():
        result = json.loads(path.read_text())
    else:
        model = load_model(root / 'model') if controller in ('learned', 'checked', 'hybrid') else None
        result = flight(initial, controller, model, seed=91000 + index)
        result.update(split=split, mission=index, initial_state=initial)
        temporary = path.with_suffix('.partial')
        temporary.write_text(json.dumps(result, separators=(',', ':')) + '\n')
        temporary.replace(path)
        print(json.dumps({'split': split, 'mission': index,
                          'controller': controller, 'outcome': result['outcome'],
                          'fuel': round(result['fuel_used'], 4)}), flush=True)
    return {key: result[key] for key in ('split', 'mission', 'controller',
        'outcome', 'minimum_radius', 'fuel_used', 'impulse_used', 'proper_time',
        'decision_count', 'decision_seconds', 'interventions')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='results/pilot')
    parser.add_argument('--controllers', nargs='+', choices=CONTROLLERS, default=list(CONTROLLERS))
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    root = Path(args.root)
    missions_path = root / 'missions.json'
    missions = json.loads(missions_path.read_text())
    paths = ['pilot_physics.py', 'pilot_control.py', 'pilot_model.py']
    hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
    hashes['missions'] = hashlib.sha256(missions_path.read_bytes()).hexdigest()
    hashes['weights'] = hashlib.sha256((root / 'model/weights.npz').read_bytes()).hexdigest()
    folder = root / 'flights'
    folder.mkdir(exist_ok=True)
    signature = root / 'evaluation-manifest.json'
    manifest = {'sha256': hashes, 'python': platform.python_version(),
                'numpy': np.__version__, 'candidate_count': 16,
                'machine': platform.machine(), 'workers': args.workers,
                'blas_thread_limit': os.environ.get('OPENBLAS_NUM_THREADS', 'unspecified'),
                'timing_note': 'Observed wall time on a shared computer, not an isolated latency benchmark.',
                'controller_seed': '91000 + mission index, shared across controllers',
                'test_splits': ['test', 'stress']}
    if signature.exists() and json.loads(signature.read_text()) != manifest:
        raise ValueError('Evaluation source or inputs changed. Use a fresh result directory.')
    signature.write_text(json.dumps(manifest, indent=2) + '\n')
    tasks = [(root, split, index, initial, controller)
             for split in ('test', 'stress')
             for index, initial in enumerate(missions['missions'][split])
             for controller in args.controllers]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(evaluate, tasks))
    with (root / 'trials.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    groups = []
    for split in ('test', 'stress'):
        for controller in args.controllers:
            group = [r for r in rows if r['split'] == split and r['controller'] == controller]
            count = len(group)
            successes = sum(r['outcome'] == 'escaped' for r in group)
            groups.append({'split': split, 'controller': controller, 'flights': count,
                'escaped': successes, 'safety_cutoff': sum(r['outcome'] == 'safety_cutoff' for r in group),
                'timeout': sum(r['outcome'] == 'timeout' for r in group),
                'success_fraction': successes/count, 'wilson_95': wilson(successes, count),
                'mean_fuel_used': float(np.mean([r['fuel_used'] for r in group])),
                'median_minimum_radius': float(np.median([r['minimum_radius'] for r in group])),
                'mean_decision_seconds': sum(r['decision_seconds'] for r in group) / sum(r['decision_count'] for r in group),
                'mean_flight_compute_seconds': float(np.mean([r['decision_seconds'] for r in group]))})
    paired = []
    for split in ('test', 'stress'):
        by_controller = {controller: {r['mission']: r for r in rows
                         if r['split'] == split and r['controller'] == controller}
                         for controller in args.controllers}
        if 'learned' in by_controller and 'checked' in by_controller:
            pairs = [(raw, by_controller['checked'][index])
                     for index, raw in by_controller['learned'].items()]
            paired.append({'split': split, 'flights': len(pairs),
                'rescued': sum(a['outcome'] != 'escaped' and b['outcome'] == 'escaped' for a, b in pairs),
                'harmed': sum(a['outcome'] == 'escaped' and b['outcome'] != 'escaped' for a, b in pairs),
                'both_escaped': sum(a['outcome'] == b['outcome'] == 'escaped' for a, b in pairs),
                'neither_escaped': sum(a['outcome'] != 'escaped' and b['outcome'] != 'escaped' for a, b in pairs)})
    summary = {'groups': groups, 'paired_raw_checked': paired, 'manifest': manifest,
               'limitations': ['The full benchmark uses one fit seed; two more fits have a separate sensitivity check.', 'Small fixed mission samples.',
                   'Numerical look-ahead is not a formal safety proof.',
                   'Classical teacher uses more candidates than learned selection.',
                   'Random checked and learned checked each score 16 proposals.',
                   'Raw control generates 16 proposals but executes the first without scoring.',
                   'Hybrid also scores 29 hand-designed burn/coast plans.',
                   'Fuel averages include failed flights; compare success and fuel together.']}
    (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    # Preserve the first paired rescue as an explanatory example, not a random sample.
    witness = None
    for split in ('test', 'stress'):
        for index in range(len(missions['missions'][split])):
            raw = folder / f'{split}-{index:03d}-learned.json'
            checked = folder / f'{split}-{index:03d}-checked.json'
            if raw.exists() and checked.exists():
                a, b = json.loads(raw.read_text()), json.loads(checked.read_text())
                if a['outcome'] != 'escaped' and b['outcome'] == 'escaped':
                    witness = {'selection': 'First test/stress mission where checking rescues raw diffusion.',
                               'learned': a, 'checked': b}
                    break
        if witness:
            break
    if witness is None:
        witness = {'selection': 'First held-out mission; no paired rescue was found.',
                   'learned': json.loads((folder / 'test-000-learned.json').read_text()),
                   'checked': json.loads((folder / 'test-000-checked.json').read_text())}
    (root / 'showcase.json').write_text(json.dumps(witness, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
