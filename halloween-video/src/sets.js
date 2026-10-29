// Escenarios del corto. Cada uno devuelve {scene, ...referencias animables}.
import * as THREE from 'three';
import { VoxelGrid, B } from './voxel.js';
import { rng } from './textures.js';
import { Fire, Particles, makeSky, makeMoon, makeClouds, makeFogBank, makeShaft, makeFarGround, makeTreeRing } from './fx.js';
import { blockTex } from './textures.js';
import { makeJack, makeVillager, makeZombie, makeLantern, makeBat, makeSkeletonRig } from './models.js';
import { Army } from './army.js';

// ---------------------------------------------------------------------------
// utilidades
// ---------------------------------------------------------------------------
function noise2(seed) {
  const r = rng(seed);
  const perm = Array.from({ length: 512 }, () => r());
  const h = (x, z) => perm[((x * 73856093) ^ (z * 19349663)) & 511];
  return (x, z) => {
    const xi = Math.floor(x), zi = Math.floor(z), fx = x - xi, fz = z - zi;
    const sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
    const a = h(xi, zi), b = h(xi + 1, zi), c = h(xi, zi + 1), d = h(xi + 1, zi + 1);
    return a + (b - a) * sx + (c - a) * sz + (a - b - c + d) * sx * sz;
  };
}

function fbm(n) {
  return (x, z) => n(x, z) * 0.6 + n(x * 2.1 + 17, z * 2.1 - 9) * 0.3 + n(x * 4.3 - 5, z * 4.3 + 3) * 0.1;
}

function addLights(scene, o) {
  const hemi = new THREE.HemisphereLight(o.sky, o.ground, o.hemi);
  scene.add(hemi);
  let dir = null;
  if (o.dir) {
    dir = new THREE.DirectionalLight(o.dir, o.dirI);
    dir.castShadow = !!o.shadow;
    dir.shadow.mapSize.set(2048, 2048);
    dir.shadow.bias = -0.0006;
    dir.shadow.normalBias = 0.04;
    const c = dir.shadow.camera;
    c.left = c.bottom = -40;
    c.right = c.top = 40;
    c.near = 1;
    c.far = 300;
    scene.add(dir, dir.target);
  }
  return { hemi, dir };
}

const SKULL = [
  '....XXXXXXXXX....',
  '..XXXXXXXXXXXXX..',
  '.XXXXXXXXXXXXXXX.',
  'XXXXXXXXXXXXXXXXX',
  'XXXXXXXXXXXXXXXXX',
  'XXoooooXXXoooooXX',
  'XXoooooXXXoooooXX',
  'XXoooooXXXoooooXX',
  'XXXoooXXXXXoooXXX',
  'XXXXXXXXnXXXXXXXX',
  '.XXXXXXnnnXXXXXX.',
  '..XXXXXXXXXXXXX..',
  '..XtmtmtmtmtmtX..',
  '..XmmmmmmmmmmmX..',
  '..XmmmmmmmmmmmX..',
  '..XtmtmtmtmtmtX..',
  '...XXXXXXXXXXX...',
];

function autumnTree(g, x, y, z, r, kind = 'leaves_orange') {
  const h = 4 + Math.floor(r() * 3);
  for (let i = 0; i < h; i++) g.set(x, y + i, z, 'oak_log');
  for (let dy = -2; dy <= 1; dy++) {
    const rad = dy === 1 ? 1 : 2;
    for (let dx = -rad; dx <= rad; dx++)
      for (let dz = -rad; dz <= rad; dz++) {
        if (Math.abs(dx) === rad && Math.abs(dz) === rad && r() < 0.6) continue;
        if (dx === 0 && dz === 0 && dy < 0) continue;
        g.set(x + dx, y + h + dy, z + dz, r() < 0.3 ? 'leaves_red' : kind);
      }
  }
}

function deadTree(g, x, y, z, r, tall = 8, leaves = 0) {
  const h = tall + Math.floor(r() * 4);
  const log = 'dark_log';
  for (let i = 0; i < h; i++) g.set(x, y + i, z, log);
  if (r() < 0.5) g.set(x + 1, y, z, log);
  if (r() < 0.5) g.set(x, y, z - 1, log);
  const nb = 2 + Math.floor(r() * 3);
  const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  for (let b = 0; b < nb; b++) {
    const [dx, dz] = dirs[Math.floor(r() * 4)];
    let bx = x, bz = z, by = y + h - 2 - Math.floor(r() * (h / 2));
    const len = 2 + Math.floor(r() * 3);
    for (let k = 0; k < len; k++) {
      bx += dx; bz += dz;
      if (k % 2) by++;
      g.set(bx, by, bz, log);
    }
    if (leaves && r() < leaves) for (let a = -1; a <= 1; a++) for (let c = -1; c <= 1; c++) if (r() < 0.7) g.set(bx + a, by + 1, bz + c, 'leaves_dark');
    if (r() < 0.25) g.set(bx + dx, by - 1, bz + dz, 'cobweb');
  }
  return y + h;
}

function makeBats(n, seed) {
  const r = rng(seed);
  const bats = [];
  for (let i = 0; i < n; i++) {
    const b = makeBat();
    b.userData.p = { cx: (r() - 0.5) * 30, cy: 10 + r() * 14, cz: (r() - 0.5) * 30, rad: 4 + r() * 8, sp: 0.4 + r() * 0.6, ph: r() * 10 };
    bats.push(b);
  }
  const group = new THREE.Group();
  group.add(...bats);
  group.userData.update = (t, off = [0, 0, 0]) => {
    for (const b of bats) {
      const p = b.userData.p, a = t * p.sp + p.ph;
      b.position.set(off[0] + p.cx + Math.cos(a) * p.rad, off[1] + p.cy + Math.sin(a * 2.3) * 1.2, off[2] + p.cz + Math.sin(a) * p.rad);
      b.rotation.y = -a;
      b.userData.flap(t + p.ph);
    }
  };
  return group;
}

