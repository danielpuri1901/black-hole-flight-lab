import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import vm from 'node:vm';

const root = resolve(import.meta.dirname, 'dashboard');
const source = async path => readFile(resolve(root, path), 'utf8');
const asModule = code => `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
const core = asModule(await source('vendor/three.core.js'));
const three = asModule((await source('vendor/three.module.js')).replaceAll("from './three.core.js'", `from '${core}'`));
const rounded = asModule((await source('vendor/addons/geometries/RoundedBoxGeometry.js')).replace("from 'three'", `from '${three}'`));
const cabinSource = (await source('cabin.js')).replace("from 'three/addons/geometries/RoundedBoxGeometry.js'", `from '${rounded}'`);
const THREE = await import(three);
const { createCabin } = await import(asModule(cabinSource));

const canvases = [];
globalThis.document = { createElement(tag) {
  assert.equal(tag, 'canvas');
  const calls = [];
  const context = new Proxy({
    calls, font: '10px sans-serif',
    createImageData: (width, height) => ({ data: new Uint8ClampedArray(width * height * 4) }),
    measureText(value) { return { width: String(value).length * Number.parseFloat(this.font?.match(/[\d.]+px/)?.[0] || '10') * .6 }; },
  }, {
    get(target, key) { return key in target ? target[key] : (...args) => calls.push([key, ...args]); },
    set(target, key, value) { if (key === 'font') calls.push(['font', value]); target[key] = value; return true; },
  });
  const canvas = { width: 0, height: 0, getContext: () => context };
  canvases.push({ canvas, calls, context });
  return canvas;
} };

const cabin = createCabin(THREE);
for (const { calls, context } of canvases) {
  assert(Number.isFinite(Number.parseFloat(context.font.match(/[\d.]+px/)?.[0])), 'Nonfinite canvas font');
  for (const [, font] of calls.filter(([method]) => method === 'font')) assert(Number.isFinite(Number.parseFloat(font.match(/[\d.]+px/)?.[0])), 'Nonfinite canvas font');
  for (const call of calls) assert(call.slice(1).filter(value => typeof value === 'number').every(Number.isFinite), `Nonfinite ${call[0]} coordinate`);
}
const longLabel = canvases.find(({ calls }) => calls.some(([method, value]) => method === 'fillText' && value === 'CAUTION / MANUAL RELEASE'));
assert(longLabel, 'Long label was not drawn');
assert(longLabel.context.measureText('CAUTION / MANUAL RELEASE').width <= 232, 'Long label exceeds texture width');
cabin.group.updateMatrixWorld(true);
const byName = name => {
  const mesh = cabin.group.getObjectByName(name);
  assert(mesh, `Missing ${name}`);
  return mesh;
};
const ray = new THREE.Raycaster();
function surfaceHeight(support, point) {
  ray.set(new THREE.Vector3(point.x, 3, point.z), new THREE.Vector3(0, -1, 0));
  const hit = ray.intersectObject(support)[0];
  assert(hit, `${support.name} does not support display at x=${point.x.toFixed(2)}, z=${point.z.toFixed(2)}`);
  return hit.point.y;
}

let checked = 0;
for (const side of ['port', 'starboard']) for (const kind of ['main', 'side']) {
  const group = byName(`${side}-${kind}-instrument`);
  const plane = byName(`${side}-${kind}-instrument-display`);
  assert.equal(plane.parent, group);
  assert.equal(plane.userData.role, 'instrument-display');
  assert.equal(plane.userData.instrument, kind);
  const support = byName(kind === 'main' ? 'dashboard-top' : `${side}-wing-top`);
  const corners = [-1, 1].flatMap(x => [-1, 1].map(y => new THREE.Vector3(x * plane.geometry.parameters.width / 2, y * plane.geometry.parameters.height / 2, 0).applyMatrix4(plane.matrixWorld)));
  for (const point of corners) {
    assert(point.toArray().every(Number.isFinite), `${plane.name} has nonfinite corner`);
    assert(point.y > surfaceHeight(support, point) + .002, `${plane.name} disappears into ${support.name}`);
  }
  const housing = group.children.find(child => child.isMesh && child !== plane);
  assert(housing, `${group.name} lacks housing`);
  const bounds = new THREE.Box3().setFromObject(housing);
  const center = new THREE.Vector3(); group.getWorldPosition(center);
  const top = surfaceHeight(support, center);
  assert(bounds.min.y < top && bounds.max.y > top, `${group.name} housing floats above or hides below support`);
  checked++;
}

function instanceBounds(mesh, index, world = true) {
  const matrix = new THREE.Matrix4();
  mesh.getMatrixAt(index, matrix);
  if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
  return mesh.geometry.boundingBox.clone().applyMatrix4(world ? matrix.premultiply(mesh.matrixWorld) : matrix);
}
function assertSeated(bottom, surface, label, allowedDepth = .004) {
  assert(bottom >= surface - allowedDepth && bottom <= surface + .0005,
    `${label} misses support by ${((bottom - surface) * 1000).toFixed(2)} mm`);
}
const toggleMesh = byName('console-toggles');
assert.equal(toggleMesh.count, 32);
let mounted = 0;
for (let i = 0; i < toggleMesh.count; i++) {
  const bounds = instanceBounds(toggleMesh, i);
  const center = bounds.getCenter(new THREE.Vector3());
  const side = center.x < 0 ? 'port' : 'starboard';
  const top = surfaceHeight(byName(`${side}-console-top`), center);
  assertSeated(bounds.min.y, top, `Toggle ${i}`);
  mounted++;
}
const rings = byName('console-knob-rings'), knobs = byName('console-knobs'), ticks = byName('console-knob-ticks');
assert.equal(rings.count, 4); assert.equal(knobs.count, 4); assert.equal(ticks.count, 4);
for (let i = 0; i < rings.count; i++) {
  const ring = instanceBounds(rings, i), knob = instanceBounds(knobs, i), tick = instanceBounds(ticks, i);
  const center = knob.getCenter(new THREE.Vector3());
  const side = center.x < 0 ? 'port' : 'starboard';
  const top = surfaceHeight(byName(`${side}-console-top`), center);
  assertSeated(ring.min.y, top, `Knob ring ${i}`, .002);
  assertSeated(knob.min.y, top, `Knob ${i}`, .002);
  assertSeated(tick.min.y, knob.max.y, `Knob tick ${i}`, .003);
  mounted += 3;
}
const bolts = byName('cabin-bolts');
assert.equal(bolts.count, 76);
for (let i = 0; i < bolts.count; i++) {
  const bounds = instanceBounds(bolts, i);
  const center = bounds.getCenter(new THREE.Vector3());
  if (i < 36) {
    const support = Math.abs(center.x) < 1.5 ? byName(`${center.x < 0 ? 'port' : 'starboard'}-floor-rail`) : byName('floor-side-seams');
    assertSeated(bounds.min.y, surfaceHeight(support, center), `Floor bolt ${i}`);
  } else {
    const side = Math.sign(center.x);
    ray.set(new THREE.Vector3(side * 1.9, center.y, center.z), new THREE.Vector3(side, 0, 0));
    const hit = ray.intersectObject(byName('wall-inserts'))[0];
    assert(hit && bounds.min.x <= hit.point.x + .0005 && bounds.max.x >= hit.point.x - .0005, `Wall bolt ${i} lacks panel support`);
  }
  mounted++;
}
for (const side of ['port', 'starboard']) for (const kind of ['main', 'side']) {
  const instrument = byName(`${side}-${kind}-instrument`);
  const casing = instrument.children[0];
  const screws = instrument.getObjectByName('instrument-screws');
  const buttons = instrument.getObjectByName('instrument-buttons');
  assert(screws && buttons, `${instrument.name} lacks fasteners`);
  for (const [parts, support, label] of [[screws, casing, 'screw'], [buttons, instrument.children[1], 'button']]) for (let i = 0; i < parts.count; i++) {
    const localBounds = instanceBounds(parts, i, false);
    const center = localBounds.getCenter(new THREE.Vector3());
    ray.set(new THREE.Vector3(center.x, center.y, 1).applyMatrix4(instrument.matrixWorld),
      new THREE.Vector3(0, 0, -1).transformDirection(instrument.matrixWorld));
    const hit = ray.intersectObject(support)[0];
    assert(hit, `${instrument.name} ${label} ${i} misses support`);
    const face = hit.point.applyMatrix4(instrument.matrixWorld.clone().invert()).z;
    assertSeated(localBounds.min.z, face, `${instrument.name} ${label} ${i}`, .002);
    mounted++;
  }
}
const vents = byName('overhead-vents');
assert.equal(vents.count, 36);
for (let i = 0; i < vents.count; i++) {
  const bounds = instanceBounds(vents, i);
  const center = bounds.getCenter(new THREE.Vector3());
  const rack = byName(`${center.x < 0 ? 'port' : 'starboard'}-overhead-rack`);
  const face = rack.getObjectByName('panel-face');
  ray.set(new THREE.Vector3(center.x, 2, center.z), new THREE.Vector3(0, 1, 0));
  const hit = ray.intersectObject(face)[0];
  assert(hit && bounds.max.y >= hit.point.y && bounds.min.y <= hit.point.y - .002, `Vent ${i} floats below rack face`);
  mounted++;
}

const rendererSource = await source('cockpit-3d.js');
const presetLiteral = rendererSource.match(/const presets = (\{[^;]+\});/);
assert(presetLiteral, 'Missing camera presets');
const presets = vm.runInNewContext(`(${presetLiteral[1]})`);
for (const [name, point] of Object.entries(presets)) for (const box of cabin.colliders) {
  assert(point.some((value, axis) => {
    const margin = axis === 1 ? 0 : .24;
    return value < box.min[axis] - margin || value > box.max[axis] + margin;
  }), `${name} preset is inside a camera collider`);
}

const displays = canvases.filter(({ canvas }) => canvas.width === 512 && canvas.height === 256);
assert.equal(displays.length, 4);
for (const display of displays) display.calls.length = 0;
const frame = { radius: 9.25, time: 12.5, energy: .95, fuel: .8, burn: [.1, -.2], controller: 'learned', trajectory: [[0, 15], [10, 11], [20, 8]] };
const displayText = () => displays.flatMap(({ calls }) => calls.filter(([method]) => method === 'fillText').map(call => call[1]));
cabin.update(frame);
const text = displayText();
assert(text.some(value => String(value).includes('12.5 M')), 'Time unit missing');
assert(text.some(value => String(value).includes('LEARNED')), 'Controller label missing');
const trace = displays[0].calls.filter(([method]) => method === 'moveTo' || method === 'lineTo');
assert(trace.filter(([method]) => method === 'lineTo').length >= 3, 'Trajectory rows did not make plot segments');
assert(trace.some(([, x, y]) => x === 270 && y === 77), 'First trajectory point missing');
assert(trace.some(([, x, y]) => x === 475 && y === 209), 'Last trajectory point missing');
const firstMidpoint = trace.find(([method, x]) => method === 'lineTo' && x === 372.5)?.[2];
assert(Number.isFinite(firstMidpoint), 'Trajectory midpoint missing');
for (const display of displays) display.calls.length = 0;
cabin.update({ ...frame, controller: 'checked' });
assert(displayText().some(value => String(value).includes('CHECKED')), 'Controller-only update was cached');
for (const display of displays) display.calls.length = 0;
cabin.update({ ...frame, controller: 'checked', trajectory: [[0, 15], [10, 14], [20, 8]] });
const secondMidpoint = displays[0].calls.find(([method, x]) => method === 'lineTo' && x === 372.5)?.[2];
assert(Number.isFinite(secondMidpoint) && secondMidpoint !== firstMidpoint, 'Trajectory-only update was cached');
for (const display of displays) display.calls.length = 0;
cabin.update({ ...frame, controller: 'checked', trajectory: null });
assert(displayText().includes('NO FLIGHT TRACE'), 'Missing trace label absent');
cabin.dispose();
console.log(`Cabin check passed: ${checked} lit displays, ${mounted} hardware parts mounted, ${Object.keys(presets).length} presets clear, telemetry plotted.`);
