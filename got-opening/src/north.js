// Set del Norte: mapa nevado, el Muro roto, el Ultimo Hogar, el camino e Invernalia con el arciano.
import { THREE, Grid, vox, mat, sd, hash3, rng, clamp, lerp, jitter, shade, mix, smooth } from './kit.js';
import { mapGround, pineGeometry, instanced, label, gearGrid, cloudTexture } from './props.js';
import { NorthInteriors } from './north_int.js';

export const WALL_Z = -40, LH = [0, 0, -15], WF = [4, 0, 34];

const LAND_GLSL = `float landMask(vec2 p){
  float w = 62.0 + 26.0 * fb(vec2(p.y * 0.018, 1.3)) - 13.0;
  float top = -150.0 + 30.0 * fb(vec2(p.x * 0.03, 5.0));
  return smoothstep(-0.5, 0.5, w - abs(p.x + 8.0 * sin(p.y * 0.02))) * smoothstep(-0.5, 0.5, p.y - top);
}`;

// ---------------------------------------------------------------------------
// el Muro: bloques de hielo apilados con brecha central escalonada
// ---------------------------------------------------------------------------
function buildWall() {
  const v = 0.2, NX = 800, NY = 70, NZ = 50;
  const g = new Grid(NX, NY, NZ);
  const cx = NX / 2, cz = NZ / 2;
  const R = rng(7);
  for (let y = 0; y < NY; y++) {
    const yu = y / NY;
    const half = (5 - 3.8 * Math.pow(yu, 0.85)) / v; // semi-grosor (trapecio)
    let x = -Math.floor(R() * 6);
    while (x < NX) {
      const len = 2 + Math.floor(R() * 7);
      const bxu = (x + len / 2 - cx) * v;
      const gap = 1.9 + Math.pow(yu, 1.5) * 5.2 + (hash3(y, x, 3) - 0.5) * 0.9;
      const ad = Math.abs(bxu) - gap;
      if (ad > 0) {
        // los extremos rotos pierden grosor (perfil en piramide escalonada)
        const endK = Math.min(1, 0.35 + ad / 7);
        const hz = Math.round(half * endK + (hash3(y, x, 9) < 0.15 ? 0.6 : 0));
        const base = mix(0xd2d7dc, 0x9aa2aa, hash3(y >> 1, x, 2) * 0.8);
        const k = 0.88 + hash3(y, x, 1) * 0.18;
        for (let xx = x; xx < x + len; xx++) for (let z = cz - hz; z <= cz + hz; z++) {
          const seam = xx === x + len - 1;
          g.set(xx, y, z, shade(base, k * (seam ? 0.8 : 1)));
        }
      }
      x += len;
    }
  }
  g.paint((x, y, z, c) => (!g.solid(x, y + 1, z) && hash3(x, y, z) < 0.5 ? 0xe6eaee : c));
  const m = vox(g, v, [cx, 0, cz], 'ice', { roughness: 0.6, metalness: 0.0 });
  m.position.set(0, 0, WALL_Z);
  return m;
}

// colina del Ultimo Hogar: anillos escalonados independientes
function buildHillRings(nRings = 7, r0 = 7.2, r1 = 1.8, step = 0.42) {
  const v = 0.125;
  const rings = [];
  for (let i = 0; i < nRings; i++) {
    const ro = lerp(r0, r1, i / nRings), ri = lerp(r0, r1, (i + 1) / nRings) - 0.05;
    const n = Math.ceil(ro / v) * 2 + 2, c = n / 2, h = Math.round(step / v);
    const g = new Grid(n, h, n);
    for (let x = 0; x < n; x++) for (let z = 0; z < n; z++) {
      const r = Math.hypot(x + 0.5 - c, z + 0.5 - c) * v;
      if (r > ro || (i < nRings - 1 && r < ri - 0.4)) continue;
      const a = Math.atan2(z - c, x - c);
      const blk = Math.floor(a * ro * 1.6);
      for (let y = 0; y < h; y++) {
        const top = y === h - 1;
        const edge = r > ro - v * 1.2;
        let col = mix(0x767b80, 0x63676c, hash3(blk, i, 2));
        if (edge && hash3(blk, y, i) < 0.3) col = shade(col, 0.8);
        if (top && hash3(x >> 2, z >> 2, i) < 0.3) col = jitter(0xb8bcc0, 0.06, x, y, z);
        g.set(x, y, z, col);
      }
    }
    const m = vox(g, v, [c, 0, c], 'stone');
    m.userData.baseY = i * step;
    rings.push(m);
  }
  return rings;
}

