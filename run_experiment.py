"""Run the predeclared compact-world-model experiment without downloading anything."""
import os

# Bound both training and exported matrix inference to one BLAS thread.
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[variable] = '1'

import argparse
import csv
import hashlib
import json
import platform
import time
import warnings
from pathlib import Path

import numpy as np
import scipy
import sklearn
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

import physics
from world_model import BOUNDARY_TOLERANCE, WorldModel, analytic_margin, export_model, load_model

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
SEEDS = [11, 22, 33, 44, 55]
SIZES = {'small': (16, 16), 'large': (64, 64)}
OPTIMIZER = {'solver': 'lbfgs', 'activation': 'tanh', 'alpha': 1e-6,
             'max_iter': 800, 'max_fun': 2000, 'tol': 1e-7}
SELECT_RULE = ('Order models small-11, small-22, small-33, small-44, small-55, '
               'large-11, large-22, large-33, large-44, large-55. '
               'Take the first model with a false escape, then its largest positive margin, '
               'breaking ties by trial order. Require learned numerical escape and exact numerical capture. '
               'If integration disagrees, record the discrepancy and try the next ranked witness. '
               'If no false escape exists, take the first disagreement, otherwise the first nominal trial.')


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def observations(seed, count):
    rng = np.random.default_rng(seed)
    radius = np.exp(rng.uniform(np.log(2.02), np.log(30), count))
    momentum = rng.uniform(3.5, 6.3, count)
    return radius, momentum, physics.potential(radius, momentum)


def freeze_tests():
    path = RESULTS / 'test_inputs.json'
    rng = np.random.default_rng(20261004)
    nominal_energy = rng.uniform(1.002, 1.2, 2000)
    nominal_momentum = rng.uniform(3.5, 6.3, 2000)
    stress_energy = rng.uniform(1.002, 1.2, 2000)
    # Balanced signs are shuffled independently of energy and boundary distance.
    signs = np.repeat([-1., 1.], 1000)
    rng.shuffle(signs)
    distances = np.exp(rng.uniform(np.log(1e-5), np.log(1e-2), 2000))
    stress_momentum = physics.critical_angular_momentum(stress_energy) * (1 + signs * distances)
    data = {'seed': 20261004, 'nominal': np.column_stack((nominal_energy, nominal_momentum)).tolist(),
            'stress': np.column_stack((stress_energy, stress_momentum)).tolist(),
            'selection_rule': SELECT_RULE}
    if path.exists():
        if json.loads(path.read_text()) != data:
            raise ValueError('Frozen tests differ from the declared protocol.')
    else:
        save_json(path, data)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return data, digest


def fit(size, seed, development=False):
    model_id = f'{size}-{seed}'
    path = RESULTS / ('development' if development else 'models') / f'{model_id}.json'
    metric_path = path.with_name(f'{model_id}-fit.json')
    if path.exists() and metric_path.exists():
        metric = json.loads(metric_path.read_text())
        if metric['optimizer'] != OPTIMIZER:
            raise ValueError(f'Existing optimizer differs for {model_id}.')
        return load_model(path), metric
    radius, momentum, target = observations(seed, 4096)
    validation_radius, validation_momentum, validation_target = observations(seed + 100000, 1024)
    data_path = RESULTS / ('development' if development else 'observations') / f'{model_id}.npz'
    data_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(data_path, radius=radius, angular_momentum=momentum, potential=target,
             validation_radius=validation_radius, validation_angular_momentum=validation_momentum,
             validation_potential=validation_target)
    features = np.column_stack((1 / radius, momentum))
    feature_scaler = StandardScaler().fit(features)
    target_scaler = StandardScaler().fit(target[:, None])
    estimator = MLPRegressor(hidden_layer_sizes=SIZES[size], random_state=seed, **OPTIMIZER)
    start = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=1):
        warnings.simplefilter('always')
        estimator.fit(feature_scaler.transform(features), target_scaler.transform(target[:, None]).ravel())
    elapsed = time.perf_counter() - start
    payload = export_model(estimator, feature_scaler, target_scaler,
                           {'model_id': model_id, 'seed': seed, 'size': size,
                            'optimizer': OPTIMIZER, 'development': development})
    model = WorldModel(payload)
    estimator_output = target_scaler.inverse_transform(estimator.predict(
        feature_scaler.transform(features))[:, None]).ravel()
    np.testing.assert_allclose(model.potential(radius, momentum), estimator_output, atol=1e-12)
    step = validation_radius * 1e-5
    numerical = (model.potential(validation_radius + step, validation_momentum)
                 - model.potential(validation_radius - step, validation_momentum)) / (2 * step)
    np.testing.assert_allclose(model.derivative(validation_radius, validation_momentum), numerical,
                               rtol=2e-5, atol=2e-8)
    residual = model.potential(validation_radius, validation_momentum) - validation_target
    acceleration_error = -.5 * (model.derivative(validation_radius, validation_momentum)
                                - physics.potential_derivative(validation_radius, validation_momentum))
    metric = {'model_id': model_id, 'seed': seed, 'size': size,
              'parameters': int(sum(weight.size for weight in estimator.coefs_)
                                + sum(bias.size for bias in estimator.intercepts_)),
              'fit_seconds': elapsed, 'iterations': int(estimator.n_iter_),
              'training_loss': float(estimator.loss_), 'optimizer': OPTIMIZER,
              'converged': not bool(caught), 'warnings': [str(item.message) for item in caught],
              'potential_rmse': float(np.sqrt(np.mean(residual**2))),
              'acceleration_rmse': float(np.sqrt(np.mean(acceleration_error**2))),
              'potential_absolute_error_95': float(np.quantile(abs(residual), .95)),
              'validation_count': len(validation_radius)}
    save_json(path, payload)
    save_json(metric_path, metric)
    print(f'{model_id}: {elapsed:.2f}s; V RMSE={metric["potential_rmse"]:.6g}; '
          f'acceleration RMSE={metric["acceleration_rmse"]:.6g}; '
          f'converged={metric["converged"]}', flush=True)
    return model, metric


