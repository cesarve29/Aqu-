// Personajes de bloques: heroe, zombi, esqueleto, explosivo, arana y dragona.
import * as THREE from 'three';
import { lerp, clamp, smooth } from './util.js';

function faceTex(rows, pal) {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 8;
  const g = cv.getContext('2d');
  rows.forEach((r, y) => [...r].forEach((ch, x) => { g.fillStyle = pal[ch]; g.fillRect(x, y, 1, 1); }));
  const t = new THREE.CanvasTexture(cv);
  t.magFilter = t.minFilter = THREE.NearestFilter;
  t.generateMipmaps = false;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
function noiseTex(c1, c2, seed, n = 8) {
  const cv = document.createElement('canvas');
  cv.width = cv.height = n;
  const g = cv.getContext('2d');
  let s = seed;
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { g.fillStyle = r() < 0.5 ? c1 : c2; g.fillRect(x, y, 1, 1); }
  const t = new THREE.CanvasTexture(cv);
  t.magFilter = t.minFilter = THREE.NearestFilter;
  t.generateMipmaps = false;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

class Mats {
  constructor() { this.list = []; }
  m(color, opt = {}) {
    const mat = new THREE.MeshLambertMaterial({ color, ...opt });
    this.list.push(mat);
    return mat;
  }
  glow(color, k = 3) {
    const mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(k) });
    return mat;
  }
  tint(r, g, b, k) {
    for (const m of this.list) { m.emissive.setRGB(r * k, g * k, b * k); }
  }
}

function box(w, h, d, mat, parent, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  if (parent) parent.add(m);
  return m;
}
function pivot(parent, x, y, z) {
  const g = new THREE.Group();
  g.position.set(x, y, z);
  parent.add(g);
  return g;
}

const FACES = {
  hero: [['HHHHHHHH', 'HHHHHHHH', 'HSSSSSSH', 'SSSSSSSS', 'SWBSSBWS', 'SSSNNSSS', 'SSMMMMSS', 'SSSSSSSS'],
    { H: '#4a2f1b', S: '#d9a27a', W: '#ffffff', B: '#2b52c9', N: '#b67a58', M: '#8a4a3a' }],
  zombie: [['GGGGGGGG', 'GgGGGgGG', 'GGGGGGGG', 'GGGGGGGG', 'GKKGGKKG', 'GGGddGGG', 'GGdddDGG', 'GGGGGGGG'],
    { G: '#4f8a3c', g: '#3d6e2e', K: '#101010', d: '#2a4a22', D: '#1c3517' }],
  skeleton: [['LLLLLLLL', 'LLLLLLLL', 'LLLLLLLL', 'LKKLLKKL', 'LKKLLKKL', 'LLLKKLLL', 'LKKKKKKL', 'LLLLLLLL'],
    { L: '#c9c9c9', K: '#3a3a3a' }],
  creeper: [['GgGGgGGG', 'GGgGGGgG', 'GKKGGKKG', 'GKKGGKKG', 'GgGKKGGg', 'GGKKKKGG', 'GGKKKKGG', 'GGKGGKGG'],
    { G: '#5fba48', g: '#3f8a30', K: '#0b0b0b' }],
};

function headMats(M, color, face) {
  const f = faceTex(FACES[face][0], FACES[face][1]);
  const side = M.m(color);
  const front = M.m(0xffffff, { map: f });
  return [side, side, side, side, front, side];
}