// cresta alargada escalonada junto al camino
function buildRidge() {
  const v = 0.125, NX = 112, NZ = 300, L = 5, step = 3;
  const g = new Grid(NX, L * step, NZ);
  const cx = NX / 2, cz = NZ / 2;
  for (let x = 0; x < NX; x++) for (let z = 0; z < NZ; z++) {
    const dx = Math.abs(x + 0.5 - cx), dz = Math.abs(z + 0.5 - cz);
    for (let i = 0; i < L; i++) {
      const hx = 52 - i * 9 + Math.sin(z * 0.05 + i) * 3, hz = 148 - i * 14;
      const qx = dx - hx + 20, qz = dz - hz + 20;
      const d = Math.hypot(Math.max(qx, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qz), 0) - 20;
      if (d > 0) break;
      for (let y = i * step; y < (i + 1) * step; y++) {
        let col = mix(0x767b80, 0x63676c, hash3(Math.floor(z / 6), i, 2));
        if (y === (i + 1) * step - 1 && hash3(x >> 2, z >> 2, i) < 0.3) col = 0xb8bcc0;
        g.set(x, y, z, col);
      }
    }
  }
  return vox(g, v, [cx, 0, cz], 'stone');
}

// castillo de madera oscura sobre la colina
function buildLastHearthCastle() {
  const v = 0.05, N = 56, NY = 60;
  const g = new Grid(N, NY, N);
  const WOOD = [0x4a3626, 0x5a4430, 0x3d2c20, 0x664c34];
  const col = (x, y, z) => WOOD[Math.floor(hash3(x >> 1, y >> 2, z >> 1) * 4)];
  // muralla cuadrada con almenas
  for (let x = 4; x < 52; x++) for (let z = 4; z < 52; z++) {
    const wall = x < 7 || x > 48 || z < 7 || z > 48;
    if (!wall) continue;
    const h = 14 + (((x + z) >> 1) % 2 ? 2 : 0);
    for (let y = 0; y < h; y++) g.set(x, y, z, col(x, y, z));
  }
  // torres de esquina
  for (const [tx, tz] of [[6, 6], [49, 6], [6, 49], [49, 49]]) g.sdf((x, y, z) => sd.box(x, y, z, tx, 10, tz, 4, 10, 4), col, [tx - 5, 0, tz - 5, tx + 5, 21, tz + 5]);
  // edificios interiores
  g.box(12, 0, 12, 30, 12, 26, col); g.box(32, 0, 30, 44, 10, 44, col); g.box(12, 0, 32, 24, 9, 44, col);
  // torre central con aguja
  g.sdf((x, y, z) => sd.box(x, y, z, 28, 20, 28, 5, 20, 5), col, [22, 0, 22, 34, 41, 34]);
  g.sdf((x, y, z) => sd.cone(x, y, z, 28, 40, 28, 28, 56, 28, 5, 0.5), (x, y, z) => jitter(0x6c5a48, 0.3, x, y, z), [22, 39, 22, 34, 58, 34]);
  // remaches/ventanas de laton
  g.paint((x, y, z, c) => (y % 6 === 3 && (x + z) % 5 === 0 && hash3(x, y, z) < 0.4 ? 0xb08a4a : c));
  return vox(g, v, [N / 2, 0, N / 2], 'wood', { roughness: 0.7, metalness: 0.2 });
}