// ---------------------------------------------------------------------------
// PUEBLO
// ---------------------------------------------------------------------------
export function buildVillage() {
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x2a2045, 0.014);
  const r = rng(101);
  const n = fbm(noise2(7));
  const g = new VoxelGrid(-64, -5, -104, 128, 34, 150);
  const hAt = (x, z) => {
    const out = Math.max(0, Math.abs(x) - 24) / 12;
    return -1 + Math.floor(n(x / 16, z / 16) * 5 * Math.min(1, out));
  };
  for (let z = -104; z < 46; z++)
    for (let x = -64; x < 64; x++) {
      const h = hAt(x, z);
      g.fill(x, -5, z, x, h - 1, z, 'dirt');
      g.set(x, h, z, 'grass');
      if (h === -1 && Math.abs(x) > 3 && r() < 0.06) g.set(x, 0, z, r() < 0.5 ? 'tall_grass' : 'dead_bush');
    }
  // camino y plaza
  for (let z = -104; z < 34; z++) for (let x = -1; x <= 1; x++) g.set(x, -1, z, r() < 0.15 ? 'gravel' : 'path');
  for (let z = -10; z <= 10; z++) for (let x = -10; x <= 10; x++) if (x * x + z * z < 85) { g.set(x, -1, z, r() < 0.3 ? 'cobble' : 'path'); g.set(x, 0, z, 0); }
  // hoguera
  for (let a = 0; a < 16; a++) g.set(Math.round(Math.cos(a / 16 * Math.PI * 2) * 2.4) - 0.5, 0, Math.round(Math.sin(a / 16 * Math.PI * 2) * 2.4) - 0.5, 'cobble');
  g.fill(-1, 0, -1, 0, 0, 0, 'oak_log');

  // casas
  const houses = [
    [5, -48, 7, 8, 5, '-x'], [-11, -48, 7, 8, 5, '+x'], [5, -32, 8, 8, 6, '-x'], [-12, -34, 8, 9, 5, '+x'],
    [7, -18, 7, 8, 5, '-x'], [-13, -18, 7, 8, 6, '+x'], [13, 3, 7, 8, 5, '-x'], [-19, 2, 7, 8, 5, '+x'], [-4, 14, 9, 7, 6, '-z'],
  ];
  const doors = [];
  for (const [x0, z0, w, d, h, face] of houses) {
    const x1 = x0 + w - 1, z1 = z0 + d - 1;
    g.fill(x0, -1, z0, x1, -1, z1, 'cobble');
    g.fill(x0, 0, z0, x1, h - 1, z1, 'oak_planks');
    for (const [cx, cz] of [[x0, z0], [x1, z0], [x0, z1], [x1, z1]]) g.fill(cx, 0, cz, cx, h - 1, cz, 'oak_log');
    g.fill(x0, 0, z0, x1, 0, z1, 'cobble');
    // ventanas
    for (let y = 2; y <= 2; y++) {
      for (let x = x0 + 2; x < x1 - 1; x += 3) { g.set(x, y, z0, 'window'); g.set(x, y, z1, 'window'); }
      for (let z = z0 + 2; z < z1 - 1; z += 3) { g.set(x0, y, z, 'window'); g.set(x1, y, z, 'window'); }
    }
    // puerta
    let door;
    if (face === '-x') { const z = z0 + Math.floor(d / 2); g.set(x0, 0, z, 'door'); g.set(x0, 1, z, 'door'); door = [x0 - 0.5, z + 0.5, -Math.PI / 2]; }
    if (face === '+x') { const z = z0 + Math.floor(d / 2); g.set(x1, 0, z, 'door'); g.set(x1, 1, z, 'door'); door = [x1 + 1.5, z + 0.5, Math.PI / 2]; }
    if (face === '-z') { const x = x0 + Math.floor(w / 2); g.set(x, 0, z0, 'door'); g.set(x, 1, z0, 'door'); door = [x + 0.5, z0 - 0.5, Math.PI]; }
    doors.push(door);
    // techo escalonado
    for (let k = 0; k < 5; k++) {
      const ax = x0 - 1 + k, bx = x1 + 1 - k, az = z0 - 1 + k, bz = z1 + 1 - k;
      if (ax > bx || az > bz) break;
      for (let x = ax; x <= bx; x++) for (let z = az; z <= bz; z++) if (x === ax || x === bx || z === az || z === bz || k === 4) g.set(x, h + k, z, 'spruce_planks');
      g.fill(ax + 1, h + k, az + 1, bx - 1, h + k, bz - 1, 'spruce_planks');
    }
  }
  // fardos de paja (escondite de la nina)
  g.fill(4, 0, -7, 5, 0, -6, 'hay');
  g.set(4, 1, -7, 'hay');
  g.fill(-7, 0, 5, -6, 0, 5, 'hay');
  // arboles de otono
  const trees = [[20, -52], [-22, -50], [24, -30], [-26, -28], [22, 20], [-24, 18], [30, -8], [-31, -12], [16, 30], [-12, 32], [34, 6], [-36, 0], [28, -64], [-30, -66]];
  for (const [x, z] of trees) autumnTree(g, x, hAt(x, z) + 1, z, r);
  // calabazas por el campo
  for (let i = 0; i < 70; i++) {
    const x = Math.floor((r() - 0.5) * 110), z = Math.floor(-100 + r() * 140);
    if (Math.abs(x) < 22 && z > -60) continue;
    g.set(x, hAt(x, z) + 1, z, 'pumpkin');
  }
  // linde del bosque muerto
  for (let z = -102; z < -64; z += 5)
    for (let x = -60; x < 60; x += 5) {
      const tx = x + Math.floor(r() * 3), tz = z + Math.floor(r() * 3);
      if (Math.abs(tx) < 5) continue;
      deadTree(g, tx, hAt(tx, tz) + 1, tz, r, 7, 0.15);
    }

  // faroles-calabaza del camino
  const jacks = [];
  for (const z of [-60, -52, -44, -36, -28, -20, -12]) {
    for (const s of [-1, 1]) {
      const x = s * 3;
      g.set(x, 0, z, 'cobble');
      const j = makeJack(1);
      j.position.set(x + 0.5, 1.5, z + 0.5);
      j.rotation.y = s < 0 ? Math.PI / 2 : -Math.PI / 2;
      scene.add(j);
      jacks.push({ mesh: j, z: z + 0.5, x: x + 0.5 });
    }
  }
  // calabazas en las puertas
  doors.forEach(([x, z, rot], i) => {
    const j = makeJack(0.8);
    const ox = Math.round(Math.sin(rot + Math.PI / 2) * 1.2);
    const oz = Math.round(Math.cos(rot + Math.PI / 2) * 1.2);
    j.position.set(x + ox, 0.4, z + oz);
    j.rotation.y = rot;
    scene.add(j);
    jacks.push({ mesh: j, z: z + oz, x: x + ox, door: true });
  });

  scene.add(g.build());
  scene.add(makeFarGround(0x8a9a80, -0.02 - 1, blockTex('grass_top')));
  scene.add(makeTreeRing(77, 75, 140, 260, 0x0a0910, [0, -1, -30]));

  // cielo, luna, nubes, niebla
  const sky = makeSky();
  scene.add(sky);
  const moon = makeMoon();
  const moonDir = new THREE.Vector3(0.1, 0.3, -1).normalize();
  moon.position.copy(moonDir.clone().multiplyScalar(600));
  moon.scale.setScalar(95);
  scene.add(moon);
  const clouds = makeClouds(5, 400, 60);
  scene.add(clouds);
  const fogEdge = makeFogBank(26, [0, 0.3, -72], [90, 2.5, 22], 0x7a80a8, 0.22, 9);
  const fogVillage = makeFogBank(16, [0, 0.2, -20], [60, 1.2, 80], 0x6a6a90, 0.08, 4);
  scene.add(fogEdge, fogVillage);

  const L = addLights(scene, { sky: 0x2a3060, ground: 0x0c0806, hemi: 0.55, dir: 0x9aaeff, dirI: 0.9, shadow: true });
  L.dir.position.copy(moonDir.clone().multiplyScalar(120));

  // hoguera y luces calidas
  const bonfire = new Fire([
    { x: 0, y: 1, z: 0, w: 2.0, h: 3.0 }, { x: 0.3, y: 1, z: 0.3, w: 1.2, h: 2.0 },
  ], { orange: true, bright: 1.1, seed: 3 });
  scene.add(bonfire.mesh);
  const bonLight = new THREE.PointLight(0xff8a3a, 70, 34, 1.6);
  bonLight.position.set(0, 3, 0);
  scene.add(bonLight);
  const sparks = new Particles(120, { center: [0, 2, 0], box: [1.5, 0.5, 1.5], vel: [0, 2.5, 0], spread: [0.6, 0.8, 0.6], life: 2.2, size: 0.07, colA: 0xffa040, bright: 3, swirl: 0.4 });
  scene.add(sparks.points);
  const roadLights = [];
  for (const z of [-56, -40, -24]) {
    const pl = new THREE.PointLight(0xff9a4a, 22, 16, 1.8);
    pl.position.set(0, 2.5, z);
    scene.add(pl);
    roadLights.push(pl);
  }
  const leaves = new Particles(160, { center: [0, 9, -30], box: [50, 14, 80], vel: [0.8, -0.9, 0.3], spread: [0.4, 0.2, 0.4], life: 12, size: 0.13, colA: 0xc8551a, colB: 0x8e2015, bright: 0.6, normal: true, swirl: 1.2 });
  scene.add(leaves.points);

  // aldeanos
  const kinds = ['farmer', 'librarian', 'cleric', 'nitwit', 'butcher', 'farmer', 'cleric', 'librarian'];
  const villagers = kinds.map((k, i) => makeVillager(k, { pumpkinHead: i % 3 === 1 }));
  villagers.forEach((v) => scene.add(v.root));
  const bats = makeBats(9, 44);
  scene.add(bats);

  return { name: 'village', scene, grid: g, sky, moon, moonDir, clouds, fogEdge, fogVillage, L, bonfire, bonLight, sparks, roadLights, jacks, villagers, doors, bats, leaves };
}

