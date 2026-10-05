"""Freeze mission splits and generate classical-plan imitation examples."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from pilot_control import CONTEXT_NAMES, flight, mission_states


def teach(task):
    split_id, split, index, initial = task
    result, examples = flight(initial, 'classical', seed=10000 * split_id + index,
                              collect=True)
    return split_id, split, index, result, examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='results/pilot')
    parser.add_argument('--train', type=int, default=64)
    parser.add_argument('--validation', type=int, default=16)
    parser.add_argument('--test', type=int, default=32)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 1, 'context_names': CONTEXT_NAMES,
                'source_sha256': {name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
                                  for name in ('pilot_physics.py', 'pilot_control.py')},
                'seeds': {'train': 7141, 'validation': 7142,
                          'test': 7143, 'stress': 7144}, 'missions': {}}
    for split, count in [('train', args.train), ('validation', args.validation),
                         ('test', args.test), ('stress', args.test)]:
        manifest['missions'][split] = mission_states(
            manifest['seeds'][split], count, stress=split == 'stress').tolist()
    manifest_path = output / 'missions.json'
    encoded = (json.dumps(manifest, indent=2) + '\n').encode()
    if manifest_path.exists() and manifest_path.read_bytes() != encoded:
        raise ValueError('Refusing to replace frozen missions with different launches')
    manifest_path.write_bytes(encoded)
    contexts, plans, splits, summaries = [], [], [], []
    checkpoint = output / 'teacher.npz'
    if checkpoint.exists():
        with np.load(checkpoint, allow_pickle=False) as data:
            contexts, plans, splits = list(data['contexts']), list(data['plans']), list(data['split'])
            summaries = json.loads(str(data['summaries']))
    completed = {(s['split'], s['mission']) for s in summaries}
    started = time.perf_counter()
    tasks = [(split_id, split, i, initial)
             for split_id, split in enumerate(('train', 'validation'))
             for i, initial in enumerate(manifest['missions'][split]) if (split, i) not in completed]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for split_id, split, i, result, examples in executor.map(teach, tasks):
            for state_context, plan in examples:
                contexts.append(state_context)
                plans.append(plan)
                splits.append(split_id)
            summaries.append({key: value for key, value in result.items()
                              if key not in ('points', 'decisions')}
                             | {'split': split, 'mission': i})
            print(json.dumps({'split': split, 'mission': i,
                              'outcome': result['outcome'], 'examples': len(examples),
                              'elapsed': round(time.perf_counter() - started, 1)}), flush=True)
            # Keep completed flights recoverable if a long generation job stops.
            temporary = output / 'teacher.partial.npz'
            np.savez_compressed(temporary, contexts=np.array(contexts),
                                plans=np.array(plans), split=np.array(splits),
                                summaries=json.dumps(summaries))
            temporary.replace(checkpoint)
            (output / 'teacher-summary.json').write_text(json.dumps({
                'mission_sha256': hashlib.sha256(encoded).hexdigest(),
                'elapsed_seconds': time.perf_counter() - started,
                'complete': split == 'validation' and i + 1 == args.validation,
                'flights': summaries}, indent=2) + '\n')


if __name__ == '__main__':
    main()
