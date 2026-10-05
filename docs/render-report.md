# Schwarzschild camera render

The dashboard image traces light through a Schwarzschild spacetime.
Its upper disk arc and thin secondary image come from bent rays.
The image is a static camera view, separate from the dashboard's equatorial spacecraft map.

## Scene and method

- Units: `G = c = M = 1`.
- Static camera radius: `32 M`.
- Camera height angle above the disk: `12.5 degrees`.
- Infinitely thin, opaque disk: `y = 0`, radius `6 M` to `18 M`.
- Native image: `1440 x 900`, one traced ray per pixel, no image upscaling.
- Shadow center: `55%` across and `53%` down the image.

Each camera ray stays in the plane through the camera and the black hole.
The local camera direction sets its impact parameter `b = r_camera sin(alpha) / sqrt(1 - 2/r_camera)`.
The renderer sets the conserved photon energy to one.
It integrates these null-geodesic equations with fourth-order Runge-Kutta:

```text
dr/dlambda = v
dv/dlambda = b²/r³ - 3b²/r⁴
dphi/dlambda = b/r²
```

The ray's position is `r (radial_basis cos(phi) + tangent_basis sin(phi))`.
The renderer interpolates disk-plane crossings between integration steps.
The first crossing within the disk radius emits light and stops that ray.
Rays that reach `r <= 2.001 M` enter the black hole.
Outgoing rays stop at `r >= 60 M`.
Step length is `min(0.9, 0.0225 r)`.
The renderer processes batches of 24,000 rays to limit memory use.

Circular disk motion uses `Omega = r^(-3/2)`.
The displayed frequency ratio includes gravitational redshift and orbital Doppler shift:
`g = sqrt(1 - 3/r) / [sqrt(1 - 2/r_camera) (1 + Omega J_y)]`.
Here `J_y` is the backward-traced ray's angular momentum around the disk axis.
The brightness uses a `g³` weight, appropriate for a specific-intensity transformation.

The radial emissivity, copper-to-ivory color map, disk bands, and spiral texture are artistic choices.
They do not come from a thermal disk spectrum or a fluid simulation.
Bloom, tone mapping, display stars, and grain are display effects.
The display stars are not a ray-traced star catalogue.
This renderer does not model spin, Kerr spacetime, absorption, scattering, or full radiative transfer.
The thin secondary image can alias at one ray per pixel.

## Fresh verification

Run `python3 render_black_hole.py --check`.
The check passes with these results:

| Check | Result |
| --- | --- |
| Analytic critical impact parameter | `3 sqrt(3) = 5.196152422706632 M` |
| Below threshold at 90%, 99%, and 99.9% | All captured |
| Above threshold at 100.1%, 101%, and 110% | All escaped |
| Capture labels after halving the step | Unchanged |
| Screen rays in crossing comparison | 2,000 |
| Disk hits shared by both resolutions | 1,000 |
| Maximum crossing-radius change | `0.00183109 M` |
| Median crossing-radius change | `0.00057618 M` |
| Disk-hit classification changes | 0 |
| Maximum null-energy invariant error | `2.36533 x 10^-6` |

The invariant is `v² + (1 - 2/r) b²/r² = 1`.
These checks validate the tested rays and the integration settings.
They do not establish an error bound for every image pixel.

Run `python3 render_black_hole.py --width 1440` to rebuild the asset.
The final local render took `14.71 seconds` and traced `1,296,000` pixels.
It found `340,522` first disk intersections.
The process used `406,568,960 bytes` maximum resident memory and no swaps, measured with `/usr/bin/time -l`.
No packages or external image assets were downloaded.
The final PNG was opened and inspected directly.
