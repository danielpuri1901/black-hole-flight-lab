# Posthoc scientific controls

An analytic construction reverses capture and escape while both potential error and acceleration error tend to zero.
It proves a worst-case boundary effect, not a nonzero error rate under a fixed launch distribution.
The saved neural uncertainty flag rejects every measured false escape when used as an abstention rule.
The saved showcase also has this flag.
These findings limit any claim that the neural models confidently choose those unsafe launches.

All controls here were added after the frozen neural experiment.
They do not change its models, observations, flight inputs, optimizer, or recorded selection rule.
The controls are explanatory analyses, not predeclared confirmatory tests.

## Constructive boundary counterexample

Use the physical potential `V(r,L)=(1-2/r)(1+L^2/r^2)` and radial acceleration `a=-V'/2`.
Fix `E=1.05`, launch radius `r0=30`, and the capture surface `r=2.001`.
Let `B(L)=max V(r,L)` over this inward interval and define the physical margin `m=B-E^2`.
Positive margin gives an outer turning point and escape for these allowed Schwarzschild launches.
Negative margin gives capture.
The exact boundary has zero margin and remains unresolved.

For each positive epsilon, choose angular momentum below the critical value with `m=-epsilon/2`.
The script solves this scalar equation with Brent's method.
The physical inner maximum is at:

```text
r* = (L^2 - sqrt(L^4 - 12L^2))/2
```

Near this boundary, `dB/dL=2L(1-2/r*)/r*^2>0`.
Thus a solution exists for sufficiently small epsilon and approaches the critical angular momentum from below.
The six recorded solutions keep the maximum inside the capture and launch surfaces.

Set `w=0.5`, `z=(r-r*)/w`, and define:

```text
q(r) = (1-z^2)^3  if |z|<1
q(r) = 0          otherwise
V_hat(r,L) = V(r,L) + epsilon*q(r)
q'(r) = -6z(1-z^2)^2/w              inside the support
q''(r) = -6(1-z^2)(1-5z^2)/w^2      inside the support
```

The bump and its first two derivatives vanish at both support endpoints.
Its zero extension is therefore C2, with a continuously differentiable acceleration.
It satisfies `0<=q<=1`, `q(r*)=1`, and `q(r0)=0`.
Everywhere, `V_hat<=B+epsilon`, with equality at `r*`.
Thus the perturbed barrier is exactly `B+epsilon`, without a finite-grid search.

Both worlds start with the same inward physical velocity `v0=-sqrt(E^2-V(r0,L))`.
The unchanged launch potential makes the perturbed conserved energy equal to `E^2`.
The perturbed margin is exactly `+epsilon/2`, while the physical margin is `-epsilon/2`.
The physical trajectory captures and the perturbed trajectory escapes.
The outer perturbed turning point is simple because both potentials decrease outward between that point and the nearby maximum.

The error bounds are exact:

```text
sup |V_hat-V| = epsilon
sup |a_hat-a| = 48*epsilon/(25*sqrt(5)*w)
```

The acceleration maximum occurs at `|z|=1/sqrt(5)`.
With `w=0.5`, its coefficient is approximately 1.7173.
Both errors vanish with epsilon, while the worst-case fate reversal persists through a changing launch.
This is a constructed potential, not a fitted neural model or a new physical theory.

## Numerical checks

The script runs all six cases at `rtol=1e-11` and `rtol=1e-13` with DOP853.
Each run uses the same physical launch and the analytic derivative of its selected potential.
All twelve physical traces capture and all twelve perturbed traces escape.
The independent physical turning-polynomial oracle also classifies all six launches as capture.

| Epsilon | Physical margin | Perturbed margin | Physical invariant drift, tighter run | Perturbed invariant drift, tighter run |
|---:|---:|---:|---:|---:|
| 1e-3 | -5e-4 | +5e-4 | 1.67e-13 | 1.16e-13 |
| 1e-4 | -5e-5 | +5e-5 | 1.40e-13 | 1.40e-13 |
| 1e-5 | -5e-6 | +5e-6 | 2.03e-13 | 2.04e-13 |
| 1e-6 | -5e-7 | +5e-7 | 1.92e-13 | 1.64e-13 |
| 1e-7 | -5e-8 | +5e-8 | 1.22e-13 | 2.50e-12 |
| 1e-8 | -5e-9 | +5e-9 | 1.37e-13 | 3.08e-13 |

The largest scalar root residual is approximately `1.03e-15` in absolute margin units.
Reported invariant drift measures the maximum over saved dense samples and solver states.
It does not bound every interpolation error or establish a rigorous trajectory error bound.
The code marks a case unresolved if outcomes disagree across tolerances or measured drift exceeds `epsilon/200`.
All six cases satisfy this diagnostic rule.
No smaller epsilon was numerically tested, and tolerance agreement alone is not a proof at the exact boundary.

Energy conservation follows directly from consistent acceleration:

```text
d(v^2+V_hat)/dtau = 2v*(-V_hat'/2) + V_hat'*v = 0
```

This identity holds even when the selected potential is wrong.
On a perturbed trajectory, `v^2+V=E^2-epsilon*q(r)`.
The physical invariant error can therefore be as large as epsilon despite small drift in the perturbed invariant.

## Uniform margin bound and its scope

Let `e(r)=V_hat(r)-V(r)` at a fixed angular momentum.
Keep the same physical initial velocity in both worlds.
Then:

```text
m_hat = max_r [V(r)+e(r)-e(r0)] - V(r0) - v0^2
|m_hat-m| <= sup_r |e(r)-e(r0)| <= 2*epsilon
```

