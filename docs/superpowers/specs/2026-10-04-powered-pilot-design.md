# Powered black-hole pilot

The pilot must control a spacecraft, spend a finite fuel budget, observe the resulting state, and replan.
The existing unpowered experiment and its fixed-energy certificate remain separate scientific results.

## Research question

Can a small learned generator replace expensive plan search near a relativistic capture boundary, and when does numerical physics checking repair its decisions?
Compare a learned proposal executed directly, the same proposals selected by exact-equation rollouts, and a classical planner.
Measure mission success, minimum radius, fuel, decision time, and the cost of the checks.
Publish adverse results as well as improvements.
This is an experiment in model-based imitation and runtime checking, not a claim of a new general learning algorithm.

## Dynamics

Use equatorial timelike Schwarzschild dynamics in units G=c=M=1.
The state is [r, radial four-velocity, angular momentum, azimuth, consumed impulse].
Controls specify radial and tangential proper acceleration in the instantaneous rest frame obtained from the static tetrad by a rotationless boost.
Bound acceleration magnitude and consumed impulse.
Use the relativistic rocket equation to display remaining propellant under an explicitly stated exhaust-speed assumption.
Stop at a mission safety surface outside r=2 and label it a safety-cutoff failure, not a proof of horizon capture.
An outward state beyond r=20 with energy at least one can finish by coasting; validate the numerical margin.
Compare the reduced engine against an independently coded full four-velocity integrator.
Check normalization, acceleration orthogonality, zero-thrust conservation, convergence, and fuel exhaustion.

## Learned planner

Generate teacher action sequences with a classical planner using the controlled engine.
Freeze train, validation, and test seeds before fitting.
An autoencoder compresses bounded action sequences into a small latent vector.
A conditional diffusion model generates latent plans from the current ship state.
A small transformer performs the denoising.
Decode, enforce physical action limits, score candidates with the controlled engine, execute the first burn, and repeat.
Use numerical physics checks rather than a learned dynamics model for the checked planner.
Export the learned weights for NumPy inference and verify parity with the training implementation.
Measure reconstruction and denoising losses, but judge the pilot through closed-loop flights.

## Presentation

Keep the existing cinematic cockpit and add powered flight mode, fuel, thrust, replanning, and controller selection.
The displayed trajectory must come from actual closed-loop decisions.
Permit deterministic replay and compare controllers on the same launch.
Retain free look and immersive mode.
Explain that the cockpit is a rendered foreground, photon optics use a static observer approximation, and the flight engine is an equatorial model.
Do not call the numerical controller formally verified or claim escape from inside the horizon.

## Execution

Use the existing local Python, NumPy, and SciPy installation for simulation and inference.
After the package manifest is approved, train on one temporary AWS CPU server with a two-hour termination backstop.
Use a $5 working allowance within the authorized $50 total budget.
Verify returned artifact checksums, then remove every temporary cloud resource.
Record source hashes, seeds, parameters, versions, measured results, and limitations in the research article.
