# Learned pilot model

The pilot generates bounded action plans from six ship-state features.
It imitates classical teacher plans and does not learn a flight dynamics model.
The controlled engine must check actual acceleration, fuel, mission cutoffs, and closed-loop outcomes.

## Interface and artifacts

```python
from pilot_model import load_model

model = load_model('results/pilot/model')
plans = model.sample(context, count=16, seed=0)
# plans.shape == (16, 12, 2)
```

`load_model` accepts an artifact directory or its `model.json` path.
Inference uses NumPy and loads the weight archive with `allow_pickle=False`.
It does not import PyTorch.
Context features have this fixed order: `[r/10, ur, L/5, q/0.7, E, 1/r]`.
Context standardization uses the training split only.
Each decoded burn has normalized radial and tangential components with Euclidean magnitude at most one.
The engine converts these normalized controls into bounded proper acceleration.

The training command writes four artifacts:

| File | Contents |
| --- | --- |
| `model.json` | Architecture, scaling, schedule, validation losses, seeds, versions, arguments, and source hashes |
| `weights.npz` | Float weights and the 32 diffusion betas |
| `training-log.json` | Training and validation losses at recorded checkpoints |
| `parity.json` | Export parity errors, paired-candidate check, action bounds, and the weight checksum |

## Architecture

The action autoencoder maps a 12-by-2 plan through 24, 64, and 8 units.
The encoder applies tanh after each affine layer.
The decoder maps 8, 64, and 24 units with tanh, then projects every burn onto the unit disk.
The latent mean and standard deviation come from the best autoencoder's training latents.

The denoiser splits the standardized eight-dimensional latent into four tokens with two values each.
A linear layer maps tokens to width 32 and adds a learned position embedding.
The state condition joins the six standardized context features with three timestep features.
The timestep features are `t/31`, `sin(pi*t/31)`, and `cos(pi*t/31)`.
A 9-to-64-to-32 tanh network adds this condition to each token.

Two transformer blocks use pre-layer normalization with epsilon `1e-5`.
Each block has two attention heads of width 16 and a residual connection.
Its feed-forward layer maps 32 to 64 to 32 units with the tanh approximation to GELU.
A final 32-to-2 projection returns the eight noise predictions.
The NumPy implementation uses the same equations and weight layout.

## Diffusion schedule and sampling

The final implementation uses a cosine cumulative schedule with offset `0.008` and beta capped at `0.999`.
This replaces the initially proposed short linear schedule, which retained too much signal at its terminal step.
For the actual 32-step cosine schedule, terminal cumulative alpha is `2.369939560098495e-6`.
The model starts from Gaussian latent noise and uses deterministic DDIM with eta zero.
The default sampler uses 16 steps, with an eight-step option recorded in the metadata.
At every DDIM step, the predicted clean latent is clamped to the tanh encoder's exact representable range.
The affine bounds are `(-1-latent_mean)/latent_std` and `(1-latent_mean)/latent_std`.
This prevents terminal noise error from sending the decoded plan outside the autoencoder's encoded domain.
The metadata records the actual bounds.

The random seed fixes the initial latent noise.
The NumPy linear layers use a fixed reduction order to preserve the first candidate across candidate counts.
The local check found the first plan bitwise identical for counts one and 16 with the same context and seed.
This supports paired direct and checked proposal comparisons.

## Training

The teacher archive must contain `contexts` with shape `(N,6)`, `plans` with shape `(N,12,2)`, and `split` with shape `(N,)`.
Split zero is training and split one is validation.
No test rows are accepted by the trainer.
The separate closed-loop test launches remain frozen by the parent experiment.

Training uses CPU PyTorch, deterministic algorithms, a fixed seed, and a configurable thread count.
The autoencoder minimizes action reconstruction MSE and keeps the best validation checkpoint.
The denoiser minimizes noise MSE with random training timesteps.
Its validation noise and timesteps stay fixed across checkpoints.
When training contains both first-burn and first-coast plans, sampling gives each group half the draws.
The group rule is a first-action normalized magnitude greater than `0.05` for burns.
The validation split keeps its natural distribution and reports separate burn and coast MSE.
`--no-balanced-burns` disables this sampling rule for an ablation.
The best validation denoiser is exported.
Losses measure reconstruction and denoising, not mission success.
The metadata also reports teacher and reconstructed burn magnitudes on validation data.

