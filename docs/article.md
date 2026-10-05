# The escape problem

## A conserved world can predict the wrong future

A compact neural simulator predicts that a particle will escape a black hole.
The same launch, calculated from general relativity, falls in.
The neural trajectory conserves its own energy to about 4 × 10⁻¹², so an energy-conservation check alone would miss the error.

We built an interactive observatory to make this failure visible, then tested ten learned potentials on a frozen set of 4,000 launches each.
On deliberately difficult boundary cases, mean false-escape rates were 28.37% for the smaller networks and 24.45% for the larger networks.
Those numbers describe raw predictions, not calibrated confidence.
A simple abstention rule caught every observed false escape.
In the boundary test, it accepted only about one third of the flights that could truly escape.

A reliable escape decision needs a bound on model error relative to its distance from the escape boundary.
Energy conservation alone does not supply that bound.

[Open the interactive observatory](/) · [Download every trial](/results/trials.csv) · [Inspect the saved protocol](/results/summary.json)

![A Schwarzschild black hole with a ray-traced disk and lensed rear arc.](/black-hole.png)

*The light paths in this image are calculated from Schwarzschild null geodesics.
Disk color and emission texture are artistic choices.
The particle trajectories in the flight map use a separate timelike calculation.*

## Why this is a useful test

A black hole supplies a sharp outcome: an inward launch either turns and returns outward, or continues toward the horizon.
The boundary between these outcomes is a separatrix.
Near it, two almost identical potentials can assign opposite fates to the same initial state.

This is an intentionally small experiment.
The models are feed-forward neural approximations to one effective potential, with 337 or 4,417 parameters.
They are not language models, video models, or foundation models.
The target is a mechanism that also matters when larger models support planning.
Low average error does not, by itself, bound error on the decisions a planner selects.

