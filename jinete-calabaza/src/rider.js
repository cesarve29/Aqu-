// El Jinete sin cabeza (calabaza llameante), su caballo negro y el nino espantapajaros.
import * as THREE from 'three';
import { paint, toTex, hex, jit, rng, blockTex } from './textures.js';
import { Fire, Particles } from './fx.js';
import { makeVillager, makeLantern } from './models.js';

const C = (c, r, a = 0.12) => jit(hex(c), r, a);

function box(parent, w, h, d, mat, x, y, z, name) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  if (name) m.name = name;
  parent.add(m);
  return m;
}
function pivot(parent, x, y, z) {
  const p = new THREE.Object3D();
  p.position.set(x, y, z);
  parent.add(p);
  return p;
}
function std(map, o = {}) {
  return new THREE.MeshStandardMaterial({ map, roughness: 0.85, metalness: 0, ...o });
}

// ---------------------------------------------------------------------------
// texturas
// ---------------------------------------------------------------------------
const armorTex = () => toTex(paint(16, 16, (x, y, r) => {
  const plate = y % 5 === 4 || x === 0 || x === 15;
  const rivet = (x === 2 || x === 13) && y % 5 === 2;
  if (rivet) return [120, 110, 100];
  return C(plate ? 0x16161c : 0x2c2c36, r, 0.25);
}, 41), false);
const chestTex = () => toTex(paint(16, 16, (x, y, r) => {
  if (y === 11 || y === 12) return C(0x3a1e10, r, 0.2); // cinturon
  if (y >= 11 && y <= 12 && (x === 7 || x === 8)) return [150, 120, 60];
  if (x === 7 || x === 8) return C(0x1a1a20, r, 0.2);
  if (y < 4 && (x < 3 || x > 12)) return C(0x40404c, r, 0.2);
  return C(y % 4 === 3 ? 0x1c1c24 : 0x30303c, r, 0.25);
}, 42), false);
const leatherTex = (base = 0x3a2416) => toTex(paint(16, 16, (x, y, r) => (y % 6 === 5 ? C(base, r, 0.2).map((v) => v * 0.6) : C(base, r, 0.25)), 43), false);
const capeTex = () => toTex(paint(16, 32, (x, y, r) => {
  // capa negra rasgada: bordes inferiores irregulares
  const cut = 32 - (3 + ((x * 7 + 3) % 5) + ((x * 13) % 3) * 2);
  if (y > cut) return null;
  if (y > cut - 2 && r() < 0.4) return null;
  return C(x % 4 === 1 ? 0x14121a : 0x0b0a10, r, 0.3);
}, 44), false);
const hideTex = (front = false) => toTex(paint(16, 16, (x, y, r) => {
  const c = C((x + y * 3) % 7 === 0 ? 0x1c1a22 : 0x101016, r, 0.3);
  return c;
}, front ? 46 : 45), false);
const maneTex = () => toTex(paint(8, 16, (x, y, r) => C(x % 2 ? 0x050507 : 0x0c0b10, r, 0.3)), false);

// Cara de la calabaza 16x16: '#' = hueco encendido
const FACES = {
  angry: [
    '................',
    '................',
    '................',
    '..##........##..',
    '..###......###..',
    '..####....####..',
    '..#####..#####..',
    '................',
    '.......##.......',
    '................',
    '.#............#.',
    '.##.##.##.##.##.',
    '.##############.',
    '..############..',
    '...#.##..##.#...',
    '................',
  ],
  smile: [
    '................',
    '................',
    '................',
    '................',
    '...###....###...',
    '..#...#..#...#..',
    '................',
    '.......##.......',
    '................',
    '.#............#.',
    '.##..........##.',
    '..##.##..##.##..',
    '...##########...',
    '....########....',
    '.....#....#.....',
    '................',
  ],
};
const CRACK = (x, y) => (x === 5 + Math.floor(y / 3) && y < 10) || (y === 3 + (x >> 1) && x > 8 && x < 15) || (x === 11 && y > 8 && y < 14);

