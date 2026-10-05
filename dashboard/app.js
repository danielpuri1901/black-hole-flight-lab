'use strict';

const $ = id => document.getElementById(id);
const canvas = $('space');
const context = canvas.getContext('2d');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const state = { flight: null, showcase: null, playing: false, progress: 0, lastFrame: 0, duration: 0, viewRadius: 19, view: 'cockpit', world: 'true', immersive: false, effects: !reducedMotion.matches, lookYaw: 0, lookPitch: 0, width: 0, height: 0, background: null, controller: null, frame: 0 };
const palette = { true: '#efb476', model: '#80c2fa' };
let wholeBarrier = false;
let cockpitRenderer = null;
let returnFocus = null;
let backgroundElements = [];
let lookDrag = null;
let lookFrame = 0;
try { if (window.CockpitRenderer) cockpitRenderer = new window.CockpitRenderer($('cockpit')); } catch (error) { $('cockpit-caption').textContent = `Moving camera unavailable: ${error.message}`; }

function followedTrace() { return state.world === 'model' ? state.flight?.model_trace : state.flight?.true_trace; }
function followedEnd() { return Boolean(followedTrace()?.points?.length && state.progress * state.duration >= followedTrace().points.at(-1)[0] - 1e-8); }

function drawCockpit() {
  const trace = followedTrace();
  const point = trace?.points?.length ? pointAt(trace.points, state.progress * state.duration) : [0, 30, 0];
  const scene = document.querySelector('.space-view');
  scene.style.setProperty('--ambient-light', state.effects ? Math.min(.9, .12 + (30 - Math.min(30, point[1])) / 32) : 0);
  scene.style.setProperty('--camera-bank', `${Math.sin(point[2]) * 3}deg`);
  const ended = followedEnd();
  $('cockpit-radius').value = `${point[1].toFixed(3)} M`;
  $('cockpit-clearance').value = `${Math.max(0, point[1] - 2).toFixed(4)} M`;
  $('cockpit-time').value = `τ ${point[0].toFixed(1)}`;
  $('cockpit-alert').hidden = !ended;
  if (ended) {
    $('cockpit-event-title').textContent = trace.outcome === 'capture' ? 'Capture surface reached.' : trace.outcome === 'escape' ? 'Outbound. A way back.' : 'Replay limit reached.';
    $('cockpit-event-detail').textContent = trace.outcome === 'capture' ? 'No return in this model. Replay stops at r = 2.001.' : trace.outcome === 'escape' ? 'The particle returns outward to r = 30.' : 'The numerical path remains unresolved.';
  }
  if (cockpitRenderer) {
    cockpitRenderer.render({ radius: point[1], phi: point[2], progress: state.progress, time: point[0], playing: state.playing || Boolean(lookDrag?.looking), lookYaw: state.lookYaw, lookPitch: state.lookPitch, energy: state.flight?.energy || 1.04, angularMomentum: state.flight?.angular_momentum || 4.3, outcome: trace?.outcome || 'unresolved', width: state.width, height: state.height });
    document.querySelector('.space-view').classList.add('renderer-active');
    $('cockpit-caption').textContent = `${cockpitRenderer.mode || 'Moving camera'}. Calculated orbit; cinematic camera lift and minimum view radius 2.05 M. Unpowered particle, not a powered shuttle.`;
  } else {
    $('cockpit-caption').textContent = 'Moving camera unavailable. Static lensed illustration shown; telemetry still follows the calculated orbit.';
  }
}

function syncPlaybackButtons() {
  const ended = state.progress === 1 || (state.view === 'cockpit' && followedEnd());
  $('play').textContent = state.playing ? 'Pause' : ended ? 'Replay' : 'Play';
  $('play').setAttribute('aria-label', state.playing ? 'Pause flight' : ended ? 'Replay flight' : 'Play flight');
  $('cockpit-play').textContent = state.playing ? 'Pause flyby' : ended ? 'Replay flyby' : state.progress === 0 ? 'Begin flyby' : 'Continue flyby';
  document.querySelector('.space-view').classList.toggle('playing', state.playing);
}