// ------------------------------------------------------------- humanoides
export function humanoid(kind) {
  const M = new Mats();
  const root = new THREE.Group();
  const P = {
    hero: { skin: 0xd9a27a, shirt: 0x2aa6a6, pants: 0x3a3f9a, shoes: 0x3b3b3b, hair: 0x4a2f1b, limb: 0.25 },
    zombie: { skin: 0x4f8a3c, shirt: 0x2f8ea0, pants: 0x3b3a8c, shoes: 0x2f2f6a, limb: 0.25 },
    skeleton: { skin: 0xc9c9c9, shirt: 0xc9c9c9, pants: 0xbdbdbd, shoes: 0xa9a9a9, limb: 0.12 },
  }[kind];
  const L = P.limb;
  const body = pivot(root, 0, 0.75, 0);
  const torso = box(0.5, 0.75, kind === 'skeleton' ? 0.16 : 0.25, M.m(P.shirt), body, 0, 0.375, 0);
  if (kind === 'skeleton') { torso.scale.x = 0.7; }
  const headP = pivot(body, 0, 0.75, 0);
  box(0.5, 0.5, 0.5, headMats(M, kind === 'hero' ? P.skin : P.skin, kind), headP, 0, 0.25, 0);
  if (kind === 'hero') {
    box(0.54, 0.14, 0.54, M.m(P.hair), headP, 0, 0.47, -0.01);
    box(0.54, 0.34, 0.08, M.m(P.hair), headP, 0, 0.27, -0.24);
  }
  const arm = (sx) => {
    const a = pivot(body, sx * (0.25 + L / 2), 0.68, 0);
    if (kind === 'skeleton') box(L, 0.75, L, M.m(P.skin), a, 0, -0.3, 0);
    else {
      box(L + 0.01, 0.25, L + 0.01, M.m(P.shirt), a, 0, -0.05, 0);
      box(L, 0.5, L, M.m(P.skin), a, 0, -0.42, 0);
    }
    return a;
  };
  const armL = arm(1), armR = arm(-1);
  const leg = (sx) => {
    const l = pivot(root, sx * 0.125, 0.75, 0);
    box(L, 0.62, L, M.m(P.pants), l, 0, -0.31, 0);
    box(L + 0.01, 0.14, L + 0.01, M.m(P.shoes), l, 0, -0.68, 0);
    return l;
  };
  const legL = leg(1), legR = leg(-1);
  const hand = pivot(armR, 0, -0.66, 0.04);
  const handL = pivot(armL, 0, -0.66, 0.04);
  root.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  return { kind, root, body, headP, armL, armR, legL, legR, hand, handL, M };
}

export function makeSword(scale = 1) {
  const g = new THREE.Group();
  const blade = new THREE.MeshLambertMaterial({ color: 0x5ff2e2, emissive: 0x0b5a54 });
  const edge = new THREE.MeshLambertMaterial({ color: 0xbffff8, emissive: 0x1d8f86 });
  const dark = new THREE.MeshLambertMaterial({ color: 0x163c3a });
  const wood = new THREE.MeshLambertMaterial({ color: 0x6b4a26 });
  const s = scale;
  box(0.09 * s, 0.62 * s, 0.035 * s, blade, g, 0, 0.42 * s, 0);
  box(0.03 * s, 0.6 * s, 0.04 * s, edge, g, 0.025 * s, 0.43 * s, 0);
  box(0.06 * s, 0.08 * s, 0.03 * s, blade, g, 0, 0.76 * s, 0);
  box(0.28 * s, 0.06 * s, 0.06 * s, dark, g, 0, 0.1 * s, 0);
  box(0.06 * s, 0.2 * s, 0.05 * s, wood, g, 0, -0.03 * s, 0);
  box(0.08 * s, 0.05 * s, 0.06 * s, dark, g, 0, -0.14 * s, 0);
  return g;
}
export function makeBow(scale = 1) {
  const g = new THREE.Group();
  const wood = new THREE.MeshLambertMaterial({ color: 0x7a5530 });
  const str = new THREE.MeshBasicMaterial({ color: 0xdddddd });
  const s = scale;
  const segs = [[0, 0, 0.0, 0.22], [0, 0.2, -0.06, 0.2], [0, -0.2, -0.06, 0.2], [0, 0.36, -0.14, 0.16], [0, -0.36, -0.14, 0.16]];
  segs.forEach(([x, y, z, h], i) => {
    const m = box(0.05 * s, h * s, 0.05 * s, wood, g, x, y * s, z * s);
    m.rotation.x = i === 0 ? 0 : (y > 0 ? -0.5 : 0.5) * (i > 2 ? 1.4 : 1);
  });
  const sm = box(0.012 * s, 0.82 * s, 0.012 * s, str, g, 0, 0, -0.2 * s);
  g.userData.string = sm;
  return g;
}
export function makeArrow() {
  const g = new THREE.Group();
  box(0.03, 0.03, 0.62, new THREE.MeshLambertMaterial({ color: 0x8a6a40 }), g, 0, 0, 0);
  box(0.06, 0.06, 0.08, new THREE.MeshLambertMaterial({ color: 0x777777 }), g, 0, 0, 0.32);
  box(0.12, 0.012, 0.12, new THREE.MeshLambertMaterial({ color: 0xeeeeee }), g, 0, 0, -0.26);
  box(0.012, 0.12, 0.12, new THREE.MeshLambertMaterial({ color: 0xeeeeee }), g, 0, 0, -0.26);
  return g;
}

