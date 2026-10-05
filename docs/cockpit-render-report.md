# Moving cockpit camera

The cockpit view traces light on the GPU as the selected orbit replay moves the camera.
The black shadow grows during approach.
At close range, the camera turns toward the shadow's edge so the bright disk stays in view.
Both replay choices use Schwarzschild light propagation.
The selected orbit changes the camera position, not the light equations.

## Interface

Create `new window.CockpitRenderer(canvas)` after loading `/cockpit.js`.
Call `render({radius, phi, time, playing, width, height})` when replay state or viewport size changes.
Width and height are CSS dimensions.
The renderer owns the canvas's internal dimensions.
It caps playing frames at `800 x 500` and paused frames at `1440 x 900`, while preserving the viewport ratio.
Paused frames use the device pixel ratio, up to two, within that limit.
The optional `time` field drives the artistic disk texture.
If absent, the texture clock uses `220 progress`.
It has no animation loop of its own.
The host controls playback and reduced-motion behavior.
The renderer also accepts the host's `progress`, `energy`, `angularMomentum`, and `outcome` fields.
Those fields do not change the light equations.
Read `mode` to distinguish `Schwarzschild ray tracing` from `Illustrative image fallback`.
Read `error` for a shader failure or context loss.
Read `hdr` to see whether the GPU uses a floating-point radiance buffer.
Call `dispose()` to release GPU resources and the fallback canvas.

## Light calculation

Units are `G = c = M = 1`.
The photon energy is normalized to one.
Each perspective ray gets an impact parameter from its direction in a local static frame:
`b = r sin(alpha) / sqrt(1 - 2/r)`.
Each ray stays in a plane through the black hole.
The shader integrates the null-geodesic equations:

```text
dr/dlambda = v
dv/dlambda = b²/r³ - 3b²/r⁴
dphi/dlambda = b/r²
```

The shader uses midpoint integration, at most 192 steps, and step length `min(1.35, 0.055 r)`.
The disk lies in `y = 0`, from `6 M` to `18 M`.
The first disk intersection emits light and stops that ray.
Captured rays stop at `2.001 M`.
Outgoing rays stop at `60 M` and sample a procedural sky by their exit direction.
Unresolved rays remain dark.
Disk brightness includes gravitational and orbital Doppler shifts with a `g³` weight.
The radial emissivity and gold-to-ivory colors are artistic choices.
Multiscale value noise creates warped filaments and bright emission knots on the disk.
The emission texture turns at a radius-dependent rate proportional to `r^(-3/2)`.
This animated texture does not simulate a fluid or use light-travel delays.
The procedural stars have varied brightness and color, with rare narrow glare profiles.
There are no particles drawn over the viewport by this renderer.

The first GPU pass stores linear radiance in an `RGBA16F` buffer when the browser supports it.
Otherwise, it stores radiance with a 12-stop logarithmic encoding in an eight-bit buffer.
A second GPU pass applies exposure and a film tone curve after adding bloom.
It also adds subtle glare, fine film grain, and edge smoothing.
Those display effects do not change ray intersections.
The display effects preserve the underlying photon calculation, but they are not a calibrated camera model.

## Camera choices and limits

The camera follows the replay radius and orbit angle.
It sits eight degrees above the orbit plane so the thin disk remains visible.
The rendered radius stops at `2.05 M`; the HUD keeps the calculated replay radius.
The horizontal field of view is about 74 degrees.
The camera bank is `0.07 sin(phi)` radians.
The camera turns sideways during approach, reaching 90% of the static observer's shadow angle below `10 M`.
For `r >= 3`, the shadow angle is `asin(3 sqrt(3) sqrt(1 - 2/r) / r)`.
Below `r = 3`, the camera uses the supplementary angle.
The turn ramps smoothly from zero at `30 M` to full strength at `10 M`.

This is a cinematic camera tied to an unpowered particle replay.
It is not a camera carried in the particle's physical reference frame.
The view omits observer-velocity aberration and the corresponding frequency shift.
It also omits black hole spin and full radiative transfer.
Its light calculation does not certify the orbit or determine capture outcomes.
The renderer uses a faster, less accurate integrator than the offline image renderer.
Thin higher-order images can still alias.

If WebGL2 is unavailable or a program fails, a 2D sibling canvas scales and rolls the existing static image.
The host labels that view `Illustrative image fallback`.
This fallback does not recalculate light paths.

## Verification

`node --check dashboard/cockpit.js` passes.
The integrated HTTP dashboard compiled both updated HDR and filament programs in the user's actual Chrome browser.
The visible mode was `Schwarzschild ray tracing`.
The page was inspected directly at these replay positions:

| Replay | Calculated radius | Visible result |
| --- | --- | --- |
| Start | `30.000 M` | Irregular white and gold filaments, luminous rear arc, and black shadow |
| 52% | `4.026 M` | Large shadow on the left, bright resolved filaments and sky on the right |
| 66% | `2.619 M` | Shadow fills most of the window; a bright arc remains at its edge |

The view changes from newly traced rays, not a scaled PNG, on the verified WebGL path.
A CPU mirror of the shader's midpoint equations tested six rays from radius `30 M`.
All rays below `3 sqrt(3)` at 90%, 99%, and 99.9% were captured.
All rays above it at 100.1%, 101%, and 110% escaped within 192 steps.
The largest null-energy invariant error in those tests was `0.00351699`.
This is a bounded accuracy check, not an error guarantee for every rendered ray.
The updated cinematic pass was inspected again at the start and at 52% replay.
The 66% check predates the emission-texture update; the null paths and camera equations are unchanged.
The actual browser check did not force WebGL failure or measure a frame rate.
No libraries or assets were downloaded.