function drawBarrier() {
  const chart = $('barrier-chart'), c = chart.getContext('2d'), box = chart.getBoundingClientRect();
  const w = box.width, h = box.height, ratio = Math.min(devicePixelRatio || 1, 2);
  chart.width = Math.round(w * ratio); chart.height = Math.round(h * ratio); c.scale(ratio, ratio);
  const profile = state.flight?.barrier_profile;
  if (!profile?.points?.length || !Number.isFinite(profile.launch_radial_energy)) {
    c.fillStyle = '#9b9bae'; c.font = '12px Avenir, sans-serif'; c.fillText('Barrier data is not available for this flight.', 0, 40);
    $('barrier-summary').textContent = 'Barrier data is not available for this flight. Orbit replay remains available.';
    return;
  }
  const points = profile.points.filter(point => point.length >= 3 && point.every(Number.isFinite)).sort((a, b) => a[0] - b[0]);
  if (!points.length) return;
  const energy = profile.launch_radial_energy;
  const peaks = [1, 2].map(column => points.reduce((peak, point) => point[column] > peak[column] ? point : peak, points[0]));
  const globalMargins = Number.isFinite(profile.exact_margin) && Number.isFinite(profile.model_margin);
  const exactMargin = globalMargins ? profile.exact_margin : peaks[0][1] - energy;
  const learnedMargin = globalMargins ? profile.model_margin : peaks[1][2] - energy;
  const describe = margin => `${scientific(Math.abs(margin))} ${margin >= 0 ? 'above' : 'below'} launch energy`;
  $('barrier-summary').textContent = `Relativity barrier: ${describe(exactMargin)}. Learned barrier: ${describe(learnedMargin)}. ${globalMargins ? 'These margins use the full radius range, 2.001 to 30.' : 'These margins use the sampled inner peaks.'}`;
  const xmin = points[0][0], xmax = points.at(-1)[0];
  let ymin, ymax;
  if (wholeBarrier) {
    ymin = Math.min(energy, ...points.flatMap(point => [point[1], point[2]]));
    ymax = Math.max(energy, peaks[0][1], peaks[1][2]);
    const padding = Math.max(.003, (ymax - ymin) * .1); ymin -= padding; ymax += padding;
  } else {
    const detail = Math.max(.002, Math.abs(energy - peaks[0][1]), Math.abs(energy - peaks[1][2])) * 1.3;
    ymin = energy - detail; ymax = energy + detail;
  }
  const left = w < 500 ? 58 : 72, right = w - 18, top = 35, bottom = h - 42;
  const x = radius => left + (radius - xmin) / (xmax - xmin) * (right - left);
  const y = potential => bottom - (potential - ymin) / (ymax - ymin) * (bottom - top);
  c.font = '10px Avenir, sans-serif'; c.fillStyle = '#aaa2b8'; c.fillText('Relative potential', left, 15);
  c.textAlign = 'right'; c.fillStyle = '#888198'; c.fillText(wholeBarrier ? 'Whole barrier' : 'Vertical detail', right, 15);
  for (let i = 0; i <= 4; i++) {
    const value = ymin + (ymax - ymin) * i / 4, row = y(value);
    c.strokeStyle = '#ffffff0d'; c.lineWidth = 1; c.beginPath(); c.moveTo(left, row); c.lineTo(right, row); c.stroke();
    c.fillStyle = '#938b9f'; c.fillText(value.toFixed(Math.abs(value) < .01 ? 4 : 3), left - 9, row + 3);
  }
  c.textAlign = 'center';
  for (const radius of [2, 4, 6, 8, 10]) {
    const column = x(Math.max(xmin, Math.min(xmax, radius)));
    c.fillStyle = '#938b9f'; c.fillText(String(radius), column, bottom + 17);
    c.strokeStyle = '#ffffff0d'; c.beginPath(); c.moveTo(column, top); c.lineTo(column, bottom); c.stroke();
  }
  c.fillStyle = '#aaa2b8'; c.fillText('Radius r / M', (left + right) / 2, h - 5);
  c.save(); c.beginPath(); c.rect(left, top, right - left, bottom - top); c.clip();
  for (const column of [1, 2]) {
    const color = column === 1 ? palette.true : palette.model;
    c.strokeStyle = color; c.lineWidth = 2; c.setLineDash(column === 2 ? [5, 4] : []);
    c.beginPath(); points.forEach((point, index) => { if (!index) c.moveTo(x(point[0]), y(point[column])); else c.lineTo(x(point[0]), y(point[column])); }); c.stroke();
    c.setLineDash([]);
    const peak = peaks[column - 1]; c.fillStyle = color; c.beginPath(); c.arc(x(peak[0]), y(peak[column]), 3, 0, Math.PI * 2); c.fill();
  }
  c.strokeStyle = '#f2ece0a0'; c.lineWidth = 1; c.setLineDash([3, 5]); c.beginPath(); c.moveTo(left, y(energy)); c.lineTo(right, y(energy)); c.stroke(); c.setLineDash([]);
  c.fillStyle = '#f2ece0'; c.textAlign = 'right'; c.fillText('Launch radial energy', right - 7, y(energy) - 8);
  c.restore();
}

function random(seed) {
  return () => { seed = Math.imul(seed ^ seed >>> 15, 1 | seed); seed ^= seed + Math.imul(seed ^ seed >>> 7, 61 | seed); return ((seed ^ seed >>> 14) >>> 0) / 4294967296; };
}

function geometry() {
  return { x: state.width * .5, y: state.height * .53, scale: Math.min(state.width * .47, state.height * .39) / state.viewRadius };
}