function pumpkinFace(kind, cracked) {
  const rows = FACES[kind];
  return [
    toTex(paint(16, 16, (x, y, r) => {
      if (rows[y][x] === '#') return jit([255, 200, 70], r, 0.15);
      if (cracked && CRACK(x, y)) return [40, 18, 6];
      return C(x % 4 === 0 ? 0xa8520e : 0xd97a18, r, 0.15);
    }, 51), false),
    toTex(paint(16, 16, (x, y) => (rows[y][x] === '#' ? [255, 190, 80] : cracked && CRACK(x, y) ? [90, 40, 10] : [0, 0, 0]), 52), false),
  ];
}
// posiciones de las llamas (coordenadas locales de la cabeza, tamano 0.62)
function faceFireSpots(kind, S) {
  const k = S / 16;
  const P = (x, y) => [(x - 7.5) * k, (7.5 - y) * k];
  if (kind === 'smile')
    return [
      { p: P(4, 5), w: 0.12, h: 0.18 }, { p: P(11, 5), w: 0.12, h: 0.18 },
      ...[3, 6, 9, 12].map((x) => ({ p: P(x, 12.5), w: 0.12, h: 0.13, m: 1 })),
    ];
  return [
    { p: P(4, 5.5), w: 0.17, h: 0.34 }, { p: P(11, 5.5), w: 0.17, h: 0.34 },
    { p: P(3.5, 5.8), w: 0.1, h: 0.22 }, { p: P(11.5, 5.8), w: 0.1, h: 0.22 },
    ...[3, 5.5, 8, 10.5, 13].map((x) => ({ p: P(x, 12.5), w: 0.13, h: 0.17, m: 1 })),
  ];
}