def labels_from_margin(margin):
    return np.where(abs(margin) <= BOUNDARY_TOLERANCE, 'unresolved',
                    np.where(margin > 0, 'escape', 'capture'))


def wilson(count, total):
    if not total:
        return [0., 1.]
    z = 1.959963984540054
    proportion = count / total
    center = (proportion + z * z / (2 * total)) / (1 + z * z / total)
    half = z * np.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total**2)) / (1 + z * z / total)
    return [float(max(0, center - half)), float(min(1, center + half))]


def decision_metrics(predicted, actual):
    count = len(actual)
    proposed = predicted == 'escape'
    false_escape = proposed & (actual == 'capture')
    false_capture = (predicted == 'capture') & (actual == 'escape')
    accepted = proposed & (actual == 'escape')
    rejected = proposed & (actual != 'escape')
    dangerous = int(false_escape.sum())
    proposed_count = int(proposed.sum())
    return {'trials': count, 'actual_escape': int((actual == 'escape').sum()),
            'actual_capture': int((actual == 'capture').sum()),
            'actual_unresolved': int((actual == 'unresolved').sum()),
            'predicted_unresolved': int((predicted == 'unresolved').sum()),
            'false_escapes': dangerous, 'false_captures': int(false_capture.sum()),
            'false_escape_rate': dangerous / count,
            'false_escape_rate_interval_95': wilson(dangerous, count),
            'false_escape_given_proposal': dangerous / proposed_count if proposed_count else None,
            'false_escape_given_proposal_interval_95': wilson(dangerous, proposed_count),
            'accepted_flights': proposed_count, 'coverage': proposed_count / count,
            'coverage_interval_95': wilson(proposed_count, count),
            'gate_accepted': int(accepted.sum()), 'gate_rejected': int(rejected.sum()),
            'gate_false_escapes': 0, 'gate_coverage': float(accepted.mean()),
            'gate_coverage_interval_95': wilson(int(accepted.sum()), count),
            'gate_rejected_unresolved': int((proposed & (actual == 'unresolved')).sum())}


def environment():
    return {'python': platform.python_version(), 'numpy': np.__version__,
            'scipy': scipy.__version__, 'scikit_learn': sklearn.__version__,
            'platform': platform.platform(), 'machine': platform.machine(),
            'blas_threads': 1, 'aws_spend_eur': 0., 'aws_resources_created': []}