// ---------------------------------------------------------------------------
// BOSQUE MUERTO
// ---------------------------------------------------------------------------
export function buildForest() {
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x22304e, 0.032);
  const r = rng(202);
  const n = fbm(noise2(19));
  const g = new VoxelGrid(-40, -4, -74, 80, 34, 148);
  const px = (z) => Math.sin(z / 12) * 4;
  const hAt = (x, z) => -1 + Math.floor(n(x / 10, z / 10) * 2.2 * Math.min(1, Math.abs(x - px(z)) / 6));
  for (let z = -74; z < 74; z++)
    for (let x = -40; x < 40; x++) {
      const h = hAt(x, z);
      g.fill(x, -4, z, x, h - 1, z, 'dirt');
      const onPath = Math.abs(x - px(z)) < 1.6;
      g.set(x, h, z, onPath ? (r() < 0.3 ? 'gravel' : 'path') : r() < 0.55 ? 'podzol' : 'grass');
      if (!onPath && r() < 0.05) g.set(x, h + 1, z, r() < 0.5 ? 'dead_bush' : 'tall_grass');
      if (!onPath && Math.abs(x - px(z)) < 9 && r() < 0.012) g.set(x, h + 1, z, 'mushroom_glow');
      else if (!onPath && r() < 0.006) g.set(x, h + 1, z, 'mushroom_red');
    }
  const trunks = [];
  for (let z = -72; z < 72; z += 5)
    for (let x = -38; x < 38; x += 5) {
      const tx = x + Math.floor(r() * 4), tz = z + Math.floor(r() * 4);
      if (Math.abs(tx - px(tz)) < 3.5) continue;
      if (tz > 14 && tz < 48 && tx - px(tz) > 2 && tx - px(tz) < 13) continue;
      deadTree(g, tx, hAt(tx, tz) + 1, tz, r, 9, 0.35);
      trunks.push([tx + 0.5, tz + 0.5]);
    }
  scene.add(g.build());
  scene.add(makeFarGround(0x5a4a3a, -1.02, blockTex('podzol_top')));
  scene.add(makeTreeRing(31, 45, 110, 300, 0x07070c, [0, -1, 0]));
  const sky = makeSky();
  sky.userData.u.uTop.value.set(0x05081a);
  sky.userData.u.uHor.value.set(0x26345a);
  sky.userData.u.uSunCol.value.set(0x8aa0ff);
  scene.add(sky);
  const L = addLights(scene, { sky: 0x3a4a80, ground: 0x0c0a08, hemi: 1.0, dir: 0x8ea6ff, dirI: 1.7, shadow: true });
  L.dir.position.set(30, 90, -40);
  const shafts = [];
  for (let i = 0; i < 7; i++) {
    const s = makeShaft(26, 0.6, 2.6, 0x8aa8ff, 0.12);
    const z = 30 - i * 11, x = px(z) + (r() - 0.5) * 8;
    s.position.set(x + 4, 22, z - 5);
    s.rotation.set(-0.35, 0, -0.25);
    scene.add(s);
    shafts.push(s);
  }
  const fireflies = new Particles(220, { center: [0, 2.5, 0], box: [40, 4, 140], vel: [0, 0.05, 0], spread: [0.25, 0.15, 0.25], life: 6, size: 0.06, colA: 0xd8ff6a, bright: 4, twinkle: 1, swirl: 0.6 });
  scene.add(fireflies.points);
  const fog = makeFogBank(30, [0, 0.3, 0], [60, 1.5, 140], 0x6878a0, 0.14, 13);
  scene.add(fog);
  const mushLight = new THREE.PointLight(0x40e0d0, 6, 10, 2);
  scene.add(mushLight);
  return { name: 'forest', scene, grid: g, px, hAt, sky, L, shafts, fireflies, fog, trunks, mushLight };
}