// Invernalia
function buildWinterfell() {
  const v = 0.1, NX = 180, NY = 60, NZ = 120;
  const g = new Grid(NX, NY, NZ);
  const cx = 90, cz = 60;
  const STONE = [0x4e4640, 0x5a5048, 0x463e38, 0x625850];
  const WOOD = [0x5a4232, 0x4a362a, 0x664a38];
  const st = (x, y, z) => STONE[Math.floor(hash3(x >> 1, y >> 1, z >> 1) * 4)];
  const wd = (x, y, z) => WOOD[Math.floor(hash3(x >> 1, y, z >> 1) * 3)];
  const rr = (dx, dz, hx, hz, r) => { // rounded rect sdf
    const qx = Math.abs(dx) - hx + r, qz = Math.abs(dz) - hz + r;
    return Math.hypot(Math.max(qx, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qz), 0) - r;
  };
  // base / patio
  for (let x = 0; x < NX; x++) for (let z = 0; z < NZ; z++) {
    const d = rr(x - cx, z - cz, 84, 56, 22);
    if (d < 0) g.set(x, 0, z, hash3(x >> 2, 0, z >> 2) < 0.5 ? 0x8c8a88 : 0x7a7876);
    // muralla exterior
    if (d < 0 && d > -5) { const h = 11 + ((x + z) % 6 < 3 ? 2 : 0); for (let y = 1; y < h; y++) g.set(x, y, z, st(x, y, z)); }
    // muralla interior
    const d2 = rr(x - cx + 4, z - cz, 70, 44, 16);
    if (d2 < 0 && d2 > -4 && !(Math.abs(z - cz) < 5 && x < cx)) { const h = 15 + ((x + z) % 6 < 3 ? 2 : 0); for (let y = 1; y < h; y++) g.set(x, y, z, st(x, y, z)); }
  }
  // torres en las murallas
  const R = rng(31);
  for (let k = 0; k < 16; k++) {
    const a = (k / 16) * Math.PI * 2;
    const tx = cx + Math.cos(a) * 80, tz = cz + Math.sin(a) * 52;
    const h = 18 + R() * 8;
    g.sdf((x, y, z) => Math.max(Math.hypot(x - tx, z - tz) - 5, y - h), st, [tx - 6, 0, tz - 6, tx + 6, h + 1, tz + 6]);
    g.sdf((x, y, z) => sd.cone(x, y, z, tx, h, tz, tx, h + 6, tz, 5.5, 1), (x, y, z) => jitter(0x3e3530, 0.2, x, y, z), [tx - 6, h - 1, tz - 6, tx + 6, h + 7, tz + 6]);
  }
  // gran torreon redondo con cupula y anillos dorados
  const kx = cx + 12, kz = cz - 14;
  g.sdf((x, y, z) => Math.max(Math.hypot(x - kx, z - kz) - 15, y - 22), (x, y, z) => (y % 7 === 0 ? 0xa8843e : st(x, y, z)), [kx - 16, 0, kz - 16, kx + 16, 23, kz + 16]);
  g.sdf((x, y, z) => sd.ellip(x, y, z, kx, 22, kz, 13, 9, 13), (x, y, z) => (Math.floor(Math.atan2(z - kz, x - kx) * 4) % 2 ? 0x7a6a58 : 0x8e7c66), [kx - 14, 22, kz - 14, kx + 14, 32, kz + 14]);
  g.sdf((x, y, z) => Math.max(Math.hypot(x - kx, z - kz) - 2, y - 36), () => 0xb8944a, [kx - 3, 30, kz - 3, kx + 3, 37, kz + 3]);
  // torre rota alta
  const bx = cx - 34, bz = cz - 26;
  g.sdf((x, y, z) => Math.max(Math.hypot(x - bx, z - bz) - 6, y - 22 - (x - bx) * 0.4), st, [bx - 7, 0, bz - 7, bx + 7, 28, bz + 7]);
  // edificios con tejado a dos aguas
  const builds = [[-55, -20, 10, 8, 10], [-52, 8, 12, 7, 12], [-30, 18, 14, 9, 11], [-10, 26, 9, 7, 9], [-14, -6, 10, 12, 12], [12, 20, 10, 8, 10], [30, 10, 7, 9, 9], [-40, 30, 9, 6, 8], [-62, 30, 6, 6, 8], [6, -36, 9, 6, 9]];
  for (const [ox, oz, hx, hz, h] of builds) {
    const x0 = cx + ox, z0 = cz + oz;
    g.box(x0 - hx, 1, z0 - hz, x0 + hx, h, z0 + hz, wd);
    for (let k = 0; k <= Math.min(hx, hz); k++) {
      const along = hx > hz;
      if (along) g.box(x0 - hx, h + 1 + k, z0 - hz + k, x0 + hx, h + 1 + k, z0 + hz - k, (x, y, z) => (hash3(x, y, z) < 0.12 ? 0x9a9690 : 0x3e3330));
      else g.box(x0 - hx + k, h + 1 + k, z0 - hz, x0 + hx - k, h + 1 + k, z0 + hz, (x, y, z) => (hash3(x, y, z) < 0.12 ? 0x9a9690 : 0x3e3330));
    }
  }
  // cajas con relieve dorado (piezas mecanicas)
  for (const [ox, oz] of [[24, 30], [-24, 38], [40, -30], [-2, 40]]) {
    const x0 = cx + ox, z0 = cz + oz;
    g.box(x0 - 5, 1, z0 - 5, x0 + 5, 7, z0 + 5, (x, y, z) => (y === 7 ? ((x + z) % 3 === 0 || x === x0 - 5 || x === x0 + 5 || z === z0 - 5 || z === z0 + 5 ? 0xc9a050 : 0x6a5032) : 0x5a4430));
  }
  const m = vox(g, v, [cx, 0, cz], 'stone');
  m.position.set(WF[0], 0, WF[2]);
  return m;
}