// pose comun de humanoides
export function poseHumanoid(h, o) {
  const walk = o.walk || 0, ph = o.phase || 0;
  const a = Math.sin(ph) * 0.75 * walk;
  h.legL.rotation.set(a, 0, 0);
  h.legR.rotation.set(-a, 0, 0);
  h.armL.rotation.set(-a * 0.8, 0, 0.04);
  h.armR.rotation.set(a * 0.8, 0, -0.04);
  h.body.rotation.set(0, 0, 0);
  h.body.position.y = 0.75 + Math.abs(Math.sin(ph)) * 0.04 * walk;
  h.headP.rotation.set(o.pitch || 0, o.headYaw || 0, 0);
  const idle = Math.sin((o.t || 0) * 1.7) * 0.04;
  h.armL.rotation.z += idle; h.armR.rotation.z -= idle;
  if (o.armsForward) {
    h.armL.rotation.x = -1.45 + Math.sin(ph * 0.5) * 0.08;
    h.armR.rotation.x = -1.45 - Math.sin(ph * 0.5) * 0.08;
  }
  if (o.swing >= 0) {
    const s = o.swing;
    const r = s < 0.28 ? lerp(-0.3, -2.7, smooth(s / 0.28)) : lerp(-2.7, -0.35, smooth((s - 0.28) / 0.45));
    h.armR.rotation.x = r;
    h.armR.rotation.z = -0.2;
    h.body.rotation.y = -Math.sin(s * Math.PI) * 0.35;
  }
  if (o.raise > 0) { h.armR.rotation.x = lerp(h.armR.rotation.x, -3.0, o.raise); h.armR.rotation.z = lerp(h.armR.rotation.z, 0.15, o.raise); }
  if (o.bow > 0 || o.bowHold) {
    h.armL.rotation.set(-1.55, 0.1, 0.1);
    h.armR.rotation.set(-1.55, -0.6 + 0.3 * (1 - o.bow), -0.1);
  }
  if (o.dead > 0) {
    h.root.rotation.z = smooth(o.dead) * Math.PI / 2;
  } else h.root.rotation.z = 0;
}

// ---------------------------------------------------------------- explosivo
export function creeper() {
  const M = new Mats();
  const root = new THREE.Group();
  const skin = new THREE.MeshLambertMaterial({ map: noiseTex('#5fba48', '#3f8a30', 7) });
  M.list.push(skin);
  const body = pivot(root, 0, 0.36, 0);
  box(0.5, 0.75, 0.25, skin, body, 0, 0.375, 0);
  const headP = pivot(body, 0, 0.75, 0);
  const f = faceTex(FACES.creeper[0], FACES.creeper[1]);
  const fm = new THREE.MeshLambertMaterial({ map: f });
  M.list.push(fm);
  box(0.5, 0.5, 0.5, [skin, skin, skin, skin, fm, skin], headP, 0, 0.25, 0);
  const legs = [];
  for (const [x, z] of [[-0.13, 0.25], [0.13, 0.25], [-0.13, -0.25], [0.13, -0.25]]) {
    const l = pivot(root, x, 0.36, z);
    box(0.25, 0.36, 0.25, skin, l, 0, -0.18, 0);
    legs.push(l);
  }
  return { kind: 'creeper', root, body, headP, legs, M };
}
export function poseCreeper(c, o) {
  const a = Math.sin(o.phase || 0) * 0.6 * (o.walk || 0);
  c.legs[0].rotation.x = a; c.legs[3].rotation.x = a;
  c.legs[1].rotation.x = -a; c.legs[2].rotation.x = -a;
  const f = o.fuse || 0;
  const s = 1 + f * 0.25 + Math.sin(f * 40) * 0.03 * f;
  c.body.scale.set(s, 1 + f * 0.12, s);
  c.headP.rotation.x = o.pitch || 0;
}