```sh
python3 train_pilot.py \
  --data results/pilot/teacher.npz \
  --output results/pilot/model \
  --seed 1729 \
  --ae-epochs 200 \
  --diffusion-steps 4000 \
  --sample-steps 16 \
  --threads 2
```

Here `--diffusion-steps` means optimizer updates, not the number of noise levels.
The saved metadata records every argument and the actual software versions.
The trainer records SHA-256 hashes of both source modules and the teacher archive.

## Source manifest and verification

The remote source manifest consists of `train_pilot.py`, `pilot_model.py`, and the frozen teacher archive.
The approved remote environment supplied CPU PyTorch and NumPy.
SciPy belongs to the separate flight engine and is not required by this inference module.
No training package or third-party pretrained model was downloaded or installed on the Mac.
The project's own trained weights and scientific JSON returned from the temporary AWS server after the user's approval.
The main fit is in `results/pilot/model`; the other fits are in its `seed-1730` and `seed-1731` subdirectories.

Local compilation and the training help command passed without importing PyTorch.
A deterministic fixture with untrained random weights produced finite plans with maximum burn norm `0.29676293600745884` after clean-latent clipping.
The maximum absolute encoded latent was exactly one, and the first candidate remained bitwise identical for sample counts one and 16.
Changing context changed the denoising result.
Invalid context shapes and non-finite context values were rejected.
These checks exercise inference code and are not evidence of a trained pilot's quality.

All three remote fits finished the export parity check before their artifacts were accepted.
The trainer compares decoded plans and denoiser predictions with the PyTorch implementation at fixed inputs.
It requires maximum absolute error below `1e-5` for both.
It also checks finite bounded samples and a bitwise-identical first candidate across candidate counts.
Each parity JSON records actual errors and the weight checksum.

The fits used Python 3.12.3, NumPy 1.26.4, CPU PyTorch 2.13.0, two Torch threads, and deterministic algorithms.
They shared the same 2,248 training decisions and 546 validation decisions.
Balanced sampling was applied to 94 active-burn and 2,154 coast training examples.
Natural validation contained 28 active-burn and 518 coast examples.

| Fit seed | Selected AE epoch | Selected diffusion update | AE validation MSE | Noise validation MSE | Decoder parity error | Denoiser parity error |
| --- | --- | --- | --- | --- | --- | --- |
| 1729 | 66 | 3,100 | `7.64795×10⁻⁵` | `0.0227282` | `1.24274×10⁻⁷` | `3.33278×10⁻⁶` |
| 1730 | 78 | 3,600 | `7.29094×10⁻⁵` | `0.0135178` | `1.56980×10⁻⁷` | `2.77098×10⁻⁶` |
| 1731 | 116 | 3,800 | `7.21629×10⁻⁵` | `0.0113607` | `1.23467×10⁻⁷` | `2.47107×10⁻⁶` |

All three fits passed the `10⁻⁵` parity tolerance and returned finite samples with maximum burn norm one.
Their first candidates remained bitwise identical across candidate counts.
Recorded fit times were 22.07, 22.21, and 22.84 seconds, respectively.
The full remote sequence took 73.87 seconds, including export and artifact assembly.
The returned archive contained 17 files and 323,378 compressed bytes, with verified archive and individual-file SHA-256 checksums.

The full cloud runner took 381.39 seconds through cleanup.
Its infrastructure estimate was `$0.01967`, excluding S3, transfer, and taxes; this is not a measured AWS bill.
Checks confirmed deletion of the instance, captured root volume, private bucket, temporary role, instance profile, and security group.
The sanitized evidence is [cloud-run.json](../results/pilot/model/cloud-run.json).
Model-specific losses and export checks are in each fit's `model.json` and `parity.json`.
These checks establish implementation agreement and completed training, not closed-loop mission performance.
The separate controller evaluation determines mission outcomes.