def full_run(inputs, digest):
    if not (RESULTS / 'development' / 'smoke.json').exists():
        raise ValueError('Run --smoke before the frozen experiment.')
    start = time.perf_counter()
    energies, momenta, distributions = [], [], []
    for distribution in ('nominal', 'stress'):
        pairs = np.asarray(inputs[distribution])
        energies.extend(pairs[:, 0]); momenta.extend(pairs[:, 1])
        distributions.extend([distribution] * len(pairs))
    energies, momenta, distributions = np.asarray(energies), np.asarray(momenta), np.asarray(distributions)
    oracle_start = time.perf_counter()
    actual = np.array([physics.outcome(e, l) for e, l in zip(energies, momenta)])
    oracle_seconds = time.perf_counter() - oracle_start
    rows, metrics, models, predictions = [], [], {}, {}
    baseline_start = time.perf_counter()
    baseline_margin = analytic_margin(energies, momenta)
    baseline = labels_from_margin(baseline_margin)
    baseline_seconds = time.perf_counter() - baseline_start
    baseline_agreement = bool(np.array_equal(baseline, actual))
    if not baseline_agreement:
        raise ValueError('Analytic baseline differs from polynomial oracle.')
    for size in SIZES:
        for seed in SEEDS:
            model, metric = fit(size, seed)
            model_id = metric['model_id']
            models[model_id] = model
            prediction_start = time.perf_counter()
            margin = model.margin(energies, momenta)
            predicted = labels_from_margin(margin)
            metric['prediction_seconds'] = time.perf_counter() - prediction_start
            data_path = RESULTS / 'observations' / f'{model_id}.npz'
            metric['observations_sha256'] = hashlib.sha256(data_path.read_bytes()).hexdigest()
            gate_start = time.perf_counter()
            proposals = np.where(predicted == 'escape')[0]
            gate_labels = np.array([physics.outcome(energies[index], momenta[index]) for index in proposals])
            metric['gate_check_seconds'] = time.perf_counter() - gate_start
            metric['gate_checked_proposals'] = len(proposals)
            np.testing.assert_array_equal(gate_labels, actual[proposals])
            predictions[model_id] = (margin, predicted)
            threshold = 2 * metric['potential_absolute_error_95']
            # A validation residual flag is an error heuristic, not a certified bound.
            uncertain = abs(margin) <= threshold
            metric['uncertainty_margin_threshold'] = threshold
            metric['distributions'] = {}
            for distribution in ('nominal', 'stress'):
                mask = distributions == distribution
                decision = decision_metrics(predicted[mask], actual[mask])
                decision['uncertain_predictions'] = int(uncertain[mask].sum())
                metric['distributions'][distribution] = decision
            metrics.append(metric)
            for index in range(len(energies)):
                rows.append({'trial_id': index, 'distribution': distributions[index],
                             'energy': float(energies[index]), 'angular_momentum': float(momenta[index]),
                             'model_id': model_id, 'seed': seed, 'size': size,
                             'prediction': predicted[index], 'actual': actual[index],
                             'margin': float(margin[index]), 'uncertain': bool(uncertain[index]),
                             'gate': 'accepted' if predicted[index] == actual[index] == 'escape'
                                     else ('rejected' if predicted[index] == 'escape' else 'not_proposed')})
            save_json(RESULTS / 'metrics' / f'{model_id}.json', metric)
            print(f'{model_id}: nominal false escapes={metric["distributions"]["nominal"]["false_escapes"]}; '
                  f'stress={metric["distributions"]["stress"]["false_escapes"]}', flush=True)
    baseline_metrics = {distribution: decision_metrics(baseline[distributions == distribution],
                                                       actual[distributions == distribution])
                        for distribution in ('nominal', 'stress')}
    for index in range(len(energies)):
        rows.append({'trial_id': index, 'distribution': distributions[index],
                     'energy': float(energies[index]), 'angular_momentum': float(momenta[index]),
                     'model_id': 'analytic', 'seed': '', 'size': 'analytic',
                     'prediction': baseline[index], 'actual': actual[index],
                     'margin': float(baseline_margin[index]), 'uncertain': baseline[index] == 'unresolved',
                     'gate': 'accepted' if baseline[index] == 'escape' else 'not_proposed'})
    with (RESULTS / 'trials.csv').open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    aggregates = []
    for size in SIZES:
        for distribution in ('nominal', 'stress'):
            subset = [metric['distributions'][distribution] for metric in metrics if metric['size'] == size]
            aggregate = {'size': size, 'distribution': distribution, 'seeds': SEEDS, 'trials_per_seed': 2000}
            for key in ('false_escapes', 'false_captures', 'false_escape_rate', 'coverage', 'gate_coverage'):
                values = [item[key] for item in subset]
                aggregate[f'{key}_mean'] = float(np.mean(values))
                aggregate[f'{key}_std'] = float(np.std(values, ddof=1))
                aggregate[f'{key}_min'] = float(min(values))
                aggregate[f'{key}_max'] = float(max(values))
            aggregates.append(aggregate)
    crosschecks = []
    for index in list(range(10)) + list(range(2000, 2010)):
        numerical = physics.trace(float(energies[index]), float(momenta[index]), max_points=100)
        if numerical['outcome'] != actual[index]:
            raise ValueError(f'Fixed numerical crosscheck differs at trial {index}.')
        crosschecks.append({'trial_id': index, 'oracle': str(actual[index]),
                            'numerical': numerical['outcome'], 'energy_drift': numerical['energy_drift']})
    showcase, selection = select_showcase(energies, momenta, actual, models, predictions)
    save_json(RESULTS / 'showcase.json', showcase)
    summary = {'protocol': {'seeds': SEEDS, 'training_observations': 4096,
                           'validation_observations': 1024, 'test_seed': 20261004,
                           'test_sha256': digest, 'nominal_trials': 2000, 'stress_trials': 2000,
                           'radius_range': [2.02, 30], 'angular_momentum_range': [3.5, 6.3],
                           'energy_range': [1.002, 1.2], 'r0': 30., 'optimizer': OPTIMIZER,
                           'sizes': {size: list(layers) for size, layers in SIZES.items()},
                           'training_sampling': 'NumPy default_rng(seed), log-uniform radius then uniform angular momentum.',
                           'validation_sampling': 'Independent default_rng(seed+100000), same radius and angular momentum distributions.',
                           'compute_comparison': 'Same data and optimizer settings; different sizes are not matched for total compute.',
                           'stress_sampling': 'Balanced sides, relative boundary distance log-uniform 1e-5 to 1e-2.',
                           'confidence_intervals': '95% Wilson intervals per model and distribution; shared trials are not pooled; stress intervals are descriptive approximations for balanced stratified sampling.',
                           'uncertainty': 'abs(margin) <= twice validation 95th-percentile absolute potential error; heuristic only.',
                           'gate': 'Independent correct-physics polynomial oracle rejects proposed escapes unless it says escape.',
                           'selected_case_rule': SELECT_RULE},
               'environment': environment(), 'model_metrics': metrics, 'aggregate_metrics': aggregates,
               'baseline': {'model_id': 'analytic', 'parameters': 0, 'potential_rmse': 0.,
                            'acceleration_rmse': 0., 'fit_seconds': 0.,
                            'prediction_seconds': baseline_seconds, 'oracle_seconds': oracle_seconds,
                            'oracle_agreement': baseline_agreement,
                            'distributions': baseline_metrics},
               'model_files': {model_id: f'models/{model_id}.json' for model_id in models},
               'selected_case': selection, 'numerical_crosschecks': crosschecks,
               'training_fit_seconds_total': sum(metric['fit_seconds'] for metric in metrics),
               'execution_seconds_this_run': time.perf_counter() - start}
    save_json(RESULTS / 'summary.json', summary)
    create_figures(summary)
    return summary


