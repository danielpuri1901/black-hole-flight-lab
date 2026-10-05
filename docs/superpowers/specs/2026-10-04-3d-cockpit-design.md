# A spatial cockpit at the black hole

## User outcome

The user wants a photorealistic, immersive 3D cabin, with detailed hardware and particle effects.
The camera must move through actual geometry while the AI flies the saved physical trajectory.
The user has authorized autonomous implementation.
A separate approval is pending for project-only Three.js downloads, capped at 10 MiB.

## Rendering decision

Use Three.js WebGL rendering for cabin geometry and a matching camera basis for the existing Schwarzschild ray tracer.
Reuse the existing flight API, trained models, saved scientific results, and black-hole shader.
Use procedural geometry and generated material textures, with no third-party cockpit model.
The visual target is an inhabited industrial research shuttle: worn graphite surfaces, brushed metal edges, restrained amber controls, pale green displays, and warm disk light.
The strongest visual feature is the black hole filling the forward windows, framed by real structural ribs and consoles.
Avoid floating UI that conceals the cabin.

Three.js provides standard physically based materials and environment lighting.
These are established rendering mechanisms.
The custom relativistic background and its coupling to cabin lighting remain approximations to test visually.
The image must not be described as a fully physically correct moving-observer view.

## Scene and navigation

The cabin coordinate system uses x right, y up, and negative z toward the windshield.
The floor is y=0; the main seated camera is approximately (0,1.45,1.1).
The interior spans roughly x=-2.2 to 2.2 and z=-3.2 to 3.4.
A broad forward window, side consoles, overhead hardware, seats, rear bulkhead, and floor provide visible depth and parallax.
Use preset pilot and aft-cabin viewpoints plus bounded free movement with keyboard controls.
Camera movement changes the local viewpoint only, not the spacecraft's orbital state.
Collision or movement bounds prevent leaving the cabin shell.
Touch and keyboard users retain accessible camera presets and flight controls.

## Material and effects requirements

Use beveled surfaces, layered panels, fasteners, switches, labels, handles, cushions, harnesses, cables, and live instrument displays.
Lights should reveal surface roughness and geometry without washing out the black-hole window.
Add sparse cabin dust visible in light, moderate bloom, subtle thrust-linked vibration, and optional synthesized cabin/engine sound.
Sound starts only from an explicit user action and must have a mute control.
Reduced motion disables vibration and drifting particles.
Pause, hidden-tab behavior, and disposal must prevent needless work.
No cloud GPU or new model training is needed for this rendering change.

## Scientific boundary

Preserve all frozen engine/model/controller source and result hashes.
The ship still follows equatorial powered Schwarzschild trajectories.
The visual cabin is three dimensional; the research mission family does not become unrestricted three-dimensional orbital dynamics.
Particle motion, cabin lighting, and vibration are presentation effects, not additional physical measurements.
The original unpowered observatory remains available.

## Success checks

Open the live result in real Chrome and inspect pilot, aft, and turned-around views.
Verify that nearby structures move with viewpoint changes and obscure one another correctly.
Verify visible black-hole rays, real instrument values, and burn-linked effects during replay.
Exercise raw/checked switching, a custom calculated flight, keyboard navigation, preset views, immersive exit, audio mute, and reduced-motion behavior.
Inspect responsive layout and browser errors.
Measure rendering cost and cap resolution before compromising interaction.
Retain the original scene as a fallback if WebGL initialization fails.

## Sources

- https://threejs.org/docs/pages/MeshStandardMaterial.html
- https://threejs.org/docs/pages/RoomEnvironment.html
- https://threejs.org/docs/pages/EffectComposer.html
