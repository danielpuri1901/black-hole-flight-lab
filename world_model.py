"""Portable tanh world models and launch decisions from their potential barriers."""
import json
from pathlib import Path

import numpy as np

BOUNDARY_TOLERANCE = 1e-10


def export_model(estimator, feature_scaler, target_scaler, metadata):
    return {
        'weights': [weight.tolist() for weight in estimator.coefs_],
        'biases': [bias.tolist() for bias in estimator.intercepts_],
        'feature_mean': feature_scaler.mean_.tolist(),
        'feature_scale': feature_scaler.scale_.tolist(),
        'target_mean': float(target_scaler.mean_[0]),
        'target_scale': float(target_scaler.scale_[0]),
        'metadata': metadata,
    }


def load_model(path):
    return WorldModel(json.loads(Path(path).read_text()))


class WorldModel:
    def __init__(self, data):
        self.weights = [np.asarray(weight, dtype=float) for weight in data['weights']]
        self.biases = [np.asarray(bias, dtype=float) for bias in data['biases']]
        self.feature_mean = np.asarray(data['feature_mean'])
        self.feature_scale = np.asarray(data['feature_scale'])
        self.target_mean = data['target_mean']
        self.target_scale = data['target_scale']
        self.metadata = data.get('metadata', {})

    def _forward(self, radius, angular_momentum, derivative=False):
        radius, angular_momentum = np.broadcast_arrays(radius, angular_momentum)
        shape = radius.shape
        r = radius.ravel()
        if np.any(r <= 0) or not np.all(np.isfinite(r)):
            raise ValueError('Radius must be positive and finite.')
        activation = (np.column_stack((1 / r, angular_momentum.ravel()))
                      - self.feature_mean) / self.feature_scale
        if derivative:
            slope = np.column_stack((-1 / r**2 / self.feature_scale[0], np.zeros(len(r))))
        for weight, bias in zip(self.weights[:-1], self.biases[:-1]):
            activation = np.tanh(activation @ weight + bias)
            if derivative:
                slope = (slope @ weight) * (1 - activation**2)
        output = ((slope if derivative else activation) @ self.weights[-1]).ravel()
        output *= self.target_scale
        if not derivative:
            output += float(self.biases[-1][0]) * self.target_scale + self.target_mean
        output = output.reshape(shape)
        return float(output) if not shape else output

    def potential(self, radius, angular_momentum):
        return self._forward(radius, angular_momentum)

    def derivative(self, radius, angular_momentum):
        return self._forward(radius, angular_momentum, derivative=True)

    def barrier(self, angular_momentum, r0=30., grid_points=256):
        """Find the highest inward barrier, including endpoints and sampled grid maxima.

        The finite grid brackets sampled local maxima before golden refinement.
        This avoids refining only one sampled peak when two peaks nearly tie.
        """
        angular_momentum = np.asarray(angular_momentum, dtype=float)
        shape = angular_momentum.shape
        momentum = angular_momentum.ravel()
        result = np.empty(len(momentum))
        grid = np.geomspace(2.001, r0, grid_points)
        for start in range(0, len(momentum), 128):
            values = momentum[start:start + 128]
            potential = self.potential(grid[None, :], values[:, None])
            best = np.maximum(potential[:, 0], potential[:, -1])
            rows, columns = np.where((potential[:, 1:-1] >= potential[:, :-2])
                                     & (potential[:, 1:-1] >= potential[:, 2:]))
            if len(rows):
                columns += 1
                left, right = grid[columns - 1].copy(), grid[columns + 1].copy()
                phi = (np.sqrt(5) - 1) / 2
                a, b = right - phi * (right - left), left + phi * (right - left)
                fa, fb = self.potential(a, values[rows]), self.potential(b, values[rows])
                for _ in range(36):
                    choose_left = fa >= fb
                    right = np.where(choose_left, b, right)
                    left = np.where(choose_left, left, a)
                    a = right - phi * (right - left)
                    b = left + phi * (right - left)
                    fa, fb = self.potential(a, values[rows]), self.potential(b, values[rows])
                np.maximum.at(best, rows, np.maximum(fa, fb))
            result[start:start + len(values)] = best
        return float(result[0]) if not shape else result.reshape(shape)

    def margin(self, energy, angular_momentum, r0=30.):
        from physics import potential
        initial_velocity_squared = np.asarray(energy)**2 - potential(r0, angular_momentum)
        return (self.barrier(angular_momentum, r0)
                - self.potential(r0, angular_momentum) - initial_velocity_squared)

    def predict_outcome(self, energy, angular_momentum, r0=30.):
        from physics import potential
        if energy**2 < potential(r0, angular_momentum):
            raise ValueError('Initial radial velocity is not real.')
        margin = float(self.margin(energy, angular_momentum, r0))
        return 'unresolved' if abs(margin) <= BOUNDARY_TOLERANCE else ('escape' if margin > 0 else 'capture')


def analytic_margin(energy, angular_momentum, r0=30.):
    from physics import potential
    energy, angular_momentum = np.broadcast_arrays(energy, angular_momentum)
    squared = angular_momentum**2
    discriminant = squared**2 - 12 * squared
    radius = (squared - np.sqrt(np.maximum(discriminant, 0))) / 2
    inside = (discriminant >= 0) & (radius >= 2.001) & (radius <= r0)
    maximum = np.maximum(potential(2.001, angular_momentum), potential(r0, angular_momentum))
    maximum = np.maximum(maximum, np.where(inside, potential(np.maximum(radius, 2.001), angular_momentum), -np.inf))
    return maximum - energy**2


def analytic_prediction(energy, angular_momentum, r0=30.):
    from physics import potential
    if energy**2 < potential(r0, angular_momentum):
        raise ValueError('Initial radial velocity is not real.')
    margin = float(analytic_margin(energy, angular_momentum, r0))
    return 'unresolved' if abs(margin) <= BOUNDARY_TOLERANCE else ('escape' if margin > 0 else 'capture')
