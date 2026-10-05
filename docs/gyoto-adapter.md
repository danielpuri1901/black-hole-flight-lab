# Independent GYOTO trajectory adapter

`run_gyoto_check.py` checks 24 equatorial, timelike launches with GYOTO.
It checks six energies and four angular momenta on both sides of the exact capture boundary.
It repeats each launch at relative tolerances of `1e-9` and `1e-11`.
The script compares observed GYOTO outcomes with the local polynomial oracle and the local DOP853 integrator.
It emits compact scientific JSON and writes progress to standard error.
The adapter limits its raw JSON to less than 100,000 bytes.
The cloud runner compresses the JSON with gzip and encodes it with base64, with a 20 KB limit on the transported result.

## Coordinate conversion

The metric is GYOTO `KerrBL` with zero spin.
The coordinates are Boyer-Lindquist `[t,r,theta,phi]`, which reduce to Schwarzschild coordinates at zero spin.
The launch is at `r=30`, `theta=pi/2`, and `phi=0`, with `G=c=M=1`.
For `f=1-2/r`, the initial contravariant four-velocity is:

```text
u^t = E/f
u^r = -sqrt(E^2 - f*(1 + L^2/r^2))
u^theta = 0
u^phi = L/r^2
```

The script passes the full eight-coordinate state to `Star.setInitCoord`.
It passes `True` to `xFill` to select proper time explicitly.
It retrieves coordinate time with `get_t`, proper time with `get_tau`, and four-velocity with `get_dot`.
The 2.0.2 binding lacks the newer NumPy wrapper for `get_tau`, so the adapter uses its documented C-array view when needed.
These APIs are present in the official 2.0.2 source and Python binding.
`get_t`, `get_tau`, and `get_dot` copy the same stored index range, so their arrays align.
The adapter verifies that coordinate retrieval does not change the stored-state count before retrieving velocity.
[Worldline header](https://github.com/gyoto/Gyoto/blob/2.0.2/include/GyotoWorldline.h), [Python binding](https://github.com/gyoto/Gyoto/blob/2.0.2/python/gyoto.i).

The engine's default horizon sink would stop before the project's capture surface.
The adapter therefore sets `HorizonSecurity=0.0001`, placing the engine sink at `r=2.0001`.
It calls capture only after observing `r<=2.001`.
It calls escape only after observing `r>=30` with positive radial four-velocity after launch.
If neither surface is observed, the flight remains unresolved.
[Official KerrBL sink implementation](https://github.com/gyoto/Gyoto/blob/2.0.2/lib/KerrBL.C).

## Measurements and limits

For each flight, the adapter records energy drift, angular momentum drift, four-velocity norm error, and departure from the equatorial plane.
It records path differences between tolerances and between engines at shared proper times.
Linear interpolation contributes to those differences, so they are diagnostics rather than certified error bounds.
Observed terminal times use stored sample crossings and are not exact event times.
The tighter run must have energy and angular momentum errors below `1e-6`, norm error below `1e-5`, and equatorial error below `1e-8`.
These numerical thresholds are operational checks, not theorem claims.
Independent numerical agreement can reveal implementation errors; it does not prove safety.
Photon checks are explicitly unperformed in this bounded run.

The remote package is Ubuntu's GYOTO 2.0.2 build, not current upstream master.
The report records the installed package versions through `dpkg-query`.
The script was syntax-checked locally, but GYOTO is absent on the Mac.

## Verified AWS result

The full AWS run completed on 2026-10-04 with `gyoto=2.0.2-1.1build3` and `python3-gyoto=2.0.2-1.1build3`.
All 24 launches agreed between both GYOTO tolerances, the local DOP853 integrator, and the polynomial oracle.
All 24 tighter GYOTO runs passed the stated conservation checks.
The 48 GYOTO integrations and local comparisons took about 1.68 seconds inside the remote adapter.

| Maximum observed error | Relative tolerance 1e-9 | Relative tolerance 1e-11 |
| --- | --- | --- |
| Four-velocity norm | 1.716e-5 | 2.133e-7 |
| Conserved energy | 1.972e-9 | 3.289e-11 |
| Angular momentum | 3.427e-11 | 1.270e-12 |
| Equatorial angle | 0 | 0 |

The tighter tolerance reduced norm error substantially.
The coarse norm maximum exceeded the operational threshold used for the tighter run, so the coarse run should not be described as passing that threshold.
The largest sampled radius difference between engines was about `3.62e-4` in units of M, and the largest azimuth difference was about `2.35e-4` radians.
These path differences include interpolation error and do not provide continuous error bounds.
The test covers the selected launches, not all initial conditions, exact boundary cases, spinning black holes, or rendered photon paths.
[Scientific result](../results/gyoto-cloud-run.json).

Independent read-only AWS checks confirmed CloudFormation `DELETE_COMPLETE`, the terminated instance, no attached block devices or volumes, and deletion of the temporary role, instance profile, and security group.
Volume deletion was not separately checked by volume ID.
An additional search found no remaining encrypted 12 GiB gp3 volumes created during the run window, across all volume states.
The saved cleanup evidence contains no account or resource identifiers.
[Cleanup evidence](../results/gyoto-cleanup.json).

## Run

```sh
/usr/bin/python3 run_gyoto_check.py --probe
/usr/bin/python3 run_gyoto_check.py
```

Upload only `run_gyoto_check.py` and `physics.py`.
The script requires the remote `gyoto`, NumPy, and SciPy packages described in the cloud plan.
