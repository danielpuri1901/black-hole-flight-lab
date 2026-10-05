# Black Hole Flight Lab

## Outcome

Build an immersive, interactive experiment about learned world models that make incorrect escape predictions near a black hole.
The user selected this direction and authorized autonomous execution.
The experiment must remain useful if learned models perform well or classical physics is the cheapest solution.
Deliver working code, saved data, an interactive demo, and an engineering article.

## Physics scope

Use equatorial, unpowered, timelike Schwarzschild geodesics in units G=c=M=1.
The launch planner chooses the initial trajectory; it does not steer during free fall.
Set initial radius to 30, energy E in [1.002, 1.2], and positive angular momentum L in [3.5, 6.3].
Reject physically invalid initial states.
The event horizon is r=2.
Stop numerical capture trajectories at r=2.001 and label this numerical stopping surface.
Use the effective potential V(r,L)=(1-2/r)(1+L*L/(r*r)).
Integrate radial position, radial velocity, and azimuth with SciPy DOP853.
Check energy conservation and tighter-tolerance convergence.
Construct a separate capture oracle using the polynomial for radial turning points.
Treat exact and numerically ambiguous boundary cases as unresolved.
Do not infer radiation survival, tidal survival, powered escape, or singularity physics.

## Experiment

Learn the effective potential from synthetic state observations.
Call these compact neural world models; do not present them as foundation models or video models.
Use existing scikit-learn MLPRegressor, NumPy, and SciPy.
Train small (16,16) and larger (64,64) tanh networks on the same datasets for seeds 11,22,33,44,55.
Inputs are inverse radius and angular momentum, standardized on training data.
Standardize the target potential on training data.
Use 4096 observations sampled uniformly in log radius between 2.02 and 30 and uniformly in L between 3.5 and 6.3.
Keep a separate validation set for tuning and error calibration.
Record fit time, parameter count, convergence status, potential RMSE, and radial-acceleration RMSE.
Freeze test sampling before training.
Nominal test has 2000 independently sampled E,L pairs.
Boundary stress test has 2000 E,L pairs, balanced on either side of the exact capture boundary, at relative distances sampled log-uniformly from 1e-5 to 1e-2.
Label boundary sampling as a stress test, not the natural frequency of missions.
Calculate predicted escape from the learned potential barrier and the learned conserved energy corresponding to the same initial physical radial velocity.
Report dangerous false escapes, false captures, accepted-flight coverage, and uncertainty intervals.
Use analytic physics as a strong baseline and a numerical geodesic calculation as an independent cross-check.
A verification treatment checks proposed escape predictions against the independent polynomial oracle.
Count rejected flights explicitly and disclose that the gate has access to the correct physics.
Do not claim the gate learns physics or proves arbitrary safety.
Select the showcased counterexample by a recorded deterministic rule and keep all test rows available.
If no dangerous false escape occurs, report that outcome and use the smallest-margin disagreement or an ordinary flight for the demo.
Do not change held-out data or training settings to force a headline.

## Interactive demo

Make a cinematic observatory with an immersive central black hole, clear trajectory overlays, and quiet controls.
Use a native browser canvas, HTML, and CSS without downloaded UI dependencies.
Expose energy, angular momentum, model choice, launch, replay, pause, scrub, and saved counterexample controls.
The browser requests trajectories from a local Python server so the same tested numerical path drives the demo.
Show model prediction, exact outcome, and uncertainty state before replay.
Use contrasting labeled lines for learned prediction and relativity.
Clearly distinguish an illustrative lensing background from the calculated coordinate trajectory plot.
Include live experiment results and links to the article and raw data.
Support keyboard focus, reduced motion, mobile layout, loading errors, and cancellation of stale flight responses.
Serve only project-owned dashboard and result files on loopback.
Validate numeric query ranges before computing trajectories.

## Deliverables and execution constraints

Keep every file inside the project folder.
No installation is required for the initial experiment.
AWS budget is a total ceiling of EUR 50, not an obligation to spend it.
Measure local execution before choosing cloud resources.
Before any additional installation, provide the exact manifest required by the user's standing instructions.
Use lower-tier implementers for bounded independent tasks.
Do not add reviewer agents or whole-project review passes.
Use failing checks, actual runs, and fresh integration verification.
Maintain docs/progress.md so restarts can resume from durable state.
Persisted prose uses normal simple English with one full sentence per line and no em dash.
