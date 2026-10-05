import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

// The view faces -z. Geometry surrounds, but does not cross, the three camera presets.
export function createCabin(THREE) {
  const group = new THREE.Group();
  group.name = 'Research shuttle cabin';
  const owned = new Set();
  const materials = new Set();
  const keep = geometry => (owned.add(geometry), geometry);
  const mat = (color, roughness = .72, metalness = .3, extra = {}) => {
    const material = new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
    materials.add(material);
    return material;
  };
  const graphite = mat(0x20282a, .88, .24);
  const dark = mat(0x0c1418, .79, .3);
  const alloy = mat(0x687174, .43, .82);
  const edge = mat(0x939b97, .35, .9);
  const bone = mat(0x68706a, .88, .18);
  const slate = mat(0x333d40, .84, .3);
  const worn = mat(0x56605f, .68, .54);
  const cushion = mat(0x454c46, .96, .03);
  const webbing = mat(0x6d6c59, .94, .04);
  const rubber = mat(0x0b1011, 1, .02);
  const amber = mat(0xb47230, .48, .3, { emissive: 0x7b2f09, emissiveIntensity: .42 });
  const green = mat(0x81bda8, .43, .25, { emissive: 0x285748, emissiveIntensity: .9 });
  const glass = mat(0x102422, .35, .18, { emissive: 0x071c16, emissiveIntensity: .4 });

  // Deterministic wear and weave. One small tile serves each material family.
  const surfaceTextures = [];
  function noise(x, y, seed) {
    let n = Math.imul(x + seed, 374761393) ^ Math.imul(y - seed, 668265263);
    n = Math.imul(n ^ n >>> 13, 1274126177);
    return ((n ^ n >>> 16) >>> 0) / 4294967295;
  }
  function surface(kind, channel) {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 128;
    const context = canvas.getContext('2d');
    const pixels = context.createImageData(128, 128);
    for (let y = 0; y < 128; y++) for (let x = 0; x < 128; x++) {
      const fine = noise(x, y, kind === 'paint' ? 11 : kind === 'metal' ? 23 : 37);
      const long = noise(x, y >> 3, 41);
      const edgeWear = x < 3 || x > 124 || y < 3 || y > 124 ? 1 : 0;
      let value;
      if (kind === 'fabric') value = 226 + (x % 4 === 0 ? 13 : -4) + (y % 4 === 0 ? 11 : -3) + fine * 5;
      else if (channel === 'roughness') value = kind === 'metal' ? 213 + fine * 24 - edgeWear * 23 : 226 + fine * 18 - edgeWear * 17;
      else value = kind === 'metal' ? 225 + fine * 13 + long * 10 + edgeWear * 6 : 229 + fine * 15 + (long > .985 ? -27 : 0) + edgeWear * 9;
      const i = (y * 128 + x) * 4;
      pixels.data[i] = pixels.data[i + 1] = pixels.data[i + 2] = Math.max(0, Math.min(255, value));
      pixels.data[i + 3] = 255;
    }
    context.putImageData(pixels, 0, 0);
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    if (kind === 'fabric') texture.repeat.set(8, 8);
    if (channel === 'color') texture.colorSpace = THREE.SRGBColorSpace;
    surfaceTextures.push(texture);
    return texture;
  }
  const paintColor = surface('paint', 'color'), paintRough = surface('paint', 'roughness');
  const metalColor = surface('metal', 'color'), metalRough = surface('metal', 'roughness');
  const fabric = surface('fabric', 'color');
  for (const material of [graphite, slate, worn, bone]) {
    material.map = paintColor; material.roughnessMap = paintRough;
    material.bumpMap = paintRough; material.bumpScale = .007;
  }
  for (const material of [alloy, edge]) {
    material.map = metalColor; material.roughnessMap = metalRough;
    material.bumpMap = metalRough; material.bumpScale = .005;
  }
  for (const material of [cushion, webbing]) {
    material.map = fabric; material.bumpMap = fabric; material.bumpScale = .009;
  }

  const cube = keep(new THREE.BoxGeometry(1, 1, 1));
  const rounded = keep(new RoundedBoxGeometry(1, 1, 1, 2, .085));
  const rod = keep(new THREE.CylinderGeometry(1, 1, 1, 10));
  const fineRod = keep(new THREE.CylinderGeometry(1, 1, 1, 7));
  const torus = keep(new THREE.TorusGeometry(1, .13, 5, 16));
  function block(parent, material, x, y, z, sx, sy, sz, bevel = false) {
    const mesh = new THREE.Mesh(bevel ? rounded : cube, material);
    mesh.position.set(x, y, z);
    mesh.scale.set(sx, sy, sz);
    parent.add(mesh);
    return mesh;
  }
  function repeatedBlocks(parent, material, positions, bevel = false) {
    const mesh = new THREE.InstancedMesh(bevel ? rounded : cube, material, positions.length);
    const object = new THREE.Object3D();
    positions.forEach(([x, y, z, sx, sy, sz], i) => {
      object.position.set(x, y, z);
      object.scale.set(sx, sy, sz);
      object.updateMatrix();
      mesh.setMatrixAt(i, object.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
    parent.add(mesh);
    return mesh;
  }
  function beam(parent, material, a, b, radius, geometry = rod) {
    const start = new THREE.Vector3(...a), end = new THREE.Vector3(...b);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(start).add(end).multiplyScalar(.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.sub(start).normalize());
    mesh.scale.set(radius, new THREE.Vector3(...b).distanceTo(new THREE.Vector3(...a)), radius);
    parent.add(mesh);
    return mesh;
  }
  function panel(parent, x, y, z, sx, sy, sz, material = graphite) {
    const casing = block(parent, dark, x, y, z, sx + .045, sy + .045, sz + .045, true);
    const face = block(parent, material, x, y, z + sz * .5 + .026, sx, sy, .019, true);
    face.name = 'panel-face';
    return casing;
  }
  function line(parent, material, a, b, width = .02) { return beam(parent, material, a, b, width, fineRod); }

  // Ribbed pressure shell. The panoramic gap remains open to the ray-traced exterior.
  block(group, graphite, 0, -.11, .1, 4.46, .2, 6.72);
  block(group, graphite, -2.18, 1.44, .1, .17, 2.98, 6.75);
  block(group, graphite, 2.18, 1.44, .1, .17, 2.98, 6.75);
  block(group, dark, 0, 2.92, .16, 4.42, .14, 6.6);
  block(group, graphite, 0, 1.45, 3.37, 4.25, 2.87, .2);
  const wallFrames = [], wallInserts = [], wallEdges = [];
  for (const side of [-1, 1]) {
    block(group, slate, side * 2.09, 1.03, -.1, .06, 1.93, 6.25);
    block(group, alloy, side * 2.08, 2.52, .1, .1, .11, 6.5);
    for (const z of [-1.75, .35, 2.37]) {
      block(group, alloy, side * 2.025, 1.46, z, .15, 2.64, .1, true);
      block(group, dark, side * 1.93, 1.44, z, .025, 2.38, .025);
    }
    for (const z of [-2.35, -1.11, .13, 1.37, 2.61]) for (const y of [.8, 1.84]) {
      wallFrames.push([side * 2.048, y, z, .045, .83, 1.08]);
      wallInserts.push([side * 2.018, y, z, .018, .73, .96]);
      wallEdges.push([side * 2.004, y - .4, z, .018, .018, .97]);
    }
    // Sloping side-window struts continue into the panoramic windshield frame.
    beam(group, alloy, [side * 2.03, .7, -2.95], [side * 1.72, 2.68, -3.02], .075);
    beam(group, edge, [side * 1.95, .72, -2.94], [side * 1.65, 2.62, -3.01], .013);
  }
  repeatedBlocks(group, worn, wallFrames, true);
  const wallInsertMesh = repeatedBlocks(group, graphite, wallInserts, true);
  wallInsertMesh.name = 'wall-inserts';
  repeatedBlocks(group, alloy, wallEdges);
  // Front windshield: horizontal armor, canted pillars, and a thin central post.
  block(group, graphite, 0, .36, -3.05, 4.3, .7, .34, true);
  block(group, alloy, 0, .73, -3.04, 4.12, .095, .15, true);
  block(group, graphite, 0, 2.81, -3.03, 4.25, .28, .28, true);
  block(group, edge, 0, 2.66, -3.025, 4.13, .025, .085);
  const rackMounts = [];
  for (const side of [-1, 1]) {
    beam(group, dark, [side * .88, .75, -3.06], [side * .99, 2.68, -3.06], .078);
    beam(group, alloy, [side * .88, .75, -3.00], [side * .99, 2.68, -3.00], .047);
    beam(group, edge, [side * .83, .8, -2.95], [side * .94, 2.61, -2.95], .008);
  }
  // Short ceiling trusses emphasize depth while leaving the forward disk visible.
  for (const z of [-2.8, -1.75, -.45, .9, 2.35]) {
    block(group, alloy, 0, 2.76, z, 4.05, .09, .095, true);
    block(group, dark, 0, 2.685, z, 3.72, .03, .04);
  }
  for (const side of [-1, 1]) {
    const rack = new THREE.Group();
    rack.name = side < 0 ? 'port-overhead-rack' : 'starboard-overhead-rack';
    rack.position.set(side * 1.22, 2.64, -1.02);
    rack.rotation.x = Math.PI / 2;
    group.add(rack);
    panel(rack, 0, 0, 0, 1.3, .7, .07);
    block(rack, alloy, 0, -.25, .08, 1.19, .015, .03);
    block(rack, bone, -.4, .12, .088, .18, .11, .025, true);
    block(rack, amber, .43, .15, .077, .09, .025, .02, true);
    block(rack, green, .29, .15, .077, .09, .025, .02, true);
    for (const offset of [-.45, .45]) rackMounts.push([side * 1.22 + offset, 2.78, -1.02, .075, .27, .11]);
    for (const z of [.1, 1.92]) {
      const bay = new THREE.Group();
      bay.position.set(side * 2.005, 1.63, z);
      bay.rotation.y = -side * Math.PI / 2;
      group.add(bay);
      panel(bay, 0, 0, 0, .82, .75, .07);
      block(bay, alloy, 0, .25, .075, .67, .025, .018);
      block(bay, rubber, 0, -.19, .09, .45, .08, .04, true);
      block(bay, green, -.25, .15, .077, .044, .027, .02, true);
    }
  }
  repeatedBlocks(group, alloy, rackMounts, true);
  const ventGeometry = keep(new THREE.BoxGeometry(.035, .24, .014));
  const vents = new THREE.InstancedMesh(ventGeometry, dark, 36);
  const ventDummy = new THREE.Object3D();
  for (let i = 0; i < 36; i++) {
    const rack = Math.floor(i / 18), j = i % 18;
    ventDummy.position.set((rack ? 1 : -1) * 1.22 - .51 + j * .06, 2.566, -1.04);
    ventDummy.rotation.set(Math.PI / 2, 0, 0);
    ventDummy.updateMatrix(); vents.setMatrixAt(i, ventDummy.matrix);
  }
  vents.instanceMatrix.needsUpdate = true;
  vents.name = 'overhead-vents';
  group.add(vents);

  // Recessed deck, walk strip, rails and bolted floor panels.
  block(group, dark, 0, .009, .1, 2.05, .025, 6.4);
  const sideSeams = [], aisleSeams = [], deckPlates = [];
  for (const side of [-1, 1]) {
    const rail = block(group, alloy, side * 1.02, .043, .05, .055, .045, 6.4);
    rail.name = side < 0 ? 'port-floor-rail' : 'starboard-floor-rail';
    block(group, dark, side * 1.65, .031, .05, .95, .025, 6.4);
    for (let z = -2.7; z <= 2.9; z += .7) {
      sideSeams.push([side * 1.62, .058, z, .83, .008, .012]);
    }
  }
  for (let z = -2.65; z <= 2.8; z += .62) {
    aisleSeams.push([0, .035, z, 1.72, .012, .018]);
    deckPlates.push([0, .045, z + .3, 1.7, .012, .5]);
  }
  const floorSeams = repeatedBlocks(group, alloy, sideSeams);
  floorSeams.name = 'floor-side-seams';
  repeatedBlocks(group, alloy, aisleSeams);
  repeatedBlocks(group, graphite, deckPlates, true);

  // Dashboard sits below sight line from all three forward-facing viewpoints.
  const dash = new THREE.Group(); group.add(dash);
  block(dash, dark, 0, .67, -2.52, 3.75, .42, .93, true);
  const dashTop = block(dash, graphite, 0, .89, -2.49, 3.79, .11, .97, true);
  dashTop.name = 'dashboard-top';
  dashTop.userData.support = 'main';
  dashTop.rotation.x = -.09;
  block(dash, slate, 0, .69, -2.02, 3.64, .36, .07, true);
  block(dash, alloy, 0, .86, -2.06, 3.76, .022, .04);
  block(dash, rubber, 0, .58, -1.965, 3.58, .09, .055);
  const deskLegs = [-1.55, 0, 1.55].map(x => [x, .255, -2.54, .21, .44, .31]);
  repeatedBlocks(dash, worn, deskLegs, true);
  const deskFeet = [-1.55, 0, 1.55].map(x => [x, .065, -2.54, .36, .06, .43]);
  repeatedBlocks(dash, alloy, deskFeet, true);
  for (const side of [-1, 1]) {
    const wing = block(dash, graphite, side * 1.64, .85, -1.69, .65, .22, 1.12, true);
    wing.name = side < 0 ? 'port-wing-top' : 'starboard-wing-top';
    wing.userData.support = 'side';
    wing.rotation.y = -side * .24;
    block(dash, alloy, side * 1.67, .74, -1.08, .58, .045, .065);
    // Rail on each side keeps the dashboard visibly mechanical.
    line(dash, edge, [side * 1.72, .94, -2.88], [side * 1.82, .94, -1.2], .013);
  }
  // Side consoles fill the pilot's near field. Their controls remain below eye height.
  const consoleGrooves = [], consoleKeys = [], consoleLips = [], consoleFeet = [];
  const consoleButtons = [];
  for (const side of [-1, 1]) {
    block(group, dark, side * 1.45, .48, -.64, .76, .77, 1.68, true);
    block(group, worn, side * 1.45, .86, -.64, .8, .12, 1.71, true);
    const consoleTop = block(group, graphite, side * 1.44, .955, -.64, .72, .08, 1.59, true);
    consoleTop.name = side < 0 ? 'port-console-top' : 'starboard-console-top';
    consoleTop.userData.support = 'side-console';
    block(group, alloy, side * 1.06, .93, -.64, .025, .06, 1.68);
    block(group, rubber, side * 1.41, .1, -.63, .62, .11, 1.56, true);
    for (const z of [-1.36, -1.08, -.8, -.52, -.24, .04]) {
      consoleGrooves.push([side * 1.46, .998, z, .54, .007, .012]);
      consoleKeys.push([side * 1.24, 1.005, z + .07, .11, .025, .075]);
      consoleButtons.push([side * 1.62, 1.006, z + .07]);
    }
    consoleLips.push([side * 1.08, 1.02, -.64, .055, .055, 1.55]);
    for (const x of [1.2, 1.7]) for (const z of [-1.2, -.08]) consoleFeet.push([side * x, .09, z, .14, .12, .16]);
    // Housing, guarded emergency lever, and cable loom at rear of each bank.
    block(group, slate, side * 1.62, 1.1, -.01, .43, .29, .27, true);
    block(group, amber, side * 1.62, 1.26, -.01, .27, .032, .14, true);
    beam(group, edge, [side * 1.54, 1.06, -.04], [side * 1.54, 1.3, -.04], .014);
    beam(group, edge, [side * 1.7, 1.06, -.04], [side * 1.7, 1.3, -.04], .014);
    for (let i = 0; i < 3; i++) {
      const x = side * (2.01 - i * .035);
      line(group, rubber, [x, .62, -1.42], [x, .62, .15], .013);
    }
  }
  repeatedBlocks(group, dark, consoleGrooves);
  repeatedBlocks(group, bone, consoleKeys, true);
  repeatedBlocks(group, alloy, consoleLips);
  repeatedBlocks(group, alloy, consoleFeet, true);
  repeatedBlocks(group, alloy, [-1, 1].flatMap(side => [-1.1, -.15].map(z => [side * 2, .62, z, .21, .065, .045])), true);
  const consoleButton = new THREE.InstancedMesh(keep(new THREE.CylinderGeometry(.029, .031, .025, 10)), green, consoleButtons.length);
  const control = new THREE.Object3D();
  consoleButtons.forEach(([x, y, z], i) => { control.position.set(x, y, z); control.updateMatrix(); consoleButton.setMatrixAt(i, control.matrix); });
  consoleButton.instanceMatrix.needsUpdate = true;
  group.add(consoleButton);

  const textures = [];
  const displays = [];
  function screen(x, y, z, width, height, draw) {
    const housing = new THREE.Group();
    const instrument = width > .7 ? 'main' : 'side';
    housing.name = `${x < 0 ? 'port' : 'starboard'}-${instrument}-instrument`;
    housing.userData.instrument = instrument;
    housing.position.set(x, y, z);
    housing.rotation.x = -1.35;
    dash.add(housing);
    block(housing, dark, 0, 0, -.023, width + .18, height + .17, .105, true);
    block(housing, worn, 0, 0, .035, width + .13, height + .12, .028, true);
    block(housing, glass, 0, 0, .061, width + .026, height + .026, .025, true);
    const canvas = document.createElement('canvas');
    canvas.width = 512; canvas.height = 256;
    const context = canvas.getContext('2d');
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = THREE.LinearFilter;
    textures.push(texture);
    const material = new THREE.MeshBasicMaterial({ map: texture, toneMapped: false });
    materials.add(material);
    const mesh = new THREE.Mesh(keep(new THREE.PlaneGeometry(width, height)), material);
    mesh.name = `${housing.name}-display`;
    mesh.userData.role = 'instrument-display';
    mesh.userData.instrument = instrument;
    mesh.position.z = .074;
    housing.add(mesh);
    const screw = new THREE.InstancedMesh(keep(new THREE.CylinderGeometry(.009, .009, .008, 8)), alloy, 4);
    const point = new THREE.Object3D();
    for (let i = 0; i < 4; i++) {
      point.position.set((i & 1 ? 1 : -1) * (width * .5 + .055), (i & 2 ? 1 : -1) * (height * .5 + .047), width > .7 ? .0305 : .031);
      point.rotation.x = Math.PI / 2;
      point.updateMatrix(); screw.setMatrixAt(i, point.matrix);
    }
    screw.instanceMatrix.needsUpdate = true; screw.name = 'instrument-screws'; housing.add(screw);
    const bezelButtons = new THREE.InstancedMesh(keep(new THREE.CylinderGeometry(.014, .014, .011, 8)), rubber, 2);
    for (let i = 0; i < 2; i++) {
      point.position.set((i ? 1 : -1) * width * .31, -height * .5 - .041, .053);
      point.rotation.x = Math.PI / 2;
      point.updateMatrix(); bezelButtons.setMatrixAt(i, point.matrix);
    }
    bezelButtons.instanceMatrix.needsUpdate = true; bezelButtons.name = 'instrument-buttons'; housing.add(bezelButtons);
    displays.push({ context, texture, draw });
    return housing;
  }
  function baseDisplay(ctx, heading) {
    ctx.fillStyle = '#06120f'; ctx.fillRect(0, 0, 512, 256);
    ctx.fillStyle = '#7f9f8f'; ctx.font = '17px monospace'; ctx.fillText(heading, 24, 31);
    ctx.strokeStyle = '#25443b'; ctx.lineWidth = 2;
    ctx.strokeRect(11, 11, 490, 234);
    ctx.beginPath(); ctx.moveTo(20, 49); ctx.lineTo(492, 49); ctx.stroke();
    for (let y = 58; y < 245; y += 5) { ctx.fillStyle = 'rgba(17,42,31,.13)'; ctx.fillRect(12, y, 488, 1); }
  }
  const fmt = (value, digits, fallback = '---') => Number.isFinite(value) ? value.toFixed(digits) : fallback;
  let traceSource = null, traceData = null;
  function flightTrace(rows) {
    if (rows === traceSource) return traceData;
    traceSource = rows; traceData = null;
    if (!Array.isArray(rows) || rows.length < 2) return null;
    const valid = rows.filter(row => Array.isArray(row) && Number.isFinite(row[0]) && Number.isFinite(row[1]));
    if (valid.length < 2 || valid.at(-1)[0] <= valid[0][0]) return null;
    let radiusMin = Infinity, radiusMax = -Infinity;
    for (const row of valid) { radiusMin = Math.min(radiusMin, row[1]); radiusMax = Math.max(radiusMax, row[1]); }
    const step = Math.max(1, Math.ceil(valid.length / 180));
    const points = valid.filter((_, i) => i % step === 0 || i === valid.length - 1).map(row => [row[0], row[1]]);
    traceData = { points, timeMin: valid[0][0], timeMax: valid.at(-1)[0], radiusMin, radiusMax };
    return traceData;
  }
  screen(-.66, .98, -2.48, 1.02, .46, (ctx, frame) => {
    baseDisplay(ctx, 'FIELD / TRAJECTORY');
    ctx.fillStyle = '#b7d7ba'; ctx.font = '27px monospace';
    ctx.fillText(`r ${fmt(frame.radius, 3)} M`, 25, 105);
    ctx.fillStyle = '#78ab95'; ctx.font = '19px monospace';
    ctx.fillText(`τ ${fmt(frame.time, 1)} M`, 25, 149);
    ctx.fillText(`E ${fmt(frame.energy, 4)}`, 25, 190);
    const trace = flightTrace(frame.trajectory);
    ctx.strokeStyle = '#315545'; ctx.lineWidth = 1;
    ctx.strokeRect(264, 66, 217, 154);
    ctx.beginPath(); ctx.moveTo(264, 143); ctx.lineTo(481, 143); ctx.stroke();
    ctx.fillStyle = '#7d9d89'; ctx.font = '12px monospace';
    ctx.fillText('RECORDED r(τ)', 270, 237);
    if (!trace) { ctx.fillText('NO FLIGHT TRACE', 281, 153); return; }
    const { points, timeMin, timeMax, radiusMin, radiusMax } = trace;
    const radiusSpan = Math.max(.001, radiusMax - radiusMin);
    const plot = (time, radius) => [270 + 205 * (time - timeMin) / (timeMax - timeMin),
      209 - 132 * (radius - radiusMin) / radiusSpan];
    ctx.strokeStyle = '#78ab95'; ctx.lineWidth = 2; ctx.beginPath();
    points.forEach(([time, radius], i) => {
      const [x, y] = plot(time, radius);
      if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
    });
    ctx.stroke();
    if (Number.isFinite(frame.time) && Number.isFinite(frame.radius)) {
      const [x, y] = plot(Math.max(timeMin, Math.min(timeMax, frame.time)), frame.radius);
      ctx.fillStyle = '#d6a36b'; ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
    }
  });
  screen(.66, .98, -2.48, 1.02, .46, (ctx, frame) => {
    baseDisplay(ctx, 'PROPULSION / CONTROL');
    const burn = frame.burn || [0, 0];
    const fuel = Number.isFinite(frame.fuel) ? Math.max(0, Math.min(1, frame.fuel)) : 1;
    ctx.fillStyle = '#b7d7ba'; ctx.font = '25px monospace';
    ctx.fillText(`FUEL ${(fuel * 100).toFixed(1)}%`, 24, 97);
    ctx.fillStyle = '#244234'; ctx.fillRect(25, 111, 450, 15);
    ctx.fillStyle = fuel < .18 ? '#d99963' : '#80bfa1'; ctx.fillRect(25, 111, 450 * fuel, 15);
    ctx.fillStyle = '#87ae9b'; ctx.font = '20px monospace';
    ctx.fillText(`R ${fmt(burn[0], 2)}  T ${fmt(burn[1], 2)}`, 24, 165);
    ctx.fillText(String(frame.controller || 'CHECKED').toUpperCase().slice(0, 25), 24, 209);
  });
  screen(-1.61, .94, -1.72, .5, .29, (ctx, frame) => {
    baseDisplay(ctx, 'NAV / OBS');
    ctx.fillStyle = '#aacbb7'; ctx.font = '26px monospace';
    ctx.fillText(`${fmt(frame.radius, 2)} M`, 24, 111);
    ctx.font = '17px monospace'; ctx.fillText('SCHWARZSCHILD', 24, 163);
    ctx.fillText('EQUATORIAL', 24, 192);
  });
  screen(1.61, .94, -1.72, .5, .29, (ctx, frame) => {
    baseDisplay(ctx, 'BURN / AXES');
    const burn = frame.burn || [0, 0];
    const bx = Math.max(-1, Math.min(1, burn[1] || 0)), by = Math.max(-1, Math.min(1, burn[0] || 0));
    ctx.strokeStyle = '#4b785e'; ctx.lineWidth = 2; ctx.beginPath();
    ctx.moveTo(255, 62); ctx.lineTo(255, 223); ctx.moveTo(166, 141); ctx.lineTo(344, 141); ctx.stroke();
    ctx.fillStyle = '#e0a25e'; ctx.beginPath(); ctx.arc(255 + bx * 70, 141 - by * 64, 12, 0, 7); ctx.fill();
  });

  // Shallow fixed labels, controls, edge guards and fasteners around screens.
  function label(text, x, y, z, w, h, parent = dash) {
    const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#bbb8a9'; ctx.font = 'bold 26px monospace';
    const size = Math.min(26, Math.floor(26 * 232 / ctx.measureText(text).width));
    ctx.font = `bold ${Math.max(14, size)}px monospace`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, 128, 32, 232);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; textures.push(texture);
    const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false }); materials.add(material);
    const mesh = new THREE.Mesh(keep(new THREE.PlaneGeometry(w, h)), material);
    mesh.position.set(x, y, z); parent.add(mesh);
    return mesh;
  }
  function printedSurface(width, height, draw, x, y, z, sx, sy, parent = group) {
    const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
    draw(canvas.getContext('2d'));
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; textures.push(texture);
    const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false }); materials.add(material);
    const mesh = new THREE.Mesh(keep(new THREE.PlaneGeometry(sx, sy)), material);
    mesh.position.set(x, y, z); parent.add(mesh);
    return mesh;
  }
  printedSurface(1024, 96, ctx => {
    ctx.fillStyle = '#8c9690'; ctx.font = '17px monospace';
    ctx.fillText('01  FIELD / TELEMETRY', 45, 59);
    ctx.fillText('02  PROPULSION / CONTROL', 605, 59);
    ctx.fillStyle = '#b98449';
    for (let x = 20; x < 1024; x += 15) ctx.fillRect(x, 7, 7, 4);
    ctx.fillRect(493, 17, 4, 67); ctx.fillRect(523, 17, 4, 67);
    ctx.fillStyle = '#657771'; ctx.font = '11px monospace';
    ctx.fillText('RV-07 / DISPLAY BUS', 449, 89);
  }, 0, .69, -1.976, 3.46, .3, dash);
  label('RESEARCH VEHICLE 07', 0, 2.712, -2.875, 1.4, .105, group);
  for (const side of [-1, 1]) {
    label(side < 0 ? 'PORT BUS / 01' : 'STARBOARD BUS / 02', side * 1.45, .59, .207, .56, .1, group);
    const plate = label('CAUTION / MANUAL RELEASE', side * 1.62, 1.31, -.01, .34, .07, group);
    plate.rotation.x = -Math.PI / 2;
    const markings = printedSurface(256, 512, ctx => {
      ctx.strokeStyle = '#68756d'; ctx.fillStyle = '#a4aaa0';
      ctx.font = '14px monospace'; ctx.textAlign = 'center';
      for (let i = 0; i < 6; i++) {
        const y = 27 + i * 90;
        ctx.strokeRect(14, y, 228, 59);
        ctx.fillText(`${String(i + 1).padStart(2, '0')} / ${['RCS ARM', 'POWER', 'ATTITUDE', 'COAST', 'RETURN', 'ISOLATE'][i]}`, 128, y + 34);
        ctx.fillStyle = '#976a3c'; ctx.fillRect(19, y + 5, 17, 3);
        ctx.fillStyle = '#a4aaa0';
      }
    }, side * 1.44, 1.001, -.64, .7, 1.55, group);
    markings.rotation.x = -Math.PI / 2;
  }

  // Instanced small hardware keeps the detailed shell inexpensive to render.
  const boltGeometry = keep(new THREE.CylinderGeometry(.016, .016, .012, 8));
  const boltPositions = [];
  for (const z of [-2.7, -2, -1.3, -.6, .1, .8, 1.5, 2.2, 2.9]) {
    for (const x of [-1.92, -1.02, 1.02, 1.92]) boltPositions.push([x, Math.abs(x) > 1.5 ? .067 : .069, z]);
  }
  for (const z of [-2.35, -1.11, .13, 1.37, 2.61]) {
    for (const side of [-1, 1]) for (const y of [.55, 1.09, 1.57, 2.1]) boltPositions.push([side * 2.006, y, z]);
  }
  const bolt = new THREE.InstancedMesh(boltGeometry, alloy, boltPositions.length);
  const dummy = new THREE.Object3D();
  boltPositions.forEach(([x, y, z], i) => {
    dummy.position.set(x, y, z);
    dummy.rotation.set(0, 0, y > .1 ? Math.PI / 2 : 0);
    dummy.updateMatrix(); bolt.setMatrixAt(i, dummy.matrix);
  });
  bolt.instanceMatrix.needsUpdate = true; bolt.name = 'cabin-bolts'; group.add(bolt);

  const toggles = new THREE.InstancedMesh(keep(new THREE.CylinderGeometry(.012, .016, .075, 8)), edge, 32);
  for (let i = 0; i < 32; i++) {
    const side = i < 16 ? -1 : 1;
    const control = i % 16;
    dummy.position.set(side * (1.33 + (control % 2) * .13), 1.035, -1.31 + Math.floor(control / 2) * .19);
    dummy.rotation.set(-.4, 0, (i % 4 === 0 ? -.23 : .16));
    dummy.updateMatrix(); toggles.setMatrixAt(i, dummy.matrix);
  }
  toggles.instanceMatrix.needsUpdate = true; toggles.name = 'console-toggles'; group.add(toggles);
  const knobPositions = [-1, 1].flatMap(side => [-1.2, -.82].map(z => [side * 1.7, z]));
  const rings = new THREE.InstancedMesh(torus, alloy, knobPositions.length);
  const knobs = new THREE.InstancedMesh(rod, dark, knobPositions.length);
  const knobTicks = [];
  const knobObject = new THREE.Object3D();
  knobPositions.forEach(([x, z], i) => {
    knobObject.position.set(x, 1.000, z); knobObject.rotation.set(-Math.PI / 2, 0, 0); knobObject.scale.set(.05, .05, .05);
    knobObject.updateMatrix(); rings.setMatrixAt(i, knobObject.matrix);
    knobObject.position.set(x, 1.008, z); knobObject.rotation.set(0, 0, 0); knobObject.scale.set(.037, .027, .037);
    knobObject.updateMatrix(); knobs.setMatrixAt(i, knobObject.matrix);
    knobTicks.push([x + .012, 1.022, z, .024, .003, .003]);
  });
  rings.instanceMatrix.needsUpdate = knobs.instanceMatrix.needsUpdate = true;
  rings.name = 'console-knob-rings'; knobs.name = 'console-knobs';
  group.add(rings, knobs);
  const ticks = repeatedBlocks(group, bone, knobTicks);
  ticks.name = 'console-knob-ticks';
  for (const side of [-1, 1]) {
    block(dash, amber, side * 1.79, .955, -2.48, .05, .025, .05, true);
    block(dash, green, side * 1.7, .955, -2.48, .05, .025, .05, true);
    // Guarded physical handles at edge of the pilot's reach.
    block(group, graphite, side * 1.7, .76, -.54, .39, .17, .5, true);
    beam(group, edge, [side * 1.7, .82, -.52], [side * 1.7, 1.11, -.52], .028);
    block(group, rubber, side * 1.7, 1.11, -.52, .21, .075, .11, true);
  }

  // A pair of occupied-scale seats sit outside the center aisle and camera path.
  function seat(side) {
    const chair = new THREE.Group(); chair.position.set(side * 1.14, 0, 1.14); group.add(chair);
    block(chair, dark, 0, .4, .13, .9, .17, .91, true);
    block(chair, cushion, 0, .52, .09, .76, .13, .73, true);
    const back = block(chair, dark, 0, 1.12, .48, .82, 1.22, .17, true);
    back.rotation.x = -.09;
    const pad = block(chair, cushion, 0, 1.1, .354, .68, .98, .12, true);
    pad.rotation.x = -.09;
    block(chair, rubber, 0, 1.73, .47, .56, .25, .23, true);
    block(chair, cushion, 0, 1.75, .32, .51, .2, .11, true);
    for (const s of [-1, 1]) {
      block(chair, alloy, s * .4, .79, .1, .065, .55, .69, true);
      block(chair, rubber, s * .4, .93, -.12, .13, .1, .47, true);
      beam(chair, alloy, [s * .29, .15, .22], [s * .35, .42, .22], .035);
      const strap = block(chair, webbing, s * .16, 1.15, .265, .085, .94, .023);
      strap.rotation.set(-.09, 0, s * .23);
      block(chair, alloy, s * .2, .78, .295, .16, .09, .045, true);
    }
    block(chair, alloy, 0, .74, .15, .22, .095, .055, true);
    block(chair, dark, 0, .2, .23, .27, .31, .36);
    for (const s of [-1, 1]) block(chair, alloy, s * .28, .08, .13, .08, .11, .85, true);
  }
  seat(-1); seat(1);

  // Rear hatch, gasket, grab bars, and equipment bays reward turning around.
  block(group, alloy, 0, 1.35, 3.23, 1.35, 2.48, .1, true);
  block(group, dark, 0, 1.35, 3.135, 1.16, 2.31, .06, true);
  block(group, graphite, 0, 1.35, 3.07, 1.07, 2.21, .055, true);
  block(group, alloy, 0, 1.36, 3.032, .05, 2.1, .025);
  const bayDoors = [], bayTrim = [];
  for (const side of [-1, 1]) {
    block(group, bone, side * 1.61, 1.55, 3.18, .74, 2.35, .12, true);
    for (let y = .58; y < 2.59; y += .39) {
      bayDoors.push([side * 1.61, y, 3.08, .61, .27, .05]);
      bayTrim.push([side * 1.61, y + .09, 3.045, .55, .012, .016]);
    }
    beam(group, edge, [side * .37, 1.09, 2.991], [side * .37, 1.66, 2.991], .029);
    beam(group, alloy, [side * .37, 1.09, 2.991], [side * .25, 1.09, 2.991], .021);
    beam(group, alloy, [side * .37, 1.66, 2.991], [side * .25, 1.66, 2.991], .021);
  }
  repeatedBlocks(group, graphite, bayDoors, true);
  repeatedBlocks(group, alloy, bayTrim);
  block(group, dark, 0, 2.65, 3.16, 1.44, .18, .22, true);
  const hatchLabel = label('PRESSURE HATCH / 07', 0, 2.65, 3.042, .93, .11, group);
  hatchLabel.rotation.y = Math.PI;
  repeatedBlocks(group, alloy, [-1, 1].flatMap(side => [1.09, 1.66].map(y => [side * .25, y, 3.03, .04, .04, .1])));
  // Cable bundles run along the shell instead of crossing the walk path.
  const cableClamps = [];
  for (const side of [-1, 1]) for (let i = 0; i < 3; i++) {
    const x = side * (2.01 - i * .055), y = .26 + i * .062;
    line(group, rubber, [x, y, -2.8], [x, y, 2.95], .018);
    for (const z of [-2.2, -.8, .6, 2]) cableClamps.push([x, y, z, .105, .058, .065]);
  }
  repeatedBlocks(group, alloy, cableClamps, true);
  const emergencyRed = mat(0x793a2e, .67, .16);
  for (const side of [-1, 1]) {
    block(group, dark, side * 1.89, .63, 2.06, .37, .79, .22, true);
    const canister = new THREE.Mesh(keep(new THREE.CylinderGeometry(.105, .105, .57, 14)), side < 0 ? green : emergencyRed);
    canister.position.set(side * 1.89, .63, 1.91);
    group.add(canister);
    block(group, alloy, side * 1.89, .86, 1.91, .25, .035, .24, true);
    block(group, rubber, side * 1.89, .34, 1.91, .27, .038, .24, true);
    block(group, dark, side * 1.89, 1.09, 2.06, .37, .16, .11, true);
    const safety = label(side < 0 ? 'O2 / RESERVE' : 'FIRE / MANUAL', side * 1.89, 1.09, 1.997, .31, .08, group);
    safety.rotation.y = Math.PI;
  }

  let lastDisplayKey = '', lastTrajectory = null;
  let lastDisplayAt = 0;
  function update(frame = {}) {
    const now = performance.now();
    if (frame.playing && now - lastDisplayAt < 100) return;
    const burn = frame.burn || [0, 0];
    const key = [frame.radius?.toFixed(2), frame.time?.toFixed(1), frame.energy?.toFixed(3), frame.fuel?.toFixed(2), burn[0]?.toFixed(2), burn[1]?.toFixed(2), frame.controller].join('|');
    if (key === lastDisplayKey && frame.trajectory === lastTrajectory) return;
    lastDisplayKey = key;
    lastTrajectory = frame.trajectory;
    lastDisplayAt = now;
    for (const display of displays) { display.draw(display.context, frame); display.texture.needsUpdate = true; }
  }
  update({ radius: 30, time: 0, energy: 1, fuel: 1, burn: [0, 0], controller: 'CHECKED' });
  function dispose() {
    owned.forEach(geometry => geometry.dispose());
    materials.forEach(material => material.dispose());
    textures.forEach(texture => texture.dispose());
    surfaceTextures.forEach(texture => texture.dispose());
  }
  const colliders = [
    { min: [-1.9, .43, -3.05], max: [1.9, 1.14, -2.0] },
    { min: [-1.86, 0, -1.5], max: [-1.04, 1.34, .2] },
    { min: [1.04, 0, -1.5], max: [1.86, 1.34, .2] },
    { min: [-1.66, 0, .76], max: [-.62, 1.9, 1.76] },
    { min: [.62, 0, .76], max: [1.66, 1.9, 1.76] }
  ];
  return { group, colliders, update, dispose };
}