// ---------------------------------------------------------------------------
// JINETE
// ---------------------------------------------------------------------------
export function makeRider() {
  const root = new THREE.Group();
  const armor = std(armorTex(), { roughness: 0.55, metalness: 0.55 });
  const chest = std(chestTex(), { roughness: 0.55, metalness: 0.5 });
  const leather = std(leatherTex());
  const capeM = std(capeTex(), { alphaTest: 0.5, side: THREE.DoubleSide, roughness: 1 });

  const hips = pivot(root, 0, 0.95, 0);
  const legR = pivot(hips, -0.17, 0, 0), legL = pivot(hips, 0.17, 0, 0);
  for (const l of [legR, legL]) {
    box(l, 0.3, 0.75, 0.3, armor, 0, -0.38, 0);
    box(l, 0.34, 0.22, 0.38, leather, 0, -0.84, 0.03);
  }
  const torso = pivot(hips, 0, 0, 0);
  box(torso, 0.7, 0.88, 0.4, chest, 0, 0.44, 0);
  box(torso, 0.74, 0.22, 0.44, leather, 0, 0.06, 0); // faldon
  box(torso, 0.42, 0.08, 0.32, armor, 0, 0.92, 0); // gorguera
  const neck = pivot(torso, 0, 0.92, 0);
  // cabeza de calabaza
  const head = pivot(neck, 0, 0.33, 0.02);
  const S = 0.62;
  const faces = {
    angry: pumpkinFace('angry', false), cracked: pumpkinFace('angry', true), smile: pumpkinFace('smile', false),
  };
  const faceMat = std(faces.angry[0], { emissiveMap: faces.angry[1], emissive: new THREE.Color(1, 0.55, 0.2), emissiveIntensity: 2.2, roughness: 0.75 });
  const side = std(blockTex('pumpkin_side'), { roughness: 0.75 });
  const top = std(blockTex('pumpkin_top'), { roughness: 0.75 });
  const pumpkin = new THREE.Mesh(new THREE.BoxGeometry(S, S, S), [side, side, top, top, faceMat, side]);
  pumpkin.castShadow = true;
  head.add(pumpkin);
  box(head, 0.09, 0.16, 0.09, new THREE.MeshStandardMaterial({ color: 0x3a4a1a }), 0.02, S / 2 + 0.07, 0);
  // llamas de ojos y boca
  const faceFires = {};
  for (const kind of ['angry', 'smile']) {
    const spots = faceFireSpots(kind, S);
    const f = new Fire(spots.map((s, i) => ({ x: s.p[0], y: s.p[1] - s.h * 0.35, z: S / 2 + 0.02, w: s.w, h: s.h, delay: 0, b: s.m ? 0.8 : 1 })), { orange: true, bright: 0.8, seed: 60 + kind.length, speed: 4 });
    f.mesh.renderOrder = 9;
    head.add(f.mesh);
    faceFires[kind] = f;
  }
  const headLight = new THREE.PointLight(0xff7a2a, 4, 6, 2);
  headLight.position.set(0, 0.1, 1.3);
  head.add(headLight);

  // brazos y hombreras
  const armR = pivot(torso, -0.5, 0.82, 0), armL = pivot(torso, 0.5, 0.82, 0);
  for (const a of [armR, armL]) {
    box(a, 0.26, 0.8, 0.26, armor, 0, -0.38, 0);
    box(a, 0.36, 0.2, 0.44, armor, 0, 0.02, 0);
    box(a, 0.29, 0.14, 0.29, leather, 0, -0.74, 0);
  }
  // capa en dos tramos
  const capeA = pivot(torso, 0, 0.9, -0.23);
  const cgA = new THREE.PlaneGeometry(0.9, 0.95); cgA.translate(0, -0.475, 0);
  const uvA = cgA.attributes.uv; for (let i = 0; i < uvA.count; i++) uvA.setY(i, 0.5 + uvA.getY(i) * 0.5);
  const cA = new THREE.Mesh(cgA, capeM); cA.castShadow = true; capeA.add(cA);
  const capeB = pivot(capeA, 0, -0.95, 0);
  const cgB = new THREE.PlaneGeometry(0.9, 0.95); cgB.translate(0, -0.475, 0);
  const uvB = cgB.attributes.uv; for (let i = 0; i < uvB.count; i++) uvB.setY(i, uvB.getY(i) * 0.5);
  const cB = new THREE.Mesh(cgB, capeM); cB.castShadow = true; capeB.add(cB);

  // espada (en la mano) y vaina (en la cadera)
  const steel = new THREE.MeshStandardMaterial({ color: 0x9aa0aa, roughness: 0.3, metalness: 0.9 });
  const hilt = new THREE.MeshStandardMaterial({ color: 0x2a1a10, roughness: 0.8 });
  const gold = new THREE.MeshStandardMaterial({ color: 0x8a6a2a, roughness: 0.4, metalness: 0.8 });
  const sword = pivot(armR, 0, -0.8, 0.02);
  box(sword, 0.07, 0.24, 0.07, hilt, 0, 0, 0);
  box(sword, 0.34, 0.06, 0.1, gold, 0, 0.14, 0);
  const blade = box(sword, 0.08, 1.15, 0.03, steel, 0, 0.74, 0);
  blade.material = steel.clone();
  blade.material.emissive = new THREE.Color(1, 0.5, 0.15);
  blade.material.emissiveIntensity = 0;
  sword.rotation.x = Math.PI / 2;
  const swordFire = new Fire(Array.from({ length: 7 }, (_, i) => ({ x: 0, y: 0.25 + i * 0.15, z: 0, w: 0.2, h: 0.32, b: 1 - i * 0.05 })), { orange: true, bright: 0.9, seed: 77, speed: 5 });
  sword.add(swordFire.mesh);
  const sheath = pivot(torso, -0.4, 0.05, 0.05);
  box(sheath, 0.1, 0.9, 0.08, leather, 0, -0.35, 0);
  box(sheath, 0.3, 0.06, 0.1, gold, 0, 0.12, 0);
  box(sheath, 0.07, 0.22, 0.07, hilt, 0, 0.26, 0);
  sheath.rotation.set(0.35, 0, 0.25);

  // brasas que salen de la cara (coordenadas de mundo)
  const embers = new Particles(90, { center: [0, 0, 0], box: [0.45, 0.2, 0.1], vel: [0, 1.1, 0.15], spread: [0.25, 0.35, 0.25], life: 1.8, size: 0.03, colA: 0xffa040, colB: 0xffe080, bright: 1.3, swirl: 0.15 });
  const swordSparks = new Particles(120, { center: [0, 0, 0], box: [0.1, 0.1, 0.1], vel: [0, 0.8, 0], spread: [0.6, 0.6, 0.6], life: 0.9, size: 0.03, colA: 0xffb050, bright: 2.5 });

  const mats = { armor, chest, leather, capeM, faceMat };
  const g = { root, hips, torso, neck, head, pumpkin, legR, legL, armR, armL, capeA, capeB, sword, sheath, swordFire, blade, faceFires, headLight, embers, swordSparks, mats, faces };
  g.face = 'angry';
  g.setFace = (kind) => {
    const key = kind;
    const tex = faces[key];
    if (faceMat.map !== tex[0]) { faceMat.map = tex[0]; faceMat.emissiveMap = tex[1]; faceMat.needsUpdate = true; }
    const fk = kind === 'smile' ? 'smile' : 'angry';
    faceFires.angry.mesh.visible = fk === 'angry';
    faceFires.smile.mesh.visible = fk === 'smile';
    g.face = fk;
  };
  // fuego de la cara: tono 'red' (furia), 'soft' (tristeza), 'gold'; k = intensidad
  g.flame = (t, { k = 1, red = 0, soft = 0, gold = 0, flare = 1 } = {}) => {
    const tint = [1 + 0.25 * red - 0.1 * soft, 1 - 0.45 * red - 0.15 * soft, 1 - 0.5 * red - 0.2 * soft];
    for (const f of Object.values(faceFires)) f.set(t, { tint, gold, bright: 0.8 * Math.min(k, 1.6) * (1 + 0.25 * gold), flare: flare * (0.6 + 0.4 * Math.min(k, 1.6)) });
    faceMat.emissiveIntensity = 0.9 * (0.35 + 0.65 * Math.min(k, 1.6)) * (1 + 0.3 * gold);
    faceMat.emissive.setRGB(1, lerp(0.55, 0.3, red) + 0.2 * gold - 0.08 * soft, 0.2 * (1 - red) + 0.05 * gold);
    headLight.intensity = 1.4 * Math.min(k, 1.6) * (1 + 0.6 * gold);
    headLight.color.setRGB(1, lerp(0.48, 0.25, red) + 0.3 * gold, 0.16 + 0.2 * gold);
  };
  g.reset = () => {
    for (const p of [hips, torso, neck, head, legR, legL, armR, armL, capeA, capeB, sheath]) p.rotation.set(0, 0, 0);
    sheath.rotation.set(0.35, 0, 0.25);
    hips.position.set(0, 0.95, 0);
    root.position.set(0, 0, 0);
    root.rotation.set(0, 0, 0);
    root.scale.setScalar(1);
    root.visible = true;
    pumpkin.visible = true;
    sword.visible = false;
    sheath.visible = true;
    sword.rotation.set(Math.PI / 2, 0, 0);
    blade.material.emissiveIntensity = 0;
    swordFire.mesh.visible = false;
    embers.points.visible = true;
    swordSparks.points.visible = false;
    g.setFace('angry');
    g.mounted = false;
    for (const m of Object.values(mats)) { m.transparent = false; m.opacity = 1; }
  };
  // sentado a caballo
  g.sit = () => {
    legR.rotation.set(-0.6, 0, -0.42);
    legL.rotation.set(-0.6, 0, 0.42);
    armR.rotation.set(-0.7, 0, 0.1);
    armL.rotation.set(-0.7, 0, -0.1);
  };
  g.walk = (ph, amt = 1) => {
    const s = Math.sin(ph * 2.4);
    legR.rotation.x = s * 0.55 * amt;
    legL.rotation.x = -s * 0.55 * amt;
    armR.rotation.x = -s * 0.35 * amt;
    armL.rotation.x = s * 0.35 * amt;
    hips.position.y = 0.95 + Math.abs(Math.cos(ph * 2.4)) * 0.04 * amt;
    capeA.rotation.x = 0.12 * amt + Math.sin(ph * 2.4) * 0.03;
  };
  // capa al viento segun velocidad (0..1)
  g.wind = (t, v) => {
    capeA.rotation.x = 0.15 + 0.9 * v + Math.sin(t * 9) * 0.08 * v;
    capeB.rotation.x = 0.1 + 0.5 * v + Math.sin(t * 11 + 1) * 0.15 * v;
    capeA.rotation.z = Math.sin(t * 5) * 0.05 * v;
  };
  const _p = new THREE.Vector3();
  g.updateFx = (t, k = 1, gold = 0) => {
    root.updateMatrixWorld(true);
    head.getWorldPosition(_p);
    embers.set(t, { center: [_p.x, _p.y + 0.25, _p.z], opacity: Math.min(1, k * 1.2), mix: gold });
    embers.points.visible = pumpkin.visible && k > 0.02;
  };
  g.updateSparks = (t, on) => {
    swordSparks.points.visible = on;
    if (!on) return;
    blade.getWorldPosition(_p);
    swordSparks.set(t, { center: [_p.x, _p.y, _p.z] });
  };
  g.reset();
  return g;
}
const lerp = (a, b, t) => a + (b - a) * t;

