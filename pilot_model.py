"""NumPy inference for the exported action autoencoder and diffusion pilot."""

from pathlib import Path
import json
import numpy as np


class PilotModel:
    def __init__(self, metadata, weights):
        self.metadata = metadata
        self.weights = weights
        self.context_mean = np.asarray(metadata['context_mean'], dtype=np.float64)
        self.context_std = np.asarray(metadata['context_std'], dtype=np.float64)
        self.latent_mean = np.asarray(metadata['latent_mean'], dtype=np.float64)
        self.latent_std = np.asarray(metadata['latent_std'], dtype=np.float64)
        self.betas = np.asarray(weights['betas'], dtype=np.float64)
        self.alpha_bar = np.cumprod(1 - self.betas)
        if metadata.get('format_version') != 1:
            raise ValueError('Unsupported pilot model format.')
        for value, shape in ((self.context_mean, (6,)), (self.context_std, (6,)),
                             (self.latent_mean, (8,)), (self.latent_std, (8,))):
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError('Invalid model scaling arrays.')
        if (self.context_std <= 0).any() or (self.latent_std <= 0).any():
            raise ValueError('Model scales must be positive.')
        if self.betas.shape != (32,) or not ((self.betas > 0) & (self.betas < 1)).all():
            raise ValueError('Expected 32 finite diffusion betas between zero and one.')
        self._validate_weights()

    def _validate_weights(self):
        expected = {'diffusion.position': (4, 32)}
        linear = {'ae.encoder.0': (24, 64), 'ae.encoder.2': (64, 8),
                  'ae.decoder.0': (8, 64), 'ae.decoder.2': (64, 24),
                  'diffusion.token': (2, 32), 'diffusion.conditioning.0': (9, 64),
                  'diffusion.conditioning.2': (64, 32), 'diffusion.output': (32, 2)}
        for block in range(2):
            name = f'diffusion.blocks.{block}'
            linear.update({f'{name}.qkv': (32, 96), f'{name}.projection': (32, 32),
                           f'{name}.mlp.0': (32, 64), f'{name}.mlp.2': (64, 32)})
            for norm in ('ln1', 'ln2'):
                expected[f'{name}.{norm}.weight'] = (32,)
                expected[f'{name}.{norm}.bias'] = (32,)
        for name, (inputs, outputs) in linear.items():
            expected[name + '.weight'] = (outputs, inputs)
            expected[name + '.bias'] = (outputs,)
        for name, shape in expected.items():
            if name not in self.weights or self.weights[name].shape != shape:
                raise ValueError(f'Missing or incorrectly shaped pilot weight: {name}')
            if not np.isfinite(self.weights[name]).all():
                raise ValueError(f'Non-finite pilot weight: {name}')

    def _linear(self, value, name):
        # Fixed reduction order preserves the first plan across candidate counts.
        return np.einsum('...i,oi->...o', value, self.weights[name + '.weight'],
                         optimize=False) + self.weights[name + '.bias']

    def _norm(self, value, name):
        mean = value.mean(axis=-1, keepdims=True)
        variance = ((value - mean)**2).mean(axis=-1, keepdims=True)
        return ((value - mean) / np.sqrt(variance + 1e-5)
                * self.weights[name + '.weight'] + self.weights[name + '.bias'])

    @staticmethod
    def _gelu(value):
        return .5 * value * (1 + np.tanh(np.sqrt(2 / np.pi)
                                        * (value + .044715 * value**3)))

    def encode(self, plans):
        plans = np.asarray(plans, dtype=np.float64)
        single = plans.ndim == 2
        if single:
            plans = plans[None]
        if plans.ndim != 3 or plans.shape[1:] != (12, 2) or not np.isfinite(plans).all():
            raise ValueError('Plans must have finite shape (N, 12, 2).')
        hidden = np.tanh(self._linear(plans.reshape(-1, 24), 'ae.encoder.0'))
        latent = np.tanh(self._linear(hidden, 'ae.encoder.2'))
        return latent[0] if single else latent

    def decode(self, latent):
        latent = np.asarray(latent, dtype=np.float64)
        single = latent.ndim == 1
        if single:
            latent = latent[None]
        if latent.ndim != 2 or latent.shape[1] != 8 or not np.isfinite(latent).all():
            raise ValueError('Latents must have finite shape (N, 8).')
        hidden = np.tanh(self._linear(latent, 'ae.decoder.0'))
        plans = np.tanh(self._linear(hidden, 'ae.decoder.2')).reshape(-1, 12, 2)
        plans /= np.maximum(1, np.linalg.norm(plans, axis=-1, keepdims=True))
        return plans[0] if single else plans

    def denoise(self, latent, context, timestep):
        """Predict diffusion noise; context is raw, latent is standardized."""
        latent = np.asarray(latent, dtype=np.float64)
        single = latent.ndim == 1
        if single:
            latent = latent[None]
        if latent.ndim != 2 or latent.shape[1] != 8 or not np.isfinite(latent).all():
            raise ValueError('Noisy latents must have finite shape (N, 8).')
        context = np.asarray(context, dtype=np.float64)
        if context.shape == (6,):
            context = np.broadcast_to(context, (len(latent), 6))
        if context.shape != (len(latent), 6) or not np.isfinite(context).all():
            raise ValueError('Context must have finite shape (6,) or (N, 6).')
        timestep = np.broadcast_to(np.asarray(timestep, dtype=np.float64), (len(latent),))
        if not np.isfinite(timestep).all() or ((timestep < 0) | (timestep > 31)).any():
            raise ValueError('Diffusion timestep must be between 0 and 31.')
        fraction = timestep / 31
        time_features = np.column_stack((fraction, np.sin(np.pi * fraction),
                                        np.cos(np.pi * fraction)))
        condition = np.concatenate(((context - self.context_mean) / self.context_std,
                                    time_features), axis=1)
        condition = self._linear(np.tanh(self._linear(condition, 'diffusion.conditioning.0')),
                                 'diffusion.conditioning.2')
        tokens = (self._linear(latent.reshape(-1, 4, 2), 'diffusion.token')
                  + self.weights['diffusion.position'] + condition[:, None, :])
        for block in range(2):
            name = f'diffusion.blocks.{block}'
            qkv = self._linear(self._norm(tokens, name + '.ln1'), name + '.qkv')
            qkv = qkv.reshape(-1, 4, 3, 2, 16).transpose(2, 0, 3, 1, 4)
            query, key, value = qkv
            score = query @ key.swapaxes(-1, -2) / 4
            score -= score.max(axis=-1, keepdims=True)
            attention = np.exp(score)
            attention /= attention.sum(axis=-1, keepdims=True)
            attended = (attention @ value).transpose(0, 2, 1, 3).reshape(-1, 4, 32)
            tokens += self._linear(attended, name + '.projection')
            hidden = self._gelu(self._linear(self._norm(tokens, name + '.ln2'), name + '.mlp.0'))
            tokens += self._linear(hidden, name + '.mlp.2')
        noise = self._linear(tokens, 'diffusion.output').reshape(-1, 8)
        return noise[0] if single else noise

    def sample(self, context, count=16, seed=0):
        """Return bounded normalized action plans with shape (count, 12, 2)."""
        if isinstance(count, bool) or not isinstance(count, (int, np.integer)) or not 1 <= count <= 4096:
            raise ValueError('Candidate count must be an integer between 1 and 4096.')
        context = np.asarray(context, dtype=np.float64)
        if context.shape != (6,) or not np.isfinite(context).all():
            raise ValueError('Supply six finite context features.')
        latent = np.random.default_rng(seed).standard_normal((count, 8))
        steps = int(self.metadata.get('sampling_steps', 16))
        if not 1 <= steps <= 32:
            raise ValueError('Sampling steps must be between 1 and 32.')
        schedule = np.rint(np.linspace(31, 0, steps)).astype(int)
        for index, timestep in enumerate(schedule):
            noise = self.denoise(latent, context, timestep)
            current = self.alpha_bar[timestep]
            predicted_clean = (latent - np.sqrt(1 - current) * noise) / np.sqrt(current)
            predicted_clean = np.clip(predicted_clean, (-1 - self.latent_mean) / self.latent_std,
                                      (1 - self.latent_mean) / self.latent_std)
            previous = self.alpha_bar[schedule[index + 1]] if index + 1 < len(schedule) else 1.
            latent = np.sqrt(previous) * predicted_clean + np.sqrt(1 - previous) * noise
        plans = self.decode(latent * self.latent_std + self.latent_mean)
        if not np.isfinite(plans).all():
            raise FloatingPointError('The learned sampler produced a non-finite plan.')
        return plans


def load_model(path):
    """Load a model directory or its model.json, without pickle or PyTorch."""
    path = Path(path)
    metadata_path = path / 'model.json' if path.is_dir() else path
    metadata = json.loads(metadata_path.read_text())
    with np.load(metadata_path.parent / metadata['weights_file'], allow_pickle=False) as archive:
        weights = {name: np.asarray(archive[name], dtype=np.float64) for name in archive.files}
    return PilotModel(metadata, weights)
