import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import vm from 'node:vm';

const root = resolve(import.meta.dirname, 'dashboard');
const source = await readFile(resolve(root, 'cockpit-3d.js'), 'utf8');
const core = await readFile(resolve(root, 'vendor/three.core.js'), 'utf8');
const module = (await readFile(resolve(root, 'vendor/three.module.js'), 'utf8'))
  .replaceAll("from './three.core.js'", `from 'data:text/javascript;base64,${Buffer.from(core).toString('base64')}'`);
const THREE = await import(`data:text/javascript;base64,${Buffer.from(module).toString('base64')}`);
const window = {};
vm.runInNewContext(source.replace(/^import .*;\n/gm, ''), { THREE, window });
const CockpitRenderer = window.CockpitRenderer;
const box = (min, max) => new THREE.Box3(new THREE.Vector3(...min), new THREE.Vector3(...max));
const walker = (position, obstacles = []) => {
  const subject = Object.create(CockpitRenderer.prototype);
  subject.location = new THREE.Vector3(...position);
  subject.look = new THREE.Quaternion();
  subject.colliders = obstacles;
  return subject;
};
const near = (actual, expected) => assert(Math.abs(actual - expected) < 1e-4, `${actual} != ${expected}`);

const pitched = walker([0, 1.45, -.65]);
pitched.look.setFromEuler(new THREE.Euler(-.7, 0, 0, 'YXZ'));
pitched.moveLocal(0, .5);
near(pitched.location.y, 1.65);
near(pitched.location.z, -1.15);

const heading = walker([0, 1.65, 0]);
heading.look.setFromEuler(new THREE.Euler(-.7, -Math.PI / 2, 0, 'YXZ'));
heading.moveLocal(0, .5);
near(heading.location.x, .5);
near(heading.location.z, 0);

const desk = box([-.8, 0, -1.5], [.8, 1.1, -.8]);
const blocked = walker([0, 1.65, 0], [desk]);
blocked.moveLocal(0, 2);
assert(blocked.location.z > -.8, 'Body passed through low desk');

const slide = walker([0, 1.65, 0], [box([.3, 0, -.5], [.8, 1.9, .5])]);
slide.moveLocal(1, 1);
assert(slide.location.x < .3 && slide.location.z < -.9, 'Wall slide failed');

const seat = walker([0, 1.65, 0], [box([.62, 0, .76], [1.66, 1.9, 1.76])]);
seat.moveLocal(1, -1);
assert(seat.location.z < .76, 'Walked through seat');

const aisle = walker([0, 1.65, 2], [
  box([-.9, 0, -.2], [-.4, 1.9, 1.8]),
  box([.4, 0, -.2], [.9, 1.9, 1.8]),
  box([-.4, 1.8, -.2], [.4, 2.1, 1.8]),
]);
aisle.moveLocal(0, 1);
near(aisle.location.z, 1);

const preset = walker([0, 1.6, -1.75]);
preset.setView('pilot');
near(preset.location.y, 1.45);
preset.moveLocal(0, .1);
near(preset.location.y, 1.65);
preset.setView('cabin');
near(preset.location.y, 1.65);
near(preset.location.z, 2.65);
preset.setView('window');
near(preset.location.y, 1.6);
preset.moveLocal(0, -.1);
near(preset.location.y, 1.65);

console.log('Cabin walking checks passed');
