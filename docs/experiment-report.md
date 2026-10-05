# Experiment report

Compact learned potentials make incorrect escape decisions near the capture boundary.
The larger models have fewer mean false escapes on this stress test, but the five seeds overlap substantially.
The exact analytic baseline makes no incorrect decisions and runs faster than either neural architecture.

## Fixed protocol

The experiment uses inward, unpowered, equatorial timelike Schwarzschild launches with G=c=M=1.
The launch radius is 30.
Capture stops at r=2.001, a numerical surface outside the event horizon at r=2.
Escape means an outward return to the launch radius.

Each training seed supplies 4096 observations.
Radius is uniform in log radius from 2.02 to 30.
Angular momentum is uniform from 3.5 to 6.3.
The small and large models use the identical observations for each seed.
The seeds are 11, 22, 33, 44, and 55.

The tanh networks have hidden layers (16,16) and (64,64).
They have 337 and 4417 fitted parameters, respectively.
Inputs are inverse radius and angular momentum.
Feature and target scalers use training observations only.
Validation uses 1024 separate observations with seed equal to training seed plus 100000.
Potential and acceleration errors below come from validation, not the final flight tests.

LBFGS uses alpha=1e-6, tol=1e-7, max_iter=800, and max_fun=2000.
A separate seed-97 smoke run checks training, JSON inference, and radial derivatives.
Its two fits take 0.62 and 1.48 seconds and both converge.
The optimizer settings stay unchanged for the final experiment.
All ten final fits converge without warnings.
The comparison uses the same observations and optimizer settings, but does not match total compute.

Before smoke training, seed 20261004 freezes 2000 nominal launches and 2000 boundary stress launches.
Nominal energy is uniform from 1.002 to 1.2 and angular momentum is uniform from 3.5 to 6.3.
Stress energy has the same distribution.
Exactly 1000 stress launches lie on each side of the exact capture boundary.
The relative boundary distance is log-uniform from 1e-5 to 1e-2.
The signs are shuffled before they are paired with energy and distance.
This stress distribution does not estimate the frequency of real missions.
All 4000 initial physical radial velocities are real and strictly inward.

Frozen input SHA-256:

`9c51999e3690d2e1d326b187bb6ae4d545235959ea652ad4c8c793d79db88178`

Observation hashes appear in each model metric.
The frozen selection rule also appears in test_inputs.json before final scoring.

## Launch decision

The learned world receives the same physical initial radial velocity as the exact world.
Its conserved energy is v0² + V_model(30,L).
The escape margin is max V_model(r,L) - V_model(30,L) - v0² over 2.001 <= r <= 30.
A positive margin predicts a turning point and escape.
A negative margin predicts capture.
Absolute margins at or below 1e-10 remain unresolved.

A 256-point log grid finds sampled local maxima and both endpoints.
Batched golden search refines every sampled maximum for 36 steps.
A finite grid can miss an unsampled narrow maximum.
The development check compares 256 and 1024 points at 129 fixed angular momenta.
The largest difference is 6.66e-16 across the two development models.
This check supports the chosen search resolution without proving all possible learned barriers.

Each neural potential also defines acceleration through its analytical radial derivative.
JSON inference matches the fitted estimator to numerical precision.
Analytical derivatives pass independent finite-difference checks.
Azimuth still uses the exact expression L/r².
These are neural surrogates for one known potential, not foundation models or fully learned spacetime simulators.

## Measured decisions

Every count below uses 2000 flights per model and distribution.
A false escape predicts escape when the independent turning-polynomial oracle says capture.
A false capture predicts capture when the oracle says escape.

| Model | Potential RMSE | Acceleration RMSE | Nominal false escapes | Stress false escapes | Stress false captures |
|---|---:|---:|---:|---:|---:|
| small-11 | 0.000987 | 0.006375 | 2 | 716 | 0 |
| small-22 | 0.000537 | 0.003595 | 0 | 612 | 0 |
| small-33 | 0.000802 | 0.002191 | 0 | 389 | 50 |
| small-44 | 0.000864 | 0.003303 | 0 | 672 | 0 |
| small-55 | 0.000772 | 0.005565 | 2 | 448 | 9 |
| large-11 | 0.001077 | 0.005563 | 0 | 660 | 0 |
| large-22 | 0.000785 | 0.002775 | 0 | 600 | 9 |
| large-33 | 0.000620 | 0.003331 | 0 | 265 | 249 |
| large-44 | 0.000739 | 0.004339 | 0 | 392 | 56 |
| large-55 | 0.000567 | 0.002180 | 0 | 528 | 0 |

