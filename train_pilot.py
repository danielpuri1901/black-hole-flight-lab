"""Train and export a compact action autoencoder and conditional diffusion pilot.

PyTorch is imported only by main. NumPy inference lives in pilot_model.py.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import time
import numpy as np


def cosine_betas(steps=32, offset=.008):
    grid = np.linspace(0, 1, steps + 1)
    cumulative = np.cos((grid + offset) / (1 + offset) * math.pi / 2)**2
    cumulative /= cumulative[0]
    return np.clip(1 - cumulative[1:] / cumulative[:-1], 1e-8, .999).astype(np.float32)


def build_torch_models(torch):
    nn = torch.nn

    class ActionAutoencoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = nn.Sequential(nn.Linear(24, 64), nn.Tanh(), nn.Linear(64, 8), nn.Tanh())
            self.decoder = nn.Sequential(nn.Linear(8, 64), nn.Tanh(), nn.Linear(64, 24), nn.Tanh())

        def encode(self, plans):
            return self.encoder(plans.reshape(-1, 24))

        def decode(self, latent):
            plans = self.decoder(latent).reshape(-1, 12, 2)
            return plans / torch.linalg.vector_norm(plans, dim=-1, keepdim=True).clamp_min(1)

        def forward(self, plans):
            return self.decode(self.encode(plans))

    class TransformerBlock(nn.Module):
        def __init__(self):
            super().__init__()
            self.ln1 = nn.LayerNorm(32, eps=1e-5)
            self.qkv = nn.Linear(32, 96)
            self.projection = nn.Linear(32, 32)
            self.ln2 = nn.LayerNorm(32, eps=1e-5)
            self.mlp = nn.Sequential(nn.Linear(32, 64), nn.GELU(approximate='tanh'), nn.Linear(64, 32))

        def forward(self, tokens):
            qkv = self.qkv(self.ln1(tokens)).reshape(-1, 4, 3, 2, 16).permute(2, 0, 3, 1, 4)
            query, key, value = qkv.unbind(0)
            attention = torch.softmax(query @ key.transpose(-1, -2) / 4, dim=-1)
            attended = (attention @ value).transpose(1, 2).reshape(-1, 4, 32)
            tokens = tokens + self.projection(attended)
            return tokens + self.mlp(self.ln2(tokens))

    class DiffusionTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.token = nn.Linear(2, 32)
            self.position = nn.Parameter(torch.randn(4, 32) * .02)
            self.conditioning = nn.Sequential(nn.Linear(9, 64), nn.Tanh(), nn.Linear(64, 32))
            self.blocks = nn.ModuleList([TransformerBlock(), TransformerBlock()])
            self.output = nn.Linear(32, 2)

        def forward(self, latent, normalized_context, timestep):
            fraction = timestep.to(latent.dtype) / 31
            time_features = torch.stack((fraction, torch.sin(math.pi * fraction),
                                         torch.cos(math.pi * fraction)), dim=-1)
            condition = self.conditioning(torch.cat((normalized_context, time_features), dim=-1))
            tokens = self.token(latent.reshape(-1, 4, 2)) + self.position + condition[:, None, :]
            for block in self.blocks:
                tokens = block(tokens)
            return self.output(tokens).reshape(-1, 8)

    return ActionAutoencoder(), DiffusionTransformer()


def read_training_data(path):
    with np.load(path, allow_pickle=False) as data:
        contexts = np.asarray(data['contexts'], dtype=np.float32)
        plans = np.asarray(data['plans'], dtype=np.float32)
        split = np.asarray(data['split'])
    if contexts.ndim != 2 or contexts.shape[1] != 6 or plans.shape != (len(contexts), 12, 2):
        raise ValueError('Expected contexts (N,6) and plans (N,12,2).')
    if split.shape != (len(contexts),) or not np.isin(split, [0, 1]).all():
        raise ValueError('The split must contain only 0 for train and 1 for validation.')
    if not np.isfinite(contexts).all() or not np.isfinite(plans).all():
        raise ValueError('Training arrays must be finite.')
    if np.linalg.norm(plans, axis=-1).max() > 1 + 1e-6:
        raise ValueError('Teacher burns must have normalized magnitude at most one.')
    if (split == 0).sum() < 2 or not (split == 1).any():
        raise ValueError('Supply at least two training plans and one validation plan.')
    return contexts, plans, split


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def train(args, torch):
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    contexts, plans, split = read_training_data(args.data)
    training = split == 0
    context_mean = contexts[training].astype(np.float64).mean(0).astype(np.float32)
    context_std = contexts[training].astype(np.float64).std(0).astype(np.float32)
    context_std = np.where(context_std < 1e-6, 1., context_std).astype(np.float32)
    normalized_context = torch.from_numpy((contexts - context_mean) / context_std)
    train_context = normalized_context[training]
    validation_context = normalized_context[~training]
    train_plans = torch.from_numpy(plans[training])
    validation_plans = torch.from_numpy(plans[~training])
    autoencoder, diffusion = build_torch_models(torch)
    generator = torch.Generator().manual_seed(args.seed + 1)
    train_burn = torch.linalg.vector_norm(train_plans[:, 0], dim=-1) > .05
    validation_burn = torch.linalg.vector_norm(validation_plans[:, 0], dim=-1) > .05
    burn_indices = torch.nonzero(train_burn).flatten()
    coast_indices = torch.nonzero(~train_burn).flatten()
    balance_applied = bool(args.balanced_burns and len(burn_indices) and len(coast_indices))
    logs = []
    started = time.perf_counter()

    def sample_training_indices(count):
        if not balance_applied:
            return torch.randint(len(train_plans), (count,), generator=generator)
        burn_count = (count + 1) // 2
        indices = torch.cat((burn_indices[torch.randint(len(burn_indices), (burn_count,), generator=generator)],
                             coast_indices[torch.randint(len(coast_indices), (count - burn_count,), generator=generator)]))
        return indices[torch.randperm(count, generator=generator)]

    def group_losses(errors):
        return {'validation_burn_mse': float(errors[validation_burn].mean()) if validation_burn.any() else None,
                'validation_coast_mse': float(errors[~validation_burn].mean()) if (~validation_burn).any() else None}

    def record(stage, step, train_loss, validation_loss, groups):
        row = {'stage': stage, 'step': step, 'train_mse': float(train_loss),
               'validation_mse': float(validation_loss), 'elapsed_seconds': time.perf_counter() - started}
        row.update(groups)
        logs.append(row)
        print(json.dumps(row), flush=True)

    def copy_state(model):
        return {name: value.detach().clone() for name, value in model.state_dict().items()}

    optimizer = torch.optim.Adam(autoencoder.parameters(), lr=args.learning_rate)
    best_ae_loss = math.inf
    best_ae_state = None
    best_ae_epoch = 0
    stale = 0
    for epoch in range(1, args.ae_epochs + 1):
        autoencoder.train()
        order = sample_training_indices(len(train_plans)) if balance_applied else torch.randperm(len(train_plans), generator=generator)
        loss_sum = 0.
        for batch in order.split(args.batch_size):
            optimizer.zero_grad()
            loss = torch.nn.functional.mse_loss(autoencoder(train_plans[batch]), train_plans[batch])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(autoencoder.parameters(), 5.)
            optimizer.step()
            loss_sum += float(loss.detach()) * len(batch)
        autoencoder.eval()
        with torch.no_grad():
            validation_errors = (autoencoder(validation_plans) - validation_plans).square().mean(dim=(1, 2))
            validation_loss = float(validation_errors.mean())
        if validation_loss < best_ae_loss:
            best_ae_loss, best_ae_state, best_ae_epoch, stale = validation_loss, copy_state(autoencoder), epoch, 0
        else:
            stale += 1
        if epoch == 1 or epoch % 10 == 0 or stale >= args.patience or epoch == args.ae_epochs:
            record('autoencoder', epoch, loss_sum / len(train_plans), validation_loss, group_losses(validation_errors))
        if stale >= args.patience:
            break
    autoencoder.load_state_dict(best_ae_state)
    autoencoder.eval()
    with torch.no_grad():
        train_latent_array = autoencoder.encode(train_plans).numpy()
        validation_latent_array = autoencoder.encode(validation_plans).numpy()
        reconstructed = autoencoder(validation_plans).numpy()
    latent_mean = train_latent_array.astype(np.float64).mean(0).astype(np.float32)
    latent_std = np.maximum(train_latent_array.astype(np.float64).std(0), 1e-6).astype(np.float32)
    train_latent = torch.from_numpy((train_latent_array - latent_mean) / latent_std)
    validation_latent = torch.from_numpy((validation_latent_array - latent_mean) / latent_std)
    betas = cosine_betas()
    alpha_bar = torch.cumprod(1 - torch.from_numpy(betas), dim=0)
    validation_generator = torch.Generator().manual_seed(args.seed + 2)
    validation_times = torch.randint(0, 32, (len(validation_latent),), generator=validation_generator)
    validation_noise = torch.randn(validation_latent.shape, generator=validation_generator)
    validation_alpha = alpha_bar[validation_times, None]
    validation_noisy = (validation_alpha.sqrt() * validation_latent
                        + (1 - validation_alpha).sqrt() * validation_noise)
    optimizer = torch.optim.Adam(diffusion.parameters(), lr=args.learning_rate)
    best_diffusion_loss = math.inf
    best_diffusion_state = None
    best_diffusion_step = 0
    stale = 0
    accumulated_loss = 0.
    accumulated_steps = 0
    for step in range(1, args.diffusion_steps + 1):
        diffusion.train()
        batch = sample_training_indices(min(args.batch_size, len(train_latent)))
        times = torch.randint(0, 32, (len(batch),), generator=generator)
        noise = torch.randn((len(batch), 8), generator=generator)
        alpha = alpha_bar[times, None]
        noisy = alpha.sqrt() * train_latent[batch] + (1 - alpha).sqrt() * noise
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(diffusion(noisy, train_context[batch], times), noise)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(diffusion.parameters(), 5.)
        optimizer.step()
        accumulated_loss += float(loss.detach())
        accumulated_steps += 1
        if step == 1 or step % args.validation_every == 0 or step == args.diffusion_steps:
            diffusion.eval()
            with torch.no_grad():
                validation_errors = (diffusion(validation_noisy, validation_context, validation_times)
                                     - validation_noise).square().mean(dim=1)
                validation_loss = float(validation_errors.mean())
            if validation_loss < best_diffusion_loss:
                best_diffusion_loss, best_diffusion_state, best_diffusion_step, stale = validation_loss, copy_state(diffusion), step, 0
            else:
                stale += 1
            record('diffusion', step, accumulated_loss / accumulated_steps, validation_loss, group_losses(validation_errors))
            accumulated_loss = 0.; accumulated_steps = 0
            if stale >= args.patience:
                break
    diffusion.load_state_dict(best_diffusion_state)
    diffusion.eval()
    with torch.no_grad():
        best_diffusion_groups = group_losses((diffusion(validation_noisy, validation_context, validation_times)
                                             - validation_noise).square().mean(dim=1))
        best_ae_groups = group_losses(torch.from_numpy((reconstructed - plans[~training])**2).mean(dim=(1, 2)))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    weights = {f'ae.{name}': value.detach().numpy() for name, value in autoencoder.state_dict().items()}
    weights.update({f'diffusion.{name}': value.detach().numpy() for name, value in diffusion.state_dict().items()})
    weights['betas'] = betas
    np.savez_compressed(output / 'weights.npz', **weights)
    metadata = {
        'format_version': 1, 'weights_file': 'weights.npz', 'seed': args.seed,
        'context_features': ['r/10', 'ur', 'L/5', 'q/0.7', 'E', '1/r'],
        'context_mean': context_mean.tolist(), 'context_std': context_std.tolist(),
        'latent_mean': latent_mean.tolist(), 'latent_std': latent_std.tolist(),
        'architecture': {'plan_shape': [12, 2], 'latent_size': 8, 'ae_hidden': 64,
                         'token_count': 4, 'token_features': 2, 'width': 32,
                         'blocks': 2, 'heads': 2, 'mlp_hidden': 64, 'layer_norm_epsilon': 1e-5,
                         'activation': 'GELU tanh approximation'},
        'diffusion_schedule': {'kind': 'cosine', 'offset': .008, 'steps': 32,
                               'beta_max': .999, 'terminal_alpha_bar': float(alpha_bar[-1])},
        'sampling': 'deterministic DDIM, eta=0', 'sampling_steps': args.sample_steps,
        'clean_latent_clipping': {'space': 'standardized encoded latent',
                                  'lower': ((-1 - latent_mean) / latent_std).tolist(),
                                  'upper': ((1 - latent_mean) / latent_std).tolist(),
                                  'reason': 'The tanh encoder has exact range [-1,1] before affine scaling.'},
        'balanced_burn_sampling': {'requested': args.balanced_burns, 'applied': balance_applied,
                                   'first_burn_norm_threshold': .05, 'burn_probability': .5 if balance_applied else None,
                                   'training_burn_count': len(burn_indices), 'training_coast_count': len(coast_indices),
                                   'validation_burn_count': int(validation_burn.sum()),
                                   'validation_coast_count': int((~validation_burn).sum())},
        'training_observations': int(training.sum()), 'validation_observations': int((~training).sum()),
        'best_ae_epoch': best_ae_epoch, 'best_diffusion_step': best_diffusion_step,
        'autoencoder_validation_mse': best_ae_loss,
        'reconstruction_validation_max_burn_norm': float(np.linalg.norm(reconstructed, axis=-1).max()),
        'teacher_validation_mean_burn_norm': float(np.linalg.norm(plans[~training], axis=-1).mean()),
        'reconstruction_validation_mean_burn_norm': float(np.linalg.norm(reconstructed, axis=-1).mean()),
        'diffusion_validation_noise_mse': best_diffusion_loss,
        'autoencoder_validation_groups': best_ae_groups,
        'diffusion_validation_groups': best_diffusion_groups,
        'train_seconds': time.perf_counter() - started,
        'parameters': {'autoencoder': sum(p.numel() for p in autoencoder.parameters()),
                       'diffusion': sum(p.numel() for p in diffusion.parameters())},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                        'torch': torch.__version__, 'platform': platform.platform(),
                        'threads': args.threads, 'device': 'cpu', 'deterministic_algorithms': True},
        'training_arguments': vars(args),
        'source_sha256': {'train_pilot.py': digest(__file__),
                          'pilot_model.py': digest(Path(__file__).with_name('pilot_model.py')),
                          'data': digest(args.data)},
        'limitations': ['The model imitates classical teacher plans; it does not learn flight dynamics.',
                        'Loss and action bounds do not certify mission success.',
                        'Conditional diffusion is evaluated through separate closed-loop flights.'],
    }
    (output / 'model.json').write_text(json.dumps(metadata, indent=2, allow_nan=False) + '\n')
    (output / 'training-log.json').write_text(json.dumps(logs, indent=2, allow_nan=False) + '\n')
    from pilot_model import load_model
    exported = load_model(output)
    parity_rng = np.random.default_rng(args.seed + 3)
    latent_fixture = parity_rng.normal(size=(4, 8)).astype(np.float32)
    context_fixture = contexts[np.flatnonzero(~training)[np.arange(4) % (~training).sum()]]
    times_fixture = np.array([0, 7, 15, 31], dtype=np.int64)
    with torch.no_grad():
        decoded_torch = autoencoder.decode(torch.from_numpy(latent_fixture)).numpy()
        noise_torch = diffusion(torch.from_numpy(latent_fixture),
                                torch.from_numpy((context_fixture - context_mean) / context_std),
                                torch.from_numpy(times_fixture)).numpy()
    decoder_error = float(np.max(np.abs(exported.decode(latent_fixture) - decoded_torch)))
    denoiser_error = float(np.max(np.abs(exported.denoise(latent_fixture, context_fixture, times_fixture) - noise_torch)))
    plans_one = exported.sample(context_fixture[0], count=1, seed=args.seed + 4)
    plans_many = exported.sample(context_fixture[0], count=16, seed=args.seed + 4)
    paired_identical = bool(np.array_equal(plans_one[0], plans_many[0]))
    parity = {'decoder_max_absolute_error': decoder_error, 'denoiser_max_absolute_error': denoiser_error,
              'absolute_tolerance': 1e-5, 'first_candidate_identical_across_counts': paired_identical,
              'sample_max_burn_norm': float(np.linalg.norm(plans_many, axis=-1).max()),
              'finite_samples': bool(np.isfinite(plans_many).all()),
              'weights_sha256': digest(output / 'weights.npz')}
    (output / 'parity.json').write_text(json.dumps(parity, indent=2, allow_nan=False) + '\n')
    assert decoder_error < 1e-5 and denoiser_error < 1e-5, parity
    assert paired_identical and parity['finite_samples'] and parity['sample_max_burn_norm'] <= 1 + 1e-12, parity
    print(json.dumps({'output': str(output), 'parity': parity}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed', type=int, default=1729)
    parser.add_argument('--ae-epochs', type=int, default=200)
    parser.add_argument('--diffusion-steps', type=int, default=4000,
                        help='Optimizer updates; the diffusion schedule has 32 noise steps.')
    parser.add_argument('--sample-steps', type=int, choices=(8, 16), default=16)
    parser.add_argument('--batch-size', type=int, default=128)
    parser.add_argument('--learning-rate', type=float, default=.001)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--patience', type=int, default=20)
    parser.add_argument('--validation-every', type=int, default=100)
    parser.add_argument('--balanced-burns', action=argparse.BooleanOptionalAction, default=True,
                        help='Sample equal burn/coast counts from training when both groups exist.')
    args = parser.parse_args()
    if min(args.ae_epochs, args.diffusion_steps, args.batch_size, args.threads,
           args.patience, args.validation_every) < 1 or not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
        parser.error('Training counts and learning rate must be positive.')
    try:
        import torch
    except ImportError as error:
        raise SystemExit('Training requires the approved remote CPU PyTorch environment. No local installation is needed.') from error
    train(args, torch)


if __name__ == '__main__':
    main()
