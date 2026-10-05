"""Predeclared sensitivity check: first eight missions per split, three fit seeds."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path

from pilot_control import flight
from pilot_model import load_model

ROOT = Path('results/pilot')
SEEDS = (1729, 1730, 1731)
MISSIONS_PER_SPLIT = 8


def evaluate(task):
    seed, split, index, initial, controller = task
    model_path = ROOT / 'model' if seed == 1729 else ROOT / 'model' / f'seed-{seed}'
    path = (ROOT / 'flights' / f'{split}-{index:03d}-{controller}.json' if seed == 1729
            else ROOT / 'seed-flights' / f'{seed}-{split}-{index:03d}-{controller}.json')
    if path.exists():
        result = json.loads(path.read_text())
    else:
        result = flight(initial, controller, load_model(model_path), seed=91000+index)
        result.update(split=split, mission=index, initial_state=initial)
        path.parent.mkdir(exist_ok=True)
        temporary = path.with_suffix('.partial')
        temporary.write_text(json.dumps(result, separators=(',', ':')) + '\n')
        temporary.replace(path)
    print(seed, split, index, controller, result['outcome'], flush=True)
    return {'fit_seed': seed, 'split': split, 'mission': index, 'controller': controller,
            'outcome': result['outcome'], 'fuel_used': result['fuel_used'],
            'decision_seconds': result['decision_seconds']}


def main():
    missions = json.loads((ROOT / 'missions.json').read_text())
    tasks = [(seed, split, index, initial, controller)
             for seed in SEEDS for split in ('test', 'stress')
             for index, initial in enumerate(missions['missions'][split][:MISSIONS_PER_SPLIT])
             for controller in ('learned', 'checked')]
    paths = {str(seed): ROOT / 'model' / (f'seed-{seed}/weights.npz' if seed != 1729 else 'weights.npz')
             for seed in SEEDS}
    signature = {'weights_sha256': {seed: hashlib.sha256(path.read_bytes()).hexdigest()
                                    for seed, path in paths.items()},
                 'source_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                    for p in ('pilot_physics.py', 'pilot_control.py', 'pilot_model.py')},
                 'missions_sha256': hashlib.sha256((ROOT/'missions.json').read_bytes()).hexdigest(),
                 'mission_selection': 'First eight missions in each frozen split; declared before training.'}
    manifest = ROOT / 'seed-check-manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != signature:
        raise ValueError('Seed-check inputs changed; do not reuse old flight checkpoints.')
    manifest.write_text(json.dumps(signature, indent=2) + '\n')
    with ProcessPoolExecutor(max_workers=2) as executor:
        rows = list(executor.map(evaluate, tasks))
    groups = []
    for seed in SEEDS:
        for split in ('test', 'stress'):
            for controller in ('learned', 'checked'):
                group = [r for r in rows if (r['fit_seed'], r['split'], r['controller']) == (seed, split, controller)]
                groups.append({'fit_seed': seed, 'split': split, 'controller': controller,
                               'escaped': sum(r['outcome'] == 'escaped' for r in group),
                               'flights': len(group),
                               'mean_fuel_used': sum(r['fuel_used'] for r in group)/len(group)})
    (ROOT / 'seed-check.json').write_text(json.dumps({'manifest': signature, 'groups': groups, 'trials': rows}, indent=2) + '\n')


if __name__ == '__main__':
    main()
