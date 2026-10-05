# Cockpit free look

The cockpit renderer accepts view offsets while the selected flight replay sets the camera position.
Looking around does not change the orbit, its energy, or its outcome.
The foreground cockpit shell remains a static image.

Pass `lookYaw` and `lookPitch` to `CockpitRenderer.render()` in radians.
Both fields default to zero.
The renderer limits yaw to `-0.8` through `0.8` and pitch to `-0.45` through `0.45`.
Positive yaw looks right.
Positive pitch looks up.
Set both fields to zero to restore the existing cinematic view.

Yaw rotates the view around the camera's local vertical axis.
Pitch rotates the view around its horizontal axis.
The renderer then derives each photon ray from the rotated view.
It calculates the ray's impact parameter and integrates the same Schwarzschild null-geodesic equations.
The camera radius and orbit angle stay unchanged.
The local camera frame remains static, with the cinematic height and radius limits described in [the rendering report](cockpit-render-report.md).
The view does not model the moving particle's physical reference frame or observer-velocity aberration.

The image fallback pans its existing static image for the same controls.
That fallback remains an illustration and does not trace new light paths.

`node --check dashboard/cockpit.js` passes.
A numerical check covers view limits at camera radii `2.05`, `4`, and `30 M`.
The rotated view axes stay orthogonal and have unit length.
The ray initialization preserves `v² + (1 - 2/r) b²/r² = 1` to floating-point precision.
The frontend owns the input controls and the final integrated Chrome check.
