# Powered pilot implementation

**Goal:** Train and demonstrate a real closed-loop pilot with a finite thrust budget near a Schwarzschild black hole.

**Architecture:** Independent relativistic engine, classical teacher, action autoencoder, conditional diffusion transformer, numerical candidate checking, and cinematic replay.

**Stack:** Existing Python, NumPy, SciPy, browser WebGL, and temporary CPU PyTorch on AWS.

## Global constraints

Preserve the completed unpowered experiment and frozen results.
Do not install local software.
Require the remote package manifest approval before installation.
Never expose account identifiers or credentials through public results.
Use real execution and independent numerical checks instead of reviewer-agent passes.
Keep the old algebraic certificate separate from numerical powered-flight checks.
Write each documentation sentence on its own line.

## Tasks

- [x] 1. Implement controlled physics in `pilot_physics.py` and independent checks in `test_pilot_physics.py`.
  State order is `[r, ur, L, phi, q]`.
  Provide energy, fuel fraction, vectorized fixed-step integration, and high-accuracy scalar integration.
  Report parameters and numerical errors.
- [x] 2. Implement classical planning, deterministic mission splits, teacher data, and closed-loop rollouts in `pilot_control.py`.
  Tune only on development missions, then freeze test launches before training.
  Include coast and fixed-rule controls.
- [x] 3. Implement action autoencoder and conditional diffusion transformer training in `train_pilot.py`, with exported NumPy inference in `pilot_model.py`.
  Verify export parity and bounded decoded actions.
- [x] 4. Create temporary cloud runner and stack under `cloud/`, train, retrieve verified artifacts, and verify cleanup.
  Keep source and artifact manifests explicit and bounded.
- [x] 5. Evaluate held-out closed-loop performance and write sanitized results under `results/pilot/`.
  Include raw learned proposals, checked learned proposals, and classical search.
  Record compute budgets, fuel, failures, and numerical convergence.
- [x] 6. Add powered pilot API and cockpit controls while preserving the original experiment.
  Run the real browser path and inspect the visible output.
- [x] 7. Update the article and README with measured results, reproduction commands, sources, costs, and limits.

## Progress

2026-10-04: User approved building the real pilot and restored AWS authentication.
Remote dependency approval was received before any installation.
The full thrust law was derived and checked algebraically against the local rest-frame acceleration construction.
The physics implementation, neural model implementation, and cloud runner have separate file ownership.
The powered engine and real feedback rescue passed 13 tests.
The broader numerical check compared 464 candidate plans at two resolutions and 65 adaptive references without classification disagreement.
Teacher generation uses two local workers and atomic per-flight checkpoints.
The frozen split has 64 training, 16 validation, 32 nominal test, and 32 closer stress launches.
Three training seeds completed on one temporary CPU server.
Seed 1729 receives the full 448-flight benchmark.
Seeds 1730 and 1731 use a predeclared sensitivity check on the first eight missions per test split, for raw and checked control.
The standalone powered cockpit is implemented at `/pilot`.
Real Chrome verified a coasting flight, replay, immersive mode, and mobile layout at 390 by 844 pixels.
The final article is `docs/pilot-article.md`, titled "Can AI escape a black hole?"
Its tables include all 448 main flights, 128 post hoc control flights, and 64 additional fit-sensitivity flights.
Checking raised the main learned pilot's escape count from 44/64 to 55/64, with 11 paired rescues and no reverse loss.
Classical search and the 29-plan fixed library each reached 60/64.
All temporary AWS resources were deleted and checked; the infrastructure estimate was $0.01967 before S3, transfer, and taxes.
Fresh final validation passed all 37 tests in 15.945 seconds.
The completed dashboard, paired witness, trained custom launch, article figures, and local links were inspected in real Chrome.
