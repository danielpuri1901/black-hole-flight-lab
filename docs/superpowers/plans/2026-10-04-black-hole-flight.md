# Black Hole Flight Lab Implementation Plan

> For agentic workers: use superpowers:subagent-driven-development with fresh bounded implementers.
> User instructions omit per-task and whole-project reviewer passes.

**Goal:** Test dangerous escape predictions and deliver an immersive reproducible demonstration.

**Architecture:** A shared Python physics module supplies independent orbit checks and numerical traces.
A training runner writes immutable observations, metrics, model parameters, and showcased flights.
A loopback HTTP server serves an interactive canvas demo and calculates requested trajectories.

**Tech Stack:** Python 3.14, installed NumPy, SciPy, scikit-learn, Matplotlib, browser Canvas, HTML, CSS, JavaScript.

**Spec:** docs/superpowers/specs/2026-10-04-black-hole-flight-design.md

## Global constraints

All files stay in the current project.
No packages, models, or repositories are installed on the Mac.
The user later authorized a temporary AWS engine check under a $50 budget.
That check installs GYOTO on its disposable server, then deletes the server and related resources.
Use timelike unpowered Schwarzschild trajectories, G=c=M=1, r0=30.
Reject invalid inputs and preserve unresolved outcomes.
Report all seeds and the full held-out test data.
The analytical baseline is a legitimate competitor.
User authorized autonomous execution and selected the experiment.

## Review focus

Boundary equality must not be called safe.
Numerical integration timeout must not become capture or escape.
Learned initial energy must match the identical physical launch velocity.
Test labels must never fit a model or choose training settings.
Stale browser responses must not overwrite a newer flight.

## Task 1: Physics and independent oracle

Files: physics.py, test_physics.py.
Expose potential(r,L), potential_derivative(r,L), critical_angular_momentum(E), outcome(E,L,r0=30), and trace(E,L,potential_fn=None,derivative_fn=None,r0=30,rtol=1e-9,max_time=2000,max_points=700).
The potential functions accept NumPy arrays.
Outcome returns 'escape', 'capture', or 'unresolved' using a turning-polynomial calculation independent of the critical formula.
Trace returns JSON-ready outcome, points (tau,r,phi), energy_drift, and diagnostics.

- [x] Write failing checks for E=1,L=4 marginal capture, obvious radial capture, safe high-angular-momentum scattering, invalid launch, and numerical-versus-oracle agreement.
- [x] Implement the formulas and DOP853 trajectory calculation.
- [x] Run the checks, compare two tolerance settings, and save the evidence in docs/progress.md.

## Task 2: Learned models and experiment

Files: world_model.py, run_experiment.py, test_world_model.py, results/.
Use the exact predeclared seeds and samples from the spec.
Export model parameters to JSON, including feature and target scaling.
Expose load_model(path), model.potential(r,L), and model.derivative(r,L).
Check exported predictions and derivatives against the trained estimator and finite differences.
Compute potential barriers on a coarse radial grid followed by vectorized local refinement.
Use the identical launch velocity in exact and learned worlds.
Write results/summary.json, results/trials.csv, model JSON files, results/showcase.json, and figures.
Summary includes protocol, environment, model_metrics, aggregate_metrics, model_files, and selected_case.
Showcase includes energy, angular_momentum, model_id, prediction, actual, true_trace, and model_trace.

- [x] Write failing checks for exported inference, derivative behavior, and baseline predictions.
- [x] Fit a separate development smoke run before the unchanged five-seed experiment.
- [x] Run the complete experiment with bounded BLAS threads, persist per-model results, and record failures honestly.
- [x] Verify all seeds and data rows exist and all exported JSON values are finite.

## Task 3: Immersive demo and server

Files: dashboard/index.html, dashboard/style.css, dashboard/app.js, serve.py.
GET /api/summary returns results/summary.json.
GET /api/showcase returns results/showcase.json.
GET /api/flyby?energy=...&angular_momentum=...&model=... returns the same schema as showcase.
Model identifiers come from summary.model_files and never become arbitrary paths.
GET /article serves docs/article.html after the article is generated.
The server binds to 127.0.0.1 and uses a fixed project root.

- [x] Create a deliberate visual design with a large orbital view, paired predictions, compact controls, and legible measured results.
- [x] Implement live launch, replay, pause, scrubbing, and selected failure loading against the fixed API contract.
- [x] Validate request ranges and errors, then run the real numerical path through HTTP.
- [x] Open in the user's real Chrome, exercise controls, inspect screenshots, and fix observed defects.

## Task 4: Results, article, and final verification

Files: README.md, docs/article.md, docs/article.html, docs/progress.md.
Write the article from saved results with sources, setup, equations, architecture, outcomes, limitations, and reproduction commands.
Distinguish benchmark facts from hypotheses and visual illustration.
Run humanizer and recheck simple language, full mechanism, and sentence-per-line rules.
Run all Python checks and HTTP smoke checks, drive the demo, and inspect exact changed files.
Record actual AWS spend and resource state.

## Final extensions

The delivered cockpit includes GPU photon tracing, a generated foreground shell, and drag or keyboard camera look.
An exact rational Sturm checker verifies the physical verdict.
Post hoc controls test abstention, smooth boundary counterexamples, constant shifts, and a privileged physical basis.
A separate GYOTO run checks 24 launches at two tolerances on a disposable AWS server.
All results and cloud cleanup evidence are saved under results/.
See docs/progress.md for measured verification and scope limits.