// ---------------------------------------------------------------- arana
export function spider() {
  const M = new Mats();
  const root = new THREE.Group();
  const dark = M.m(0x2c2622), darker = M.m(0x1b1714);
  const body = pivot(root, 0, 0.55, 0);
  box(0.9, 0.7, 1.0, dark, body, 0, 0.1, -0.55);
  box(0.6, 0.5, 0.45, darker, body, 0, 0.0, 0.05);
  const head = box(0.62, 0.58, 0.55, dark, body, 0, 0.05, 0.5);
  const eye = M.glow(0xff2020, 4);
  for (const [x, y] of [[-0.18, 0.12], [0.18, 0.12], [-0.08, 0.2], [0.08, 0.2], [-0.24, 0.0], [0.24, 0.0]]) box(0.08, 0.06, 0.02, eye, head, x, y, 0.28);
  const legs = [];
  for (let i = 0; i < 8; i++) {
    const side = i < 4 ? 1 : -1, k = i % 4;
    const l = pivot(body, side * 0.28, 0.0, 0.25 - k * 0.2);
    const seg = box(1.1, 0.12, 0.12, darker, l, side * 0.55, 0, 0);
    l.rotation.y = side * (k - 1.5) * 0.35;
    l.userData = { side, k, baseY: l.rotation.y };
    legs.push(l);
  }
  return { kind: 'spider', root, body, legs, M };
}
export function poseSpider(s, o) {
  const ph = o.phase || 0, w = o.walk || 0;
  s.legs.forEach((l, i) => {
    const { side, k, baseY } = l.userData;
    const off = (k % 2 ? Math.PI : 0) + (side > 0 ? 0 : Math.PI);
    l.rotation.z = side * (0.45 + Math.max(0, Math.sin(ph * 1.4 + off)) * 0.35 * w);
    l.rotation.y = baseY + Math.sin(ph * 1.4 + off) * 0.25 * w;
  });
  s.root.rotation.z = (o.dead || 0) > 0 ? Math.PI * smooth(o.dead) : 0;
}

