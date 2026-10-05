# Powered cockpit verification

The powered cockpit now places a procedural 3D cabin in front of the live Schwarzschild photon renderer.
It reads actual powered state histories from the local API.
The two recorded AI traces represent different control decisions in the same physical engine.

## Browser checks

The real Chrome browser opened `http://127.0.0.1:8008/pilot`.
A coast launch at radius 9, energy 1.02, and angular momentum 3.4 completed through the form and API.
The replay advanced through nine recorded decisions and stopped at the mission safety radius 2.1.
Fuel remained at 100 percent, as expected with zero thrust.
The page showed the safety cutoff as a failed return rather than a proven horizon crossing.

Immersive mode filled the viewport, and Escape restored the standard page.
The immersive heading was reduced after visual inspection so it covered less of the window.
At a 390 by 844 pixel viewport, the document width remained 390 pixels.
The launch form, controls, and scene fit without horizontal overflow.
The initial radius and fuel placeholders were shortened to prevent overlap in the mobile instrument row.
The viewport override was reset after testing.
The browser developer log contained no JavaScript errors during these checks.

## Trained pilot and finished artifacts

A real checked-model launch at radius 9, energy 1.02, and angular momentum 3.4 escaped through the form and API.
The controller made 31 decisions, reached a sampled minimum radius of 4.313M, and retained 70.5% of its propellant.
The terminal proper time was 61.5M.

The recorded nominal mission 8 loaded both actual control histories.
Scrubbing the raw trace to its endpoint showed the safety surface at 2.1M, proper time 17.7M, and 52.0% remaining propellant.
The checked trace reached 20M at proper time 49.9M, with 46.7% remaining propellant.
Switching controllers preserved the replay time within the destination trace's duration.
Immersive mode, replay scrubbing, and the Center view button were exercised on the recorded pair.

The final dashboard displayed 14 main rows and four supplemental rows.
Supplemental rows were labeled post hoc and linked to their own artifact.
The visible note explained that these controls use no learned weights.
The finished dashboard and article had a 390-pixel document width in a 390-by-844 viewport.
The result table scrolls within its container on narrow screens.
The browser developer log contained no JavaScript errors in the final checks.
All temporary viewport overrides were reset.

The article rendered both scientific SVG figures, the measured tables, and the final headline.
All 15 distinct local article links and figure URLs returned HTTP 200.
Both the cockpit and article tabs were retained as deliverables in real Chrome.

The initial missing-artifact state correctly says that training is in progress.
It does not invent a learned flight.

## Three-dimensional cabin and frame pacing

The 3D upgrade was exercised in the real Chrome browser at a 1470 by 661 pixel viewport.
Pilot, Cabin, and Window presets share the same calculated orbital state.
Pointer dragging and arrow keys rotate the view; WASD and Q/E move the camera inside the cabin.
The camera moved from behind the seats into the center aisle without advancing proper time.
A forward movement at x=0.546 stopped at z=1.880, outside the expanded seat collider.
Moving sideways into the aisle allowed the camera to continue to z=0.512.
The renderer also has swept movement checks, so a large step cannot skip a seat collider.

The first UI loop mistakenly treated dragging as idle animation and limited it to about 15 frames per second.
Dragging now renders on each animation frame, while unattended dust remains capped at 15 frames per second.
A separate playback bug retained a cancelled animation-frame handle and prevented Begin flight from restarting the loop.
The fix clears that handle before scheduling a new frame.
The recorded checked flight then advanced through its full trace and ended at radius 20M and proper time 49.9M.

Static cabin geometry and the fixed light direction allow the shadow map to be reused.
This reduced the measured pilot-view draw calls from 388 to 148 before the final attachment repairs.
Live instrument texture uploads are limited to 10 per second during playback; paused scrubs update immediately.
The exterior image is reused when its camera and orbital inputs are unchanged.
During interaction, the renderer uses a smaller pixel budget while retaining the cabin geometry, bloom, dust, and shadows.

Two rolling samples of 120 flight frames had a median interval of 16.7 milliseconds and a 95th-percentile interval of 16.8 milliseconds.
The sampled GPU elapsed times were 11.5 and 12.5 milliseconds.
A real pointer drag supplied eight frames with a median and 95th percentile of 16.7 milliseconds.
A ten-second camera sweep produced 599 frames, with a median of 16.7 milliseconds and a 95th percentile of 17.5 milliseconds.
These are local browser measurements, not a guarantee for other devices.
The sweep can be repeated at `/pilot?diagnostics` with the Run camera benchmark button.
Its result stays visible after the run and is also stored in the canvas `data-benchmark-stats` attribute.
Rolling cadence and renderer costs are exposed in `data-frame-stats` and `data-render-stats`.

