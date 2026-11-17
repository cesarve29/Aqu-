// Personajes voxel articulados: Jon y Daenerys.
import * as THREE from 'three';
import { Grid, meshGrid, voxMaterial, jitter, shade, mix, hash3, lerp, clamp } from './voxel.js';

export const CV = 1 / 32; // tamano de voxel de personaje (m)

const MAT = voxMaterial({ roughness: 0.85, key: 'char' });

function partMesh(grid, pivot) {
  const m = new THREE.Mesh(meshGrid(grid, { scale: CV, origin: pivot }), MAT);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

// ---------------------------------------------------------------------------
// Cabezas
// ---------------------------------------------------------------------------
const SKIN_J = 0xe2a888, SKIN_D = 0xf2c8b0;
const HAIR_J = 0x1c1512, HAIR_J2 = 0x2a1e18, BEARD_J = 0x231a15;
const HAIR_D = 0xe8e0cc, HAIR_D2 = 0xcfc4a8;

// cara frontal en z = 14 (rejilla 16x19x17); cubo de cara x1..14, y3..16, z1..14
function buildHead(kind, ex) {
  const g = new Grid(16, 19, 17);
  const isJ = kind === 'jon';
  const skin = isJ ? SKIN_J : SKIN_D;
  const hair = isJ ? HAIR_J : HAIR_D, hair2 = isJ ? HAIR_J2 : HAIR_D2;
  // craneo
  g.box(1, 3, 1, 14, 16, 14, (x, y, z) => jitter(skin, 0.05, x, y, z));
  // mandibula un poco mas estrecha
  for (const x of [1, 14]) for (let z = 10; z <= 14; z++) { g.clear(x, 3, z); g.clear(x, 4, z); }
  // pelo: capa superior/trasera/lateral
  const H = (x, y, z) => jitter(hash3(x, y >> 1, z) < 0.35 ? hair2 : hair, 0.12, x, y, z);
  g.box(0, 15, 0, 15, 18, 15, H);            // coronilla
  g.box(0, 3, 0, 15, 16, 2, H);              // nuca
  g.box(0, 8, 0, 0, 17, 13, H);              // lados
  g.box(15, 8, 0, 15, 17, 13, H);
  g.box(1, 16, 13, 14, 17, 15, H);           // flequillo / frente
  if (isJ) {
    // pelo largo y ondulado cayendo por los lados y detras
    g.box(0, 2, 1, 0, 9, 9, H); g.box(15, 2, 1, 15, 9, 9, H);
    g.box(0, 0, 0, 15, 3, 3, H);
    // mechones sobre la frente
    g.set(4, 15, 15, hair); g.set(5, 15, 15, hair); g.set(11, 15, 15, hair); g.set(2, 14, 15, hair);
    g.box(1, 16, 15, 3, 17, 15, H); g.box(12, 16, 15, 14, 17, 15, H);
    // mono atras
    g.box(6, 13, 0, 9, 16, 0, H);
  } else {
    // trenzas plateadas
    g.box(0, 2, 0, 15, 4, 4, H);
    for (let y = 0; y < 17; y++) { g.set(0, y, 6, hash3(y, 1, 1) < 0.5 ? hair2 : hair); g.set(15, y, 6, hash3(y, 2, 1) < 0.5 ? hair2 : hair); }
    for (let z = 2; z < 14; z++) { g.set(3, 18, z, hair2); g.set(12, 18, z, hair2); }
    g.box(0, 6, 1, 0, 15, 12, H); g.box(15, 6, 1, 15, 15, 12, H);
  }
  // facciones en la cara (z = 14) y nariz (z = 15)
  const FZ = 14;
  const dark = 0x2a1d1a, white = 0xe8e4de, iris = isJ ? 0x3b2a20 : 0x6b5a7a;
  const browCol = isJ ? 0x1a1310 : 0xbcae94;
  // ojos y = 9..10
  const eyeL = [3, 4, 5], eyeR = [10, 11, 12];
  for (const xs of [eyeL, eyeR]) {
    if (ex.eyes === 'closed') {
      for (const x of xs) g.set(x, 9, FZ, shade(skin, 0.62));
      for (const x of xs) g.set(x, 10, FZ, shade(skin, 0.9));
    } else if (ex.eyes === 'squint') {
      for (const x of xs) g.set(x, 9, FZ, shade(skin, 0.6));
      g.set(xs[1], 10, FZ, dark); g.set(xs[0], 10, FZ, white); g.set(xs[2], 10, FZ, white);
    } else {
      g.set(xs[0], 10, FZ, white); g.set(xs[2], 10, FZ, white); g.set(xs[1], 10, FZ, iris);
      g.set(xs[0], 9, FZ, white); g.set(xs[2], 9, FZ, white); g.set(xs[1], 9, FZ, dark);
      if (ex.eyes === 'up') { g.set(xs[1], 9, FZ, white); g.set(xs[1], 10, FZ, dark); }
    }
    // parpado superior
    for (const x of xs) g.set(x, 11, FZ, shade(skin, 0.8));
    // lagrimas / ojos rojos
    if (ex.tears) { g.set(xs[0], 8, FZ, 0xc79a8f); g.set(xs[2], 8, FZ, 0xc79a8f); }
  }
  // cejas
  const browY = 12;
  for (const [x0, inner] of [[2, 6], [9, 9]]) {
    for (let x = x0; x < x0 + 5; x++) {
      let y = browY;
      if (ex.brow === 'sad' && (x === inner || x === inner - 1 + (inner === 9 ? 1 : 0))) y = browY + 1;
      if (ex.brow === 'fear') y = browY + 1;
      g.set(x, y, FZ, browCol);
      if (isJ) g.set(x, y, FZ + 1, browCol);
    }
  }
  // nariz
  g.box(7, 6, FZ + 1, 8, 9, FZ + 1, (x, y, z) => jitter(skin, 0.06, x, y, z));
  g.set(7, 6, FZ + 1, shade(skin, 0.8)); g.set(8, 6, FZ + 1, shade(skin, 0.8));
  // mejillas sonrosadas / ojeras
  for (const x of [3, 4, 11, 12]) g.set(x, 8, FZ, shade(skin, ex.tears ? 0.9 : 0.96));
  // boca y barba
  const lip = isJ ? 0x8a5a50 : 0xb67a74;
  const mouthY = 5;
  if (isJ) {
    // barba
    const B = (x, y, z) => jitter(hash3(x, y, z) < 0.3 ? 0x3a2b22 : BEARD_J, 0.15, x, y, z);
    g.box(1, 3, 10, 14, 5, FZ, B);
    g.box(1, 3, 6, 2, 8, FZ, B); g.box(13, 3, 6, 14, 8, FZ, B);
    g.box(4, 6, FZ, 11, 6, FZ, B); // bigote
    g.box(3, 2, 9, 12, 2, 14, B);  // menton
    g.box(1, 3, FZ + 1, 14, 4, FZ + 1, B); // barba sobresale
    g.box(5, 3, FZ + 2, 10, 3, FZ + 2, B);
  }
  // boca
  if (ex.mouth === 'open') {
    for (let x = 6; x <= 9; x++) { g.set(x, mouthY, FZ + (isJ ? 1 : 0), 0x2a1210); g.set(x, mouthY - 1, FZ + (isJ ? 1 : 0), 0x3a1a16); }
    if (isJ) { g.set(6, mouthY, FZ + 1, 0xd8d0c4); g.set(7, mouthY, FZ + 1, 0xd8d0c4); }
  } else if (ex.mouth === 'grit') {
    for (let x = 5; x <= 10; x++) g.set(x, mouthY, FZ + (isJ ? 1 : 0), x % 2 ? 0xd8d0c4 : 0xc8c0b4);
  } else if (ex.mouth === 'part') {
    for (let x = 6; x <= 9; x++) g.set(x, mouthY, FZ + (isJ ? 1 : 0), x === 6 || x === 9 ? lip : 0x3a1a16);
  } else {
    for (let x = 6; x <= 9; x++) g.set(x, mouthY, FZ + (isJ ? 1 : 0), lip);
  }
  if (!isJ) { for (let x = 6; x <= 9; x++) g.set(x, mouthY - 1, FZ, shade(lip, 1.1)); }
  // orejas
  if (!isJ) { g.set(0, 9, 8, skin); g.set(15, 9, 8, skin); }
  return g;
}

// ---------------------------------------------------------------------------
// Cuerpos
// ---------------------------------------------------------------------------
function quilted(base, x, y, z) {
  const q = ((x + y) % 4 === 0 || (x - y + 64) % 4 === 0) ? 0.78 : 1;
  return jitter(shade(base, q), 0.1, x, y, z);
}

function jonParts() {
  const LEATHER = 0x3d3936, LEATHER2 = 0x2e2b29, BELT = 0x2a1d16, METAL = 0xa8a8a8, SKIN = SKIN_J, BOOT = 0x1d1715;
  const P = {};
  // torso 16x18x10 (incluye cuello alto)
  let g = new Grid(16, 22, 10);
  g.box(1, 0, 1, 14, 17, 8, (x, y, z) => quilted(LEATHER, x, y, z));
  g.box(0, 12, 1, 15, 17, 8, (x, y, z) => quilted(LEATHER2, x, y, z)); // hombros
  g.box(4, 17, 2, 11, 20, 7, (x, y, z) => jitter(LEATHER2, 0.08, x, y, z)); // cuello alto
  g.box(5, 18, 3, 10, 21, 6, (x, y, z) => jitter(SKIN, 0.05, x, y, z));
  g.box(1, 0, 0, 14, 1, 9, (x, y, z) => jitter(BELT, 0.1, x, y, z)); // cinturon
  g.set(7, 0, 9, METAL); g.set(8, 0, 9, METAL); g.set(7, 1, 9, METAL); g.set(8, 1, 9, METAL);
  // broche de plata en el pecho (lado izq.)
  g.box(10, 12, 9, 12, 14, 9, (x, y, z) => jitter(0xc8c8c8, 0.2, x, y, z)); g.set(11, 15, 9, 0xb0b0b0);
  // correa de cuero diagonal
  for (let y = 2; y < 16; y++) g.set(Math.round(3 + y * 0.6), y, 9, jitter(BELT, 0.2, y, 1, 1));
  P.torso = { g, pivot: [8, 0, 5] };
  // pelvis 16x6x10
  g = new Grid(16, 6, 10);
  g.box(1, 0, 1, 14, 5, 8, (x, y, z) => quilted(LEATHER2, x, y, z));
  P.pelvis = { g, pivot: [8, 6, 5] };
  // brazo superior 7x11x7 (pivote hombro arriba)
  g = new Grid(7, 11, 7);
  g.box(0, 0, 0, 6, 10, 6, (x, y, z) => quilted(LEATHER, x, y, z));
  g.box(0, 7, 0, 6, 10, 6, (x, y, z) => quilted(LEATHER2, x, y, z));
  P.uarm = { g, pivot: [3.5, 10.5, 3.5] };
  // antebrazo + mano 7x12x7
  g = new Grid(7, 12, 7);
  g.box(0, 4, 0, 6, 11, 6, (x, y, z) => jitter(LEATHER2, 0.1, x, y, z));
  g.box(0, 4, 0, 6, 6, 6, (x, y, z) => jitter(BELT, 0.15, x, y, z)); // brazal
  g.box(1, 0, 1, 5, 3, 5, (x, y, z) => jitter(SKIN, 0.06, x, y, z));
  g.box(1, 0, 5, 2, 2, 6, (x, y, z) => jitter(SKIN, 0.06, x, y, z)); // pulgar
  P.farm = { g, pivot: [3.5, 11.5, 3.5] };
  // muslo con faldon del abrigo 8x12x9
  g = new Grid(8, 13, 9);
  g.box(0, 0, 0, 7, 12, 8, (x, y, z) => quilted(LEATHER2, x, y, z));
  P.thigh = { g, pivot: [4, 12.5, 4.5] };
  // espinilla + bota 8x13x10
  g = new Grid(8, 13, 11);
  g.box(0, 0, 0, 7, 12, 7, (x, y, z) => jitter(y < 9 ? BOOT : 0x2a2522, 0.12, x, y, z));
  g.box(0, 0, 8, 7, 2, 10, (x, y, z) => jitter(BOOT, 0.12, x, y, z)); // puntera
  P.shin = { g, pivot: [4, 12.5, 4] };
  // faldon trasero del abrigo
  g = new Grid(16, 16, 2);
  g.box(0, 0, 0, 15, 15, 1, (x, y, z) => quilted(LEATHER2, x, y, z));
  P.skirt = { g, pivot: [8, 15.5, 1] };
  // espada Garra en su vaina (cadera izq.)
  g = new Grid(4, 40, 4);
  g.box(1, 0, 1, 2, 29, 2, (x, y, z) => jitter(0x241a14, 0.1, x, y, z)); // vaina
  g.box(0, 30, 0, 3, 30, 3, (x, y, z) => 0x777777); // guarda
  g.box(1, 31, 1, 2, 36, 2, (x, y, z) => jitter(0x3a2a1a, 0.15, x, y, z)); // empunadura
  g.box(0, 37, 0, 3, 39, 3, (x, y, z) => jitter(0xb8b8b0, 0.2, x, y, z)); // pomo (lobo)
  P.sword = { g, pivot: [2, 32, 2] };
  return P;
}

function danyParts() {
  const COAT = 0x1e1a1c, COAT2 = 0x2b2226, RED = 0x5a1e1e, SKIN = SKIN_D, SILVER = 0xb8b8b8;
  const P = {};
  let g = new Grid(14, 20, 9);
  g.box(1, 0, 1, 12, 15, 7, (x, y, z) => jitter(hash3(x, y >> 1, z) < 0.2 ? COAT2 : COAT, 0.1, x, y, z));
  g.box(0, 11, 1, 13, 15, 7, (x, y, z) => jitter(COAT2, 0.1, x, y, z));
  g.box(4, 15, 2, 9, 18, 6, (x, y, z) => jitter(SKIN, 0.05, x, y, z)); // cuello
  g.box(3, 15, 1, 10, 16, 7, (x, y, z) => jitter(RED, 0.12, x, y, z)); // cuello del abrigo
  // cadena plateada cruzando el pecho
  for (let x = 1; x <= 12; x++) g.set(x, 13 - Math.round(Math.abs(x - 6.5) * 0.25), 8, x % 2 ? SILVER : 0x8a8a8a);
  // puntadas rojas
  P.torso = { g, pivot: [7, 0, 4.5] };
  g = new Grid(14, 6, 9);
  g.box(1, 0, 1, 12, 5, 7, (x, y, z) => jitter(COAT, 0.1, x, y, z));
  P.pelvis = { g, pivot: [7, 6, 4.5] };
  g = new Grid(6, 10, 6);
  g.box(0, 0, 0, 5, 9, 5, (x, y, z) => jitter(COAT, 0.1, x, y, z));
  P.uarm = { g, pivot: [3, 9.5, 3] };
  g = new Grid(6, 11, 6);
  g.box(0, 3, 0, 5, 10, 5, (x, y, z) => jitter(COAT, 0.1, x, y, z));
  g.box(1, 0, 1, 4, 2, 4, (x, y, z) => jitter(SKIN, 0.05, x, y, z));
  P.farm = { g, pivot: [3, 10.5, 3] };
  // vestido largo: muslo y pierna anchos
  g = new Grid(8, 12, 9);
  g.box(0, 0, 0, 7, 11, 8, (x, y, z) => jitter(COAT2, 0.1, x, y, z));
  P.thigh = { g, pivot: [4, 11.5, 4.5] };
  g = new Grid(8, 13, 10);
  g.box(0, 2, 0, 7, 12, 8, (x, y, z) => jitter(COAT, 0.1, x, y, z));
  g.box(1, 0, 2, 6, 1, 9, (x, y, z) => jitter(0x151212, 0.1, x, y, z));
  P.shin = { g, pivot: [4, 12.5, 4] };
  // pelo largo (cae por la espalda)
  g = new Grid(14, 18, 3);
  g.box(1, 0, 0, 12, 17, 2, (x, y, z) => jitter(hash3(x, y >> 2, z) < 0.4 ? HAIR_D2 : HAIR_D, 0.1, x, y, z));
  for (let y = 0; y < 3; y++) for (const x of [1, 2, 11, 12]) g.clear(x, y, 0);
  P.skirt = { g, pivot: [7, 17.5, 1.5] }; // usamos "skirt" como melena trasera
  // daga clavada en el pecho
  g = new Grid(3, 14, 3);
  g.box(1, 0, 1, 1, 8, 1, (x, y, z) => jitter(0x2a2420, 0.15, x, y, z));
  g.box(0, 9, 0, 2, 9, 2, (x, y, z) => 0x8a8a84);
  g.box(1, 10, 1, 1, 13, 1, (x, y, z) => 0x6f6a64);
  P.sword = { g, pivot: [1, 0, 1] };
  return P;
}

// ---------------------------------------------------------------------------
// Ensamblado con esqueleto
// ---------------------------------------------------------------------------
export class Character {
  constructor(kind) {
    this.kind = kind;
    const P = kind === 'jon' ? jonParts() : danyParts();
    const isJ = kind === 'jon';
    const torsoH = isJ ? 17 : 15, shoulderX = isJ ? 11 : 9.5, hipX = isJ ? 4 : 3.5;
    const legLen = isJ ? 12 : 11.5;
    this.root = new THREE.Group();      // posicion en el mundo (cadera)
    this.hips = new THREE.Group(); this.root.add(this.hips);
    this.hips.add(partMesh(P.pelvis.g, P.pelvis.pivot));
    this.spine = new THREE.Group(); this.hips.add(this.spine);
    this.spine.add(partMesh(P.torso.g, P.torso.pivot));
    this.neck = new THREE.Group(); this.neck.position.set(0, (torsoH + 1) * CV, 0); this.spine.add(this.neck);
    this.head = new THREE.Group(); this.neck.add(this.head);
    this.headCache = new Map();
    this.headMesh = null;
    this.setExpr({ eyes: 'open', mouth: 'closed', brow: 'neutral' });
    const mkArm = (side) => {
      const sh = new THREE.Group(); sh.position.set(side * shoulderX * CV, (torsoH - 2.5) * CV, 0); this.spine.add(sh);
      sh.add(partMesh(P.uarm.g, P.uarm.pivot));
      const el = new THREE.Group(); el.position.set(0, -(P.uarm.g.ny - 0.5) * CV, 0); sh.add(el);
      el.add(partMesh(P.farm.g, P.farm.pivot));
      return { sh, el };
    };
    this.armL = mkArm(1); this.armR = mkArm(-1);
    const mkLeg = (side) => {
      const hp = new THREE.Group(); hp.position.set(side * hipX * CV, -5 * CV, 0); this.hips.add(hp);
      hp.add(partMesh(P.thigh.g, P.thigh.pivot));
      const kn = new THREE.Group(); kn.position.set(0, -legLen * CV, 0); hp.add(kn);
      kn.add(partMesh(P.shin.g, P.shin.pivot));
      return { hp, kn };
    };
    this.legL = mkLeg(1); this.legR = mkLeg(-1);
    // faldon / melena
    this.skirt = new THREE.Group();
    if (isJ) { this.skirt.position.set(0, -4 * CV, -4.5 * CV); this.hips.add(this.skirt); }
    else { this.skirt.position.set(0, (torsoH + 1) * CV, -4 * CV); this.spine.add(this.skirt); }
    this.skirt.add(partMesh(P.skirt.g, P.skirt.pivot));
    // espada / daga
    this.sword = new THREE.Group();
    const sm = partMesh(P.sword.g, P.sword.pivot);
    this.sword.add(sm);
    if (isJ) { this.sword.position.set(8.5 * CV, -2 * CV, 1 * CV); this.sword.rotation.set(0.15, 0, 0.35); this.hips.add(this.sword); }
    else { this.sword.position.set(1.5 * CV, 9 * CV, 4.8 * CV); this.sword.rotation.set(1.45, 0, 0.1); this.spine.add(this.sword); this.sword.visible = false; }
  }
  setExpr(ex) {
    const key = `${ex.eyes}|${ex.mouth}|${ex.brow}|${ex.tears ? 1 : 0}`;
    if (this.exprKey === key) return;
    this.exprKey = key;
    let m = this.headCache.get(key);
    if (!m) {
      m = partMesh(buildHead(this.kind, ex), [8, 3, 8]);
      this.headCache.set(key, m);
    }
    if (this.headMesh) this.head.remove(this.headMesh);
    this.headMesh = m; this.head.add(m);
  }
  // pose: objeto con angulos (rad). Todos opcionales.
  pose(p) {
    const e = (o, v) => { if (v) o.rotation.set(v[0] || 0, v[1] || 0, v[2] || 0, 'YXZ'); else o.rotation.set(0, 0, 0); };
    e(this.hips, p.hips); e(this.spine, p.spine); e(this.neck, p.neck); e(this.head, p.head);
    e(this.armL.sh, p.shL); e(this.armL.el, p.elL); e(this.armR.sh, p.shR); e(this.armR.el, p.elR);
    e(this.legL.hp, p.hpL); e(this.legL.kn, p.knL); e(this.legR.hp, p.hpR); e(this.legR.kn, p.knR);
    if (this.kind === 'jon') {
      // el faldon sigue a las piernas
      const ax = Math.max(0, -Math.min((p.hpL || [0])[0], (p.hpR || [0])[0]));
      this.skirt.rotation.set(-Math.min(ax, 1.2) * 0.5 + 0.05, 0, 0);
    } else {
      this.skirt.rotation.set((p.hair || 0.08), 0, 0);
    }
    if (p.expr) this.setExpr(p.expr);
    if (p.dagger !== undefined && this.kind !== 'jon') this.sword.visible = p.dagger;
  }
}

// interpolacion de poses (lineal sobre angulos)
export function blendPose(a, b, t) {
  const out = {};
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if (k === 'expr' || k === 'dagger') { out[k] = t < 0.5 ? (a[k] ?? b[k]) : (b[k] ?? a[k]); continue; }
    const va = a[k], vb = b[k];
    if (typeof va === 'number' || typeof vb === 'number') { out[k] = lerp(va ?? 0, vb ?? 0, t); continue; }
    const A = va || [0, 0, 0], B = vb || [0, 0, 0];
    out[k] = [lerp(A[0] || 0, B[0] || 0, t), lerp(A[1] || 0, B[1] || 0, t), lerp(A[2] || 0, B[2] || 0, t)];
  }
  return out;
}