def select_showcase(energy, momentum, actual, models, predictions):
    discrepancies = []
    candidates = []
    for model_id, model in models.items():
        margin, predicted = predictions[model_id]
        indices = np.where((predicted == 'escape') & (actual == 'capture'))[0]
        indices = sorted(indices, key=lambda index: (-margin[index], index))
        candidates.extend((model_id, int(index), 'false_escape') for index in indices)
    if not candidates:
        for model_id in models:
            margin, predicted = predictions[model_id]
            indices = np.where(predicted != actual)[0]
            if len(indices):
                index = min(indices, key=lambda index: (abs(margin[index]), index))
                candidates.append((model_id, int(index), 'disagreement'))
                break
    if not candidates:
        candidates = [(next(iter(models)), 0, 'ordinary_flight')]
    for model_id, index, kind in candidates:
        model = models[model_id]
        true_trace = physics.trace(float(energy[index]), float(momentum[index]))
        model_trace = physics.trace(float(energy[index]), float(momentum[index]),
                                    potential_fn=model.potential, derivative_fn=model.derivative)
        prediction = str(predictions[model_id][1][index])
        if true_trace['outcome'] != actual[index] or model_trace['outcome'] != prediction:
            discrepancies.append({'model_id': model_id, 'trial_id': index,
                                  'prediction': prediction, 'model_trace': model_trace['outcome'],
                                  'actual': str(actual[index]), 'true_trace': true_trace['outcome']})
            continue
        tight = physics.trace(float(energy[index]), float(momentum[index]), rtol=1e-11)
        if tight['outcome'] != true_trace['outcome']:
            raise ValueError('Showcase exact outcome changes at tighter tolerance.')
        difference = abs(tight['diagnostics']['terminal_time'] - true_trace['diagnostics']['terminal_time'])
        selection = {'model_id': model_id, 'trial_id': index, 'kind': kind,
                     'energy': float(energy[index]), 'angular_momentum': float(momentum[index]),
                     'margin': float(predictions[model_id][0][index]), 'prediction': prediction,
                     'actual': str(actual[index]), 'trace_discrepancies': discrepancies,
                     'exact_tighter_tolerance_terminal_time_difference': float(difference),
                     'true_energy_drift': true_trace['energy_drift'],
                     'model_energy_drift': model_trace['energy_drift']}
        return {'energy': float(energy[index]), 'angular_momentum': float(momentum[index]),
                'model_id': model_id, 'prediction': prediction, 'actual': str(actual[index]),
                'true_trace': true_trace, 'model_trace': model_trace}, selection
    raise ValueError('All showcase candidates disagreed with numerical traces; inspect saved metrics.')