// estanque y engranaje del bosque de dioses (relativo al arbol)
function buildGodswood() {
  const v = 0.06, N = 140;
  const g = new Grid(N, 4, N); const c = N / 2;
  for (let x = 0; x < N; x++) for (let z = 0; z < N; z++) {
    const dx = x + 0.5 - c, dz = z + 0.5 - c, r = Math.hypot(dx, dz), a = Math.atan2(dz, dx);
    // anillo engranaje alrededor de la base
    const tooth = ((a / (Math.PI * 2)) * 40 % 1 + 1) % 1 < 0.5;
    if (r < 22 + (tooth ? 2 : 0) && r > 18) { for (let y = 0; y < 3; y++) g.set(x, y, z, jitter(0x8a8378, 0.2, x, y, z)); continue; }
    if (r <= 18) { g.set(x, 0, z, jitter(0xb8b2a8, 0.15, x, 0, z)); g.set(x, 1, z, jitter(0xc8c2b8, 0.15, x, 1, z)); continue; }
    // estanque
    const pd = Math.hypot(dx - 34, (dz - 20) * 1.3) - 24 - 6 * Math.sin(a * 3);
    if (pd < 0 && r > 24) { g.set(x, 0, z, 0x3c7aa8); g.setE(x, 0, z, 40); }
  }
  return vox(g, v, [c, 0, c], 'pond', { roughness: 0.25, metalness: 0.2, emiGain: 1.5, emiTint: 0x6aa8e0 });
}