// ---------------------------------------------------------------- dragona
export function dragon() {
  const M = new Mats();
  const root = new THREE.Group();
  const hide = M.m(0x2a2733), belly = M.m(0x3b3747), plate = M.m(0x4a4558), horn = M.m(0xd8d0c8);
  const eye = M.glow(0xd36bff, 6);
  const body = pivot(root, 0, 0, 0);
  box(3.0, 2.4, 6.0, hide, body, 0, 0, 0);
  box(2.6, 0.5, 5.4, belly, body, 0, -1.3, 0);
  for (let i = 0; i < 5; i++) box(0.35, 0.8, 0.6, plate, body, 0, 1.5, -2.2 + i * 1.1);
  // cuello
  const neck = [];
  let parent = pivot(body, 0, 0.6, 2.8);
  for (let i = 0; i < 6; i++) {
    const seg = pivot(parent, 0, 0, i === 0 ? 0 : 1.15);
    box(1.25, 1.25, 1.3, hide, seg, 0, 0, 0.55);
    box(0.25, 0.45, 0.5, plate, seg, 0, 0.8, 0.55);
    neck.push(seg);
    parent = seg;
  }
  const headP = pivot(parent, 0, 0, 1.3);
  box(2.0, 1.5, 2.2, hide, headP, 0, 0.1, 0.9);
  box(1.5, 0.8, 1.9, hide, headP, 0, -0.05, 2.9);
  for (const sx of [-1, 1]) {
    box(0.3, 0.2, 0.4, plate, headP, sx * 0.4, 0.42, 3.4);
    box(0.25, 0.25, 0.9, horn, headP, sx * 0.6, 1.0, 0.0).rotation.x = -0.5;
    box(0.36, 0.2, 0.08, eye, headP, sx * 0.75, 0.38, 2.0);
  }
  const jaw = pivot(headP, 0, -0.45, 1.6);
  box(1.4, 0.4, 2.0, belly, jaw, 0, -0.15, 1.1);
  // cola
  const tail = [];
  parent = pivot(body, 0, 0.3, -3.0);
  for (let i = 0; i < 11; i++) {
    const seg = pivot(parent, 0, 0, i === 0 ? 0 : -1.05);
    const s = 1.15 - i * 0.06;
    box(s, s, 1.1, hide, seg, 0, 0, -0.5);
    if (i % 2 === 0) box(0.22, 0.42, 0.5, plate, seg, 0, s / 2 + 0.2, -0.5);
    tail.push(seg);
    parent = seg;
  }
  // alas
  const memb = new THREE.MeshLambertMaterial({ color: 0x2a2732, side: THREE.DoubleSide, transparent: true, opacity: 0.92 });
  M.list.push(memb);
  const wings = [];
  for (const sx of [1, -1]) {
    const w = pivot(body, sx * 1.4, 0.9, 1.0);
    box(7.0, 0.45, 0.45, hide, w, sx * 3.5, 0, 0);
    const m1 = new THREE.Mesh(new THREE.PlaneGeometry(7, 5.5), memb);
    m1.rotation.x = -Math.PI / 2; m1.position.set(sx * 3.5, -0.05, -2.8); m1.castShadow = true;
    w.add(m1);
    const tip = pivot(w, sx * 7.0, 0, 0);
    box(6.0, 0.35, 0.35, hide, tip, sx * 3.0, 0, 0);
    const m2 = new THREE.Mesh(new THREE.PlaneGeometry(6, 4.5), memb);
    m2.rotation.x = -Math.PI / 2; m2.position.set(sx * 3.0, -0.05, -2.3); m2.castShadow = true;
    tip.add(m2);
    wings.push({ w, tip, sx });
  }
  // patas
  const legs = [];
  for (const [x, z] of [[-1.2, 2], [1.2, 2], [-1.2, -2], [1.2, -2]]) {
    const l = pivot(body, x, -1.1, z);
    box(0.7, 1.8, 0.8, hide, l, 0, -0.8, 0);
    box(0.9, 0.3, 1.2, plate, l, 0, -1.75, 0.2);
    legs.push(l);
  }
  root.traverse((o) => { if (o.isMesh) o.castShadow = true; });
  const parts = [];
  root.traverse((o) => { if (o.isMesh) parts.push(o); });
  return { kind: 'dragon', root, body, neck, headP, jaw, tail, wings, legs, M, parts };
}

export function poseDragon(d, o) {
  const t = o.t, flap = o.flap ?? 1;
  const ph = t * (o.flapSpeed || 3.2);
  for (const { w, tip, sx } of d.wings) {
    const a = Math.sin(ph) * 0.65 * flap + (o.fold || 0) * 0.9;
    w.rotation.z = sx * a;
    tip.rotation.z = sx * (Math.sin(ph - 0.9) * 0.55 * flap + (o.fold || 0) * 0.6);
  }
  d.body.position.y = -Math.sin(ph) * 0.35 * flap;
  const np = o.neckPitch || 0, ny = o.neckYaw || 0;
  d.neck.forEach((s, i) => {
    s.rotation.x = np / 6 + Math.sin(t * 1.3 - i * 0.6) * 0.04;
    s.rotation.y = ny / 6 + Math.sin(t * 0.9 - i * 0.5) * 0.05;
  });
  d.headP.rotation.x = (o.headPitch || 0);
  d.jaw.rotation.x = (o.jaw || 0) * 0.7;
  d.tail.forEach((s, i) => {
    s.rotation.y = Math.sin(t * 1.6 - i * 0.55) * 0.09;
    s.rotation.x = Math.sin(t * 1.1 - i * 0.4) * 0.05 + (o.tailDown || 0) * 0.03;
  });
  d.legs.forEach((l, i) => { l.rotation.x = (o.perch ? 0 : 0.7) + Math.sin(t * 1.5 + i) * 0.05; });
}