// ---------------------------------------------------------------------------
// PANTANO
// ---------------------------------------------------------------------------
export function buildSwamp() {
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x16201a, 0.03);
  const r = rng(303);
  const n = fbm(noise2(23));
  const g = new VoxelGrid(-44, -6, -54, 88, 30, 108);
  for (let z = -54; z < 54; z++)
    for (let x = -44; x < 44; x++) {
      g.fill(x, -6, z, x, -3, z, 'mud');
      const v = n(x / 9, z / 9);
      if (v > 0.56 && Math.abs(x) > 2) {
        g.fill(x, -2, z, x, -1, z, 'dirt');
        g.set(x, -1, z, r() < 0.5 ? 'grass' : 'podzol');
        if (r() < 0.12) g.set(x, 0, z, 'tall_grass');
      } else if (v > 0.45) g.set(x, -2, z, 'mud');
    }
  // pasarela de tablones
  for (let z = -52; z < 52; z++) {
    g.fill(-1, -1, z, 0, -1, z, 'spruce_planks');
    if (z % 4 === 0) { g.fill(-2, -3, z, -2, -1, z, 'oak_log'); g.fill(1, -3, z, 1, -1, z, 'oak_log'); }
  }
  // arboles del pantano con lianas
  for (let i = 0; i < 26; i++) {
    const x = Math.floor((r() - 0.5) * 80), z = Math.floor((r() - 0.5) * 100);
    if (Math.abs(x) < 5 || (x > 3 && x < 16 && z > -14 && z < 4)) continue;
    const h = 6 + Math.floor(r() * 3);
    g.fill(x, -3, z, x, h, z, 'oak_log');
    for (let dx = -3; dx <= 3; dx++)
      for (let dz = -3; dz <= 3; dz++) {
        if (Math.abs(dx) + Math.abs(dz) > 4) continue;
        g.set(x + dx, h, z + dz, 'leaves_dark');
        if (Math.abs(dx) + Math.abs(dz) <= 2) g.set(x + dx, h + 1, z + dz, 'leaves_dark');
        if ((Math.abs(dx) === 3 || Math.abs(dz) === 3) && r() < 0.35) {
          const len = 1 + Math.floor(r() * 4);
          g.fill(x + dx, h - len, z + dz, x + dx, h - 1, z + dz, 'leaves_dark');
        }
      }
  }
  // choza de la bruja sobre pilotes
  const hx0 = 6, hx1 = 12, hz0 = -9, hz1 = -3;
  for (const [cx, cz] of [[hx0, hz0], [hx1, hz0], [hx0, hz1], [hx1, hz1]]) g.fill(cx, -3, cz, cx, 2, cz, 'oak_log');
  g.fill(hx0 - 2, 3, hz0, hx1, 3, hz1, 'spruce_planks');
  for (let y = 4; y <= 7; y++)
    for (let x = hx0; x <= hx1; x++)
      for (let z = hz0; z <= hz1; z++) if (x === hx0 || x === hx1 || z === hz0 || z === hz1) g.set(x, y, z, 'spruce_planks');
  for (const [cx, cz] of [[hx0, hz0], [hx1, hz0], [hx0, hz1], [hx1, hz1]]) g.fill(cx, 4, cz, cx, 7, cz, 'oak_log');
  g.fill(hx0 - 1, 8, hz0 - 1, hx1 + 1, 8, hz1 + 1, 'dark_planks');
  g.fill(hx0, 9, hz0, hx1, 9, hz1, 'dark_planks');
  // ventana abierta hacia la pasarela
  g.fill(hx0, 5, -7, hx0, 6, -5, 0);
  // escalera
  for (let k = 0; k < 4; k++) g.set(hx0 - 3 - k, 2 - k, -6, 'spruce_planks');
  scene.add(g.build());

  // agua
  scene.add(makeTreeRing(41, 50, 110, 220, 0x060a08, [0, -1, 0]));
  const water = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshStandardMaterial({ color: 0x0f2a1c, roughness: 0.08, metalness: 0.2, transparent: true, opacity: 0.88 }));
  water.rotation.x = -Math.PI / 2;
  water.position.set(0, -1.15, 0);
  water.receiveShadow = true;
  scene.add(water);
  const lilyGeo = new THREE.PlaneGeometry(0.9, 0.9).rotateX(-Math.PI / 2);
  const lilyMat = new THREE.MeshStandardMaterial({ color: 0x2e6b22, roughness: 0.6 });
  const lilies = new THREE.InstancedMesh(lilyGeo, lilyMat, 120);
  const m = new THREE.Matrix4();
  for (let i = 0; i < 120; i++) {
    m.makeRotationY(r() * 6);
    m.setPosition((r() - 0.5) * 70, -1.12, (r() - 0.5) * 100);
    lilies.setMatrixAt(i, m);
  }
  scene.add(lilies);

  // caldero
  const caul = new THREE.Group();
  const cm = new THREE.MeshStandardMaterial({ color: 0x1e1e24, roughness: 0.5, metalness: 0.6 });
  const pot = new THREE.Mesh(new THREE.BoxGeometry(1, 0.9, 1), cm);
  pot.position.y = 0.45;
  const brew = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.8).rotateX(-Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x40ff40, emissive: 0x30ff40, emissiveIntensity: 1.2 }));
  brew.position.y = 0.91;
  caul.add(pot, brew);
  caul.position.set(hx0 - 1.5, 3, -4);
  scene.add(caul);
  const bubbles = new Particles(50, { center: [hx0 - 1.5, 4.2, -4], box: [0.6, 0.2, 0.6], vel: [0, 1.0, 0], spread: [0.2, 0.3, 0.2], life: 1.6, size: 0.06, colA: 0x7aff5a, bright: 1.2 });
  scene.add(bubbles.points);
  const caulLight = new THREE.PointLight(0x50ff50, 25, 14, 1.8);
  caulLight.position.set(hx0 - 1.5, 5, -4);
  scene.add(caulLight);
  // bruja + cortina
  const witch = makeVillager('witch');
  witch.root.position.set(hx0 + 1.3, 4, -6);
  witch.root.rotation.y = -Math.PI / 2;
  scene.add(witch.root);
  const winLight = new THREE.PointLight(0x9a5aff, 8, 6, 2);
  winLight.position.set(hx0 + 2, 5.5, -6);
  scene.add(winLight);
  const curtain = new THREE.Mesh(new THREE.PlaneGeometry(3, 2), new THREE.MeshStandardMaterial({ color: 0x4a1a5a, roughness: 1, side: THREE.DoubleSide }));
  curtain.rotation.y = Math.PI / 2;
  curtain.position.set(hx0 + 0.6, 6, -6);
  scene.add(curtain);

  const sky = makeSky();
  sky.userData.u.uTop.value.set(0x040a10);
  sky.userData.u.uHor.value.set(0x24382e);
  sky.userData.u.uSunCol.value.set(0x9ac8a0);
  sky.userData.u.uSunDir.value.set(-0.35, 0.4, -0.85).normalize();
  scene.add(sky);
  const moon = makeMoon([220, 240, 200]);
  moon.position.set(-200, 230, -520);
  moon.scale.setScalar(70);
  scene.add(moon);
  const L = addLights(scene, { sky: 0x3a5a50, ground: 0x0a0c0a, hemi: 0.9, dir: 0xa8c8b0, dirI: 1.3, shadow: true });
  L.dir.position.set(-40, 90, -100);
  const fog = makeFogBank(34, [0, -0.6, 0], [80, 1.2, 100], 0x6a8a70, 0.16, 21);
  scene.add(fog);
  const bats = makeBats(7, 77);
  scene.add(bats);
  const fireflies = new Particles(120, { center: [0, 1.5, 0], box: [40, 3, 100], vel: [0, 0.05, 0], spread: [0.2, 0.1, 0.2], life: 6, size: 0.05, colA: 0xb8ff6a, bright: 3, twinkle: 1, swirl: 0.5 });
  scene.add(fireflies.points);
  return { name: 'swamp', scene, grid: g, sky, moon, L, fog, bats, witch, curtain, caul, bubbles, caulLight, winLight, fireflies, hut: { hx0, hz0, hx1, hz1 } };
}