def create_figures(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output = RESULTS / 'figures'
    output.mkdir(exist_ok=True)
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    for size, color in [('small', '#d59048'), ('large', '#507b99')]:
        metrics = [metric for metric in summary['model_metrics'] if metric['size'] == size]
        for axis, distribution in zip(axes, ('nominal', 'stress')):
            axis.plot(SEEDS, [100 * metric['distributions'][distribution]['false_escape_rate']
                             for metric in metrics], 'o-', label=size, color=color)
            axis.set_title(distribution.capitalize())
            axis.set_xlabel('Training seed')
            axis.set_ylabel('False escapes / all flights (%)')
            axis.set_ylim(bottom=0); axis.legend(); axis.grid(alpha=.2)
    figure.tight_layout(); figure.savefig(output / 'false-escapes.png', dpi=160); plt.close(figure)
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    for size, color in [('small', '#d59048'), ('large', '#507b99')]:
        metrics = [metric for metric in summary['model_metrics'] if metric['size'] == size]
        for axis, key in zip(axes, ('potential_rmse', 'acceleration_rmse')):
            axis.semilogy(SEEDS, [metric[key] for metric in metrics], 'o-', label=size, color=color)
            axis.set_xlabel('Training seed'); axis.set_ylabel(key.replace('_', ' '))
            axis.legend(); axis.grid(alpha=.2)
    figure.tight_layout(); figure.savefig(output / 'validation-errors.png', dpi=160); plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true', help='Separate development seed 97, without final test labels.')
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    inputs, digest = freeze_tests()
    if args.smoke:
        metrics = []
        for size in SIZES:
            model, metric = fit(size, 97, development=True)
            momentum = np.linspace(3.5, 6.3, 129)
            coarse = model.barrier(momentum, grid_points=256)
            fine = model.barrier(momentum, grid_points=1024)
            difference = float(np.max(abs(coarse - fine)))
            if difference > 1e-8:
                raise ValueError('Development barrier grid check failed.')
            metric['barrier_resolution_check'] = {'momentum_count': 129, 'grid_points': [256, 1024],
                                                  'max_absolute_difference': difference}
            data_path = RESULTS / 'development' / f'{size}-97.npz'
            metric['observations_sha256'] = hashlib.sha256(data_path.read_bytes()).hexdigest()
            metrics.append(metric)
        save_json(RESULTS / 'development' / 'smoke.json',
                  {'seed': 97, 'optimizer': OPTIMIZER, 'metrics': metrics, 'environment': environment(),
                   'final_test_sha256': digest,
                   'decision': 'Use this fixed optimizer budget. Record iteration-limit warnings instead of tuning on test labels.'})
    else:
        summary = full_run(inputs, digest)
        print(json.dumps({'models': len(summary['model_metrics']), 'rows': 44000,
                          'selected_case': summary['selected_case']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