The first inequality uses `|max f-max g|<=sup|f-g|` on the complete inward interval.
The second requires the genuine uniform bound `sup|e|<=epsilon` on that interval, including launch.
Thus `m_hat>2*epsilon` certifies positive physical margin and escape for the specified outer Schwarzschild launch.
Likewise, `m_hat<-2*epsilon` certifies negative physical margin and capture.
Equality or smaller absolute margins give no certificate.
The certificate concerns the physical fate; arbitrary conservative potentials can also have degenerate turning points.

A bound on `sup|e(r)-e(r0)|` can be sharper than `2*epsilon`.
It equals epsilon for the constructed bump and zero for a constant shift.
Validation RMSE, a residual percentile, and a finite grid do not establish this uniform bound.
The neural models therefore receive no certified epsilon from this analysis.

When a fixed distribution has no probability mass on zero physical margin, the probability of `|m|<=2*epsilon` tends to zero.
A bounded margin density makes that probability at most proportional to epsilon near zero.
Sign disagreements from uniformly bounded potential errors lie within this band.
Thus the failure mass can shrink to zero even though a worst-case counterexample exists for each sufficiently small epsilon.
The constructed launches move toward the boundary as epsilon shrinks.
They do not estimate a fixed real mission distribution or prove that more accurate models retain a fixed failure rate.

## Constant-shift gauge control

Add either `C=-0.1` or `C=+0.1` to the entire physical potential.
The acceleration is unchanged because the derivative of a constant is zero.
The selected launch energy shifts by the same C as the barrier, so the margin remains unchanged.
Four traces cover both shifts and both sides of the physical boundary.
The trajectories match their unshifted controls exactly at the recorded points, and all fates agree.
The absolute potential error is 0.1, yet the acceleration and margin errors are zero.
Thus absolute potential error alone can measure an arbitrary energy reference instead of a decision error.

## Privileged least-squares baseline

Fit the existing small-11 observations with columns `[1,1/r,L^2/r^2,L^2/r^3]`.
This basis comes directly from the known physical formula.
It is a privileged physics baseline, not a discovered symbolic law.
The fit uses the same 4096 training observations and retains their separate 1024 validation observations.

Recovered coefficients are `[0.9999999999999989,-1.9999999999999882,1.0000000000000007,-2.000000000000005]`.
The exact coefficients are `[1,-2,1,-2]`.
The design matrix has rank 4 and condition number approximately 42.82.
Training RMSE is `1.36e-15`; validation RMSE is `1.56e-15`.
The largest validation residual is `1.23e-14`.

An analytic quadratic finds every radial extremum of the fitted basis.
It uses no grid to estimate the barrier.
This baseline agrees with the independent polynomial oracle on all 4000 frozen launches.
It makes zero false escapes, zero false captures, and no unresolved decisions.
These results show the value of supplying the correct structure for this known system.
They do not test the ability to discover that structure from unrestricted data.

## Abstention using the saved neural uncertainty flag

The frozen experiment flags `abs(m_hat)<=2*validation_95th_percentile_absolute_potential_residual`.
The new policy accepts a launch only when prediction is escape and this saved flag is false.
All other launches receive abstention, not a capture prediction.
The policy analysis is posthoc, although the flag itself was predeclared.
It uses the saved flags without threshold retuning, retraining, or access to the oracle in its acceptance rule.
The oracle supplies evaluation labels only.

| Model | Nominal accepted / 2000 | Stress accepted / 2000 | Accepted false escapes, both distributions |
|---|---:|---:|---:|
| small-11 | 1130 | 348 | 0 |
| small-22 | 1130 | 390 | 0 |
| small-33 | 1130 | 271 | 0 |
| small-44 | 1130 | 364 | 0 |
| small-55 | 1130 | 303 | 0 |
| large-11 | 1130 | 284 | 0 |
| large-22 | 1130 | 317 | 0 |
| large-33 | 1131 | 329 | 0 |
| large-44 | 1130 | 308 | 0 |
| large-55 | 1130 | 338 | 0 |

Mean stress coverage is 16.76% for small models and 15.76% for large models.
Exactly 50% of stress launches physically escape.
The policy therefore retains 33.52% and 31.52% of true stress escapes, respectively.
Mean nominal coverage is 56.50% and 56.51%; physical escape coverage is 56.55%.
Each model uses the same frozen cases, so these repeated trials must not be pooled as independent evidence.

The selected small-11 showcase, trial 3569, is flagged uncertain and is rejected by this policy.
It demonstrates a wrong raw model decision with a self-consistent trajectory.
It does not demonstrate a wrong decision that passes the saved uncertainty flag.
Measured zero false escapes under abstention is not a population guarantee or a uniform-error certificate.
The low stress coverage also means abstention cannot be treated as cost-free.

## Reproduction and artifacts

Run from the project directory:

```sh
python3 run_controls.py
python3 -m unittest test_controls -v
```

The script uses installed NumPy, SciPy, and Matplotlib without downloads or neural retraining.
Five tests cover the derivative, support, exact supremum formula, margin reversal, numerical fates, gauge invariance, baseline, and abstention.
`results/controls.json` records all six perturbations, four gauge cases, fitted coefficients, frozen-input hashes, and per-model policy metrics.
Each perturbation includes both tolerances, terminal events, model invariant drift, and physical invariant drift.
`results/figures/controlled-errors.png` shows the analytic errors, signed margins, measured invariant drift, and a local barrier example.