// ---------------------------------------------------------------------------
// CEMENTERIO (con la montana lejana)
// ---------------------------------------------------------------------------
export function buildGraveyard() {
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x141a30, 18, 520);
  const r = rng(404);
  const n = fbm(noise2(31));
  const g = new VoxelGrid(-44, -6, -64, 88, 36, 108);
  const hAt = (x, z) => -1 + Math.floor(7 * Math.exp(-(x * x * 0.6 + (z + 14) * (z + 14)) / 700) + n(x / 8, z / 8) * 1.5);
  for (let z = -64; z < 44; z++)
    for (let x = -44; x < 44; x++) {
      const h = hAt(x, z);
      g.fill(x, -6, z, x, h - 1, z, 'dirt');
      const onPath = Math.abs(x) < 1.5;
      g.set(x, h, z, onPath ? 'gravel' : r() < 0.2 ? 'podzol' : 'grass');
      if (!onPath && r() < 0.05) g.set(x, h + 1, z, r() < 0.6 ? 'dead_bush' : 'tall_grass');
    }
  // tumbas
  const graves = [];
  for (let z = 30; z > -14; z -= 4)
    for (const x of [-12, -9, -6, -3, 3, 6, 9, 12]) {
      if (r() < 0.12) continue;
      const tx = x + (r() < 0.3 ? 1 : 0), tz = z + Math.floor(r() * 2);
      const h = hAt(tx, tz) + 1;
      const kind = r();
      const mat = r() < 0.5 ? 'mossy_bricks' : 'stone_bricks';
      if (kind < 0.55) { g.fill(tx, h, tz, tx, h + 1, tz, mat); }
      else if (kind < 0.85) { g.fill(tx, h, tz, tx, h + 2, tz, 'mossy_cobble'); g.set(tx - 1, h + 1, tz, 'mossy_cobble'); g.set(tx + 1, h + 1, tz, 'mossy_cobble'); }
      else { g.fill(tx, h, tz, tx + 1, h + 1, tz, mat); }
      g.set(tx, h - 1, tz + 1, 'podzol');
      g.set(tx, h - 1, tz + 2, 'podzol');
      graves.push([tx + 0.5, h, tz + 2]);
    }
  // lapida gigante con runas
  const gz = -22, gh = hAt(0, gz) + 1;
  g.fill(-4, gh - 1, gz - 2, 4, gh - 1, gz + 2, 'stone_bricks');
  g.fill(-3, gh, gz - 1, 3, gh + 5, gz, 'mossy_bricks');
  for (let i = 0; i < 4; i++) g.fill(-2, gh + 1 + i, gz, 2, gh + 1 + i, gz, 'rune' + (i + 1));
  g.fill(-2, gh + 6, gz - 1, 2, gh + 6, gz, 'mossy_bricks');
  g.fill(-1, gh + 7, gz - 1, 1, gh + 7, gz, 'mossy_bricks');
  // arboles muertos
  for (const [x, z] of [[-18, -6], [17, 4], [-25, 20], [26, -18], [-30, -30], [32, 26]]) deadTree(g, x, hAt(x, z) + 1, z, r, 9, 0);
  // postes con farol de almas
  const lanterns = [];
  for (const [x, z] of [[-2, 24], [2, 12], [-2, 0], [2, -12]]) {
    const h = hAt(x, z) + 1;
    g.fill(x, h, z, x, h + 1, z, 'cobble');
    const l = makeLantern(true);
    l.position.set(x + 0.5, h + 2, z + 0.5);
    scene.add(l);
    lanterns.push(l);
  }
  scene.add(g.build());
  scene.add(makeFarGround(0x6a7a60, -1.02, blockTex('grass_top')));
  scene.add(makeTreeRing(13, 50, 120, 200, 0x08080e, [0, -1, -10]));

  // montana lejana (voxeles gruesos x4)
  const mg = new VoxelGrid(-30, 0, -30, 60, 30, 30);
  const mn = fbm(noise2(55));
  for (let x = -30; x < 30; x++)
    for (let z = -30; z < 0; z++) {
      const h = Math.floor(24 - Math.abs(x) * 0.7 - Math.abs(z + 15) * 0.6 + mn(x / 5, z / 5) * 6);
      if (h > 0) g && mg.fill(x, 0, z, x, Math.min(29, h), z, h > 20 ? 'stone' : 'deepslate');
    }
  const mountain = mg.build(30);
  mountain.scale.setScalar(4);
  mountain.position.set(0, -6, -240);
  mountain.traverse((o) => { o.castShadow = false; });
  scene.add(mountain);
  const mtnFire = new Fire(Array.from({ length: 14 }, (_, i) => ({ x: (i - 7) * 4.5, y: -4, z: -244 + (i % 3) * 3, w: 7, h: 12 })), { bright: 1.2, seed: 8 });
  scene.add(mtnFire.mesh);
  const mtnGlow = makeShaft(90, 18, 40, 0x3aa0ff, 0.25);
  mtnGlow.rotation.x = Math.PI;
  mtnGlow.position.set(0, -6, -244);
  scene.add(mtnGlow);

  const sky = makeSky();
  scene.add(sky);
  const moon = makeMoon();
  moon.position.set(140, 260, 480);
  moon.scale.setScalar(80);
  scene.add(moon);
  const L = addLights(scene, { sky: 0x3a4280, ground: 0x100c0c, hemi: 0.9, dir: 0x9aaeff, dirI: 1.4, shadow: true });
  L.dir.position.set(40, 90, 80);
  const runeLight = new THREE.PointLight(0x4ac8ff, 0, 18, 1.6);
  runeLight.position.set(0.5, gh + 3, gz + 3);
  scene.add(runeLight);
  const soulLights = lanterns.slice(0, 3).map((l) => {
    const p = new THREE.PointLight(0x4ab8ff, 10, 10, 2);
    p.position.copy(l.position).add(new THREE.Vector3(0, 0.3, 0));
    scene.add(p);
    return p;
  });
  const fog = makeFogBank(30, [0, gh - 2, 5], [60, 2, 60], 0x7a88b0, 0.16, 17);
  scene.add(fog);
  const zombies = [];
  const zPos = [[-3.5, 18], [3.5, 14], [-3.5, 8], [3.5, 4], [-3.5, -2], [3.5, -6]];
  for (const [x, z] of zPos) {
    const zb = makeZombie();
    zb.home = [x, hAt(Math.floor(x), Math.floor(z)) + 1, z];
    scene.add(zb.root);
    zombies.push(zb);
  }
  const runeSparks = new Particles(80, { center: [0.5, gh + 3, gz + 1], box: [5, 4, 0.5], vel: [0, 0.6, 0.4], spread: [0.3, 0.3, 0.3], life: 2.5, size: 0.04, colA: 0x5ad0ff, bright: 1.5 });
  scene.add(runeSparks.points);
  const bats = makeBats(6, 12);
  scene.add(bats);
  return { name: 'graveyard', scene, grid: g, hAt, sky, moon, L, lanterns, zombies, graves, gz, gh, runeLight, soulLights, fog, mountain, mtnFire, mtnGlow, runeSparks, bats };
}

