# Observatory demo

The demo compares the calculated relativistic trajectory with the trajectory from a saved learned potential.
The browser requests both traces from the same local experiment server.
It does not calculate or invent physical outcomes.

## Visual design

The scene uses deep violet space, ivory text, a warm copper accretion disk, and an ice-blue learned orbit.
A large native canvas provides the calculated flight map.
A separate lensed view presents a black hole image calculated from Schwarzschild light paths with artistic disk emission.
The image and the coordinate map remain separate because they do not use the same projection.
The default cockpit view follows either real calculated trajectory with a moving camera.
Play, launch, and scrub preserve the selected cockpit or map view.
A sparse window frame and live radius, horizon clearance, and proper time give the cockpit its sense of scale.
The moving camera uses a cinematic lift and a minimum visual radius of 2.05 M.
It is not the exact optical view of a moving spacecraft.
The renderer states whether it uses Schwarzschild ray tracing or an illustrative fallback.
The flight remains an unpowered particle trajectory.
A visible play button starts the flyby in the first viewport.
Immersive view expands the cockpit inside the browser without a fullscreen permission request.
The page traps keyboard focus inside the scene and makes the background inert until exit.
Escape exits and restores focus to the control that opened the scene.
Replay, recorded-flight, world-switch, and exit controls remain available.
An alpha image supplies decorative shuttle hardware while native HTML controls remain separate and accessible.
The Effects toggle controls window reflections, decorative dust, and ambient light on the hardware.
These effects are artistic and do not alter the orbit or simulate physical sensors.
Decorative dust motion pauses with replay and is disabled by reduced motion.
The shader receives the selected trajectory's actual proper time.
The cockpit supports drag-to-look and arrow keys when the view has keyboard focus.
Yaw is limited to 0.8 radians in each direction and pitch to 0.45 radians.
Center view restores the original camera direction.
Looking changes the camera direction only, while the calculated orbit and its outcomes stay fixed.
On a normal mobile page, vertical touch motion scrolls the page and horizontal touch motion turns the view.
Immersive mode lets touch motion turn the view in both directions.
Capture freezes at the recorded numerical surface, r = 2.001.
The endpoint message does not show flight inside the horizon.
A narrow flight desk holds the launch controls, outcomes, and replay.
Georgia gives the observatory title its quiet character.
Local Avenir and system sans-serif fonts keep controls legible.
The luminous disk in the coordinate map is explicitly illustrative.
The plotted paths use Schwarzschild coordinates, with the event horizon at r = 2 on the same scale.

## Interaction

The energy and angular momentum sliders use the specified bounds.
Model choices come from the saved summary.
Launch requests real traces from `/api/flyby`.
The recorded flight loads `/api/showcase` data.
Play, pause, reset, and scrubbing use shared proper time.
The two traces are interpolated independently because they have different time samples.
A captured marker stops at the numerical horizon surface and then disappears.
Map controls zoom in, zoom out, and fit the full orbit.
New requests cancel earlier requests so stale responses cannot replace a newer flight.
The experiment section links to all saved test rows, the JSON summary, and the article.
The barrier plot uses sampled exact and learned potentials from the loaded flight response.
Each curve subtracts its own potential at the launch radius so the initial physical radial speed gives the same horizontal energy line.
The default vertical detail includes the energy line and both sampled peaks.
The plot can also show the whole potential range.
Text reports the energy margin against each sampled peak.
The graph does not replace the independent orbit check.
The interface reports the exact certificate result separately from raw learned predictions and heuristic abstention.
Certificate details expose the root count, sign variations, rational inputs, and a user-triggered JSON download.
The certificate is an exact rational Sturm check under the unpowered Schwarzschild assumptions, not a Lean proof.

## Accessibility and verification

All controls have labels and visible keyboard focus.
The page supports narrow screens without hiding the launch controls.
The view switch stays near the top of the scene.
On desktop, the scene fits the viewport and stays visible while the page scrolls through the flight desk.
The map has no wheel handler, so an ordinary wheel gesture scrolls the page.
Reduced motion prevents automatic playback.
Replay pauses when the browser tab is hidden.
Loading errors remain visible and explain how to recover.
Numerical data comes only from saved result fields.
Unrecorded fields display an explicit missing-data label.
The JavaScript passes `node --check dashboard/app.js`.
The replay interpolation check verifies independent time grids and terminal clamping.
Real Chrome checks passed for a new launch, trajectory switching, playback, pause, scrubbing, and certificate inspection.
Drag and arrow keys changed the view without changing paused flight telemetry.
Center view restored the original framing.
Immersive entry, Escape exit, and focus restoration worked.
The final immersive layout was inspected at 390 by 844 pixels with no horizontal overflow.
The viewport override was reset after testing.
The application produced no captured browser errors.

Run the replay interpolation check from the project root:

```sh
node <<'JS'
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('dashboard/app.js', 'utf8');
vm.runInThisContext(source.match(/function pointAt[\s\S]*?\n}\n/)[0]);
assert.deepEqual(pointAt([[0, 30, 0], [10, 10, 2]], 5), [5, 20, 1]);
assert.deepEqual(pointAt([[0, 30, 0], [20, 10, 2]], 5), [5, 25, 0.5]);
assert.deepEqual(pointAt([[0, 30, 0], [10, 2.001, 2]], 50), [10, 2.001, 2]);
console.log('Replay interpolation: independent time grids and terminal clamping pass.');
JS
```
