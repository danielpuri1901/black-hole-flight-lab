"""Posthoc analytic controls, separate from the frozen neural experiment."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

import physics
from world_model import BOUNDARY_TOLERANCE, analytic_margin

ROOT = Path(__file__).resolve().parent
ENERGY = 1.05
WIDTH = 0.5
EPSILONS = 10.0 ** -np.arange(3, 9)
TOLERANCES = (1e-11, 1e-13)


def bump(radius, center, width=WIDTH):
    """Compact C2 bump and its radial derivative, with exact support."""
    z = (np.asarray(radius, dtype=float) - center) / width
    inside = np.abs(z) < 1
    base = np.maximum(1 - z * z, 0)
    return np.where(inside, base**3, 0), np.where(inside, -6 * z * base**2 / width, 0)


def controlled_world(epsilon):
    critical = float(physics.critical_angular_momentum(ENERGY))
    momentum = brentq(lambda value: float(analytic_margin(ENERGY, value)) + epsilon / 2,
                     np.sqrt(12) + .01, critical, xtol=1e-14)
    squared = momentum * momentum
    center = (squared - np.sqrt(squared * squared - 12 * squared)) / 2

    def potential(radius, angular_momentum):
        return physics.potential(radius, angular_momentum) + epsilon * bump(radius, center)[0]

    def derivative(radius, angular_momentum):
        return physics.potential_derivative(radius, angular_momentum) + epsilon * bump(radius, center)[1]

    return momentum, center, potential, derivative


def trace_summary(trace):
    return {'outcome': trace['outcome'], 'energy_drift': trace['energy_drift'],
            'diagnostics': trace['diagnostics']}


def perturbation_controls():
    rows = []
    for epsilon in EPSILONS:
        momentum, center, potential, derivative = controlled_world(float(epsilon))
        physical_margin = float(analytic_margin(ENERGY, momentum))
        model_margin = float(potential(center, momentum) - potential(30., momentum)
                             - (ENERGY**2 - physics.potential(30., momentum)))
        runs = []
        for tolerance in TOLERANCES:
            physical = physics.trace(ENERGY, momentum, rtol=tolerance, max_points=500)
            perturbed = physics.trace(ENERGY, momentum, potential_fn=potential,
                                     derivative_fn=derivative, rtol=tolerance, max_points=500)
            runs.append({'rtol': tolerance, 'physical': trace_summary(physical),
                         'perturbed': trace_summary(perturbed)})
        # This resolution rule is diagnostic, not a rigorous integration error bound.
        resolved = (all(run['physical']['outcome'] == 'capture'
                        and run['perturbed']['outcome'] == 'escape'
                        and max(run['physical']['energy_drift'], run['perturbed']['energy_drift'])
                        < epsilon / 200 for run in runs)
                    and physical_margin < 0 < model_margin)
        rows.append({'epsilon': float(epsilon), 'energy': ENERGY, 'angular_momentum': momentum,
                     'critical_angular_momentum': float(physics.critical_angular_momentum(ENERGY)),
                     'center': float(center), 'width': WIDTH,
                     'potential_sup_error': float(epsilon),
                     'acceleration_sup_error': float(48 * epsilon / (25 * np.sqrt(5) * WIDTH)),
                     'physical_margin': physical_margin, 'perturbed_margin': model_margin,
                     'target_physical_margin': float(-epsilon / 2),
                     'target_perturbed_margin': float(epsilon / 2),
                     'root_margin_residual': float(physical_margin + epsilon / 2),
                     'physical_oracle': physics.outcome(ENERGY, momentum),
                     'analytic_perturbed_outcome': 'escape' if model_margin > 0 else 'unresolved',
                     'numerical_status': 'confirmed' if resolved else 'unresolved',
                     'traces': runs})
    return rows


def gauge_controls():
    rows = []
    critical = float(physics.critical_angular_momentum(ENERGY))
    for factor in (.99, 1.01):
        momentum = critical * factor
        physical = physics.trace(ENERGY, momentum, rtol=1e-12, max_points=500)
        for shift in (-.1, .1):
            shifted = physics.trace(ENERGY, momentum,
                                   potential_fn=lambda r, L: physics.potential(r, L) + shift,
                                   derivative_fn=physics.potential_derivative,
                                   rtol=1e-12, max_points=500)
            margin = float(analytic_margin(ENERGY, momentum))
            shifted_margin = float((margin + ENERGY**2 + shift)
                                   - (physics.potential(30., momentum) + shift)
                                   - (ENERGY**2 - physics.potential(30., momentum)))
            rows.append({'energy': ENERGY, 'angular_momentum': momentum, 'constant': shift,
                         'potential_sup_error': abs(shift), 'acceleration_sup_error': 0.,
                         'physical_margin': margin, 'shifted_margin': shifted_margin,
                         'physical': trace_summary(physical), 'shifted': trace_summary(shifted),
                         'max_point_difference': float(np.max(np.abs(
                             np.asarray(physical['points']) - np.asarray(shifted['points']))))})
    return rows


def features(radius, momentum):
    radius, momentum = np.broadcast_arrays(radius, momentum)
    return np.stack((np.ones_like(radius), 1 / radius,
                     momentum**2 / radius**2, momentum**2 / radius**3), axis=-1)


def basis_barrier(coefficients, momentum, r0=30.):
    """Find all extrema of the known four-feature basis, without a grid."""
    momentum = np.asarray(momentum, dtype=float)
    _, c1, c2, c3 = coefficients
    a, b, c = -c1, -2 * c2 * momentum**2, -3 * c3 * momentum**2
    if a == 0:
        raise ValueError('This control expects a nonzero inverse-radius coefficient.')
    discriminant = b * b - 4 * a * c
    maximum = np.maximum(features(physics.CAPTURE_RADIUS, momentum) @ coefficients,
                         features(r0, momentum) @ coefficients)
    for sign in (-1, 1):
        radius = (-b + sign * np.sqrt(np.maximum(discriminant, 0))) / (2 * a)
        inside = (discriminant >= 0) & (radius >= physics.CAPTURE_RADIUS) & (radius <= r0)
        safe_radius = np.where(inside, radius, r0)
        maximum = np.maximum(maximum, np.where(inside,
                             features(safe_radius, momentum) @ coefficients, -np.inf))
    return maximum


def basis_control():
    source = ROOT / 'results/observations/small-11.npz'
    with np.load(source) as observations:
        design = features(observations['radius'], observations['angular_momentum'])
        coefficients, _, rank, singular = np.linalg.lstsq(design, observations['potential'], rcond=None)
        training_error = design @ coefficients - observations['potential']
        validation_error = (features(observations['validation_radius'],
                                    observations['validation_angular_momentum']) @ coefficients
                            - observations['validation_potential'])
    frozen = ROOT / 'results/test_inputs.json'
    inputs = json.loads(frozen.read_text())
    scores = {}
    for distribution in ('nominal', 'stress'):
        energy, momentum = np.asarray(inputs[distribution]).T
        margin = (basis_barrier(coefficients, momentum)
                  - features(30., momentum) @ coefficients
                  - (energy**2 - physics.potential(30., momentum)))
        predicted = np.where(abs(margin) <= BOUNDARY_TOLERANCE, 'unresolved',
                             np.where(margin > 0, 'escape', 'capture'))
        actual = np.asarray([physics.outcome(E, L) for E, L in zip(energy, momentum)])
        scores[distribution] = {'count': len(energy),
                                'agreements': int(np.sum(predicted == actual)),
                                'false_escapes': int(np.sum((predicted == 'escape') & (actual == 'capture'))),
                                'false_captures': int(np.sum((predicted == 'capture') & (actual == 'escape'))),
                                'unresolved': int(np.sum(predicted == 'unresolved')),
                                'max_margin_error': float(np.max(abs(margin - analytic_margin(energy, momentum))))}
    return {'status': 'posthoc privileged known-physics basis; not discovered',
            'columns': ['1', '1/r', 'L^2/r^2', 'L^2/r^3'],
            'expected_coefficients': [1., -2., 1., -2.], 'coefficients': coefficients.tolist(),
            'rank': int(rank), 'design_condition_number': float(singular[0] / singular[-1]),
            'training_count': len(training_error), 'validation_count': len(validation_error),
            'training_rmse': float(np.sqrt(np.mean(training_error**2))),
            'training_max_error': float(np.max(abs(training_error))),
            'validation_rmse': float(np.sqrt(np.mean(validation_error**2))),
            'validation_max_error': float(np.max(abs(validation_error))),
            'observations_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'frozen_inputs_sha256': hashlib.sha256(frozen.read_bytes()).hexdigest(),
            'distributions': scores}


def selective_policy_control():
    """Reject the saved uncertainty flag without refitting or tuning its threshold."""
    source = ROOT / 'results/trials.csv'
    with source.open() as handle:
        rows = [row for row in csv.DictReader(handle) if row['model_id'] != 'analytic']
    models = {}
    for model_id in dict.fromkeys(row['model_id'] for row in rows):
        groups = {}
        for distribution in ('nominal', 'stress'):
            group = [row for row in rows if row['model_id'] == model_id
                     and row['distribution'] == distribution]
            accepted = [row for row in group if row['prediction'] == 'escape'
                        and row['uncertain'] == 'False']
            true_escapes = sum(row['actual'] == 'escape' for row in group)
            correct = sum(row['actual'] == 'escape' for row in accepted)
            groups[distribution] = {'count': len(group), 'accepted': len(accepted),
                                    'accepted_true_escapes': correct,
                                    'false_escapes': sum(row['actual'] == 'capture' for row in accepted),
                                    'accepted_unresolved_truth': sum(row['actual'] == 'unresolved' for row in accepted),
                                    'rejected_uncertain_escapes': sum(row['prediction'] == 'escape'
                                                                    and row['uncertain'] == 'True' for row in group),
                                    'true_escapes': true_escapes,
                                    'missed_true_escapes': true_escapes - correct,
                                    'coverage': len(accepted) / len(group),
                                    'true_escape_recall': correct / true_escapes}
        models[model_id] = groups
    averages = {size: {distribution: float(np.mean([
        groups[distribution]['coverage'] for name, groups in models.items() if name.startswith(size + '-')]))
        for distribution in ('nominal', 'stress')} for size in ('small', 'large')}
    witness = json.loads((ROOT / 'results/showcase.json').read_text())
    selected = [row for row in rows if row['model_id'] == witness['model_id']
                and float(row['energy']) == witness['energy']
                and float(row['angular_momentum']) == witness['angular_momentum']]
    if len(selected) != 1:
        raise ValueError('The saved showcase must identify exactly one frozen trial.')
    return {'status': 'posthoc policy analysis using the predeclared saved uncertainty flag',
            'rule': 'Accept only prediction=escape and uncertain=False; otherwise abstain.',
            'threshold': 'Existing twice validation 95th-percentile absolute potential residual; no retuning.',
            'certificate': False, 'trials_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'models': models, 'mean_coverage_by_architecture': averages,
            'showcase': {'model_id': witness['model_id'], 'trial_id': int(selected[0]['trial_id']),
                         'flagged_uncertain': selected[0]['uncertain'] == 'True',
                         'accepted_by_selective_policy': selected[0]['prediction'] == 'escape'
                         and selected[0]['uncertain'] == 'False'}}


def plot_controls(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    epsilon = np.asarray([row['epsilon'] for row in rows])
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    axes[0, 0].loglog(epsilon, epsilon, 'o-', label='potential supremum')
    axes[0, 0].loglog(epsilon, [row['acceleration_sup_error'] for row in rows], 's-', label='acceleration supremum')
    axes[0, 0].set(title='Exact analytic error bounds', xlabel='epsilon', ylabel='supremum error')
    axes[0, 0].legend()
    axes[0, 1].plot(epsilon, [row['physical_margin'] for row in rows], 'o-', label='physical: capture')
    axes[0, 1].plot(epsilon, [row['perturbed_margin'] for row in rows], 's-', label='perturbed: escape')
    axes[0, 1].set_xscale('log')
    axes[0, 1].set_yscale('symlog', linthresh=1e-9)
    axes[0, 1].axhline(0, color='gray', linewidth=.8)
    axes[0, 1].set(title='Opposite fates for moving boundary launches', xlabel='epsilon', ylabel='barrier margin')
    axes[0, 1].legend()
    for world, marker in [('physical', 'o'), ('perturbed', 's')]:
        for index, tolerance in enumerate(TOLERANCES):
            axes[1, 0].loglog(epsilon, [row['traces'][index][world]['energy_drift'] for row in rows],
                              marker + ('-' if index else '--'), label=f'{world}, rtol={tolerance:g}')
    axes[1, 0].loglog(epsilon, epsilon / 200, ':', color='black', label='diagnostic threshold: epsilon/200')
    axes[1, 0].set(title='Measured drift in each world invariant', xlabel='epsilon', ylabel='max sampled energy drift')
    axes[1, 0].legend(fontsize=8)
    momentum, center, potential, _ = controlled_world(float(epsilon[0]))
    radius = np.linspace(center - .4 * WIDTH, center + .4 * WIDTH, 500)
    axes[1, 1].plot(radius, physics.potential(radius, momentum) - ENERGY**2, label='physical V - E squared')
    axes[1, 1].plot(radius, potential(radius, momentum) - ENERGY**2, label='perturbed V - E squared')
    axes[1, 1].axhline(0, color='gray', linewidth=.8)
    axes[1, 1].set(title='Local barrier, epsilon=0.001', xlabel='radius', ylabel='potential minus energy squared')
    axes[1, 1].legend(fontsize=8)
    for axis in axes.flat:
        axis.grid(alpha=.2)
    fig.suptitle('Posthoc controls: vanishing errors, persistent worst-case fate reversal')
    destination = ROOT / 'results/figures/controlled-errors.png'
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def main():
    rows = perturbation_controls()
    payload = {'schema_version': 1, 'protocol_status': 'posthoc after frozen neural experiment',
               'launch_radius': 30., 'capture_radius': physics.CAPTURE_RADIUS,
               'numerical_resolution_rule': ('Both rtol=1e-11 and 1e-13 give physical capture and perturbed escape; '
                                            'all measured invariant drifts < epsilon/200; opposite analytic margins. '
                                            'Diagnostic only, not a rigorous numerical error certificate.'),
               'perturbation': rows, 'gauge': gauge_controls(), 'basis': basis_control(),
               'selective_policy': selective_policy_control()}
    path = ROOT / 'results/controls.json'
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + '\n')
    plot_controls(rows)
    print(json.dumps({'confirmed_perturbations': sum(row['numerical_status'] == 'confirmed' for row in rows),
                      'total_perturbations': len(rows), 'basis': payload['basis']}, indent=2))


if __name__ == '__main__':
    main()