// arciano: tronco blanco con cara + ramas ; hojas rojas aparte
function buildWeirwood() {
  const v = 0.04, N = 130, NY = 120;
  const t = new Grid(N, NY, N), l = new Grid(N, NY, N);
  const c = N / 2;
  const BARK = (x, y, z) => jitter(hash3(x >> 1, y >> 2, z >> 1) < 0.3 ? 0xd6d0c4 : 0xebe7de, 0.12, x, y, z);
  t.sdf((x, y, z) => {
    const tw = Math.sin(y * 0.15) * 1.2;
    return sd.cone(x + tw, y, z, c, 0, c, c, 52, c, 12 - Math.min(4, y * 0.02), 7);
  }, BARK, [c - 16, 0, c - 16, c + 16, 54, c + 16]);
  // raices
  for (let k = 0; k < 6; k++) {
    const a = k / 6 * Math.PI * 2 + 0.3;
    t.sdf((x, y, z) => sd.cone(x, y, z, c, 6, c, c + Math.cos(a) * 20, 0, c + Math.sin(a) * 20, 5, 1.5), BARK, [c - 24, 0, c - 24, c + 24, 10, c + 24]);
  }
  // ramas recursivas
  const tips = [];
  const R = rng(91);
  const branch = (ax, ay, az, dx, dy, dz, len, r, depth) => {
    const bx = ax + dx * len, by = ay + dy * len, bz = az + dz * len;
    t.sdf((x, y, z) => sd.cone(x, y, z, ax, ay, az, bx, by, bz, r, r * 0.65), BARK,
      [Math.floor(Math.min(ax, bx) - r - 1), Math.floor(Math.min(ay, by) - r - 1), Math.floor(Math.min(az, bz) - r - 1), Math.ceil(Math.max(ax, bx) + r + 1), Math.ceil(Math.max(ay, by) + r + 1), Math.ceil(Math.max(az, bz) + r + 1)]);
    if (depth === 0 || r < 1.2) { tips.push([bx, by, bz]); return; }
    const n = depth > 1 ? 3 : 2;
    for (let i = 0; i < n; i++) {
      let ndx = dx + (R() - 0.5) * 1.1, ndy = dy + 0.35 + R() * 0.3, ndz = dz + (R() - 0.5) * 1.1;
      const L = Math.hypot(ndx, ndy, ndz); ndx /= L; ndy /= L; ndz /= L;
      branch(bx, by, bz, ndx, ndy, ndz, len * (0.6 + R() * 0.2), r * 0.62, depth - 1);
    }
  };
  for (let k = 0; k < 7; k++) {
    const a = k / 7 * Math.PI * 2 + R() * 0.4;
    const out = 0.75 + R() * 0.25;
    const y0 = 34 + R() * 16;
    let dx = Math.cos(a) * out, dz = Math.sin(a) * out, dy = 0.55 + R() * 0.3;
    const L = Math.hypot(dx, dy, dz);
    branch(c, y0, c, dx / L, dy / L, dz / L, 26 + R() * 8, 5.5, 3);
  }
  branch(c, 50, c, 0.05, 1, 0.02, 28, 6, 3);
  // cara tallada (+z)
  const fz = c + 10;
  for (const ex of [-4, 4]) t.sdf((x, y, z) => sd.ellip(x, y, z, c + ex, 30, fz, 2.2, 1.4, 3), (x, y, z) => 0x7a1414, [c + ex - 4, 27, fz - 5, c + ex + 4, 33, fz + 4]);
  t.sdf((x, y, z) => sd.ellip(x, y, z, c, 22, fz, 3.5, 1.2, 3), () => 0x3a2a24, [c - 5, 20, fz - 5, c + 5, 24, fz + 4]);
  t.sdf((x, y, z) => sd.ellip(x, y, z, c, 26, fz + 1, 1.2, 3, 2), BARK, [c - 3, 22, fz - 2, c + 3, 30, fz + 4]);
  // hojas
  for (const [x0, y0, z0] of tips) {
    const rr = 8 + hash3(x0, y0, z0) * 5;
    l.sdf((x, y, z) => (hash3(x, y, z) < 0.68 ? sd.sphere(x, y, z, x0, y0 + 2, z0, rr * 1.25) : 1), (x, y, z) => jitter(hash3(x >> 1, y >> 1, z >> 1) < 0.5 ? 0x9a1d28 : 0xb5303a, 0.3, x, y, z),
      [Math.floor(x0 - rr * 1.3), Math.floor(y0 - rr * 1.3 + 2), Math.floor(z0 - rr * 1.3), Math.ceil(x0 + rr * 1.3), Math.ceil(y0 + rr * 1.3 + 2), Math.ceil(z0 + rr * 1.3)]);
  }
  const trunk = vox(t, v, [c, 0, c], 'bark', { roughness: 0.8 });
  const leaves = vox(l, v, [c, 0, c], 'leaves', { roughness: 0.75 });
  return { trunk, leaves };
}

