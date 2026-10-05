# Cockpit detail and telemetry

Continue the approved 3D cockpit direction while keeping the measured interactive frame rate.
Use the existing renderer and local modules; no downloads or cloud resources are needed.
The frozen scientific sources and recorded flight results remain unchanged.

## Visual direction

Keep charcoal paint `#20282a`, dark panels `#0c1418`, worn alloy `#687174`, muted fabric `#454c46`, amber `#b47230`, and instrument green `#81bda8`.
Keep the existing serif page headings and compact instrument lettering.
Use fine surface variation and printed hardware markings to establish scale.
Preserve clear forward windows and a level cabin frame.
Show a lensed disk arc at launch without changing the spacecraft radius or light-path equations.
Use radial disk detail with controlled highlights instead of broad glowing cells.

The visual plan follows the established spacecraft design rather than adding unrelated interface elements.
Texture detail should carry most of the added complexity, with no new full-screen effects.

## Tasks

- [x] Cabin: deterministic paint wear, fabric texture, printed panel markings, and full visibility of instrument screens.
- [x] Renderer: refine artistic disk emission, camera aim, and lighting while retaining the ray equations and interaction pixel budgets.
- [x] Interface: pass the selected controller and actual trajectory to the cabin; use geometric time units.
- [x] Regression check: validate transformed instrument geometry and actual telemetry text with the existing local Three.js modules.
- [x] Browser: inspect close-up and cabin views, controller switching, playback, narrow layout, and interactive frame cadence.
- [x] Documentation: record actual results and keep the research article's visualization limits clear.

## Observed defects

The solid desk hid the lower portion of the instrument faces.
The cabin display labeled proper time in seconds even though the simulation uses geometric units.
The trajectory screen drew an arbitrary sine wave.
The renderer frame did not carry the selected controller, so the cabin fell back to a checked-pilot label.
Correct these defects before judging the added surface detail.

## Workflow

Existing file owners handle their isolated rendering changes.
The root agent checks the actual Chrome output.
The user prohibits separate reviewer-agent passes, so there are none.