function resize() {
  const box = canvas.getBoundingClientRect();
  state.width = box.width;
  state.height = box.height;
  const ratio = Math.min(devicePixelRatio || 1, 2);
  canvas.width = Math.round(box.width * ratio);
  canvas.height = Math.round(box.height * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  state.background = document.createElement('canvas');
  state.background.width = canvas.width;
  state.background.height = canvas.height;
  const sky = state.background.getContext('2d');
  sky.scale(ratio, ratio);
  const { width: w, height: h } = state;
  sky.fillStyle = '#080914';
  sky.fillRect(0, 0, w, h);
  const mist = sky.createRadialGradient(w * .55, h * .57, 0, w * .55, h * .57, w * .65);
  mist.addColorStop(0, '#202035'); mist.addColorStop(.45, '#111326'); mist.addColorStop(1, '#080914');
  sky.fillStyle = mist; sky.fillRect(0, 0, w, h);
  const rng = random(7294);
  for (let i = 0; i < w * h / 940; i++) {
    const x = rng() * w, y = rng() * h, radius = rng() > .992 ? 1.5 : .25 + rng() * .65;
    const alpha = .13 + rng() * .6;
    sky.fillStyle = `rgba(${rng() > .76 ? '230,195,160' : '198,204,235'},${alpha})`;
    sky.beginPath(); sky.arc(x, y, radius, 0, Math.PI * 2); sky.fill();
    if (radius > 1) { sky.fillStyle = '#d8def320'; sky.fillRect(x - 5, y - .2, 10, .4); sky.fillRect(x - .2, y - 5, .4, 10); }
  }
  draw();
}

function drawBlackHole(g) {
  const c = context, s = g.scale, radius = 2 * s;
  c.save(); c.translate(g.x, g.y);
  // Decorative light is independent of the geodesic solver. The horizon uses the map scale.
  let glow = c.createRadialGradient(0, 0, radius * .7, 0, 0, radius * 5.9);
  glow.addColorStop(0, '#ffd7a92d'); glow.addColorStop(.22, '#f6b27d2b'); glow.addColorStop(.48, '#cb795a14'); glow.addColorStop(1, '#9d586100');
  c.fillStyle = glow; c.beginPath(); c.arc(0, 0, radius * 5.9, 0, Math.PI * 2); c.fill();
  c.rotate(-.17);
  c.save(); c.scale(1, .27);
  glow = c.createRadialGradient(0, 0, radius * 1.15, 0, 0, radius * 5.6);
  glow.addColorStop(0, '#fff1d600'); glow.addColorStop(.13, '#ffe7bc65'); glow.addColorStop(.25, '#eaaa7c59'); glow.addColorStop(.57, '#bb705831'); glow.addColorStop(1, '#b4684400');
  c.fillStyle = glow; c.beginPath(); c.arc(0, 0, radius * 5.6, 0, Math.PI * 2); c.fill();
  const rng = random(577);
  for (let i = 0; i < 235; i++) {
    const r = radius * (1.55 + rng() ** 1.7 * 3.7);
    const start = rng() * Math.PI * 2, length = .15 + rng() * 1.3;
    const alpha = (.04 + .23 * rng()) * (1 - (r / radius - 1.5) / 5);
    c.strokeStyle = `rgba(255,${Math.round(158 + rng() * 74)},${Math.round(90 + rng() * 65)},${alpha})`;
    c.lineWidth = .6 + rng() * 2; c.beginPath(); c.arc(0, 0, r, start, start + length); c.stroke();
  }
  c.restore();
  // A bright, distorted rear arc gives the illustrative disk its visual depth.
  c.save(); c.scale(1, 1.02);
  for (let i = 20; i >= 0; i--) {
    c.strokeStyle = `rgba(255,${190 + i},${120 + i * 3},${.012 + (20 - i) * .002})`;
    c.lineWidth = 1 + i * 1.3;
    c.beginPath(); c.arc(0, 0, radius * 1.22, Math.PI, Math.PI * 2); c.stroke();
  }
  c.restore();
  c.fillStyle = '#020207'; c.beginPath(); c.arc(0, 0, radius, 0, Math.PI * 2); c.fill();
  c.strokeStyle = '#bda57d55'; c.lineWidth = .7; c.beginPath(); c.arc(0, 0, radius, 0, Math.PI * 2); c.stroke();
  c.shadowColor = '#ffc989'; c.shadowBlur = 14;
  c.strokeStyle = '#ffe2bda0'; c.lineWidth = 1.25; c.beginPath(); c.arc(0, 0, radius * 1.045, -.8, Math.PI * .87); c.stroke();
  c.shadowBlur = 0;
  c.save(); c.scale(1, .27);
  for (let i = 0; i < 24; i++) {
    c.strokeStyle = `rgba(255,${195 + i},${135 + i * 3},${.12 - i * .003})`;
    c.lineWidth = .8; c.beginPath(); c.arc(0, 0, radius * (1.48 + i * .07), .05, Math.PI - .05); c.stroke();
  }
  c.restore(); c.restore();
}

function position(point, g) {
  const angle = point[2] + Math.PI * .86;
  return [g.x + point[1] * Math.cos(angle) * g.scale, g.y - point[1] * Math.sin(angle) * g.scale];
}

function pointAt(points, tau) {
  if (tau <= points[0][0]) return points[0];
  if (tau >= points.at(-1)[0]) return points.at(-1);
  let lo = 0, hi = points.length - 1;
  while (hi - lo > 1) { const mid = (hi + lo) >> 1; if (points[mid][0] <= tau) lo = mid; else hi = mid; }
  const amount = (tau - points[lo][0]) / (points[hi][0] - points[lo][0]);
  return [tau, points[lo][1] + (points[hi][1] - points[lo][1]) * amount, points[lo][2] + (points[hi][2] - points[lo][2]) * amount];
}

function strokePath(points, g, until) {
  context.beginPath();
  for (let i = 0; i < points.length; i++) {
    if (points[i][0] > until) { const p = position(pointAt(points, until), g); context.lineTo(...p); break; }
    const p = position(points[i], g);
    if (!i) context.moveTo(...p); else context.lineTo(...p);
  }
  context.stroke();
}

function drawTrace(trace, kind, g, tau) {
  if (!trace?.points?.length) return;
  const c = context, points = trace.points;
  c.save(); c.strokeStyle = palette[kind]; c.lineWidth = 1;
  c.globalAlpha = kind === 'true' ? .25 : .28;
  c.setLineDash(kind === 'model' ? [4, 5] : []);
  strokePath(points, g, Infinity);
  c.globalAlpha = 1; c.lineWidth = kind === 'true' ? 1.9 : 1.6;
  c.shadowColor = palette[kind]; c.shadowBlur = 7;
  strokePath(points, g, tau);
  c.setLineDash([]); c.shadowBlur = 0;
  const point = pointAt(points, tau), [x, y] = position(point, g);
  const ended = tau >= points.at(-1)[0];
  if (!(ended && trace.outcome === 'capture')) {
    const glow = c.createRadialGradient(x, y, 0, x, y, 15);
    glow.addColorStop(0, kind === 'true' ? '#efb47666' : '#80c2fa66'); glow.addColorStop(1, '#00000000');
    c.fillStyle = glow; c.beginPath(); c.arc(x, y, 15, 0, Math.PI * 2); c.fill();
    c.fillStyle = palette[kind]; c.beginPath(); c.arc(x, y, kind === 'true' ? 3 : 2.5, 0, Math.PI * 2); c.fill();
    c.strokeStyle = '#080914'; c.lineWidth = 1; c.stroke();
  }
  c.restore();
}

function draw() {
  if (state.view === 'cockpit') { drawCockpit(); return; }
  if (state.view === 'lensed') return;
  if (!state.background) return;
  context.clearRect(0, 0, state.width, state.height);
  context.drawImage(state.background, 0, 0, state.width, state.height);
  const g = geometry();
  drawBlackHole(g);
  const tau = state.progress * state.duration;
  if (state.flight) {
    drawTrace(state.flight.model_trace, 'model', g, tau);
    drawTrace(state.flight.true_trace, 'true', g, tau);
  }
  // A quiet scale bar makes the visual zoom interpretable.
  const x = state.width - 95, y = state.height - 83;
  context.strokeStyle = '#8b849b66'; context.lineWidth = 1;
  const length = 5 * g.scale;
  context.beginPath(); context.moveTo(x - length, y); context.lineTo(x, y); context.moveTo(x - length, y - 3); context.lineTo(x - length, y + 3); context.moveTo(x, y - 3); context.lineTo(x, y + 3); context.stroke();
  context.font = '9px Avenir, sans-serif'; context.fillStyle = '#8b849b'; context.textAlign = 'right'; context.fillText('5 M', x, y - 9);
  const label = document.querySelector('.map-label');
  label.style.left = `${g.x + 2 * g.scale + 13}px`;
  label.style.top = `${g.y + 10}px`;
}

function animate(now) {
  if (!state.playing) return;
  const elapsed = state.lastFrame ? Math.min(now - state.lastFrame, 100) : 0;
  state.lastFrame = now;
  state.progress = Math.min(1, state.progress + elapsed / 18000 * Number($('speed').value));
  if (state.view === 'cockpit' && followedTrace()?.points?.length) state.progress = Math.min(state.progress, followedTrace().points.at(-1)[0] / state.duration);
  updateReplay(); draw();
  if (state.progress === 1 || (state.view === 'cockpit' && followedEnd())) pause(); else state.frame = requestAnimationFrame(animate);
}

function pause() {
  state.playing = false; state.lastFrame = 0; cancelAnimationFrame(state.frame);
  syncPlaybackButtons();
  if (state.view === 'cockpit') draw();
}

function play() {
  if (!state.flight) return;
  if (state.view === 'lensed') setView('cockpit');
  if (state.progress === 1 || (state.view === 'cockpit' && followedEnd())) state.progress = 0;
  state.playing = true; state.lastFrame = 0;
  syncPlaybackButtons();
  state.frame = requestAnimationFrame(animate);
}

function updateReplay() {
  $('scrub').value = Math.round(state.progress * 1000);
  $('cockpit-scrub').value = Math.round(state.progress * 1000);
  $('replay-time').value = `τ ${(state.progress * state.duration).toFixed(1)}`;
}

function status(message, error = false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function setView(view) {
  const lensed = view === 'lensed';
  state.view = view;
  document.querySelector('.space-view').classList.toggle('lensed', lensed);
  document.querySelector('.space-view').classList.toggle('cockpit', view === 'cockpit');
  $('cockpit-view').setAttribute('aria-pressed', String(view === 'cockpit'));
  $('lensed-view').setAttribute('aria-pressed', String(lensed));
  $('map-view').setAttribute('aria-pressed', String(view === 'map'));
  $('scene-description').innerHTML = lensed ? 'Schwarzschild light paths with artistic disk emission.<br>Open the Flight map to compare calculated orbits.' : 'Calculated paths on a Schwarzschild coordinate map.<br>The light and lensing are an illustration.';
  if (lensed) pause();
  syncPlaybackButtons(); draw();
}
function displayOutcome(value) { return value === 'escape' ? 'Escape' : value === 'capture' ? 'Capture' : 'Unresolved'; }
function number(value, digits = 3) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('en', { maximumFractionDigits: digits }) : 'Not recorded'; }
function scientific(value) { return typeof value === 'number' && Number.isFinite(value) ? value.toExponential(2) : 'Not recorded'; }

function showFlight(flight, autoPlay = true) {
  if (!flight.true_trace?.points?.length || !flight.model_trace?.points?.length) throw new Error('The flight response has no usable trajectories. Try another launch.');
  pause(); state.flight = flight; state.progress = 0;
  state.duration = Math.max(flight.true_trace.points.at(-1)[0], flight.model_trace.points.at(-1)[0]);
  $('energy').value = flight.energy; $('angular-momentum').value = flight.angular_momentum;
  $('energy-value').value = Number(flight.energy).toFixed(4); $('momentum-value').value = Number(flight.angular_momentum).toFixed(4);
  if (flight.model_id) $('model').value = flight.model_id;
  $('prediction').textContent = displayOutcome(flight.prediction);
  $('actual').textContent = displayOutcome(flight.actual);
  $('kernel-outcome').textContent = `Exact kernel: ${flight.certificate_verified_outcome ? displayOutcome(flight.certificate_verified_outcome).toLowerCase() : 'not recorded'}.`;
  const certificate = flight.certificate;
  $('certificate-summary').textContent = certificate ? `Root count: ${certificate.root_count ?? 'unresolved'}. Sign variations: ${certificate.variations?.lower ?? 'not recorded'} at the lower bound, ${certificate.variations?.upper ?? 'not recorded'} at the upper bound. Square-free polynomial: ${certificate.square_free ? 'yes' : 'no'}.` : 'No exact certificate is recorded for this flight.';
  $('certificate-data').textContent = certificate ? JSON.stringify(certificate, null, 2) : '';
  $('download-certificate').disabled = !certificate;
  $('cockpit-outcomes').textContent = `Model: ${displayOutcome(flight.prediction).toLowerCase()}. Physics: ${displayOutcome(flight.actual).toLowerCase()}.${flight.uncertain === true ? ' Validation: abstain.' : ''}`;
  $('validation-check').textContent = typeof flight.uncertain === 'boolean' ? `Validation check: ${flight.uncertain ? 'abstain' : 'outside the heuristic band'}.` : 'Validation check: not recorded.';
  const unresolved = flight.prediction === 'unresolved' || flight.actual === 'unresolved';
  $('outcome-note').textContent = unresolved ? 'This launch is too close to the boundary to label with confidence. Unresolved does not mean safe.' : flight.prediction === flight.actual ? 'The model and exact physics agree on this outcome. Compare the paths to see the difference.' : flight.prediction === 'escape' ? 'The model predicts escape. Exact physics predicts capture. This is a dangerous false escape.' : 'The model predicts capture. Exact physics predicts escape. This is a false capture.';
  $('trace-note').textContent = `Numerical energy drift: relativity ${scientific(flight.true_trace.energy_drift)}, model ${scientific(flight.model_trace.energy_drift)}. Replay uses shared proper time τ, with each path interpolated independently.`;
  ['scrub', 'play', 'reset', 'cockpit-play', 'cockpit-scrub'].forEach(id => $(id).disabled = false);
  syncPlaybackButtons(); updateReplay(); draw(); drawBarrier();
  status('Flight calculated. Both outcomes shown before replay.');
  if (autoPlay && !reducedMotion.matches) play();
}

async function request(url, signal) {
  const response = await fetch(url, { signal, cache: 'no-store' });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Flight server returned ${response.status}.`);
  return data;
}

async function launch(event) {
  event?.preventDefault();
  if (state.view === 'lensed') setView('cockpit');
  state.controller?.abort(); state.controller = new AbortController();
  const controller = state.controller;
  const parameters = new URLSearchParams({ energy: $('energy').value, angular_momentum: $('angular-momentum').value, model: $('model').value });
  status('Calculating both trajectories…'); $('launch').textContent = 'Calculating…';
  try {
    const flight = await request(`/api/flyby?${parameters}`, controller.signal);
    if (controller !== state.controller) return;
    showFlight(flight);
  } catch (error) { if (controller === state.controller && error.name !== 'AbortError') status(`${error.message} Adjust the launch and try again.`, true); }
  finally { if (controller === state.controller) $('launch').innerHTML = 'Launch flyby <span aria-hidden="true">↗</span>'; }
}

function renderSummary(summary) {
  const models = summary.model_metrics || [];
  const files = summary.model_files || {};
  const select = $('model'); select.replaceChildren();
  for (const id of Object.keys(files)) {
    const metric = models.find(item => item.model_id === id);
    const option = document.createElement('option'); option.value = id;
    const size = Array.isArray(metric?.size) ? metric.size.join(' × ') : metric?.size;
    option.textContent = metric ? `${size || id} · seed ${metric.seed}` : id;
    select.append(option);
  }
  if (!select.options.length) throw new Error('No saved models found. Run the experiment, then reload.');
  select.disabled = false; $('launch').disabled = false;
  const protocol = summary.protocol || {};
  $('training-count').textContent = number(protocol.training_samples ?? protocol.training_observations ?? protocol.train_samples ?? protocol.n_train, 0);
  const nominal = protocol.nominal_trials ?? protocol.nominal_test_samples ?? protocol.nominal_samples ?? protocol.n_nominal;
  const stress = protocol.stress_trials ?? protocol.boundary_test_samples ?? protocol.boundary_samples ?? protocol.n_boundary;
  $('test-count').textContent = typeof nominal === 'number' && typeof stress === 'number' ? number(nominal + stress, 0) : 'See protocol';
  $('model-count').textContent = number(models.length, 0);
  const body = $('metrics'); body.replaceChildren();
  for (const model of models) {
    const row = document.createElement('tr');
    const size = Array.isArray(model.size) ? model.size.join(' × ') : model.size || model.model_id;
    const values = [`${size} / ${model.seed}`, number(model.parameters, 0), scientific(model.potential_rmse), scientific(model.acceleration_rmse), typeof model.fit_seconds === 'number' ? `${number(model.fit_seconds, 2)} s` : 'Not recorded'];
    for (const value of values) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    body.append(row);
  }
  renderClassification(summary.aggregate_metrics || []);
}

function renderClassification(rows) {
  const root = $('classification-results'); root.replaceChildren();
  if (!Array.isArray(rows)) return;
  for (const row of rows) {
    const falseEscapes = row.false_escapes_mean;
    const total = row.trials_per_seed;
    if (typeof falseEscapes !== 'number') continue;
    const section = document.createElement('div'), heading = document.createElement('h3'), description = document.createElement('p');
    const size = Array.isArray(row.size) ? row.size.join(' × ') : row.size || row.model_size || 'Models';
    heading.textContent = `${size === 'small' ? 'Small models' : size === 'large' ? 'Larger models' : size} / ${row.distribution === 'stress' ? 'boundary stress test' : 'nominal flights'}`;
    description.textContent = `${number(falseEscapes, 1)} ± ${number(row.false_escapes_std, 1)} false escapes per ${number(total, 0)} flights, averaged across ${number(row.seeds?.length, 0)} seeds.`;
    if (typeof row.coverage_mean === 'number') description.textContent += ` Models accept ${number(row.coverage_mean * 100, 1)}% of flights. The physics gate accepts ${number(row.gate_coverage_mean * 100, 1)}%.`;
    description.textContent += ' ± shows variation between seeds.';
    section.append(heading, description); root.append(section);
  }
}

$('flight-form').addEventListener('submit', launch);
$('energy').addEventListener('input', () => { $('energy-value').value = Number($('energy').value).toFixed(4); status('Launch to calculate this energy.'); });
$('angular-momentum').addEventListener('input', () => { $('momentum-value').value = Number($('angular-momentum').value).toFixed(4); status('Launch to calculate this angular momentum.'); });
$('model').addEventListener('change', () => status('Launch to compare this model.'));
function loadRecordedFlight() {
  if (state.view === 'lensed') setView('cockpit');
  state.controller?.abort(); $('launch').innerHTML = 'Launch flyby <span aria-hidden="true">↗</span>';
  if (state.showcase) { showFlight(state.showcase); status('Recorded test flight loaded from the saved experiment.'); }
}
$('load-case').addEventListener('click', loadRecordedFlight);
$('cockpit-case').addEventListener('click', loadRecordedFlight);
$('play').addEventListener('click', () => state.playing ? pause() : play());
$('cockpit-play').addEventListener('click', () => state.playing ? pause() : play());
$('reset').addEventListener('click', () => { pause(); state.progress = 0; updateReplay(); draw(); });
function scrub(value) {
  if (state.view === 'lensed') setView('cockpit');
  pause(); state.progress = Number(value) / 1000; updateReplay(); draw(); syncPlaybackButtons();
}
$('scrub').addEventListener('input', () => scrub($('scrub').value));
$('cockpit-scrub').addEventListener('input', () => scrub($('cockpit-scrub').value));
$('cockpit-view').addEventListener('click', () => setView('cockpit'));
$('lensed-view').addEventListener('click', () => setView('lensed'));
$('map-view').addEventListener('click', () => setView('map'));
$('lensed-image').addEventListener('load', draw);
$('lensed-image').addEventListener('error', () => { $('lensed-view').disabled = true; if (state.view === 'lensed') setView('map'); });
$('cockpit-shell').addEventListener('load', () => document.querySelector('.space-view').classList.add('shell-ready'));
if ($('cockpit-shell').complete && $('cockpit-shell').naturalWidth) document.querySelector('.space-view').classList.add('shell-ready');
function followWorld(world) {
  state.world = world;
  $('follow-true').setAttribute('aria-pressed', String(world === 'true'));
  $('follow-model').setAttribute('aria-pressed', String(world === 'model'));
  $('cockpit-world-title').textContent = world === 'true' ? 'Following relativity' : 'Following the learned model';
  if (state.view === 'cockpit' && followedEnd()) pause();
  syncPlaybackButtons(); draw();
}
$('follow-true').addEventListener('click', () => followWorld('true'));
$('follow-model').addEventListener('click', () => followWorld('model'));
function immersiveControls() {
  const scene = document.querySelector('.space-view');
  return [scene, ...scene.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]')].filter(element => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden');
}
function setImmersive(active) {
  if (active === state.immersive) return;
  const scene = document.querySelector('.space-view');
  state.immersive = active;
  if (active) {
    returnFocus = document.activeElement;
    backgroundElements = [...document.querySelectorAll('.site-header, .flight-desk, .barrier-section, .experiment, footer')].map(element => ({ element, inert: element.inert }));
    backgroundElements.forEach(({ element }) => element.inert = true);
    setView('cockpit');
    scene.setAttribute('role', 'dialog'); scene.setAttribute('aria-modal', 'true'); scene.setAttribute('aria-label', 'Immersive black hole cockpit');
  } else {
    backgroundElements.forEach(({ element, inert }) => element.inert = inert);
    backgroundElements = [];
    scene.removeAttribute('role'); scene.removeAttribute('aria-modal'); scene.removeAttribute('aria-label');
  }
  scene.classList.toggle('immersive', active);
  document.body.classList.toggle('immersive-open', active);
  $('immersive-view').textContent = active ? 'Exit immersive view' : 'Immersive view';
  $('immersive-view').setAttribute('aria-pressed', String(active));
  $('leave-immersive').hidden = !active;
  if (active) ($('cockpit-play').disabled ? $('leave-immersive') : $('cockpit-play')).focus({ preventScroll: true });
  else if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  requestAnimationFrame(resize);
}
$('immersive-view').addEventListener('click', () => setImmersive(!state.immersive));
$('leave-immersive').addEventListener('click', () => setImmersive(false));
function setEffects(active) {
  state.effects = active;
  document.querySelector('.space-view').classList.toggle('effects-on', active);
  $('effects').setAttribute('aria-pressed', String(active)); $('effects').textContent = active ? 'Effects on' : 'Effects off';
  draw();
}
$('effects').addEventListener('click', () => setEffects(!state.effects));
function setLook(yaw, pitch) {
  state.lookYaw = Math.max(-.8, Math.min(.8, yaw));
  state.lookPitch = Math.max(-.45, Math.min(.45, pitch));
  if (!state.playing && !lookFrame) lookFrame = requestAnimationFrame(() => { lookFrame = 0; draw(); });
}
$('center-view').addEventListener('click', () => setLook(0, 0));
const lookScene = document.querySelector('.space-view');
lookScene.addEventListener('pointerdown', event => {
  if (lookDrag || state.view !== 'cockpit' || event.button !== 0 || !(event.target === lookScene || event.target.id === 'cockpit' || event.target.classList.contains('cockpit-fallback'))) return;
  lookDrag = { id: event.pointerId, startX: event.clientX, startY: event.clientY, lastX: event.clientX, lastY: event.clientY, looking: event.pointerType !== 'touch' || state.immersive };
  lookScene.setPointerCapture(event.pointerId);
  if (lookDrag.looking) { lookScene.focus({ preventScroll: true }); lookScene.classList.add('looking'); }
});
lookScene.addEventListener('pointermove', event => {
  if (!lookDrag || lookDrag.id !== event.pointerId) return;
  if (!lookDrag.looking) {
    const dx = event.clientX - lookDrag.startX, dy = event.clientY - lookDrag.startY;
    if (Math.abs(dy) > 8 && Math.abs(dy) > Math.abs(dx)) { endLook(event); return; }
    if (Math.abs(dx) < 8) return;
    lookDrag.looking = true; lookScene.focus({ preventScroll: true }); lookScene.classList.add('looking');
  }
  setLook(state.lookYaw + (event.clientX - lookDrag.lastX) * 1.7 / Math.max(1, state.width), state.lookPitch - (event.clientY - lookDrag.lastY) * 1.1 / Math.max(1, state.height));
  lookDrag.lastX = event.clientX; lookDrag.lastY = event.clientY;
});
function endLook(event) {
  if (!lookDrag || lookDrag.id !== event.pointerId) return;
  if (lookScene.hasPointerCapture(event.pointerId)) lookScene.releasePointerCapture(event.pointerId);
  lookDrag = null; lookScene.classList.remove('looking');
  if (!state.playing) setLook(state.lookYaw, state.lookPitch);
}
lookScene.addEventListener('pointerup', endLook);
lookScene.addEventListener('pointercancel', endLook);
lookScene.addEventListener('lostpointercapture', endLook);
document.addEventListener('keydown', event => {
  const arrows = { ArrowLeft: [-.04, 0], ArrowRight: [.04, 0], ArrowUp: [0, .035], ArrowDown: [0, -.035] };
  if (state.view === 'cockpit' && arrows[event.key] && lookScene.contains(document.activeElement) && !event.target.closest('button, input, select, textarea, a, summary, [contenteditable="true"]')) {
    event.preventDefault(); const step = event.shiftKey ? 2 : 1;
    setLook(state.lookYaw + arrows[event.key][0] * step, state.lookPitch + arrows[event.key][1] * step); return;
  }
  if (!state.immersive) return;
  if (event.key === 'Escape') { event.preventDefault(); setImmersive(false); return; }
  if (event.key === 'Tab') {
    const controls = immersiveControls(), first = controls[0], last = controls.at(-1);
    if (event.shiftKey && (document.activeElement === first || !controls.includes(document.activeElement))) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || !controls.includes(document.activeElement))) { event.preventDefault(); first?.focus(); }
  }
  if (event.code === 'Space' && !['INPUT', 'BUTTON', 'SELECT', 'TEXTAREA', 'SUMMARY'].includes(event.target.tagName)) { event.preventDefault(); if (state.playing) pause(); else play(); }
});
document.addEventListener('focusin', event => { if (state.immersive && !document.querySelector('.space-view').contains(event.target)) immersiveControls()[0]?.focus(); });
$('download-certificate').addEventListener('click', () => {
  if (!state.flight?.certificate) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(state.flight.certificate, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = 'black-hole-certificate.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('zoom-in').addEventListener('click', () => { state.viewRadius = Math.max(5, state.viewRadius / 1.4); draw(); });
$('zoom-out').addEventListener('click', () => { state.viewRadius = Math.min(90, state.viewRadius * 1.4); draw(); });
$('fit-view').addEventListener('click', () => {
  const points = state.flight ? [...state.flight.true_trace.points, ...state.flight.model_trace.points] : [];
  state.viewRadius = points.length ? Math.max(10, ...points.map(point => point[1])) * 1.08 : 35;
  draw();
});
reducedMotion.addEventListener('change', () => { if (reducedMotion.matches) { pause(); setEffects(false); } });
document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
new ResizeObserver(resize).observe(canvas);
new ResizeObserver(drawBarrier).observe($('barrier-chart'));
$('barrier-zoom').addEventListener('click', () => {
  wholeBarrier = !wholeBarrier;
  $('barrier-zoom').setAttribute('aria-pressed', String(wholeBarrier));
  $('barrier-zoom').textContent = wholeBarrier ? 'Show vertical detail' : 'Show whole barrier';
  drawBarrier();
});
setView('cockpit');
setEffects(state.effects);

async function initialize() {
  try {
    const [summary, showcase] = await Promise.all([request('/api/summary'), request('/api/showcase')]);
    renderSummary(summary); state.showcase = showcase;
    const dangerous = showcase.prediction === 'escape' && showcase.actual === 'capture';
    $('case-button-text').textContent = dangerous ? 'Load the false escape' : 'Load recorded test flight';
    $('cockpit-case').textContent = dangerous ? 'Replay false escape' : 'Load recorded flight';
    $('load-case').disabled = false;
    $('cockpit-case').disabled = false;
    showFlight(showcase, false);
    status(dangerous ? 'A recorded false escape. Begin the flyby, then switch worlds.' : 'A recorded test flight. Begin the flyby to explore.');
  } catch (error) {
    status(`${error.message} Check the local experiment server and reload.`, true);
    $('metrics').replaceChildren(); const row = document.createElement('tr'), cell = document.createElement('td');
    cell.colSpan = 5; cell.textContent = 'Measured results could not load. Check the local server and reload.'; row.append(cell); $('metrics').append(row);
  }
}
initialize();