Conservation-based learning has substantial prior work.
[Hamiltonian Neural Networks](https://github.com/greydanus/hamiltonian-nn) use physical structure to learn dynamics with a conserved quantity.
Our models use a related structural choice, a learned scalar potential whose derivative defines acceleration, but do not reproduce that paper's method.
[Model-Based Policy Optimization](https://bair.berkeley.edu/blog/2019/12/12/mbpo/) studies model bias and the costs of long rollouts in control.
Here, a direct barrier calculation isolates the wrong outcome before any rollout error can accumulate.

The claim is narrow: conserving an approximate invariant does not establish that the invariant, or the decision boundary it defines, is correct.
This is an elementary property of the equations, not a claim to have discovered a new law of learning.

## Define the physical world

Use an equatorial, unpowered particle in a stationary, non-rotating Schwarzschild spacetime.
Set G = c = M = 1.
The event horizon is at r = 2.
The launch radius is r₀ = 30.
Energy E and angular momentum L are per unit rest mass; τ is the particle's proper time.

The metric restricted to the equatorial plane is:

```text
f(r) = 1 − 2/r
 ds² = −f(r) dt² + dr²/f(r) + r² dφ²
```

Using E = f dt/dτ, L = r² dφ/dτ, and timelike normalization ds² = −dτ² gives:

```text
V(r,L) = (1 − 2/r)(1 + L²/r²)
v² + V(r,L) = E²,                    v = dr/dτ

dr/dτ = v
dv/dτ = −1/r² + L²/r³ − 3L²/r⁴
dφ/dτ = L/r²
```

This is the effective-potential reduction developed in Sean Carroll's [Schwarzschild lecture notes](https://ned.ipac.caltech.edu/level5/March01/Carroll3/Carroll7.html), expressed here with the factor of one half absorbed into V and E².

The initial radial velocity is strictly inward: v₀ = −√[E² − V(r₀,L)].
Escape means an outward return through r₀.
Capture means reaching r = 2.001, a numerical stopping surface just outside the horizon.
Timeouts and numerically ambiguous boundary cases remain unresolved.
This avoids treating a long delay as either escape or capture.

These equations describe trajectory fate only.
They omit thrust, black-hole spin, radiation, tides, and vehicle survival.
No part of the experiment simulates travel through a singularity.
NASA's [black-hole anatomy](https://science.nasa.gov/universe/black-holes/anatomy/) distinguishes the event horizon, a causal boundary, from the central singularity where the physical interpretation of the classical theory is uncertain.
The sensitive turning region in this experiment lies outside the horizon.

## Give both worlds the same launch

Let V̂ denote the learned potential.
The learned world starts with the same r₀, L, and physical velocity v₀ as the exact world.
Its conserved quantity is therefore K̂ = v₀² + V̂(r₀,L).
Setting K̂ = E² instead would silently change the initial velocity whenever the learned launch potential is wrong.

Define the escape margin:

```text
m(V) = max over r in [2.001, r₀] of [V(r,L) − V(r₀,L)] − v₀²
```

A positive margin predicts an inward barrier and escape through a regular outer turning point.
A negative margin means no barrier blocks the incoming path before the stopping surface.
Equality is unresolved.
Degenerate turning points require separate analysis; a sign test alone is not a general theorem for arbitrary multi-barrier dynamics.
The dashboard plots each potential after subtracting its own launch value, so its horizontal energy line describes the same initial radial motion in both worlds.

Adding a constant to a potential changes its absolute values but changes neither acceleration nor this margin.
This gauge control matters: raw potential error can increase without changing any trajectory.

## Separate training, judgment, and display

The implementation uses three independent physical checks.
A potential-extremum formula supplies the analytic baseline.
A turning-polynomial calculation supplies the reference labels.
An adaptive numerical solver supplies trajectories and tolerance checks.
They share the physical assumptions, but do not classify flights by calling the same threshold function.

```text
Frozen observations → fit potential → export weights → predict escape margin
Frozen launches ────────────────────────────────────→ polynomial oracle
Selected launches ─────────────────────────────────→ numerical trajectories
Saved data and trajectories ───────────────────────→ interactive observatory
```

Multiplying E² − V by r³ gives the turning polynomial:

```text
P(r) = (E² − 1)r³ + 2r² − L²r + 2L²
```

The polynomial minimum identifies whether a forbidden radial interval blocks the launch from the outer branch.
The implementation also checks the launch branch and treats a double root within a scaled roundoff tolerance as unresolved.
The orbit solver uses SciPy's [DOP853 integration and event detection](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).
It stops on an inward capture crossing or outward escape crossing.

The learned barrier search samples 256 log-spaced radii, brackets every sampled local maximum, and refines those brackets.
A development comparison against 1,024 radii agreed to 6.66 × 10⁻¹⁶ for the tested models and angular momenta.
That is a resolution check, not a proof that a finite grid finds every possible narrow learned maximum.

## Freeze the test before training

Each seed supplies 4,096 exact potential observations.
Radius is uniform in log radius from 2.02 to 30; L is uniform from 3.5 to 6.3.
The two architectures receive identical observations for that seed.
Inputs are inverse radius and L, standardized using training data only.
Another 1,024 independently sampled observations measure validation error.

The five training seeds are 11, 22, 33, 44, and 55.
Both networks use tanh activations and LBFGS with the same optimizer settings.
All ten fits converge without warnings.
The study matches data, but does not match total compute or tune each architecture to its best performance.
It cannot establish a scaling law.

The frozen test contains two distributions:

| Distribution | Construction | Question |
|---|---|---|
| Nominal | 2,000 launches; E uniform in [1.002, 1.2], L uniform in [3.5, 6.3] | How often does the model fail across this broad launch range? |
| Boundary stress | 2,000 launches; exactly 1,000 on each side of the analytic threshold; relative distance log-uniform from 10⁻⁵ to 10⁻² | What happens when launch fate has a small margin? |

The stress set deliberately overrepresents difficult cases.
Its error rate is not an estimate of mission risk.
Training and testing use the same physical system; the stress test changes the distribution of decision margins.

The saved test-file SHA-256 is:

```text
9c51999e3690d2e1d326b187bb6ae4d545235959ea652ad4c8c793d79db88178
```

## Measure the decision, not only the fit

A false escape predicts escape for a launch the independent oracle labels capture.
Every entry below is a mean across five training seeds, each evaluated on the same 2,000 launches in the named distribution.
The ± values are seed standard deviations, not standard errors or pooled trial confidence intervals.

| Model | Parameters | Nominal false escapes | Boundary false escapes | Boundary false captures |
|---|---:|---:|---:|---:|
| Small neural potential | 337 | 0.04% | 28.37% ± 7.12 percentage points | 0.59% |
| Larger neural potential | 4,417 | 0% | 24.45% ± 8.01 percentage points | 3.14% |
| Analytic potential | 0 fitted | 0% | 0% | 0% |

The larger architecture has a lower mean false-escape rate here, with substantial overlap across seeds.
Individual potential RMSE values range from about 5.37 × 10⁻⁴ to 1.08 × 10⁻³.
A small validation error therefore coexists with a large error rate under the deliberately concentrated boundary distribution.
The sampled validation RMSE is not a uniform bound on the barrier error.

![False-escape rates for every saved model and both launch distributions.](/results/figures/false-escapes.png)

All ten models reuse the same test launches.
Treating the 40,000 neural predictions as 40,000 independent physical trials would overstate the evidence.
The saved metrics give intervals per model and distribution, plus variation across training seeds.
The balanced stress design makes its Wilson intervals descriptive approximations.

## The abstention result changes the interpretation

The original protocol recorded an uncertainty flag whenever the absolute learned margin was at most twice the validation 95th-percentile absolute potential residual.
After the main experiment, we evaluated a policy that rejects escape proposals with this flag.
We did not retune its threshold on the flight labels.
This policy analysis is post hoc, although the flag and threshold rule were specified earlier.

| Boundary policy | Small-model acceptance | Larger-model acceptance | Observed false escapes |
|---|---:|---:|---:|
| Accept every raw escape prediction | 77.78% | 71.31% | 28.37% / 24.45% of all launches |
| Reject the validation-error band | 16.76% | 15.76% | 0 in each tested model |
| Require the exact physics oracle | 49.41% | 46.86% | 0 by construction |
| Use the analytic planner directly | 50% | 50% | 0 |

Acceptance is measured over all 2,000 stress launches.
Exactly half can truly escape.
The simple abstention policy is effective on the saved tests, but discards most valid escape opportunities near the boundary.
Its percentile threshold is not a mathematical certificate for unseen launches.
The oracle gate retains more coverage because it knows the correct dynamics; it cannot recover safe flights that the neural planner never proposes.

The showcased failure is also flagged by the abstention rule.
Calling it a calibrated, high-confidence failure would be inaccurate.
The lesson is the cost of accepting raw predictions, and the coverage cost of a cheap refusal rule.

## Inspect one actual false escape

The recorded selection rule takes the first model in a fixed order with a false escape, then its largest positive margin, subject to numerical confirmation.
It selects small-11, trial 3569:

```text
E = 1.0027667008383363
L = 4.0219717740634575
learned escape margin = +0.0027257575165550163
```

The learned particle turns at r ≈ 4.30269 and returns outward.
The exact particle reaches the capture surface.
The exact trajectory's energy drift is 3.16 × 10⁻¹⁰.
The learned trajectory's drift in its own invariant is 3.78 × 10⁻¹², while its drift measured with the exact physical potential is about 0.003277.

This is a selected illustration, not a random representative mission.
Tightening the exact solver tolerance preserves capture and changes terminal proper time by only 2.07 × 10⁻⁸.
The discrepancy is already present in the potentials' barrier margins, before numerical propagation.

## A decision certificate needs a margin

Fix L, r₀, the physical v₀, and the compact radial interval.
Write e(r) = V̂(r,L) − V(r,L).
Suppose a valid uniform bound β is available for the anchored error:

```text
sup_r |e(r) − e(r₀)| ≤ β
```

Then the exact and learned margins satisfy:

```text
|m(V̂) − m(V)| ≤ β
```

Proof: at every radius, the two anchored potentials differ by at most β.
Taking a maximum can change either value by at most β, and both subtract the same v₀².
A uniform absolute potential bound |e| ≤ ε supplies β ≤ 2ε.
If the launch value is exact, β ≤ ε is sufficient.
Constant potential shifts have β = 0.

Thus m(V̂) > β certifies a positive physical margin, while m(V̂) < −β certifies a negative margin, subject to the stated one-dimensional launch assumptions.
If a numerical barrier calculation has an additional certified error η, replace β by β + η.
Parameter uncertainty and discrepancy between Schwarzschild physics and a real vehicle require additional bounds.

A sampled RMSE, a residual percentile, and a visually smooth orbit do not supply this uniform bound.
This proof is an elementary analytic argument, not a machine-checked Lean proof.
The neural models in this project do not carry such a certificate.

## Require an exact certificate for the physical verdict

The live flight response also carries a certificate that a small standard-library checker can verify.
It uses rational arithmetic, so no floating-point tolerance decides its root count.
The inputs mean the exact rational values of the displayed decimal text, not uncertain physical measurements.

The generator supplies a [Sturm chain](https://docs.sympy.org/latest/modules/polys/reference.html#sympy.polys.polytools.sturm): P, its derivative, and the successive negative polynomial remainders.
The checker reconstructs P from E and L and verifies each remainder relation.
It evaluates the signs at r = 2 and r = 30, then checks the declared verdict.
For a square-free polynomial, the difference in sign variations gives the number of roots in that interval.
With an allowed inward launch, zero roots mean capture and two simple roots mean an outer turning point and escape.
Repeated roots remain unresolved.

For the showcased false escape, the evidence is small enough to inspect:

```text
Signs at r = 2:   + − − −     one variation
Signs at r = 30:  + + + −     one variation
Roots in (2,30):  1 − 1 = 0
Checked verdict: capture
Neural verdict:  escape
```

The exact checker agrees with the floating-point physics oracle on all 4,000 frozen launches.
A separate precision test distinguishes L = 4 − 10⁻³⁰ from L = 4 + 10⁻³⁰ at E = 1: capture and escape, respectively.
Both values round to the same ordinary binary float, 4, which the exact checker correctly leaves unresolved if that rounded value is supplied.
Exact arithmetic preserves supplied information; it cannot restore precision already discarded.
Mutation tests alter coefficients, endpoint signs, root counts, and claimed outcomes; the checker rejects the invalid evidence.
It also checks the marginal E = 1, L = 4 case without labelling that double-root trajectory safe.
The conservative repeated-root rule can abstain unnecessarily, for example when L = 0 creates a repeated polynomial root outside the interval.

This is the concrete AI-plus-kernel experiment: the model proposes a fate, while inspectable algebra justifies the physical label.
The kernel does not trust the model's energy conservation, its narration, or the image.
Its trusted base includes the checker, Python's rational arithmetic, Sturm's theorem, and the physical reduction to P.
Those foundations are stated assumptions, not mechanically checked Lean theorems.
A correct certificate proves the decision within the specified model; it does not prove that the model describes a real spacecraft.

[Inspect certificate results and the full saved witness](/results/certificates.json).

## Build a counterexample whose error tends to zero

To separate the mechanism from optimizer quality, the post hoc control adds a known smooth bump to the exact potential.
For each ε, choose a capturing launch with exact margin −ε/2.
Center a compact bump at the exact barrier maximum r*, with width w = 0.5:

```text
z = (r − r*) / w
q(r) = (1 − z²)³  when |z| < 1; otherwise 0
Vε(r,L) = V(r,L) + ε q(r)
```

The bump is twice continuously differentiable, equals one at the barrier maximum, and vanishes at the launch radius.
Because neither the original potential nor the bump exceeds its value at r*, the perturbed barrier increases by exactly ε.
The learned margin becomes +ε/2 and predicts escape.
The original launch still captures.

The uniform potential error is ε.
The uniform radial acceleration error is at most 48ε / (25√5 w).
Both errors tend to zero, yet a false escape exists arbitrarily close to the boundary.
Each perturbed system still conserves its own energy in the continuous equations.

This does not imply a nonzero limiting error rate on a fixed smooth launch distribution.
The failing launches move closer to the boundary as ε decreases.
Their probability mass can shrink to zero.
It also does not contradict continuous dependence of trajectories over a fixed finite time interval.
Near the unstable maximum, the residence time grows logarithmically as the margin approaches zero, and terminal fate is an especially sensitive target.

The control is a worst-case construction, not evidence that ordinary mission risk stays high as model error improves.
Its purpose is to show exactly why a margin condition is necessary.

The saved control checks six values of ε from 10⁻³ through 10⁻⁸.
At both numerical tolerances, 10⁻¹¹ and 10⁻¹³, every exact trajectory captures and every perturbed trajectory escapes.
Four constant-shift controls preserve the original trajectories and margins.

![Controlled potential and acceleration errors decrease while each selected launch still changes fate.](/results/figures/controlled-errors.png)

## Let a four-coefficient model compete

A second post hoc control fits a linear model to the original seed-11 observations using the features 1, 1/r, L²/r², and L²/r³.
Least squares recovers coefficients [1, −2, 1, −2] to within 1.18 × 10⁻¹⁴.
Its independent validation RMSE is 1.56 × 10⁻¹⁵, and it agrees with the oracle on all 4,000 frozen launches.

This basis contains the known physical formula.
The learner did not discover the features, so it would be misleading to call this autonomous discovery of relativity.
It is a privileged structural baseline that reveals how much of this task can be solved by choosing the right representation.
Network size is not the only resource that matters.

[Inspect all post hoc controls](/results/controls.json).

## Reproduce the experiment

The main experiment runs with installed local software.
No software packages or pretrained model weights were installed on the Mac.
The cockpit foreground is a generated visual asset, with a transparent window over the calculated scene.
The ten final fits took 11.08 seconds in total with one BLAS thread.
The saved environment records Python 3.14.0, NumPy 2.4.2, SciPy 1.17.1, and scikit-learn 1.8.0 on macOS arm64.

The analytic baseline made all 4,000 decisions in about 0.20 ms in one local timing run.
The neural batches took about 0.25 seconds for small models and 0.75 to 0.79 seconds for larger models.
These are single measurements, not a controlled speed benchmark.
For this known potential, direct analytic physics is the simplest operational solution.

```sh
python3 -m unittest discover -v
python3 run_experiment.py --smoke
python3 run_experiment.py
python3 run_controls.py
python3 run_certificates.py
python3 render_black_hole.py --check
python3 build_article.py
python3 serve.py --port 8008
```

Open `http://127.0.0.1:8008/` in a browser.
Load the saved false escape, replay both trajectories, change E or L, and launch again.
Use the barrier graph to inspect why the decision changes.
The live server calculates new trajectories; the animation does not invent them.
Saved model weights allow scoring to resume without retraining.
Changing or deleting saved fits changes the reproduction path, so preserve the original artifacts when comparing runs.

The repository separates physics, model fitting, rendering, and HTTP delivery.
Frozen inputs and exported weights survive an interrupted agent session.
Per-model result files permit resume, while the independent oracle and numerical checks catch interface mistakes that plausible prose would not reveal.
The selected-flight rule is stored with the test protocol instead of being reconstructed from memory.
These are concrete controls for long-running agent work: persist state and make claims depend on executable evidence.

The camera image traces 1,296,000 light rays.
Checks compare photon capture against the analytic critical impact parameter and compare disk crossings after halving the integration step.
The physical photon paths are separate from the decorative emission model and from the coordinate flight map.
[GYOTO](https://gyoto.obspm.fr/) is an established relativistic ray-tracing system for more extensive work; this project's renderer covers only the narrow Schwarzschild scene required here.

## A cockpit whose spectacle can be inspected

The first-person view follows the radius and angle of either the exact or learned trajectory.
Changing worlds changes the camera's flight.
Both views trace light with the same Schwarzschild equations.
The neural model changes the flight path, while the optical model stays fixed.
The live renderer recalculates photon paths on the GPU as the camera moves.
Drag across the window to look around, or focus the view and use the arrow keys.
Center view restores the cinematic framing.
Looking changes the directions of traced rays, while the calculated orbit continues unchanged.
The detailed cockpit shell is a generated foreground image, not a walkable 3D interior.
Its decorative switches are separate from the working flight controls.

The camera sits eight degrees above the equatorial plane and turns toward the edge of the black-hole shadow during approach.
This framing keeps the close pass visible.
The viewing radius is clamped at 2.05 while the telemetry continues to the numerical stopping radius of 2.001.
The camera is a cinematic static-frame view, not the exact optical experience of an observer comoving with the particle.
It omits that observer's velocity aberration and frequency shift.

Disk emission, turbulence, glare, cockpit reflections, and particles are visual effects.
They do not supply observations to the neural model or determine a verdict.
The geometric photon calculation and the physical flight classifier have separate accuracy limits.
A good-looking image is not evidence that either calculation is correct.

## Check our solver against GYOTO on AWS

The local checks could still share a mistake in the physical reduction or its implementation.
We used the authorized cloud budget to run an independent implementation check with [GYOTO](https://gyoto.obspm.fr/).
Ubuntu's packaged GYOTO 2.0.2 ran on one temporary `t3.small` server in `us-east-1`.
CloudFormation created the resources; Systems Manager ran the adapter and returned its measurements.
Only the adapter and local physics source were uploaded.
No packages were installed on the Mac.

The adapter uses GYOTO's zero-spin Kerr metric, which reduces to Schwarzschild spacetime.
It supplies the full initial four-velocity and explicitly integrates proper time.
Six energies, from E = 1 through E = 2, each have four angular momenta around the critical value.
The closest launches sit 10⁻⁵ above or below that value.
Each launch runs at relative tolerances of 10⁻⁹ and 10⁻¹¹, for 48 GYOTO integrations in total.

All 24 launches agree with both the local numerical solver and the polynomial oracle: 12 captures and 12 escapes.
Every tighter run passes the recorded conservation thresholds.

| Measurement across 24 launches | Result |
|---|---:|
| Largest energy drift, tighter run | 3.29 × 10⁻¹¹ |
| Largest angular momentum drift, tighter run | 1.27 × 10⁻¹² |
| Largest four-velocity norm error, coarse / tighter | 1.72 × 10⁻⁵ / 2.13 × 10⁻⁷ |
| Largest radius difference between tolerances | 2.73 × 10⁻⁴ M |
| Largest radius difference between GYOTO and the local solver | 3.62 × 10⁻⁴ M |

Path comparisons use linear interpolation at shared proper times, so their differences include interpolation error.
Stored samples detect stopping-surface crossings; they do not establish exact terminal times.
This check covers timelike flights, not the cockpit's photon renderer.
Independent numerical agreement strengthens the implementation check without supplying a formal proof.

The science program took 1.68 seconds; provisioning, execution, and teardown together took 367 seconds.
The runner confirmed CloudFormation deletion after retrieving the result.
Separate AWS reads confirmed termination and deletion of the temporary role, instance profile, and security group.
No attached volumes or matching root-disk volumes from the run window remain.
Estimated compute, public IPv4, and disk cost is $0.00277, before tax and transfer.
That estimate uses elapsed wall time and published rates; it is not a final bill or a verified credit deduction.
The server also had a 45-minute termination backstop.
[EC2 rates](https://aws.amazon.com/ec2/pricing/on-demand/), [disk rates](https://aws.amazon.com/ebs/pricing/), and [IPv4 pricing](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/) define the cost model.

[Inspect all GYOTO measurements and cleanup status](/results/gyoto-cloud-run.json).
[Inspect the independent cleanup checks](/results/gyoto-cleanup.json).

## What the evidence supports

The experiment shows a failure of raw learned-potential decisions under a chosen boundary distribution, despite numerical conservation of the learned invariant.
It also shows that a cheap abstention rule removes every observed false escape at a substantial coverage cost.
The constructed smooth perturbations explain why arbitrarily small model error cannot give uniform fate guarantees without a margin condition.

It does not establish a failure rate for frontier foundation models, a scaling limit, or a new general AI-safety theorem.
Five seeds and one analytic physical system do not support those claims.
The exact oracle has privileged knowledge, the structured classical solution is cheaper, and the strongest safety statement remains conditional on the physical assumptions.

The next informative experiments would compare active sampling near the unstable orbit, derivative-supervised fitting, and certified uniform-error methods at matched data and compute budgets.
A rotating black hole would test a harder physical setting, but would also require new validation and cannot be added merely by changing the picture.