// ---------------------------------------------------------------------------
// CABALLO NEGRO
// ---------------------------------------------------------------------------
export function makeHorse() {
  const root = new THREE.Group();
  const hide = std(hideTex(), { roughness: 0.7 });
  const mane = std(maneTex(), { roughness: 1 });
  const hoof = new THREE.MeshStandardMaterial({ color: 0x050506, roughness: 0.6 });
  const eyeM = new THREE.MeshStandardMaterial({ color: 0xff2010, emissive: new THREE.Color(1, 0.08, 0.02), emissiveIntensity: 3 });
  const saddleM = std(leatherTex(0x2a1810));
  const trim = new THREE.MeshStandardMaterial({ color: 0x6a1010, roughness: 0.7 });
  // pivote trasero para encabritarse
  const rear = pivot(root, 0, 0, -0.62);
  const body = pivot(rear, 0, 0, 0.62);
  box(body, 0.72, 0.74, 1.6, hide, 0, 1.38, 0);
  box(body, 0.76, 0.12, 0.62, saddleM, 0, 1.79, -0.08);
  box(body, 0.78, 0.04, 0.64, trim, 0, 1.73, -0.08);
  box(body, 0.06, 0.45, 0.08, saddleM, 0.38, 1.5, 0);
  box(body, 0.06, 0.45, 0.08, saddleM, -0.38, 1.5, 0);
  const legs = [];
  const fires = [];
  for (const [x, z, front] of [[-0.22, 0.62, 1], [0.22, 0.62, 1], [-0.22, -0.62, 0], [0.22, -0.62, 0]]) {
    const l = pivot(body, x, 1.12, z);
    box(l, 0.24, 0.98, 0.26, hide, 0, -0.49, 0);
    box(l, 0.27, 0.16, 0.29, hoof, 0, -1.04, 0.01);
    const f = new Fire([{ x: 0, y: -1.14, z: 0.02, w: 0.42, h: 0.5 }, { x: 0.05, y: -1.14, z: -0.05, w: 0.28, h: 0.35 }], { orange: true, bright: 0.9, seed: 90 + legs.length, speed: 4.5 });
    l.add(f.mesh);
    fires.push(f);
    l.userData.front = front;
    legs.push(l);
  }
  const neck = pivot(body, 0, 1.55, 0.7);
  box(neck, 0.36, 0.95, 0.5, hide, 0, 0.42, 0.02);
  box(neck, 0.12, 0.95, 0.2, mane, 0, 0.5, -0.27);
  neck.rotation.x = 0.55;
  const head = pivot(neck, 0, 0.88, 0.06);
  box(head, 0.38, 0.38, 0.8, hide, 0, 0.0, 0.28);
  box(head, 0.32, 0.26, 0.3, hide, 0, -0.07, 0.66);
  box(head, 0.08, 0.16, 0.08, hide, -0.12, 0.26, 0.0);
  box(head, 0.08, 0.16, 0.08, hide, 0.12, 0.26, 0.0);
  box(head, 0.12, 0.2, 0.3, mane, 0, 0.22, -0.02);
  const eyes = [box(head, 0.05, 0.08, 0.1, eyeM, -0.195, 0.06, 0.32), box(head, 0.05, 0.08, 0.1, eyeM, 0.195, 0.06, 0.32)];
  head.rotation.x = 0.15;
  const tail = pivot(body, 0, 1.6, -0.82);
  box(tail, 0.16, 0.9, 0.16, mane, 0, -0.42, -0.02);
  tail.rotation.x = 0.4;
  const saddle = pivot(body, 0, 1.82, -0.05); // punto de montura
  const g = { root, rear, body, legs, fires, neck, head, tail, eyes, eyeM, saddle, mats: [hide, mane, hoof, saddleM, trim] };
  g.reset = () => {
    root.visible = true;
    root.position.set(0, 0, 0);
    root.rotation.set(0, 0, 0);
    rear.rotation.set(0, 0, 0);
    body.position.set(0, 0, 0.62);
    body.rotation.set(0, 0, 0);
    neck.rotation.set(0.55, 0, 0);
    head.rotation.set(0.15, 0, 0);
    tail.rotation.set(0.4, 0, 0);
    for (const l of legs) l.rotation.set(0, 0, 0);
    eyeM.emissiveIntensity = 3;
    eyeM.emissive.setRGB(1, 0.08, 0.02);
    for (const m of g.mats) { m.transparent = false; m.opacity = 1; }
  };
  g.hoofFire = (t, k = 1) => {
    for (const f of fires) { f.set(t, { bright: 0.9 * k, flare: 0.5 + 0.6 * k }); f.mesh.visible = k > 0.01; }
  };
  // galope: ph = fase en radianes; amt 0..1
  g.gallop = (ph, amt = 1) => {
    const A = 0.75 * amt;
    const off = [0, 0.35, Math.PI, Math.PI + 0.35];
    legs.forEach((l, i) => { l.rotation.x = Math.sin(ph + off[i]) * A * (l.userData.front ? 1.1 : 0.9) + (l.userData.front ? -0.1 : 0.1) * amt; });
    body.position.y = Math.abs(Math.sin(ph)) * 0.18 * amt;
    body.rotation.x = Math.sin(ph + 0.6) * 0.07 * amt;
    neck.rotation.x = 0.7 + Math.sin(ph + 1.2) * 0.12 * amt;
    head.rotation.x = 0.05 + Math.sin(ph + 2) * 0.1 * amt;
    tail.rotation.x = 0.4 + 0.6 * amt + Math.sin(ph * 2) * 0.1 * amt;
  };
  g.walk = (ph, amt = 1) => {
    const A = 0.35 * amt;
    const off = [0, Math.PI * 0.5, Math.PI, Math.PI * 1.5];
    legs.forEach((l, i) => { l.rotation.x = Math.sin(ph + off[i]) * A; });
    body.position.y = Math.abs(Math.sin(ph * 2)) * 0.03 * amt;
    neck.rotation.x = 0.55 + Math.sin(ph * 2) * 0.05 * amt;
  };
  // encabritarse (k 0..1)
  g.rear = (k, t = 0) => {
    rear.rotation.x = -0.95 * k;
    const [fr, fl, br, bl] = legs;
    fr.rotation.x = -1.3 * k + Math.sin(t * 12) * 0.5 * k;
    fl.rotation.x = -0.9 * k + Math.sin(t * 12 + 2) * 0.5 * k;
    br.rotation.x = 0.95 * k + 0.1 * k;
    bl.rotation.x = 0.95 * k - 0.1 * k;
    neck.rotation.x = 0.55 - 0.5 * k;
    head.rotation.x = 0.15 - 0.35 * k;
    tail.rotation.x = 0.4 + 0.4 * k;
  };
  g.reset();
  return g;
}