No model produces a nominal false capture.
All exact oracle outcomes are resolved in these two saved test distributions.

| Architecture | Nominal false escapes, mean rate | Stress false escapes, mean rate | Stress rate, seed standard deviation |
|---|---:|---:|---:|
| Small | 0.04% | 28.37% | 7.12 percentage points |
| Large | 0% | 24.45% | 8.01 percentage points |

The same held-out flights are reused across models.
The report does not pool these repeated flights as independent evidence.
Aggregate variation uses the five training seeds.
Summary files give 95% Wilson intervals separately for each model and distribution.
For zero false escapes among 2000 trials, the interval upper limit is approximately 0.192%.
Stress intervals are descriptive approximations because the two boundary sides have fixed balanced counts.

The uncertainty flag uses twice the validation 95th-percentile absolute potential residual.
It marks a decision whose absolute margin falls below that threshold.
This is an error heuristic, not a calibrated safety guarantee.
An uncertainty flag alone does not reject a launch in the raw prediction metrics.

## Exact baseline and verification gate

The analytic baseline uses extrema of the exact potential.
It agrees with the independent turning-polynomial oracle on all 4000 launches.
It makes zero false escapes and zero false captures.
It accepts 1131 nominal flights and 1000 stress flights.
Twenty fixed exact numerical traces, the first ten flights from each distribution, agree with the oracle.
Their maximum energy drift is 7.83e-10.

The verification gate separately runs the polynomial oracle on every proposed escape.
It accepts a proposal only when the oracle says escape.
It rejects all measured false escapes.
Its zero false escapes follows from access to the correct physics.
This treatment does not learn physics or establish safety outside the specified equations and launch domain.
An unresolved oracle outcome would also cause rejection.

Average stress coverage falls from 77.78% to 49.41% for small models after verification.
Average stress coverage falls from 71.31% to 46.86% for large models after verification.
Coverage is the fraction of all launches that the planner accepts.
The gate cannot recover flights that the neural model incorrectly predicts as capture.
Each model metric and every trial row record accepted and rejected proposals separately.

## Saved counterexample

The recorded rule orders all small models by seed, then all large models by seed.
It selects the first model with a false escape and then its largest positive margin.
Ties use trial order.
Numerical traces must confirm learned escape and exact capture before the example is accepted.
No candidate is skipped in this run.

The selected model is small-11 and the selected trial is 3569.
Energy is 1.0027667008383363 and angular momentum is 4.0219717740634575.
The learned escape margin is 0.0027257575165550163.
The learned trajectory escapes while the exact trajectory reaches the numerical capture surface.

Exact energy drift is 3.16e-10.
Learned energy drift within the learned world is 3.78e-12.
The same learned trajectory has exact-physics energy drift of 0.003277.
The model therefore conserves its own energy while its wrong potential barrier permits the wrong launch decision.
Tighter exact integration changes the terminal time by 2.07e-8 and preserves capture.

## Local cost and reproduction

All training and inference run locally with one BLAS thread.
The ten final fits total 11.08 seconds.
Each 4000-flight neural prediction batch takes 0.25 to 0.26 seconds for small models and 0.75 to 0.79 seconds for large models.
Checking only the proposed escapes takes about 0.007 to 0.009 seconds per model.
The exact vectorized baseline takes about 0.00020 seconds for all 4000 decisions.
The separate polynomial oracle takes about 0.012 seconds for all 4000 checks.
These are single wall-clock measurements on the recorded local environment, not a controlled timing benchmark.
The correct analytic model is the simplest and fastest solution for this known physical system.

Python is 3.14.0, NumPy is 2.4.2, SciPy is 1.17.1, and scikit-learn is 1.8.0.
The machine runs macOS on arm64.
No packages or models are downloaded.
This main training experiment created no AWS resources and incurred no cloud charges.
The later independent-engine validation has a separate cloud plan and result artifact.

Run from the project directory:

```sh
python3 -m unittest test_physics test_world_model -q
python3 run_experiment.py --smoke
python3 run_experiment.py
```

Existing model JSON files and fit records allow the experiment to resume without retraining.
Rescoring can change wall-clock measurements while preserving decisions for the frozen models and inputs.
The saved files include all 44000 rows: ten neural models and the analytic baseline, each with 4000 flights.
Plots appear in results/figures.
Results and the selected numerical trajectories appear in results/summary.json and results/showcase.json.

This experiment measures launch planning in a narrow known physics problem.
It does not test active steering, radiation survival, tidal survival, video prediction, or general AI safety.
The architecture comparison does not establish a scaling law.
A stronger surrogate, adaptive sampling, or direct analytic physics could change the outcome.