// ---------------------------------------------------------------------------
// MONTANA: entrada en forma de calavera + tunel descendente
// ---------------------------------------------------------------------------
export function buildMountain() {
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x101428, 0.014);
  const r = rng(505);
  const n = fbm(noise2(41));
  const g = new VoxelGrid(-54, -26, -74, 108, 78, 120);
  const FACE = -12;
  for (let z = -74; z < 46; z++)
    for (let x = -54; x < 54; x++) {
      let h;
      if (z >= FACE) h = -1 + Math.floor(n(x / 8, z / 8) * 1.6 * Math.min(1, Math.abs(x) / 6));
      else h = Math.min(51, Math.floor(36 + (FACE - z) * 1.2 - Math.abs(x) * 0.35 + n(x / 7, z / 7) * 8));
      if (z >= FACE - 1 && z < FACE && Math.abs(x) > 18) h = Math.min(h, 30 + Math.floor(n(x / 5, 1) * 6) - Math.floor(Math.max(0, Math.abs(x) - 18) * 0.8));
      g.fill(x, -26, z, x, h, z, z < FACE ? (r() < 0.7 ? 'stone' : 'deepslate') : 'dirt');
      if (z >= FACE) {
        g.set(x, h, z, Math.abs(x) < 3 ? 'gravel' : r() < 0.5 ? 'podzol' : r() < 0.5 ? 'stone' : 'gravel');
        if (Math.abs(x) > 3 && r() < 0.05) g.set(x, h + 1, z, 'dead_bush');
      } else if (r() < 0.25) g.set(x, h, z, 'cobble');
    }
  // laderas laterales que abrazan la entrada
  for (let z = FACE; z < FACE + 14; z++)
    for (const s of [-1, 1])
      for (let k = 0; k < 16; k++) {
        const x = s * (19 + k);
        const h = Math.floor(30 - (z - FACE) * 2.2 - k * 0.6 + n(x / 5, z / 5) * 4);
        if (h > -1) g.fill(x, -1, z, x, h, z, r() < 0.7 ? 'stone' : 'cobble');
      }
  // calavera tallada (escala x2)
  const eyeFires = [];
  for (let row = 0; row < 17; row++)
    for (let col = 0; col < 17; col++) {
      const ch = SKULL[row][col];
      if (ch === '.') continue;
      for (let a = 0; a < 2; a++)
        for (let b = 0; b < 2; b++) {
          const x = (col - 8) * 2 + a - 1, y = (16 - row) * 2 - 2 + b;
          if (ch === 'X' || ch === 't') g.fill(x, y, FACE, x, y, FACE + 1, 'bone');
          if (ch === 't') g.set(x, y, FACE - 1, 'bone');
          if (ch === 'o') { g.fill(x, y, FACE - 6, x, y, FACE + 1, 0); g.set(x, y - 1, FACE - 6, 'soul_sand'); }
          if (ch === 'n') g.fill(x, y, FACE - 3, x, y, FACE + 1, 0);
          if (ch === 'm') g.fill(x, y, FACE - 2, x, y, FACE + 1, 0);
        }
    }
  for (const ex of [-9, 9]) eyeFires.push({ x: ex, y: 13, z: FACE - 4.5, w: 4.5, h: 4.5 }, { x: ex - 2, y: 13, z: FACE - 5, w: 3, h: 3.5 }, { x: ex + 2, y: 13, z: FACE - 5, w: 3, h: 3.5 });
  // tunel descendente
  const floorAt = (z) => -1 - Math.floor(Math.max(0, FACE - 1 - z) / 2.5);
  for (let z = FACE + 1; z >= -72; z--) {
    const f = floorAt(z);
    const wob = Math.round(Math.sin(z / 9) * 1.5);
    for (let x = -3 + wob; x <= 3 + wob; x++) {
      g.fill(x, f + 1, z, x, f + 7, z, 0);
      g.set(x, f, z, r() < 0.3 ? 'deepslate_bricks' : 'deepslate');
      if (r() < 0.12 && z < FACE - 2) g.set(x, f + 7, z, 'dripstone');
    }
  }
  // abrir la boca hasta el suelo exterior
  for (let x = -12; x <= 12; x++) for (let z = FACE - 2; z <= FACE + 1; z++) if (g.get(x, 0, z) === B.dirt) g.set(x, 0, z, 0);
  // parches de arena de almas con fuego azul
  const fires = [...eyeFires];
  const soulSpots = [[-7, 2], [8, 6], [-12, 10], [13, 1], [-4, 14], [5, 18]];
  for (const [x, z] of soulSpots) {
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) g.set(x + a, -1, z + b, 'soul_sand');
    fires.push({ x: x + 0.5, y: 0, z: z + 0.5, w: 1.6, h: 2.2 }, { x: x + 1.2, y: 0, z: z - 0.4, w: 1.1, h: 1.5 });
  }
  // huesos sueltos
  for (let i = 0; i < 18; i++) {
    const x = Math.floor((r() - 0.5) * 40), z = Math.floor(FACE + 2 + r() * 30);
    if (Math.abs(x) > 3) g.set(x, 0, z, 'bone');
  }
  // fuego del fondo del tunel y antorchas de almas a lo largo del descenso
  for (let i = 0; i < 10; i++) fires.push({ x: (r() - 0.5) * 5, y: floorAt(-66) + 1, z: -60 - r() * 10, w: 2, h: 3 });
  for (let z = -18; z >= -54; z -= 6) {
    const cx = Math.round(Math.sin(z / 9) * 1.5) + 0.5;
    for (const sd of [-1, 1]) {
      const x = cx + sd * 2.6;
      g.set(Math.floor(x), floorAt(z), z, 'soul_sand');
      fires.push({ x, y: floorAt(z) + 1, z: z + 0.5, w: 0.9, h: 1.3 });
    }
  }
  scene.add(g.build());
  const farGround = makeFarGround(0x5a5a5a, -1.02, blockTex('gravel'));
  farGround.position.z = 600 + FACE + 2; // no debe cortar el tunel bajo la montana
  scene.add(farGround);
  scene.add(makeTreeRing(17, 58, 130, 200, 0x08080e, [0, -1, 20]));
  const fire = new Fire(fires, { bright: 0.9, seed: 12 });
  scene.add(fire.mesh);

  const sky = makeSky();
  scene.add(sky);
  const moon = makeMoon();
  moon.position.set(-260, 240, 420);
  moon.scale.setScalar(80);
  scene.add(moon);
  const L = addLights(scene, { sky: 0x2a3060, ground: 0x0a0808, hemi: 0.55, dir: 0x9aaeff, dirI: 0.9, shadow: true });
  L.dir.position.set(-60, 80, 100);
  const blue = [];
  for (const [x, y, z, i, d] of [[0, 5, FACE + 1, 40, 30], [-9, 13, FACE - 3, 18, 16], [9, 13, FACE - 3, 18, 16], [0, floorAt(-24) + 4, -24, 35, 16], [0, floorAt(-36) + 4, -36, 45, 18], [0, floorAt(-48) + 4, -48, 55, 22], [0, floorAt(-64) + 3, -64, 60, 36]]) {
    const p = new THREE.PointLight(0x3aa8ff, i, d, 1.6);
    p.position.set(x, y, z);
    scene.add(p);
    blue.push(p);
  }
  const embers = new Particles(200, { center: [0, 4, FACE + 2], box: [16, 6, 3], vel: [0, 0.9, 1.6], spread: [0.5, 0.5, 0.8], life: 6, size: 0.05, colA: 0x5ac8ff, colB: 0xffa040, bright: 1.6, swirl: 0.8 });
  scene.add(embers.points);
  const fog = makeFogBank(26, [0, 0, 10], [60, 2, 40], 0x7a88b0, 0.15, 29);
  scene.add(fog);
  const bats = makeBats(8, 90);
  scene.add(bats);
  const drips = new Particles(60, { center: [0, floorAt(-30) + 6, -30], box: [6, 0.1, 40], vel: [0, -6, 0], spread: [0, 0.2, 0], life: 1.2, size: 0.05, colA: 0x9ad8ff, bright: 1.5 });
  scene.add(drips.points);
  return { name: 'mountain', scene, grid: g, FACE, floorAt, sky, moon, L, fire, blue, embers, fog, bats, drips };
}