// ---------------------------------------------------------------------------
// NINO disfrazado de espantapajaros con farol
// ---------------------------------------------------------------------------
export function makeScarecrowKid() {
  const v = makeVillager('scarecrow');
  v.root.scale.setScalar(0.6);
  v.head.scale.setScalar(1.3);
  const straw = new THREE.MeshStandardMaterial({ map: blockTex('hay_top'), roughness: 1 });
  const strawDark = new THREE.MeshStandardMaterial({ map: blockTex('hay_side'), roughness: 1 });
  // sombrero de paja
  box(v.head, 0.9, 0.06, 0.9, straw, 0, 0.66, 0);
  box(v.head, 0.5, 0.26, 0.5, strawDark, 0, 0.8, 0);
  // mechones de paja
  for (const [x, y, z, sx, sy, sz] of [[-0.27, 0.4, 0.1, 0.1, 0.2, 0.4], [0.27, 0.4, 0.1, 0.1, 0.2, 0.4], [0, 0.42, -0.27, 0.5, 0.2, 0.08]]) box(v.head, sx, sy, sz, straw, x, y, z);
  for (const s of [-1, 1]) box(v.arms, 0.14, 0.12, 0.16, straw, s * 0.375, -0.05, 0.22);
  const lan = makeLantern(false);
  lan.scale.setScalar(0.7);
  lan.position.set(0.25, -0.32, 0.28);
  v.arms.add(lan);
  v.lantern = lan;
  v.light = new THREE.PointLight(0xffb060, 3, 6, 2);
  v.light.position.set(0.25, -0.1, 0.4);
  v.arms.add(v.light);
  const reset0 = v.reset;
  v.reset = () => {
    reset0();
    v.arms.rotation.set(0, 0, 0);
    v.arms.position.set(0, 0.6, 0.15);
    v.lantern.visible = true;
    v.light.intensity = 3;
    v.root.scale.setScalar(0.6);
  };
  v.sit = () => {
    v.legL.rotation.set(-0.8, 0, 0.4);
    v.legR.rotation.set(-0.8, 0, -0.4);
  };
  v.reset();
  return v;
}