export class North {
  constructor(scene, ctx) {
    this.root = new THREE.Group(); scene.add(this.root);
    const r = this.out = new THREE.Group(); this.root.add(r);
    ctx.renderer.localClippingEnabled = true;
    this.ground = mapGround({ landGLSL: LAND_GLSL, tile: 1.0, land: 0x9a9fa4, land2: 0x6c7176, sea: 0x0c1826, sea2: 0x1a3048 }); r.add(this.ground);
    this.wall = buildWall(); r.add(this.wall);
    // anillos de la colina
    this.hill = new THREE.Group(); this.hill.position.set(LH[0], 0, LH[2]); r.add(this.hill);
    this.rings = buildHillRings(); this.rings.forEach((m) => { m.position.y = m.userData.baseY; this.hill.add(m); });
    this.castle = buildLastHearthCastle(); this.castle.position.y = 7 * 0.42; this.hill.add(this.castle);
    // segunda loma escalonada junto al camino
    this.mound = buildRidge(); this.mound.position.set(18, 0, 10); r.add(this.mound);
    // rotulos
    this.lblLH = label('Last Hearth', 1.3); this.lblLH.position.set(-3.5, 0.0, -5.5); this.lblLH.rotation.y = 0.35; r.add(this.lblLH);
    this.lblWF = label('Winterfell', 1.3); this.lblWF.position.set(WF[0] + 3, 0.0, WF[2] + 8.5); this.lblWF.rotation.y = -0.25; r.add(this.lblWF);
    // Invernalia
    this.wf = buildWinterfell(); r.add(this.wf);
    this.gods = new THREE.Group(); this.gods.position.set(WF[0] + 5.2, 0.1, WF[2] + 0.5); r.add(this.gods);
    this.godswood = buildGodswood(); this.gods.add(this.godswood);
    const tree = buildWeirwood();
    this.trunk = tree.trunk; this.leaves = tree.leaves;
    this.gods.add(this.trunk); this.gods.add(this.leaves);
    this.trunk.receiveShadow = false; this.leaves.receiveShadow = false;
    this.clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
    this.trunk.material = mat('barkclip', { roughness: 0.8 }); this.trunk.material.clippingPlanes = [this.clip];
    // bosques
    const pts = [];
    const R = rng(5);
    const free = (x, z) => {
      if (Math.abs(x) < 7 && z > WALL_Z - 1 && z < WALL_Z + 30 && Math.abs(x) < 3 + (z - WALL_Z) * 0.05) return false; // camino de hielo
      if (Math.hypot(x - LH[0], z - LH[2]) < 8) return false;
      if (Math.abs(z - WALL_Z) < 3) return false;
      if (x > 8 && x < 26 && z > -8 && z < 27) return false; // camino y cresta
      if (Math.abs(x - WF[0]) < 10 && Math.abs(z - WF[2]) < 7) return false;
      if (Math.abs(x - WF[0] - 3) < 8 && Math.abs(z - WF[2] - 8.5) < 2) return false;
      return true;
    };
    for (let i = 0; i < 26000 && pts.length < 9000; i++) {
      const x = (R() - 0.5) * 120, z = -110 + R() * 190;
      const dens = hash3(Math.floor(x / 6), 0, Math.floor(z / 6));
      if (dens < 0.45 || !free(x, z)) continue;
      pts.push([x, 0, z, R() * 6, 0.8 + R() * 0.5]);
    }
    // bosque denso a la derecha del camino
    for (let i = 0; i < 5000; i++) { const x = -6 + R() * 12, z = -8 + R() * 32; if (free(x, z)) pts.push([x, 0, z, R() * 6, 0.8 + R() * 0.4]); }
    // pinos sobre la loma
    for (let i = 0; i < 260; i++) { pts.push([18 + (R() - 0.5) * 2.5, 5 * 3 * 0.125, 10 + (R() - 0.5) * 22, R() * 6, 1]); }
    this.pines = instanced(pineGeometry(), 0.07, [3.5, 0, 3.5], 'pine', pts); r.add(this.pines);
    // nubes para el cenital
    const ct = cloudTexture(3);
    this.clouds = new THREE.Group(); r.add(this.clouds);
    for (let i = 0; i < 14; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: ct, color: 0x20262e, transparent: true, opacity: 1.0, depthWrite: false, fog: false }));
      s.position.set((hash3(i, 1, 1) - 0.5) * 200, 40 + hash3(i, 2, 2) * 70, -20 + (hash3(i, 3, 3) - 0.5) * 200); s.scale.set(120, 80, 1);
      this.clouds.add(s);
    }
    // luces
    this.moon = new THREE.DirectionalLight(0xd0daf0, 1.4);
    this.moon.castShadow = true; this.moon.shadow.mapSize.set(2048, 2048); this.moon.shadow.bias = -0.0004; this.moon.shadow.normalBias = 0.02;
    r.add(this.moon); r.add(this.moon.target);
    this.hemi = new THREE.HemisphereLight(0x8a94a8, 0x24272c, 0.55); r.add(this.hemi);
    this.ice = new THREE.PointLight(0x6aa0ff, 0, 30, 1.5); r.add(this.ice);
    this.interiors = new NorthInteriors(this.root, ctx);
    this.interiors.attachTree(this.trunk.geometry, null, this.leaves.geometry, this.leaves.material);
  }
  update(lt, cam, st, t) {
    // sombras centradas en lo que se ve
    const sc = st.shadow || [0, 0, -20, 40];
    const s = this.moon.shadow.camera; s.left = -sc[3]; s.right = sc[3]; s.top = sc[3]; s.bottom = -sc[3]; s.near = 1; s.far = 400; s.updateProjectionMatrix();
    this.moon.target.position.set(sc[0], sc[1], sc[2]);
    this.moon.position.set(sc[0] + 55, sc[1] + 90, sc[2] + 50);
    this.moon.intensity = st.moon ?? 1.4; this.hemi.intensity = st.hemi ?? 0.55;
    // escarcha
    const U = this.ground.material.userData.U;
    U.uFrostR.value = st.frost ?? 0;
    this.ice.position.set(0, 2, WALL_Z + 4); this.ice.intensity = st.iceLight ?? 0;
    // anillos de la colina: giro y hundimiento
    const sp = st.spiral ?? 0;
    this.rings.forEach((m, i) => {
      m.rotation.y = sp * (i % 2 ? 1 : -1) * (0.6 + i * 0.12);
      m.position.y = m.userData.baseY * (1 - (st.sink ?? 0));
    });
    this.castle.position.y = 7 * 0.42 * (1 - (st.sink ?? 0)) + (st.rise ?? 0);
    // arbol
    const grow = st.grow ?? 1;
    const ts = 0.55 * (st.treeScale ?? 1);
    this.clip.constant = this.gods.position.y + grow * 5.0 * ts;
    this.trunk.scale.setScalar(ts);
    const lf = st.leaves ?? 1;
    this.leaves.visible = lf > 0.01;
    this.leaves.scale.set(ts, ts * (0.3 + 0.7 * lf), ts);
    this.leaves.scale.multiplyScalar(0.4 + 0.6 * lf);
    this.clouds.visible = !!st.clouds;
    this.lblLH.visible = st.lblLH !== false; this.lblWF.visible = st.lblWF !== false;
    this.interiors.update(lt, cam, st, t);
    const inside = !!st.inside;
    this.out.visible = !inside;
    this.interiors.root.visible = inside;
    this.moon.visible = !inside; this.hemi.visible = !inside;
  }
}