// ---------------------------------------------------------------------------
// CAVERNA de los esqueletos
// ---------------------------------------------------------------------------
export function buildCavern() {
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x040814, 0.022);
  scene.background = new THREE.Color(0x020308);
  const r = rng(606);
  const n = fbm(noise2(61));
  const g = new VoxelGrid(-36, -12, -106, 72, 58, 116);
  const ceil = (x, z) => Math.floor(30 - (x / 32) ** 2 * 18 + n(x / 6, z / 6) * 6);
  const half = (z) => 30 - Math.floor(n(3, z / 9) * 4) - (z > -4 ? Math.min(26, (z + 4) * 6) : 0);
  g.fill(-36, -12, -106, 35, 45, 9, 'deepslate');
  for (let z = -102; z < 6; z++)
    for (let x = -34; x < 34; x++) {
      if (Math.abs(x) > half(z)) continue;
      let f = 0;
      if (Math.abs(x) > 7) f = Math.floor(n(x / 5, z / 5) * 2.4);
      if (z < -60) f = Math.max(f, z < -66 ? 1 : 0);
      if (z < -66 && Math.abs(x) < 14) f = 2;
      const c = ceil(x, z);
      g.fill(x, f, z, x, c, z, 0);
      const top = r();
      g.set(x, f - 1, z, top < 0.15 ? 'stone' : top < 0.3 ? 'gravel' : 'deepslate');
      if (r() < 0.05) g.set(x, c, z, 'dripstone');
    }
  // tunel de entrada
  for (let z = 0; z < 9; z++) for (let x = -2; x <= 2; x++) g.fill(x, 0, z, x, 5, z, 0);
  // pasillo central de ladrillo
  for (let z = -60; z < 4; z++) for (let x = -3; x <= 2; x++) g.set(x, -1, z, 'deepslate_bricks');
  // canales de fuego azul
  const fires = [];
  for (let z = -46; z <= -4; z++)
    for (const x of [-5, 4]) {
      g.set(x, -1, z, 0);
      g.set(x, -2, z, 'soul_soil');
      if (z % 1 === 0) fires.push({ x: x + 0.5, y: -1, z: z + 0.5, w: 1.1, h: 1.6 + r() * 0.8, delay: 0 });
    }
  // fosa de fuego con puente de huesos
  for (let z = -60; z <= -48; z++)
    for (let x = -30; x <= 30; x++) {
      if (Math.abs(x) > half(z)) continue;
      g.fill(x, -10, z, x, -1, z, 0);
      g.set(x, -11, z, 'soul_sand');
      if ((x + z) % 3 === 0 && r() < 0.6) fires.push({ x: x + 0.5, y: -10, z: z + 0.5, w: 2.4, h: 3 + r() * 3, b: 0.35 });
    }
  for (let z = -61; z <= -47; z++) { g.set(-1, -1, z, 'bone'); g.set(0, -1, z, 'bone'); if (r() < 0.2) g.set(r() < 0.5 ? -2 : 1, -1, z, 'bone'); }
  // parches de arena de almas con fuego
  for (let i = 0; i < 26; i++) {
    const x = Math.round((r() < 0.5 ? -1 : 1) * (10 + r() * 16)), z = Math.round(-4 - r() * 42);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) if (r() < 0.8) { const y = g.top(x + a, z + b); if (y < 4) g.set(x + a, y, z + b, 'soul_sand'); }
    const y = g.top(x, z) + 1;
    fires.push({ x: x + 0.5, y, z: z + 0.5, w: 1.8, h: 2.4 + r() });
  }
  // montanas de huesos
  const piles = [[-16, -14], [16, -16], [-18, -32], [18, -30], [-15, -42], [15, -43]];
  const pileTops = [];
  for (const [px, pz] of piles) {
    const base = g.top(px, pz) + 1;
    for (let y = 0; y < 5; y++) {
      const rad = 4.5 - y;
      for (let x = -5; x <= 5; x++) for (let z = -5; z <= 5; z++) if (x * x + z * z < rad * rad * (0.8 + r() * 0.4)) g.set(px + x, base + y, pz + z, 'bone');
    }
    pileTops.push([px, base, pz]);
  }
  // calaveras gigantes en las paredes
  const wallSkulls = [[-1, -20], [1, -22], [-1, -40], [1, -38]];
  for (const [side, zc] of wallSkulls) {
    const wx = side < 0 ? -half(zc) - 1 : half(zc) + 1;
    for (let row = 0; row < 17; row++)
      for (let col = 0; col < 17; col++) {
        const ch = SKULL[row][col];
        if (ch === '.') continue;
        const z = zc + (col - 8) * side, y = 22 - row;
        for (let d = 0; d < 3; d++) g.set(wx - side * d, y, z, ch === 'o' || ch === 'n' || ch === 'm' ? (d === 0 ? 'obsidian' : 0) : 'bone');
      }
    fires.push({ x: wx - side * 1.5 + 0.5, y: 13, z: zc + 0.5 - 4.5 * side, w: 3, h: 3.5 }, { x: wx - side * 1.5 + 0.5, y: 13, z: zc + 0.5 + 4.5 * side, w: 3, h: 3.5 });
  }
  // sala del trono: tarima, trono y altar
  g.fill(-13, 2, -100, 12, 2, -66, 'deepslate_bricks');
  for (let k = 0; k < 3; k++) g.fill(-4 + k, 3 + k, -99, 3 - k, 3 + k, -91 + k, 'deepslate_bricks');
  g.fill(-2, 6, -97, 1, 7, -94, 'bone');
  g.fill(-3, 6, -98, 2, 16, -98, 'bone');
  g.fill(-4, 17, -98, 3, 17, -98, 'bone');
  for (const x of [-4, 3]) g.fill(x, 6, -98, x, 18, -98, 'bone');
  for (const x of [-3, 2]) g.fill(x, 6, -97, x, 9, -95, 'bone');
  for (let k = 0; k < 3; k++) for (let z = -63 - k; z >= -65; z--) g.fill(-4, 0, z, 3, k, z, 'deepslate_bricks');
  g.fill(-1, 3, -77, 0, 3, -76, 'bone');
  g.fill(-1, 4, -77, 0, 4, -76, 'obsidian');
  // braseros de hueso
  const braz = [[-9, -70], [8, -70], [-9, -86], [8, -86]];
  for (const [x, z] of braz) { g.fill(x, 3, z, x + 1, 8, z + 1, 'bone'); fires.push({ x: x + 1, y: 9, z: z + 1, w: 2.4, h: 3.6 }); }
  // dripstone extra
  for (let i = 0; i < 260; i++) {
    const x = Math.floor((r() - 0.5) * 60), z = Math.floor(-100 + r() * 100);
    const c = ceil(x, z);
    if (Math.abs(x) < half(z) && !g.get(x, c, z)) { g.set(x, c, z, 'dripstone'); if (r() < 0.4) g.set(x, c - 1, z, 'dripstone'); }
  }
  // cadenas con faroles de almas
  const lanterns = [];
  for (let i = 0; i < 14; i++) {
    const x = Math.round((r() - 0.5) * 34), z = Math.round(-6 - r() * 90);
    if (z < -46 && z > -62) continue;
    const c = ceil(x, z);
    const len = 6 + Math.floor(r() * 8);
    for (let y = c; y > c - len; y--) if (!g.get(x, y, z)) g.set(x, y, z, 'chain');
    const l = makeLantern(true);
    l.position.set(x + 0.5, c - len + 0.55, z + 0.5);
    scene.add(l);
    lanterns.push(l);
  }
  scene.add(g.build());

  for (const f of fires) f.delay = Math.hypot(f.x, f.z + 76) / 70;
  const fire = new Fire(fires, { bright: 0.75, seed: 21 });
  scene.add(fire.mesh);
  // anillo de fuego del altar (separado)
  const ringList = [];
  for (let a = 0; a < 18; a++) ringList.push({ x: -0.0 + Math.cos(a / 18 * Math.PI * 2) * 3.6, y: 3, z: -76 + Math.sin(a / 18 * Math.PI * 2) * 3.6, w: 1.2, h: 2.2 });
  const ringFire = new Fire(ringList, { bright: 0.9, seed: 33 });
  scene.add(ringFire.mesh);

  // orbe (la voz robada)
  const orb = new THREE.Group();
  const orbCore = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xdff4ff, emissiveIntensity: 1.6 }));
  const orbShell = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.8, 0.8), new THREE.MeshBasicMaterial({ color: 0x9adfff, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false }));
  orb.add(orbCore, orbShell);
  orb.position.set(0, 6.3, -76);
  scene.add(orb);
  const orbLight = new THREE.PointLight(0xe0f4ff, 30, 14, 1.8);
  scene.add(orbLight);
  const orbSwirl = new Particles(90, { center: [0, 6.3, -76], box: [1.6, 1.6, 1.6], vel: [0, 0.3, 0], spread: [0.3, 0.3, 0.3], life: 2, size: 0.035, colA: 0xffffff, bright: 1.2, swirl: 0.6 });
  scene.add(orbSwirl.points);

  // luces
  const hemi = new THREE.HemisphereLight(0x1a3a6a, 0x05060a, 0.5);
  scene.add(hemi);
  const lights = [];
  for (const [x, y, z, i, d] of [[0, 4, 2, 14, 18], [0, 7, -8, 45, 34], [0, 7, -24, 45, 34], [0, 7, -40, 45, 34], [0, -7, -54, 30, 30], [-14, 6, -22, 25, 24], [14, 6, -34, 25, 24], [0, 12, -72, 55, 40], [0, 14, -90, 55, 40]]) {
    const p = new THREE.PointLight(0x3a9cff, i, d, 1.5);
    p.position.set(x, y, z);
    p.userData.base = i;
    scene.add(p);
    lights.push(p);
  }
  const shafts = [];
  for (const [x, z] of [[-6, -14], [9, -30], [-4, -70], [6, -84]]) {
    const s = makeShaft(ceil(x, z) + 1, 0.4, 2.2, 0x6ab8ff, 0.14);
    s.position.set(x, ceil(x, z) + 1, z);
    s.rotation.z = 0.08;
    scene.add(s);
    shafts.push(s);
  }
  const embers = new Particles(500, { center: [0, 6, -40], box: [56, 12, 96], vel: [0, 0.7, 0], spread: [0.3, 0.4, 0.3], life: 7, size: 0.05, colA: 0x5ac8ff, colB: 0xffa030, bright: 1.4, swirl: 0.7 });
  scene.add(embers.points);
  const pitEmbers = new Particles(220, { center: [0, -6, -54], box: [50, 4, 12], vel: [0, 2.6, 0], spread: [0.5, 0.8, 0.5], life: 3.5, size: 0.06, colA: 0x5ac8ff, colB: 0xffa030, bright: 1.5, swirl: 0.5 });
  scene.add(pitEmbers.points);
  const fog = makeFogBank(30, [0, 0.4, -45], [56, 1.5, 100], 0x3a6aa8, 0.05, 37);
  scene.add(fog);

  // ejercito
  const list = [];
  for (let z = -6; z >= -45; z -= 2.2)
    for (const s of [-1, 1]) {
      list.push({ x: s * 7.2, y: 0, z, yaw: -s * Math.PI / 2, bow: true, row: 1, side: s });
      list.push({ x: s * 9.6, y: g.top(s * 9.6, Math.round(z)) + 1, z: z - 1.1, yaw: -s * Math.PI / 2, bow: true, row: 2, side: s });
    }
  for (const [px, base, pz] of pileTops)
    for (let k = 0; k < 5; k++) {
      const a = (k / 5) * Math.PI * 2 + px;
      const x = px + Math.cos(a) * 2.2, z = pz + Math.sin(a) * 2.2;
      list.push({ x, y: g.top(Math.floor(x), Math.floor(z)) + 1, z, yaw: Math.atan2(-x, -(z + 20)), sit: 1, pile: true });
    }
  for (let i = 0; i < 40; i++) {
    const s = r() < 0.5 ? -1 : 1;
    const x = s * (12 + r() * 14), z = -6 - r() * 40;
    list.push({ x, y: g.top(Math.floor(x), Math.floor(z)) + 1, z, yaw: Math.atan2(-x, 0) + (r() - 0.5), bow: r() < 0.4, crowd: true });
  }
  for (const s of [-1, 1]) for (let k = 0; k < 6; k++) list.push({ x: s * (5 + (k % 2) * 2.5), y: 3, z: -68 - k * 4, yaw: -s * Math.PI / 2, bow: k % 2 === 0, guard: true });
  const army = new Army(list, 7);
  scene.add(army.group);

  const king = makeSkeletonRig('king');
  king.root.scale.setScalar(3);
  scene.add(king.root);
  const crown = new THREE.Group();
  const gold = new THREE.MeshStandardMaterial({ color: 0x3a6a9a, emissive: 0x1a4a8a, emissiveIntensity: 1.2, metalness: 0.8, roughness: 0.35 });
  const band = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.14, 0.6), gold);
  crown.add(band);
  for (const [x, z] of [[-0.25, -0.25], [0.25, -0.25], [-0.25, 0.25], [0.25, 0.25], [0, 0.27], [0, -0.27], [0.27, 0], [-0.27, 0]]) {
    const sp = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.16, 0.08), gold);
    sp.position.set(x, 0.14, z);
    crown.add(sp);
  }
  crown.position.y = 0.58;
  king.head.add(crown);
  const crownFire = new Fire([{ x: 0, y: 0.1, z: 0, w: 0.6, h: 0.7 }], { bright: 1.1, seed: 2 });
  crown.add(crownFire.mesh);
  const cape = new THREE.Mesh(new THREE.PlaneGeometry(0.75, 1.25), new THREE.MeshStandardMaterial({ color: 0x2a0f3a, roughness: 1, side: THREE.DoubleSide }));
  cape.position.set(0, -0.1 + 0.75 - 0.6 + 0.35, -0.16);
  king.torso.add(cape);
  const staff = new THREE.Group();
  const shaft = new THREE.Mesh(new THREE.BoxGeometry(0.08, 1.7, 0.08), new THREE.MeshStandardMaterial({ color: 0x3a2a1a }));
  shaft.position.y = -0.2;
  const gem = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.2), new THREE.MeshStandardMaterial({ color: 0x9ad8ff, emissive: 0x3ab0ff, emissiveIntensity: 1.5 }));
  gem.position.y = 0.7;
  staff.add(shaft, gem);
  staff.position.set(0, -0.62, 0.05);
  king.armR.add(staff);
  const kingLight = new THREE.PointLight(0x4ab8ff, 10, 12, 1.8);
  scene.add(kingLight);

  return { name: 'cavern', scene, grid: g, fire, ringFire, orb, orbCore, orbLight, orbSwirl, hemi, lights, shafts, embers, pitEmbers, fog, army, list, king, crown, crownFire, staff, gem, kingLight, lanterns, ceil };
}
