'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const scene = $('pilot-scene');
  const names = { learned: 'Raw AI', checked: 'Checked AI', hybrid: 'Hybrid AI + classical', classical: 'Classical search', radial: 'Outward radial burn', coast: 'Coast', random_checked: 'Checked random' };
  const outcomes = { escaped: 'Escaped', safety_cutoff: 'Safety cutoff', timeout: 'Time limit' };
  const state = { flight: null, showcase: null, controller: 'checked', tau: 0, playing: false, lastFrame: 0, lastDraw: 0, viewDirty: true, effectsTime: 0, frame: 0, request: null, serial: 0, immersive: false, onScreen: true, yaw: 0, pitch: 0, drag: null, benchmark: null, keys: new Set(), width: 1, height: 1 };
  let renderer = null, returnFocus = null, background = [];
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const cadence = new URLSearchParams(location.search).has('diagnostics') ? [] : null;
  const cadenceSummary = () => Object.fromEntries(['drag', 'movement', 'flight', 'idle'].map(mode => {
    const values = cadence.filter(sample => sample.mode === mode).map(sample => sample.ms).sort((a, b) => a - b);
    return [mode, { count: values.length, median: values[Math.floor(values.length * .5)] ?? null, p95: values[Math.floor(values.length * .95)] ?? null }];
  }));
  let lastCadence = 0, lastStatsWrite = 0;
  $('pilot-benchmark-start').addEventListener('click', () => {
    if (state.benchmark) return;
    if (state.playing) pause();
    const start = performance.now();
    state.benchmark = { start, yaw: state.yaw, pitch: state.pitch, last: 0, samples: [] };
    $('pilot-benchmark-start').disabled = true;
    $('pilot-benchmark-result').textContent = 'Measuring camera frames…';
    requestDraw();
  });
  function fallbackRenderer(error) {
    if (error) console.warn('3D cockpit unavailable:', error);
    renderer?.dispose?.();
    const canvas = $('pilot-canvas');
    const replacement = canvas.cloneNode();
    canvas.replaceWith(replacement);
    scene.classList.remove('three-d');
    renderer = window.FallbackCockpitRenderer ? new window.FallbackCockpitRenderer(replacement) : null;
  }
  try {
    if (window.CockpitRenderer) renderer = new window.CockpitRenderer($('pilot-canvas'));
    if (renderer?.is3D) scene.classList.add('three-d');
    else if (window.FallbackCockpitRenderer && window.CockpitRenderer !== window.FallbackCockpitRenderer) fallbackRenderer(renderer?.error);
  } catch (error) { fallbackRenderer(error); }
  const spatial = Boolean(renderer?.is3D);
  $('pilot-benchmark').hidden = !cadence || !spatial;
  for (const button of scene.querySelectorAll('[data-pilot-view]')) button.hidden = !spatial;
  $('pilot-sound').hidden = !spatial || !(window.AudioContext || window.webkitAudioContext);
  $('pilot-look').textContent = spatial ? 'Click Walk cabin, then use WASD to walk. Drag or use arrow keys to look. Walking does not steer the ship.' : 'Drag or use arrow keys to look. Camera rotation does not steer the ship.';
  let audio = null, audioOn = false;
  function soundLevel(burn) {
    if (!audio) return;
    audio.gain.gain.setTargetAtTime(audioOn && !document.hidden ? .006 + Math.min(.018, Math.hypot(...burn) * .018) : 0, audio.context.currentTime, .08);
  }
  async function toggleSound() {
    if (!audio) {
      try {
        const Context = window.AudioContext || window.webkitAudioContext;
        const context = new Context();
        const gain = context.createGain(); gain.gain.value = 0; gain.connect(context.destination);
        const tones = [57, 114].map((frequency, index) => { const tone = context.createOscillator(); tone.type = index ? 'triangle' : 'sine'; tone.frequency.value = frequency; tone.connect(gain); tone.start(); return tone; });
        audio = { context, gain, tones };
      } catch (error) { console.warn('Cockpit sound unavailable:', error); $('pilot-sound').disabled = true; $('pilot-sound').textContent = 'Sound unavailable'; return; }
    }
    audioOn = !audioOn;
    if (audioOn) await audio.context.resume();
    $('pilot-sound').textContent = audioOn ? 'Sound on' : 'Sound off';
    $('pilot-sound').setAttribute('aria-pressed', String(audioOn));
    requestDraw();
  }
  $('pilot-sound').addEventListener('click', toggleSound);
  function status(message, type = '') { $('pilot-status').textContent = message; $('pilot-status').className = `pilot-status ${type}`; }
  function endTime() { return state.flight?.points.at(-1)?.[0] || 0; }
  function pointAt(points, tau) {
    if (tau <= points[0][0]) return points[0];
    if (tau >= points.at(-1)[0]) return points.at(-1);
    let low = 0, high = points.length - 1;
    while (high - low > 1) { const middle = (low + high) >> 1; if (points[middle][0] <= tau) low = middle; else high = middle; }
    const a = points[low], b = points[high], fraction = (tau - a[0]) / (b[0] - a[0]);
    return a.map((value, index) => value + (b[index] - value) * fraction);
  }
  function decisionAt(tau) {
    const decisions = state.flight?.decisions || [];
    let index = -1;
    for (let i = 0; i < decisions.length && decisions[i].tau <= tau; i++) index = i;
    return { decision: index >= 0 ? decisions[index] : null, index };
  }
  function buttons() {
    const available = Boolean(state.flight);
    $('pilot-play').disabled = !available;
    $('pilot-scrub').disabled = !available;
    $('pilot-play').textContent = state.playing ? 'Pause flight' : state.tau >= endTime() && available ? 'Replay flight' : state.tau ? 'Resume flight' : 'Begin flight';
    scene.classList.toggle('playing', state.playing);
  }
  function draw() {
    const point = state.flight ? pointAt(state.flight.points, state.tau) : [0, Number($('pilot-launch-radius').value), 0, Number($('pilot-momentum').value), 0, 0, Number($('pilot-energy').value), 1];
    const { decision, index } = decisionAt(state.tau);
    const burn = state.tau >= endTime() && state.flight ? [0, 0] : decision?.action || [0, 0];
    const interactive = state.playing || Boolean(state.drag?.looking) || state.keys.size > 0 || Boolean(state.benchmark);
    const frame = { radius: point[1], phi: point[4], energy: point[6], angularMomentum: point[3], time: point[0], progress: endTime() ? state.tau / endTime() : 0, playing: interactive, flightPlaying: state.playing, interactive, lookYaw: state.yaw, lookPitch: state.pitch, outcome: state.flight?.outcome || 'unresolved', width: state.width, height: state.height, fuel: point[7], burn, controller: state.flight ? names[state.controller] || state.controller : 'NO FLIGHT', trajectory: state.flight?.points, effectsTime: state.effectsTime, reducedMotion: reducedMotion.matches };
    try { renderer?.render(frame); } catch (error) { if (renderer?.is3D) { fallbackRenderer(error); renderer?.render(frame); } else console.error('Cockpit render failed:', error); }
    if (!renderer?.is3D) {
      scene.classList.remove('three-d');
      for (const button of scene.querySelectorAll('[data-pilot-view]')) button.hidden = true;
      $('pilot-sound').hidden = true;
      $('pilot-hud').hidden = true;
      $('pilot-benchmark').hidden = true;
    }
    soundLevel(burn);
    const renderMode = renderer ? `${renderer.mode}. Cinematic camera / artistic emission.` : 'Illustrative image fallback. Calculated flight data is separate.';
    if ($('pilot-render-mode').textContent !== renderMode) $('pilot-render-mode').textContent = renderMode;
    if (state.hudFlight === state.flight && state.hudTau === state.tau && state.hudRadius === point[1]) return;
    state.hudFlight = state.flight; state.hudTau = state.tau; state.hudRadius = point[1];
    scene.style.setProperty('--pilot-light', String(Math.min(1, 4 / point[1])));
    if (!state.flight) return;
    $('pilot-radius').textContent = `${point[1].toFixed(3)} M`;
    $('pilot-time').textContent = `τ ${point[0].toFixed(1)} M`;
    $('pilot-fuel').textContent = `${(100 * point[7]).toFixed(1)}%`;
    $('pilot-fuel-meter').hidden = false;
    $('pilot-fuel-meter').value = point[7];
    $('pilot-scrub').value = String(Math.round(state.tau / Math.max(endTime(), .001) * 1000));
    const terminal = state.tau >= endTime();
    const norm = Math.hypot(...burn);
    scene.style.setProperty('--pilot-thrust', String(Math.min(1, norm)));
    $('pilot-burn').textContent = norm > .001 ? `Radial ${burn[0].toFixed(2)} / tangent ${burn[1].toFixed(2)}` : 'Coasting';
    const x = 32 + burn[1] * 25, y = 32 - burn[0] * 25;
    $('pilot-thrust-line').setAttribute('x2', x); $('pilot-thrust-line').setAttribute('y2', y);
    $('pilot-thrust-dot').setAttribute('cx', x); $('pilot-thrust-dot').setAttribute('cy', y);
    $('pilot-replans').textContent = index < 0 ? 'Before the first recorded decision.' : `Decision ${index + 1} / ${state.flight.decisions.length}${decision.intervention ? ' · checked selection changed the first proposal' : ''}${Number.isFinite(decision.seconds) ? ` · ${(decision.seconds * 1000).toFixed(0)} ms compute` : ''}`;
    if ($('pilot-terminal').hidden === terminal) $('pilot-terminal').hidden = !terminal;
  }
  function resize() { const rect = scene.getBoundingClientRect(); state.width = rect.width; state.height = rect.height; requestDraw(); }
  function idleEffects() { return spatial && renderer?.is3D && state.onScreen && !reducedMotion.matches && !document.hidden; }
  function requestDraw() { state.viewDirty = true; if (!state.frame && !document.hidden) startLoop(); }
  function pause() { state.playing = false; if (state.frame) cancelAnimationFrame(state.frame); state.frame = 0; buttons(); if (state.keys.size && !document.hidden) startLoop(); else requestDraw(); }
  function tick(now) {
    state.frame = 0;
    if (document.hidden) return;
    const delta = Math.min((now - state.lastFrame) / 1000, .15); state.lastFrame = now;
    const benchmark = state.benchmark;
    if (benchmark) {
      benchmark.firstFrameDelayMs ??= Math.round((performance.now() - benchmark.start) * 10) / 10;
      const elapsed = (now - benchmark.start) / 1000;
      if (elapsed < 10) state.yaw = benchmark.yaw + .7 * Math.sin(elapsed * 1.8);
      else {
        state.yaw = benchmark.yaw; state.pitch = benchmark.pitch; state.benchmark = null; state.viewDirty = true;
        const sorted = benchmark.samples.sort((a, b) => a - b);
        const result = { frames: sorted.length, medianMs: sorted[Math.floor(sorted.length * .5)] ?? null, p95Ms: sorted[Math.floor(sorted.length * .95)] ?? null, maxMs: sorted.at(-1) ?? null, framesOver50Ms: sorted.filter(ms => ms > 50).length, firstFrameDelayMs: benchmark.firstFrameDelayMs, durationSeconds: Math.round(elapsed * 10) / 10 };
        $('pilot-canvas').dataset.benchmarkStats = JSON.stringify(result);
        $('pilot-benchmark-result').textContent = `${result.frames} frames · median ${result.medianMs ?? 'n/a'} ms · p95 ${result.p95Ms ?? 'n/a'} ms`;
        $('pilot-benchmark-start').disabled = false;
      }
    }
    if (state.playing) {
      state.tau = Math.min(endTime(), state.tau + delta * endTime() / 22);
      if (state.tau >= endTime()) { state.playing = false; buttons(); }
    }
    if (spatial && state.keys.size) {
      const right = Number(state.keys.has('KeyD')) - Number(state.keys.has('KeyA'));
      const forward = Number(state.keys.has('KeyW')) - Number(state.keys.has('KeyS'));
      const length = Math.hypot(right, forward) || 1;
      renderer?.moveLocal?.(right / length * delta * 1.7, forward / length * delta * 1.7);
    }
    if (!reducedMotion.matches) state.effectsTime += delta;
    if (state.playing || state.keys.size || state.drag?.looking || state.benchmark || state.viewDirty || now - state.lastDraw >= 66) {
      const mode = state.benchmark ? 'benchmark' : state.drag?.looking ? 'drag' : state.keys.size ? 'movement' : state.playing ? 'flight' : 'idle';
      if (state.benchmark) { if (state.benchmark.last) state.benchmark.samples.push(Math.round((now - state.benchmark.last) * 10) / 10); state.benchmark.last = now; }
      if (cadence && lastCadence) { cadence.push({ mode, ms: Math.round((now - lastCadence) * 10) / 10 }); if (cadence.length > 120) cadence.shift(); }
      if (cadence && now - lastStatsWrite >= 1000) { $('pilot-canvas').dataset.frameStats = JSON.stringify(cadenceSummary()); lastStatsWrite = now; }
      lastCadence = now; state.lastDraw = now; state.viewDirty = false; draw();
    }
    if (state.playing || state.keys.size || state.drag?.looking || state.benchmark || idleEffects()) state.frame = requestAnimationFrame(tick);
  }
  function startLoop() { if (!state.frame) { state.lastFrame = performance.now(); state.frame = requestAnimationFrame(tick); } }
  function play() {
    if (!state.flight) return;
    if (state.playing) { pause(); return; }
    if (state.tau >= endTime()) state.tau = 0;
    if (state.frame) cancelAnimationFrame(state.frame);
    state.frame = 0;
    state.playing = true; buttons(); startLoop();
  }
  function validFlight(flight) {
    if (!flight || !outcomes[flight.outcome] || !Array.isArray(flight.points) || !flight.points.length) throw new Error('The server returned no usable flight trace.');
    flight.points.forEach((point, index) => {
      if (point.length !== 8 || !point.every(Number.isFinite) || point[1] <= 2 || (index && point[0] <= flight.points[index - 1][0])) throw new Error('The saved flight has invalid state data.');
    });
    if (!Array.isArray(flight.decisions)) throw new Error('The flight has no recorded decision list.');
    return flight;
  }
  function setFlight(flight, controller, preserveTime = false) {
    validFlight(flight); pause(); state.flight = flight; state.controller = controller; state.tau = preserveTime ? Math.min(state.tau, endTime()) : 0;
    $('pilot-outcome').textContent = outcomes[flight.outcome];
    $('pilot-minimum').textContent = Number.isFinite(flight.minimum_radius) ? `${flight.minimum_radius.toFixed(3)} M` : 'Not reported';
    $('pilot-used').textContent = Number.isFinite(flight.fuel_used) ? `${(flight.fuel_used * 100).toFixed(1)}%` : 'Not reported';
    $('pilot-controller').value = controller;
    $('pilot-raw').setAttribute('aria-pressed', String(controller === 'learned'));
    $('pilot-checked').setAttribute('aria-pressed', String(controller === 'checked'));
    const first = flight.points[0];
    $('pilot-launch-radius').value = String(first[1]); $('pilot-energy').value = String(first[6]); $('pilot-momentum').value = String(first[3]); sliderLabels();
    const paired = state.showcase && (flight === state.showcase.learned || flight === state.showcase.checked);
    $('pilot-comparison').textContent = paired ? `Same launch. Raw AI: ${outcomes[state.showcase.learned.outcome].toLowerCase()}. Checked AI: ${outcomes[state.showcase.checked.outcome].toLowerCase()}.` : `${names[controller]} · ${outcomes[flight.outcome].toLowerCase()}. Outcomes come from the calculated powered flight.`;
    const terminalText = flight.outcome === 'escaped' ? ['Return condition reached.', 'Outward coasting flight reaches r = 20 M with energy above 1.'] : flight.outcome === 'safety_cutoff' ? ['Safety surface reached.', 'The mission ends at r = 2.1 M. This is outside the horizon, and counts as a failed return.'] : ['Flight time limit reached.', 'No return was established before the mission time limit.'];
    $('pilot-terminal-title').textContent = terminalText[0]; $('pilot-terminal-detail').textContent = terminalText[1]; $('pilot-terminal').hidden = true;
    const track = $('pilot-decision-track'); track.replaceChildren();
    for (const decision of flight.decisions) { const mark = document.createElement('i'); mark.style.left = `${Math.min(100, decision.tau / Math.max(endTime(), .001) * 100)}%`; if (decision.intervention) mark.className = 'changed'; track.append(mark); }
    buttons(); requestDraw();
  }
  async function getJSON(url, signal) {
    const response = await fetch(url, { signal, cache: 'no-store' });
    if (!response.ok) { let detail = ''; try { detail = (await response.json()).error || ''; } catch (_) {} const error = new Error(detail || `Request failed (${response.status}).`); error.status = response.status; throw error; }
    return response.json();
  }
  function stopRequest() { state.request?.abort(); state.request = null; state.serial++; $('pilot-launch').disabled = false; $('pilot-cancel').hidden = true; }
  async function recorded() {
    stopRequest(); pause();
    if (state.showcase) { setFlight(state.showcase.checked, 'checked'); status(state.showcase.selection || 'Recorded paired launch loaded.'); return; }
    const controller = new AbortController(); state.request = controller; const serial = ++state.serial;
    status('Loading the recorded paired launch…', 'loading');
    try {
      const showcase = await getJSON('/results/pilot/showcase.json', controller.signal);
      validFlight(showcase.learned); validFlight(showcase.checked);
      if (serial !== state.serial) return;
      state.showcase = showcase; $('pilot-raw').disabled = false; $('pilot-checked').disabled = false;
      setFlight(showcase.checked, 'checked'); status(showcase.selection || 'Recorded paired launch loaded.');
    } catch (error) {
      if (error.name === 'AbortError' || serial !== state.serial) return;
      if (error.status === 404) { status('Training in progress. Recorded AI flights will appear when training and evaluation finish. You can calculate a classical or coasting flight now.'); if (!state.flight) $('pilot-comparison').textContent = 'Training in progress. No learned flight is being simulated here.'; }
      else status(`Could not load the recorded launch. ${error.message}`, 'error');
    } finally { if (serial === state.serial) state.request = null; }
  }
  $('pilot-form').addEventListener('submit', async event => {
    event.preventDefault(); stopRequest(); pause();
    const controller = new AbortController(); state.request = controller; const serial = ++state.serial;
    const selected = $('pilot-controller').value;
    const query = new URLSearchParams({ radius: $('pilot-launch-radius').value, energy: $('pilot-energy').value, momentum: $('pilot-momentum').value, controller: selected });
    $('pilot-launch').disabled = true; $('pilot-cancel').hidden = false;
    status(`Calculating ${names[selected].toLowerCase()} in the powered physics. This can take 20 seconds or longer.`, 'loading');
    try {
      const flight = await getJSON(`/api/pilot?${query}`, controller.signal);
      if (serial !== state.serial) return;
      setFlight(flight, selected); status('Flight calculated. Begin the replay to inspect each recorded burn.');
      if (!reducedMotion.matches) play();
    } catch (error) { if (error.name !== 'AbortError' && serial === state.serial) status(`Flight could not be calculated. ${error.message}`, 'error'); }
    finally { if (serial === state.serial) { state.request = null; $('pilot-launch').disabled = false; $('pilot-cancel').hidden = true; } }
  });
  $('pilot-cancel').addEventListener('click', () => { stopRequest(); status('Calculation cancelled in this page. The server may finish work already started.'); });
  $('pilot-witness').addEventListener('click', recorded);
  for (const [id, controller] of [['pilot-raw', 'learned'], ['pilot-checked', 'checked']]) $(id).addEventListener('click', () => { if (!state.showcase) return; stopRequest(); setFlight(state.showcase[controller], controller, true); status(state.showcase.selection || 'Same recorded launch, different controller.'); });
  $('pilot-play').addEventListener('click', play);
  $('pilot-scrub').addEventListener('input', () => { pause(); state.tau = Number($('pilot-scrub').value) / 1000 * endTime(); buttons(); requestDraw(); });
  function sliderLabels() { $('pilot-launch-radius-value').textContent = `${Number($('pilot-launch-radius').value).toFixed(2)} M`; $('pilot-energy-value').textContent = Number($('pilot-energy').value).toFixed(4); $('pilot-momentum-value').textContent = Number($('pilot-momentum').value).toFixed(3); }
  for (const id of ['pilot-launch-radius', 'pilot-energy', 'pilot-momentum']) $(id).addEventListener('input', () => { sliderLabels(); if (!state.flight) requestDraw(); });
  function controls() { return [scene, ...scene.querySelectorAll('button:not(:disabled), input:not(:disabled), [tabindex="0"]')].filter(element => element.getClientRects().length); }
  function immersive(active) {
    if (active === state.immersive) return;
    state.immersive = active;
    if (active) {
      returnFocus = document.activeElement;
      background = [...document.querySelectorAll('.site-header, .pilot-desk, .pilot-lab, footer')].map(element => ({ element, inert: element.inert }));
      background.forEach(({ element }) => element.inert = true);
      scene.setAttribute('role', 'dialog'); scene.setAttribute('aria-modal', 'true'); scene.setAttribute('aria-label', 'Immersive powered flight cockpit');
    } else { background.forEach(({ element, inert }) => element.inert = inert); background = []; scene.removeAttribute('role'); scene.removeAttribute('aria-modal'); scene.removeAttribute('aria-label'); scene.classList.remove('hud-hidden'); $('pilot-hud').textContent = 'Hide HUD'; $('pilot-hud').setAttribute('aria-pressed', 'false'); }
    scene.classList.toggle('immersive', active); document.body.classList.toggle('pilot-immersive-open', active);
    $('pilot-hud').hidden = !active || !renderer?.is3D;
    $('pilot-exit').hidden = !active; $('pilot-immersive').textContent = active ? 'Exit immersive view' : 'Immersive view'; $('pilot-immersive').setAttribute('aria-pressed', String(active));
    if (active) ($('pilot-play').disabled ? $('pilot-exit') : $('pilot-play')).focus({ preventScroll: true }); else returnFocus?.focus({ preventScroll: true });
    requestAnimationFrame(resize);
  }
  $('pilot-immersive').addEventListener('click', () => immersive(!state.immersive)); $('pilot-exit').addEventListener('click', () => immersive(false));
  $('pilot-hud').addEventListener('click', () => {
    const hidden = scene.classList.toggle('hud-hidden');
    $('pilot-hud').textContent = hidden ? 'Show HUD' : 'Hide HUD';
    $('pilot-hud').setAttribute('aria-pressed', String(hidden));
  });
  for (const button of scene.querySelectorAll('[data-pilot-view]')) button.addEventListener('click', () => {
    renderer?.setView?.(button.dataset.pilotView);
    for (const choice of scene.querySelectorAll('[data-pilot-view]')) choice.setAttribute('aria-pressed', String(choice === button));
    look(0, 0);
    scene.focus({ preventScroll: true });
  });
  function look(yaw, pitch) { state.yaw = spatial ? yaw : Math.max(-.8, Math.min(.8, yaw)); state.pitch = Math.max(spatial ? -1.35 : -.45, Math.min(spatial ? 1.35 : .45, pitch)); requestDraw(); }
  $('pilot-center').addEventListener('click', () => { look(0, 0); scene.focus({ preventScroll: true }); });
  scene.addEventListener('pointerdown', event => {
    if (state.drag || event.button !== 0 || !(event.target === scene || event.target.id === 'pilot-canvas' || event.target.classList.contains('cockpit-fallback'))) return;
    state.drag = { id: event.pointerId, startX: event.clientX, startY: event.clientY, x: event.clientX, y: event.clientY, looking: event.pointerType !== 'touch' || state.immersive };
    scene.setPointerCapture(event.pointerId); if (state.drag.looking) { scene.focus({ preventScroll: true }); scene.classList.add('looking'); }
  });
  scene.addEventListener('pointermove', event => {
    const drag = state.drag; if (!drag || drag.id !== event.pointerId) return;
    if (!drag.looking) { const dx = event.clientX - drag.startX, dy = event.clientY - drag.startY; if (Math.abs(dy) > 8 && Math.abs(dy) > Math.abs(dx)) { endLook(event); return; } if (Math.abs(dx) < 8) return; drag.looking = true; scene.focus({ preventScroll: true }); scene.classList.add('looking'); }
    look(state.yaw + (event.clientX - drag.x) * 1.7 / state.width, state.pitch - (event.clientY - drag.y) * 1.1 / state.height); drag.x = event.clientX; drag.y = event.clientY;
  });
  function endLook(event) { if (!state.drag || state.drag.id !== event.pointerId) return; if (scene.hasPointerCapture(event.pointerId)) scene.releasePointerCapture(event.pointerId); state.drag = null; scene.classList.remove('looking'); requestDraw(); }
  for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) scene.addEventListener(event, endLook);
  document.addEventListener('keydown', event => {
    const arrows = { ArrowLeft: [-.04, 0], ArrowRight: [.04, 0], ArrowUp: [0, .035], ArrowDown: [0, -.035] };
    const interactive = event.target.closest('button,input,select,a,summary,textarea,[contenteditable="true"]');
    if (arrows[event.key] && scene.contains(document.activeElement) && !interactive) { event.preventDefault(); look(state.yaw + arrows[event.key][0], state.pitch + arrows[event.key][1]); return; }
    if (spatial && !interactive && scene.contains(document.activeElement) && /^(Key[WASD])$/.test(event.code)) { event.preventDefault(); state.keys.add(event.code); startLoop(); return; }
    if (!state.immersive) return;
    if (event.key === 'Escape') { event.preventDefault(); immersive(false); }
    if (event.key === 'Tab') { const all = controls(), first = all[0], last = all.at(-1); if (event.shiftKey && (document.activeElement === first || !all.includes(document.activeElement))) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && (document.activeElement === last || !all.includes(document.activeElement))) { event.preventDefault(); first?.focus(); } }
    if (event.code === 'Space' && !interactive) { event.preventDefault(); play(); }
  });
  document.addEventListener('keyup', event => { if (state.keys.delete(event.code) && !state.keys.size && !state.playing) requestDraw(); });
  window.addEventListener('blur', () => state.keys.clear());
  document.addEventListener('focusin', event => { if (state.immersive && !scene.contains(event.target)) controls()[0]?.focus(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { state.keys.clear(); if (state.benchmark) { state.yaw = state.benchmark.yaw; state.pitch = state.benchmark.pitch; state.benchmark = null; $('pilot-benchmark-start').disabled = false; $('pilot-benchmark-result').textContent = 'Benchmark cancelled when tab was hidden.'; } pause(); soundLevel([0, 0]); } else { if (audioOn) audio?.context.resume(); requestDraw(); } });
  window.addEventListener('pagehide', () => { renderer?.dispose?.(); audio?.tones.forEach(tone => tone.stop()); audio?.context.close(); });
  reducedMotion.addEventListener('change', requestDraw);
  async function loadResults() {
    const results = await Promise.allSettled([
      getJSON('/results/pilot/summary.json'),
      getJSON('/results/pilot/controls-summary.json')
    ]);
    const summary = results[0].status === 'fulfilled' ? results[0].value : null;
    const supplemental = results[1].status === 'fulfilled' ? results[1].value : null;
    const mainGroups = Array.isArray(summary?.groups) ? summary.groups : [];
    const controlGroups = Array.isArray(supplemental?.groups) ? supplemental.groups : [];
    const rows = [...mainGroups.map(group => ({ group, postHoc: false })),
                  ...controlGroups.map(group => ({ group, postHoc: true }))];
    if (!rows.length) {
      const failed = results.find(result => result.status === 'rejected' && result.reason.status !== 404);
      if (failed) $('pilot-results').firstElementChild.firstElementChild.textContent = `Measured results could not be loaded. ${failed.reason.message}`;
      return;
    }
    const controlNames = { random_with_coast: 'Checked random + exact coast', fixed_checked: 'Checked fixed plans (29)' };
    const body = $('pilot-results'); body.replaceChildren();
    for (const { group, postHoc } of rows) {
      const row = document.createElement('tr');
      const label = `${names[group.controller] || controlNames[group.controller] || group.controller} / ${group.split}${postHoc ? ' · post hoc' : ''}`;
      const cells = [label, `${group.escaped} / ${group.flights}`, group.safety_cutoff, group.timeout,
        Number.isFinite(group.mean_fuel_used) ? `${(100 * group.mean_fuel_used).toFixed(1)}%` : 'Not reported',
        Number.isFinite(group.mean_decision_seconds) ? `${(group.mean_decision_seconds * 1000).toFixed(1)} ms` : 'Not reported'];
      for (const value of cells) { const cell = document.createElement('td'); cell.textContent = String(value); row.append(cell); }
      body.append(row);
    }
    if (Array.isArray(summary?.limitations)) $('pilot-limitations').textContent = summary.limitations.join(' ');
    $('pilot-post-hoc-note').hidden = !controlGroups.length;
  }
  new IntersectionObserver(([entry]) => { state.onScreen = entry.isIntersecting; if (state.onScreen) requestDraw(); }).observe(scene);
  new ResizeObserver(resize).observe(scene); sliderLabels(); buttons(); resize(); recorded(); loadResults();
})();
