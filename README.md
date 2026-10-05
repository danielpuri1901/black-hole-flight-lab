# Black Hole Flight Lab

Two interactive experiments test learned predictions and learned control near a Schwarzschild black hole.
The powered pilot uses an action autoencoder and diffusion transformer to propose burns, then ranks plans with relativistic equations.
The earlier experiment tests learned gravitational potentials against an exact rational escape calculation.

## Local setup

Use Python 3.14.0 to match the recorded local runs.
From this folder, create an isolated environment and install the pinned packages:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The saved model weights and results are included.
Local inference does not need PyTorch; [the cloud plan](docs/pilot-cloud-plan.md) records the separate training environment.
Node.js 24 is used by CI and is needed for the optional cabin checks near the end of this file.
Start the server below, then use the reproduction commands for either experiment.
See [the study guide](docs/study-guide.md) for the concepts behind the code.

## Automated checks

GitHub Actions runs the Python tests, cockpit geometry and walking checks, JavaScript syntax checks, vendor hash checks, and article builds.
The workflow uses read-only repository permissions and does not provision cloud resources or retrain models.
Run the core checks locally with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -v
node check_cabin.mjs
node check_cabin_walk.mjs
```

## Open the experiment

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 serve.py --port 8008
```

Open [the powered cockpit](http://127.0.0.1:8008/pilot) or [the powered pilot article](http://127.0.0.1:8008/pilot-article).
Select **Begin flight**, switch between **Raw AI** and **Checked AI**, and use **Immersive view**.
The recorded pair starts from the same state and executes different learned control decisions.
The custom launch form calculates a new feedback-controlled flight with the selected controller.
The replay shows actual radius, propellant, and commanded thrust from that calculation.

The original [unpowered observatory](http://127.0.0.1:8008/) and [technical article](http://127.0.0.1:8008/article) remain available.
Select **Begin flyby**, switch between **Relativity** and **Learned model**, and try **Immersive view**.
Scrub the replay or change launch energy, angular momentum, and the saved neural model.
The barrier plot explains why the trajectories disagree.
Expand **Inspect exact certificate** to see the algebra behind the physical verdict.

The server binds only to `127.0.0.1`.
No external account, API, font, or asset is required.

## Powered pilot result

Raw diffusion escaped on 44 of 64 held-out launches.
Numerical ranking of its proposals increased that count to 55, with 11 paired rescues and no reverse loss.
Classical search escaped on 60 launches.
A post hoc control using 29 fixed burn/coast plans also escaped on 60, without learned weights.
The results support checking learned proposals but do not establish that this task requires learning.

The full record contains 640 evaluation flights, including supplemental controls and two extra model fits.
All 38 automated checks passed, and the real Chrome flow was exercised with trained inference.
The powered checker is numerical, not a formal safety proof.

## Reproduce the powered pilot

The saved weights use NumPy inference, so local evaluation does not require PyTorch.
The commands below resume per-flight checkpoints and reject changed experiment inputs.
Run the three evaluations in sequence to preserve the two-worker compute budget.

```sh
python3 -m unittest discover -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 verify_pilot_rollouts.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 run_pilot_experiment.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 run_pilot_controls.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 run_pilot_seed_check.py
python3 plot_pilot_results.py
python3 build_article.py --pilot
```

The original comparison contains 448 flights across seven controllers and 64 held-out missions.
Two post hoc controls test an explicit coast option and a fixed burn library.
Two extra model fits test sensitivity on a predeclared subset of launches.
See [the article](docs/pilot-article.md) for measured outcomes and limitations.

Three fits trained on a temporary CPU EC2 instance with approved remote dependencies.
The returned archive contains only project-trained weights and results.
The infrastructure estimate was $0.01967, excluding S3, transfer, and tax.
This is an estimate, not a final bill.
Instance, root volume, bucket, role, instance profile, and security group deletion were verified.
The [cloud evidence](results/pilot/model/cloud-run.json) and [cloud plan](docs/pilot-cloud-plan.md) record the details.
No ongoing cloud service is needed to use the cockpit.

## Original unpowered result

Ten compact neural potentials were tested on the same frozen 4,000 launches.
Mean false-escape rates on a deliberately concentrated boundary test were 28.37% for small models and 24.45% for larger models.
A validation-error abstention policy rejected every observed false escape but accepted only 16.76% and 15.76% of boundary launches, respectively.
The exact planner accepts the truly escaping 50%.
These are stress-test results, not mission-risk estimates or a test of foundation models.

The post hoc controls add smooth counterexamples whose potential and acceleration errors tend to zero, a constant-shift control, and a privileged four-feature physical baseline.
The exact rational certificate checker agrees with all 4,000 frozen physical labels.
It uses Sturm root counting with Python `Fraction`; it is not a Lean proof of the runtime or of general relativity.

## Reproduce the unpowered experiment

The saved models and observations are part of this folder.
The runner resumes existing fits and rescores the frozen launches.
Keep the original artifacts when comparing fresh training runs; rescoring can change timing measurements.

```sh
python3 -m unittest discover -v
python3 run_experiment.py --smoke
python3 run_experiment.py
python3 run_controls.py
python3 run_certificates.py
python3 render_black_hole.py --check
python3 build_article.py
```

Rebuild the static camera image with `python3 render_black_hole.py --width 1440`.
The cockpit uses its own live WebGL renderer, with an image fallback if WebGL is unavailable.

The recorded local package versions are pinned in [requirements.txt](requirements.txt).
Training limits BLAS threads to one.
The unpowered model fits used no cloud resources.
A separate GYOTO check ran 24 launches at two tolerances on the temporary server described in [the cloud plan](docs/cloud-plan.md).
All outcomes agreed with the local solver and oracle.
CloudFormation deletion completed.
The infrastructure cost estimate is $0.00277 before tax and transfer; this is not a final bill.

## Files

| File | Purpose |
|---|---|
| [docs/pilot-article.md](docs/pilot-article.md) | Powered pilot methods, comparisons, cloud evidence, and limits |
| [pilot_physics.py](pilot_physics.py) | Controlled relativistic equations and fuel accounting |
| [pilot_control.py](pilot_control.py) | Teacher search, candidate ranking, and feedback control |
| [pilot_model.py](pilot_model.py) | Exported autoencoder and diffusion transformer inference |
| [train_pilot.py](train_pilot.py) | Remote CPU training and export parity checks |
| [results/pilot/](results/pilot/) | Frozen missions, trained models, individual flights, and summaries |
| [cloud/run_pilot.py](cloud/run_pilot.py) | Temporary training job, verified artifact return, and cleanup |
| [docs/article.md](docs/article.md) | Full scientific write-up, sources, proofs, results, and limits |
| [physics.py](physics.py) | Exact potential, independent turning-polynomial oracle, numerical trajectories |
| [world_model.py](world_model.py) | Portable neural inference, derivatives, and barrier decisions |
| [run_experiment.py](run_experiment.py) | Frozen main experiment and model exports |
| [run_controls.py](run_controls.py) | Post hoc perturbation, gauge, structural, and abstention controls |
| [verify_certificate.py](verify_certificate.py) | Exact rational evidence generator and checker |
| [run_certificates.py](run_certificates.py) | Frozen-input crosscheck and saved certificate evidence |
| [serve.py](serve.py) | Local HTTP server and live numerical flight API |
| [dashboard/](dashboard/) | Cockpit, coordinate map, barrier plot, and measured results |
| [results/summary.json](results/summary.json) | Main protocol, environment, and all model metrics |
| [results/trials.csv](results/trials.csv) | 44,000 decisions, including the analytic baseline |
| [results/controls.json](results/controls.json) | Post hoc controls and selective acceptance results |
| [results/certificates.json](results/certificates.json) | Exact certificate checks and full showcase evidence |
| [results/gyoto-cloud-run.json](results/gyoto-cloud-run.json) | Independent GYOTO measurements, timing, cleanup status, and cost estimate |
| [run_gyoto_check.py](run_gyoto_check.py) | Coordinate adapter and independent-engine checks |
| [cloud/gyoto-stack.json](cloud/gyoto-stack.json) | Temporary server infrastructure and termination backstop |

## Physical and visual scope

Both experiments use equatorial Schwarzschild physics with G=c=M=1.
The powered pilot has finite proper acceleration and an ideal propellant budget.
It stops at the safety surface r=2.1 or at an outward coasting escape state at r=20.
Numerical plan ranking is not a formal safety guarantee.
The original flight is an unpowered timelike geodesic with launch radius 30.
Capture stops numerically at r=2.001; the physical horizon is r=2.
The mathematical certificate classifies the horizon fate, not numerical integration error.
Timeouts and degenerate cases remain unresolved.

The powered cockpit is a geometric 3D cabin driven by measured trajectories.
Select **Walk cabin**, then use WASD to walk and drag or use arrow keys to look around.
Walking stays at standing height and stops at the desk, consoles, and seats.
Pilot and Window restore fixed viewpoints; walking from either view returns to standing height.
Camera movement does not change the orbit.
Instrument textures show the actual replay state, while the surrounding hardware is decorative.
The field screen plots the recorded radius history, and the control screen identifies the selected controller.
Metal materials, cached shadows, sparse cabin dust, bloom, and optional synthesized sound provide the visual and audio effects.
Three.js is vendored under `dashboard/vendor/`, with its MIT license and a file integrity manifest.
The original unpowered cockpit retains its generated foreground image.
Camera framing, minimum viewing radius, and artistic disk emission are presentation choices.
It is not the exact optical view of a moving observer.
Neither experiment models vehicle attitude, radiation, structural loads, or tidal survival.
The coordinate map, static ray-traced view, and cockpit are separate views with distinct visual assumptions.

Run `node check_cabin.mjs` to check instrument clearance, hardware attachment, camera presets, telemetry labels, and trace refresh without a GPU.
This uses the vendored Three.js geometry and a minimal canvas stub; it does not replace visual inspection in Chrome.
Run `node check_cabin_walk.mjs` to check floor movement, furniture collision, sliding, and camera presets.
Open `/pilot?diagnostics` to run the ten-second camera benchmark on your device.