Visual inspection found unsupported desk and ceiling-rack parts, raised switches, and disconnected trim.
The repairs add desk legs, console feet, rack mounts, and a continuous front fascia.
Controls, harnesses, and cable mounts now meet their supporting surfaces.
Transformed geometry bounds were checked for contact, then the cabin was inspected from the aisle and side views.
Immersive mode, Hide HUD, Escape, and sound on/off controls worked in Chrome.
Sound was left off.
The final full-screen ten-second camera sweep also produced 599 frames, with a median interval of 16.7 milliseconds and a 95th percentile of 17.5 milliseconds.
Proper time stayed at zero throughout that camera-only benchmark.
At a 390 by 844 pixel viewport, the 3D page's document width remained 390 pixels.
The temporary viewport override was reset.
The final Chrome developer log contained no JavaScript errors.

All 38 Python checks passed in 16.720 seconds after the server route changes.
The three new or changed rendering modules passed JavaScript syntax checks.
All 15 vendored Three.js file hashes matched the approved dependency manifest.
The frozen powered physics, controller, and model source hashes remained unchanged.

## Material detail and truthful instruments

The next visual pass adds small deterministic paint, metal, and fabric textures, plus printed panel markings.
The accretion disk uses finer sheared bands with lower peak emission and bloom.
An artistic upward camera aim exposes the upper lensed arc at the recorded launch radius.
The camera change does not alter the orbit or the light-path integration equations.

Close inspection found that the solid tabletop still hid the lower rows of the instrument screens.
All four lit faces were raised clear of their supports, while their housings remain mounted in the desk.
The trajectory screen's decorative curve was replaced by the actual recorded radius history.
Proper time now uses geometric units, and the interface supplies the selected controller to the cabin renderer.
In Chrome, switching from Raw AI to Checked AI at proper time zero changed both the controller name and the recorded curve.
The burn command changed with the selected trace.

The new `node check_cabin.mjs` check passed against actual Three.js geometry.
It checks all four screen planes against their supporting surfaces and all three camera presets against expanded colliders.
Captured canvas calls verify time units, controller text, input trajectory coordinates, controller-only refresh, trajectory-only refresh, and the missing-trace state.
The canvas stub tests geometry and drawing commands; it does not test GPU output.
The four rendering JavaScript files passed syntax checks.
The frozen science source hashes remained unchanged.

The finished full-screen ten-second camera sweep produced 599 frames.
Its median interval was 16.7 milliseconds, and its 95th percentile was 18.3 milliseconds.
These measurements are from the local Chrome session with the added material detail.

The recorded checked flight played to radius 20.000M, proper time 49.9M, and 46.7% fuel remaining.
Long hardware labels now fit their texture width, including the pressure hatch and manual release markings.
The canvas check rejects nonfinite fonts and coordinates and checks the longest label's measured width.
At a 390 by 844 pixel viewport, the camera controls now occupy one row above the mission text.
Their measured bottom edge was 112.5 pixels, above the mission text's top edge at 159 pixels.
The document width remained 390 pixels, and the viewport override was reset.
Fresh geometry and JavaScript syntax checks passed after the final label repair.
The final Chrome console contained no JavaScript errors.
The demo was left paused in the forward immersive view, with sound off.

## Grounded walking and hardware contact

The next user inspection found floating switches and camera movement that behaved like flight.
A downward Chrome view confirmed that two switch rows crossed the empty center aisle.
Looking down while pressing W changed camera height from 1.450 to 1.133 scene units.
Movement used the full look rotation, and collision checked only the eye position.
Clicking a camera preset also left focus on its button, where movement keys were ignored.

WASD now moves on the floor plane at a fixed standing eye height of 1.65 scene units.
Collision checks the body footprint against furniture, including surfaces below eye height.
Walk cabin and Center view return keyboard focus to the scene.
Q/E vertical movement was removed, and walking instructions remain visible in immersive mode.
This is a cabin navigation control, not a simulation of astronaut biomechanics or onboard gravity.

Switches and knobs now sit on the existing side consoles, leaving the aisle open.
Floor bolts, wall bolts, overhead vents, screen screws, and bezel buttons were aligned with their actual support surfaces.
The hardware check now rejects positive attachment gaps greater than 0.5 millimeters in cabin coordinates.
It also limits penetration so a buried part cannot pass as mounted.

In Chrome, walking from the rear cabin to the desk kept eye height at 1.65 while looking down.
The desk stopped forward movement at z=-1.760.
The starboard seat stopped forward movement at z=2.000 with x=1.251.
Moving sideways into the aisle then allowed forward travel to z=1.172 at x=0.181.
Proper time remained zero during these camera checks.

The final Node checks passed for 180 mounted hardware parts, four displays, and grounded movement.
JavaScript syntax checks passed, and the final Chrome console contained no JavaScript errors.
Timing varied across four ten-second camera sweeps: 507 frames in 10.2 seconds, then 496, 575, and 595 frames in 10 seconds each.
The last run had a median interval of 16.7 milliseconds, a 95th percentile of 17.5 milliseconds, and one interval of 50.1 milliseconds.
Earlier stalls were not isolated to a cause, so these results do not establish a guaranteed 60 FPS.
Benchmark diagnostics now retain the longest interval, the count above 50 milliseconds, and the delay to the first frame.
The original demo tab was left in immersive Walk cabin view with keyboard focus on the scene and sound off.
