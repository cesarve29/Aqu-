// Set del Sur: mapa con Desembarco del Rey, puerta, ciudad, Fortaleza Roja, mecanismo de torre y salones del trono.
import { THREE, Grid, vox, mat, sd, hash3, rng, clamp, lerp, jitter, shade, mix, emoji } from './kit.js';
import { mapGround, instanced, pineGeometry, label, gearGrid, cloudTexture } from './props.js';

export const SI = [500, 0, 0]; // mecanismo + salon de engranajes
export const SN = [700, 0, 0]; // nave con vidriera

const LAND_GLSL = `float landMask(vec2 p){
  float coast = -16.0 + 9.0 * fb(vec2(p.y * 0.03, 2.1)) + 3.0 * sin(p.y * 0.08);
  float lake = length((p - vec2(10.0, 16.0)) * vec2(1.0, 1.4)) - 3.5 - 1.5 * fb(p * 0.3);
  return smoothstep(-0.5, 0.5, p.x - coast) * smoothstep(-0.3, 0.3, lake);
}`;

const RED = [0x6a3e2c, 0x7a4a34, 0x5c3424, 0x84523a];
const red = (x, y, z) => RED[Math.floor(hash3(x >> 1, y >> 1, z >> 1) * 4)];
const GOLD = 0xc0964a;

// ciudad ovalada: murallas, calles radiales y casas
function buildCity() {
  const v = 0.1, NX = 380, NY = 24, NZ = 240;
  const g = new Grid(NX, NY, NZ);
  const cx = 190, cz = 120;
  const R = rng(4);
  for (let x = 0; x < NX; x++) for (let z = 0; z < NZ; z++) {
    const dx = (x + 0.5 - cx) / 185, dz = (z + 0.5 - cz) / 115;
    const r = Math.hypot(dx, dz);
    if (r > 1) continue;
    // suelo de la ciudad
    g.set(x, 0, z, hash3(x >> 2, 0, z >> 2) < 0.5 ? 0x5a4636 : 0x4e3c2e);
    // muralla
    if (r > 0.965) { const h = 9 + ((x + z) % 6 < 3 ? 2 : 0); for (let y = 1; y < h; y++) g.set(x, y, z, red(x, y, z)); continue; }
    // calles radiales y anillo
    const a = Math.atan2(dz, dx);
    const street = Math.abs(Math.sin(a * 4)) < 0.05 || Math.abs(r - 0.6) < 0.015;
    if (street) continue;
    // casas: bloques por celda
    const cxl = Math.floor(x / 6), czl = Math.floor(z / 6);
    const hsh = hash3(cxl, 1, czl);
    if (hsh < 0.12) continue;
    const lx = x % 6, lz = z % 6;
    if (lx === 0 || lz === 0) continue;
    const h = 2 + Math.floor(hsh * 4);
    for (let y = 1; y <= h; y++) g.set(x, y, z, hash3(cxl, y, czl) < 0.5 ? 0x6e5240 : 0x5e4434);
    // tejado
    const roof = hash3(cxl, 3, czl) < 0.5 ? 0x7a3a2a : 0x5a4a3e;
    if (lx >= 2 && lx <= 4 && lz >= 1 && lz <= 5) g.set(x, h + 1, z, roof);
  }
  const m = vox(g, v, [cx, 0, cz], 'city', { roughness: 0.85 });
  return m;
}

// torre de puerta con anillos de laton
function gateTowerGrid() {
  const v = 0.05, N = 40, NY = 80;
  const g = new Grid(N, NY, N);
  const c = N / 2;
  g.sdf((x, y, z) => {
    const r = 15 - y * 0.05;
    return Math.max(Math.hypot(x - c, z - c) - r, y - 70);
  }, (x, y, z) => (y > 60 && y % 4 < 2 ? 0xc8a050 : (Math.floor(Math.atan2(z - c, x - c) * 8) % 2 ? RED[0] : RED[1])), [0, 0, 0, N - 1, 71, N - 1]);
  g.sdf((x, y, z) => Math.max(Math.hypot(x - c, z - c) - 11, y - 76), (x, y, z) => (y % 3 === 0 ? GOLD : RED[3]), [c - 12, 70, c - 12, c + 12, 77, c + 12]);
  // ventanas oscuras
  g.paint((x, y, z, col) => (y % 14 > 8 && y % 14 < 12 && (x + z) % 9 === 0 ? 0x1a100a : col));
  return vox(g, v, [c, 0, c], 'redwood', { roughness: 0.6, metalness: 0.3 });
}

// la Fortaleza Roja
function buildRedKeep() {
  const v = 0.08, NX = 120, NY = 70, NZ = 90;
  const g = new Grid(NX, NY, NZ);
  const cx = 60;
  // colina escalonada
  for (let x = 0; x < NX; x++) for (let z = 0; z < NZ; z++) {
    const d = Math.hypot((x - cx) / 60, (z - 45) / 45);
    if (d > 1) continue;
    const h = Math.min(10, Math.floor((1 - d) * 22));
    for (let y = 0; y <= h; y++) g.set(x, y, z, jitter(0x5a4434, 0.2, x >> 1, y, z >> 1));
  }
  const base = 10;
  // muralla frontal con torres redondas y anillos dorados
  g.box(14, base, 70, 106, base + 10, 74, red);
  for (const tx of [22, 46, 74, 98]) {
    g.sdf((x, y, z) => Math.max(Math.hypot(x - tx, z - 74) - 8 + (y - base) * 0.05, y - base - 20), (x, y, z) => ((y - base) % 6 === 0 ? GOLD : red(x, y, z)), [tx - 9, base, 65, tx + 9, base + 21, 83]);
    g.sdf((x, y, z) => Math.max(Math.hypot(x - tx, z - 74) - 9, y - base - 22), (x, y, z) => ((x + z) % 3 ? GOLD : RED[3]), [tx - 10, base + 20, 64, tx + 10, base + 23, 84]);
  }
  // escalinata central
  for (let k = 0; k < 16; k++) g.box(54, base + k, 74 + 16 - k, 66, base + k, 75 + 16 - k, (x, y, z) => (x === 54 || x === 66 ? GOLD : 0x8a6a50));
  // torres cuadradas
  for (const [tx, tz, h] of [[40, 56, 30], [80, 56, 34], [28, 40, 26], [92, 40, 28], [60, 50, 40]]) {
    g.box(tx - 6, base, tz - 6, tx + 6, base + h, tz + 6, (x, y, z) => ((y - base) % 8 === 0 ? GOLD : red(x, y, z)));
    for (let x = tx - 6; x <= tx + 6; x += 2) for (const z of [tz - 6, tz + 6]) g.set(x, base + h + 1, z, RED[2]);
  }
  // gran salon con agujas doradas
  g.box(30, base, 14, 90, base + 26, 30, red);
  for (let k = 0; k < 10; k++) {
    const px = 32 + k * 6.4;
    g.sdf((x, y, z) => sd.cone(x, y, z, px, base + 26, 22, px, base + 42 + (k % 3) * 4, 22, 2.2, 0.3), () => GOLD, [px - 3, base + 25, 19, px + 3, base + 55, 25]);
  }
  for (const [tx, tz] of [[30, 14], [90, 14], [30, 30], [90, 30]]) g.sdf((x, y, z) => sd.cone(x, y, z, tx, base, tz, tx, base + 52, tz, 4, 1), (x, y, z) => ((y % 7) ? red(x, y, z) : GOLD), [tx - 5, base, tz - 5, tx + 5, base + 53, tz + 5]);
  g.paint((x, y, z, c) => (c !== GOLD && y > base + 4 && y % 9 === 4 && (x + z) % 7 === 0 ? 0xe8b860 : c));
  const m = vox(g, v, [cx, 0, 45], 'keep', { roughness: 0.6, metalness: 0.25 });
  return m;
}

// trono de hierro
export function ironThrone(v = 0.03, big = false) {
  const N = big ? 200 : 120, NY = big ? 200 : 130, NZ = big ? 90 : 70;
  const g = new Grid(N, NY, NZ);
  const cx = N / 2, cz = NZ / 2;
  const S = big ? 1.6 : 1;
  const IR = [0x3a3a3c, 0x4a4a4c, 0x2e2e30, 0x5a5856];
  const col = (x, y, z) => IR[Math.floor(hash3(x, y >> 1, z) * 4)];
  const blade = (x, y, z) => jitter(0x5c5e62, 0.3, x, y, z);
  if (!big) {
    g.box(cx - 24, 0, cz - 20, cx + 24, 8, cz + 20, col);
    g.box(cx - 18, 9, cz - 15, cx + 18, 16, cz + 15, col);
    g.box(cx - 11, 17, cz - 10, cx + 11, 26, cz + 10, col);
    g.box(cx - 15, 17, cz - 10, cx - 11, 38, cz + 12, col); g.box(cx + 11, 17, cz - 10, cx + 15, 38, cz + 12, col);
    g.box(cx - 12, 26, cz - 12, cx + 12, 60, cz - 8, col);
  }
  const R = rng(17);
  const nS = big ? 70 : 46;
  const by = big ? 30 : 46, bz = big ? cz : cz - 10;
  for (let k = 0; k < nS; k++) {
    const a = -1.35 + (k / (nS - 1)) * 2.7 + (R() - 0.5) * 0.06;
    const L = (big ? 150 : 50) * (0.55 + R() * 0.45) * (1 - Math.abs(a) * 0.3);
    const x0 = cx + Math.sin(a) * 6 * S, y0 = by + (R() - 0.5) * 6, z0 = bz + (R() - 0.5) * 8 * S;
    const x1 = x0 + Math.sin(a) * L, y1 = y0 + Math.cos(a) * L, z1 = z0 - (big ? 4 + R() * 14 : 2);
    const w = (big ? 3.2 : 1.6);
    // hoja
    g.sdf((x, y, z) => sd.cone(x, y, z, x0, y0, z0, x1, y1, z1, w, 0.3), blade,
      [Math.floor(Math.min(x0, x1) - 4), Math.floor(Math.min(y0, y1) - 4), Math.floor(Math.min(z0, z1) - 4), Math.ceil(Math.max(x0, x1) + 4), Math.ceil(Math.max(y0, y1) + 4), Math.ceil(Math.max(z0, z1) + 4)]);
    // guarda y empunadura
    if (big || k % 2 === 0) {
      const gx = x0 + Math.sin(a) * L * 0.12, gy = y0 + Math.cos(a) * L * 0.12, gz = z0 + 1;
      g.sdf((x, y, z) => sd.cone(x, y, z, gx - Math.cos(a) * w * 2.5, gy + Math.sin(a) * w * 2.5, gz, gx + Math.cos(a) * w * 2.5, gy - Math.sin(a) * w * 2.5, gz, w * 0.6, w * 0.6), col,
        [Math.floor(gx - w * 4), Math.floor(gy - w * 4), Math.floor(gz - w * 2), Math.ceil(gx + w * 4), Math.ceil(gy + w * 4), Math.ceil(gz + w * 2)]);
    }
  }
  if (!big) for (let k = 0; k < 40; k++) {
    const a = R() * Math.PI * 2;
    const bx = cx + Math.cos(a) * (14 + R() * 10), bz2 = cz + Math.sin(a) * (10 + R() * 8), byy = 4 + R() * 30;
    const dx = (R() - 0.5) * 14, dy = 3 + R() * 10, dz = (R() - 0.5) * 14;
    g.sdf((x, y, z) => sd.cone(x, y, z, bx, byy, bz2, bx + dx, byy + dy, bz2 + dz, 1.2, 0.3), blade, [Math.floor(bx - 9), Math.floor(byy - 2), Math.floor(bz2 - 9), Math.ceil(bx + 9), Math.ceil(byy + 14), Math.ceil(bz2 + 9)]);
  }
  return { g, origin: [cx, 0, cz], v };
}

// vidriera: arco alto con rosetón y leon (color por pixel, emisivo)
function windowMesh() {
  const W = 50, H = 110, v = 0.05;
  const c = document.createElement('canvas'); c.width = W * 4; c.height = H * 4;
  const x = c.getContext('2d');
  x.fillStyle = '#cfc6b4'; x.fillRect(0, 0, c.width, c.height);
  x.strokeStyle = '#6a2418'; x.lineWidth = 6;
  for (let i = 0; i < 9; i++) { x.beginPath(); x.arc(c.width * (i % 3) / 2, 200 + i * 60, 90 + (i % 4) * 20, 0, Math.PI * 2); x.stroke(); }
  x.strokeStyle = '#8a3020'; x.lineWidth = 4;
  for (let i = 0; i < 14; i++) { x.beginPath(); x.moveTo(0, i * 45); x.lineTo(c.width, i * 45 + 120); x.stroke(); }
  // roseton
  const rx = c.width / 2, ry = 130, rr = 88;
  x.fillStyle = '#c84a1a'; x.beginPath(); x.arc(rx, ry, rr, 0, Math.PI * 2); x.fill();
  x.fillStyle = '#f0a040'; x.beginPath(); x.arc(rx, ry, rr * 0.82, 0, Math.PI * 2); x.fill();
  x.fillStyle = '#f6efe0'; x.beginPath(); x.arc(rx, ry, rr * 0.68, 0, Math.PI * 2); x.fill();
  x.lineWidth = 8; x.strokeStyle = '#3a1a10'; x.beginPath(); x.arc(rx, ry, rr, 0, Math.PI * 2); x.stroke();
  x.globalCompositeOperation = 'source-atop';
  x.save(); x.filter = 'brightness(0.15) sepia(1)'; emoji(x, '🦁', rx, ry + 4, 72); x.restore();
  x.globalCompositeOperation = 'source-over';
  const d = x.getImageData(0, 0, c.width, c.height).data;
  const g = new Grid(W, H, 2);
  for (let i = 0; i < W; i++) for (let j = 0; j < H; j++) {
    const yy = H - 1 - j;
    // arco superior
    const ax = (i + 0.5 - W / 2) / (W / 2), ay = (j - H + W / 2) / (W / 2);
    if (j > H - W / 2 && ax * ax + ay * ay > 1) continue;
    const p = ((yy * 4 + 2) * c.width + i * 4 + 2) * 4;
    const col = (d[p] << 16) | (d[p + 1] << 8) | d[p + 2];
    const lead = i === 0 || i === W - 1 || j === 0;
    g.set(i, j, 0, lead ? 0x2a1a12 : col);
    if (!lead) g.setE(i, j, 0, 255);
    if (lead) g.set(i, j, 1, 0x2a1a12);
  }
  return vox(g, v, [W / 2, 0, 1], 'glass', { roughness: 0.4, emiGain: 0.65, emiTint: 0xffffff });
}

function skullGrid() {
  const g = new Grid(40, 18, 18);
  const B = (x, y, z) => jitter(0xb8ae98, 0.2, x, y, z);
  g.sdf((x, y, z) => sd.smin(sd.ellip(x, y, z, 10, 9, 9, 9, 8, 8), sd.cone(x, y, z, 12, 7, 9, 38, 4, 9, 6, 3), 3), B);
  for (const s of [-1, 1]) g.carve((x, y, z) => sd.sphere(x, y, z, 14, 11, 9 + s * 5, 2.6));
  for (let x = 16; x < 38; x += 2) for (const s of [-1, 1]) g.box(x, 0, 9 + s * 4, x, 3, 9 + s * 4, 0xe8e0cc);
  g.carve((x, y, z) => sd.box(x, y, z, 28, 3, 9, 10, 1, 3));
  return g;
}

export class South {
  constructor(scene, ctx) {
    this.root = new THREE.Group(); scene.add(this.root);
    const out = this.out = new THREE.Group(); this.root.add(out);
    this.ground = mapGround({ landGLSL: LAND_GLSL, tile: 1.0, land: 0x7a6656, land2: 0x5a4a3e, sea: 0x0f2a44, sea2: 0x2a5476, river: 0x2a3a50 });
    out.add(this.ground);
    this.city = buildCity(); out.add(this.city);
    this.lbl = label("King's Landing", 4.0, 0.12); this.lbl.position.set(0, 0, -16); out.add(this.lbl);
    // colinas escalonadas (curvas de nivel) alrededor
    const R = rng(8);
    const hillPts = [];
    for (let i = 0; i < 9; i++) hillPts.push([22 + R() * 30, -30 + R() * 60, 4 + R() * 6]);
    this.hills = new THREE.Group(); out.add(this.hills);
    for (const [hx, hz, hr] of hillPts) {
      const v = 0.25, n = Math.ceil(hr / v) * 2 + 2, c = n / 2, L = 5;
      const g = new Grid(n, L, n);
      for (let x = 0; x < n; x++) for (let z = 0; z < n; z++) {
        const r = Math.hypot(x + 0.5 - c, z + 0.5 - c) * v / hr + 0.15 * Math.sin(Math.atan2(z - c, x - c) * 3 + hx);
        for (let y = 0; y < L; y++) if (r < 1 - y * 0.18) g.set(x, y, z, mix(0x4e4034, 0x3a3028, y / L));
      }
      const m = vox(g, v, [c, 0, c], 'hill'); m.position.set(hx, 0, hz); this.hills.add(m);
    }
    // bosques
    const pts = [];
    for (let i = 0; i < 6000 && pts.length < 3500; i++) {
      const x = -14 + R() * 70, z = -45 + R() * 90;
      if (Math.hypot((x) / 20, z / 13) < 1.1) continue;
      if (x > 12 && x < 34 && z > -2 && z < 18) continue;
      if (hash3(Math.floor(x / 5), 3, Math.floor(z / 5)) < 0.55) continue;
      pts.push([x, 0, z, R() * 6, 0.9 + R() * 0.4]);
    }
    this.pines = instanced(pineGeometry(false, 0x2c3a26), 0.07, [3.5, 0, 3.5], 'pineS', pts); out.add(this.pines);
    // puerta: dos torres que se elevan + engranajes
    this.gate = new THREE.Group(); this.gate.position.set(17, 0, 6); this.gate.rotation.y = -0.45; out.add(this.gate);
    this.towers = [-1, 1].map((s) => { const m = gateTowerGrid(); m.position.set(0, 0, s * 1.6); this.gate.add(m); return m; });
    const gg = gearGrid(14, 14, 3, 0x8a6a40);
    this.gateGears = [-1, 1].map((s) => { const m = vox(gg, 0.06, [17, 0, 17], 'gear', { roughness: 0.4, metalness: 0.8 }); m.position.set(0.6, 0.05, s * 3.1); this.gate.add(m); return m; });
    // muros junto a la puerta
    const wg = new Grid(10, 22, 90); wg.box(0, 0, 0, 9, 21, 89, red); for (let z = 0; z < 90; z += 4) wg.box(0, 22, z, 9, 22, z + 1, red);
    for (const s of [-1, 1]) { const m = vox(wg, 0.06, [5, 0, s > 0 ? 0 : 90], 'redwood'); m.position.set(0, 0, s * 2.1); this.gate.add(m); }
    // Fortaleza Roja y Pozo Dragon
    this.keep = buildRedKeep(); this.keep.position.set(-9, 0, -3); this.keep.rotation.y = Math.PI / 2 - 0.3; out.add(this.keep);
    const dg = new Grid(40, 16, 40); dg.sdf((x, y, z) => Math.max(sd.sphere(x, y, z, 20, 0, 20, 19), -sd.sphere(x, y, z, 20, 0, 20, 16)), (x, y, z) => (Math.floor(Math.atan2(z - 20, x - 20) * 5) % 2 ? 0x5a7a52 : 0x4a6a46));
    this.pit = vox(dg, 0.08, [20, 0, 20], 'pit', { roughness: 0.5, metalness: 0.4 }); this.pit.position.set(4, 0, -6); out.add(this.pit);
    // nubes
    const ct = cloudTexture(9);
    this.clouds = new THREE.Group(); out.add(this.clouds);
    for (let i = 0; i < 12; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: ct, color: 0x2a2620, transparent: true, depthWrite: false, fog: false }));
      s.position.set((hash3(i, 1, 4) - 0.5) * 200, 40 + hash3(i, 2, 4) * 60, (hash3(i, 3, 4) - 0.5) * 200); s.scale.set(120, 80, 1); this.clouds.add(s);
    }
    this.sun = new THREE.DirectionalLight(0xffe2c0, 1.6); this.sun.castShadow = true; this.sun.shadow.mapSize.set(2048, 2048); this.sun.shadow.bias = -0.0004; this.sun.shadow.normalBias = 0.02;
    out.add(this.sun); out.add(this.sun.target);
    this.hemi = new THREE.HemisphereLight(0xa08e7a, 0x2a2018, 0.7); out.add(this.hemi);

    // ---------------- interiores ----------------
    const I = this.inA = new THREE.Group(); I.position.set(...SI); this.root.add(I);
    this.buildMech(I);
    const N = this.inB = new THREE.Group(); N.position.set(...SN); this.root.add(N);
    this.buildNave(N);
  }

  buildMech(I) {
    // torre con tejado en estrella y rodillos (cenital). La torre esta en (0,0,0), techo a y=6
    const v = 0.05;
    const tg = new Grid(70, 120, 70); const c = 35;
    // cuerpo de la torre (hueco por dentro: el pozo)
    tg.sdf((x, y, z) => Math.max(sd.box(x, y, z, c, 60, c, 26, 60, 26), -sd.box(x, y, z, c, 60, c, 20, 61, 20)), (x, y, z) => (y % 10 === 0 ? GOLD : red(x, y, z)));
    // remaches dorados
    tg.paint((x, y, z, col) => (y % 10 === 5 && (x + z) % 6 === 0 ? 0xf0d080 : col));
    this.mechTower = vox(tg, v, [c, 0, c], 'redwood'); I.add(this.mechTower);
    // tejado en estrella: 4 paneles triangulares que se abren
    this.roof = [];
    for (let k = 0; k < 4; k++) {
      const pg = new Grid(56, 4, 40);
      for (let x = 0; x < 56; x++) for (let z = 0; z < 40; z++) if (Math.abs(x - 28) < (40 - z) * 0.7 && z < 40) for (let y = 0; y < 3; y++) pg.set(x, y, z, (x + z) % 7 === 0 && y === 2 ? 0xf0d080 : RED[(x >> 2) % 4]);
      const piv = new THREE.Group(); piv.position.set(0, 6.05, 0); piv.rotation.y = k * Math.PI / 2; I.add(piv);
      const m = vox(pg, v, [28, 0, 0], 'redwood'); m.position.set(0, 0, 1.0); piv.add(m);
      const hinge = new THREE.Group(); hinge.position.set(0, 0, 1.0); piv.add(hinge); piv.remove(m); hinge.add(m); m.position.set(0, 0, 0);
      this.roof.push(hinge);
    }
    // rodillos y engranajes alrededor
    this.rollers = [];
    for (let k = 0; k < 3; k++) {
      const rg = new Grid(30, 30, 50); rg.sdf((x, y, z) => Math.max(Math.hypot(x - 15, y - 15) - 13, Math.abs(z - 25) - 24), (x, y, z) => (z % 8 < 2 ? GOLD : (Math.floor(Math.atan2(y - 15, x - 15) * 3) % 2 ? RED[1] : RED[3])));
      const m = vox(rg, v, [15, 15, 25], 'redwood'); m.position.set(-2.0 - k * 1.25, 4.6, 1.2 - k * 0.6); m.rotation.y = 0.5; I.add(m); this.rollers.push(m);
    }
    this.mechGears = [];
    for (let k = 0; k < 5; k++) {
      const R0 = 8 + k * 3; const m = vox(gearGrid(R0, R0, 3, k % 2 ? 0xc0964a : 0x8a6a40), v, [R0 + 3, 0, R0 + 3], 'gear', { roughness: 0.4, metalness: 0.8 });
      m.position.set(-2 + (k % 3) * 1.2, 5.2 + k * 0.1, -2.5 - k * 0.6); m.rotation.z = Math.PI / 2 * (k % 2); I.add(m); this.mechGears.push(m);
    }
    // marco con mapa pintado
    const fg = new Grid(50, 4, 70); fg.box(0, 0, 0, 49, 3, 69, (x, y, z) => (x < 3 || x > 46 || z < 3 || z > 66 ? RED[3] : (y === 3 ? mix(0x3a5a6a, 0xb8a888, hash3(x >> 2, 0, z >> 2)) : RED[0])));
    const fm = vox(fg, v, [25, 0, 35], 'redwood'); fm.position.set(-1.5, 5.6, -4.8); I.add(fm);
    // suelo del set (madera oscura)
    const floor = new THREE.Mesh(new THREE.RingGeometry(1.4, 40, 48), new THREE.MeshStandardMaterial({ color: 0x3a2a20, roughness: 0.9 })); floor.rotation.x = -Math.PI / 2; floor.position.y = 0.0; I.add(floor);
    // pozo interior: anillos que giran con luces
    this.shaft = new THREE.Group(); this.shaft.position.set(0, 0, 0); I.add(this.shaft);
    for (let k = 0; k < 9; k++) {
      const rg = new Grid(44, 4, 44);
      for (let x = 0; x < 44; x++) for (let z = 0; z < 44; z++) {
        const r = Math.hypot(x + 0.5 - 22, z + 0.5 - 22), a = Math.atan2(z - 22, x - 22);
        if (r > 21 || r < 17) continue;
        for (let y = 0; y < 4; y++) g4(rg, x, y, z, Math.floor(a * 9) % 7 === 0 && y === 3 ? 0xffe0a0 : RED[(Math.floor(a * 8) + 8) % 4]);
      }
      rg.paint((x, y, z, col) => { if (col === 0xffe0a0) rg.setE(x, y, z, 255); return col; });
      const m = vox(rg, 0.045, [22, 0, 22], 'shaftring', { emiGain: 0.8, emiTint: 0xffd090 }); m.position.y = 5.5 - k * 0.65; this.shaft.add(m);
    }
    // sala de engranajes con el trono (bajo el pozo, y = -12)
    this.throneHallA = new THREE.Group(); this.throneHallA.position.set(0, -12, 0); I.add(this.throneHallA);
    const hg = new Grid(200, 110, 160); const hcx = 100, hcz = 40;
    // suelo de tablones radiales
    for (let x = 0; x < 200; x++) for (let z = 0; z < 160; z++) {
      const a = Math.atan2(z - 40, x - 100); hg.set(x, 0, z, Math.floor(a * 18) % 2 ? 0x4a3628 : 0x5a4232);
    }
    hg.box(0, 0, 155, 199, 109, 159, red); hg.box(0, 0, 0, 199, 109, 3, (x, y, z) => shade(red(x, y, z), (x >> 3) % 2 ? 0.32 : 0.4)); hg.box(0, 0, 0, 4, 109, 159, red); hg.box(195, 0, 0, 199, 109, 159, red);
    // tarima del trono al fondo (z bajo)
    hg.box(70, 1, 4, 130, 6, 30, (x, y, z) => shade(red(x, y, z), 0.6)); hg.box(78, 7, 4, 122, 10, 22, (x, y, z) => shade(red(x, y, z), 0.6));
    const hm = vox(hg, 0.1, [hcx, 0, hcz], 'hallA', { roughness: 0.8 }); this.throneHallA.add(hm);
    // engranajes gigantes en las paredes
    this.wallGears = [];
    for (let k = 0; k < 6; k++) {
      const R0 = 30 + (k % 3) * 10; const m = vox(gearGrid(R0, Math.round(R0 * 0.8), 4, 0x6a5038), 0.1, [R0 + 3, 2, R0 + 3], 'gearW', { roughness: 0.5, metalness: 0.6 });
      const s = k % 2 ? 1 : -1; m.rotation.z = Math.PI / 2; m.position.set(s * 9.4, 3 + (k >> 1) * 1.5, -2 + (k >> 1) * 4);
      if (k === 5) { m.rotation.set(Math.PI / 2, 0, 0); m.position.set(0, 5.5, -3.6); } this.throneHallA.add(m); this.wallGears.push(m);
    }
    const th = ironThrone(0.035); this.thA = vox(th.g, th.v, th.origin, 'iron', { roughness: 0.45, metalness: 0.75 }); this.thA.position.set(0, 1.0, -2.3); this.throneHallA.add(this.thA);
    const sk = skullGrid();
    for (const s of [-1, 1]) { const m = vox(sk, 0.06, [10, 0, 9], 'bone'); m.position.set(s * 3.2, 0.1, -1.2); m.rotation.y = s > 0 ? Math.PI * 0.85 : Math.PI * 0.15; this.throneHallA.add(m); }
    this.aLight = new THREE.SpotLight(0xffd8a8, 40, 30, 0.5, 0.7, 1.3); this.aLight.position.set(0, 9, 3); this.aLight.target = this.thA; this.throneHallA.add(this.aLight);
    this.aAmb = new THREE.HemisphereLight(0x8a7462, 0x1a120c, 0.5); I.add(this.aAmb);
    for (const sx of [-1, 1]) { const l = new THREE.PointLight(0xffb070, 35, 12, 1.6); l.position.set(sx * 7.5, 3, 1.5); this.throneHallA.add(l); }
    this.mechSun = new THREE.DirectionalLight(0xffe0c0, 1.6); this.mechSun.position.set(5, 20, 8); I.add(this.mechSun);
  }

  buildNave(N) {
    const v = 0.1;
    const g = new Grid(120, 120, 300); const cx = 60;
    const WOOD = [0x3a261a, 0x4a3022, 0x2e1e14, 0x553a28];
    const wd = (x, y, z) => WOOD[Math.floor(hash3(x >> 1, y >> 3, z) * 4)];
    // suelo de tablones (a lo largo de z)
    g.box(0, 0, 0, 119, 0, 299, (x, y, z) => (x % 6 === 0 ? 0x2a1a12 : wd(x, 0, z)));
    // muros laterales con columnas
    g.box(0, 0, 0, 3, 119, 299, wd); g.box(116, 0, 0, 119, 119, 299, wd);
    for (let z = 20; z < 300; z += 40) for (const x of [14, 105]) g.box(x - 4, 0, z - 4, x + 4, 119, z + 4, wd);
    // muro del fondo con hueco de ventana
    g.box(0, 0, 0, 119, 119, 5, wd);
    g.carve((x, y, z) => { const dx = x - cx; const top = 80 + Math.sqrt(Math.max(0, 225 - dx * dx)); return Math.abs(dx) < 15 && y > 10 && y < top && z < 7 ? -1 : 1; });
    // tarima escalonada del trono
    for (let k = 0; k < 4; k++) g.box(cx - 22 + k * 3, 1 + k, 8, cx + 22 - k * 3, 1 + k, 34 - k * 5, (x, y, z) => wd(x, y, z));
    // escombros: tablones caidos y espadas clavadas
    const R = rng(3);
    for (let k = 0; k < 26; k++) {
      const z0 = 60 + R() * 220, x0 = 30 + R() * 60, L = 10 + R() * 18, a = R() * Math.PI;
      g.sdf((x, y, z) => sd.box((x - x0) * Math.cos(a) + (z - z0) * Math.sin(a), y - 1.5, -(x - x0) * Math.sin(a) + (z - z0) * Math.cos(a), 0, 0, 0, L / 2, 1, 1.5), wd, [Math.floor(x0 - L), 0, Math.floor(z0 - L), Math.ceil(x0 + L), 4, Math.ceil(z0 + L)]);
    }
    for (let k = 0; k < 30; k++) {
      const z0 = 40 + R() * 250, x0 = R() < 0.5 ? 8 + R() * 14 : 98 + R() * 14;
      g.sdf((x, y, z) => sd.cone(x, y, z, x0, 0, z0, x0 + (R() - 0.5) * 2, 12 + R() * 8, z0, 0.9, 0.3), () => 0x7a7c80, [Math.floor(x0 - 3), 0, Math.floor(z0 - 3), Math.ceil(x0 + 3), 22, Math.ceil(z0 + 3)]);
    }
    // relojes tallados en las paredes (engranajes en relieve)
    this.naveMesh = vox(g, v, [cx, 0, 0], 'nave', { roughness: 0.8 }); N.add(this.naveMesh);
    for (const s of [-1, 1]) for (let k = 0; k < 3; k++) {
      const m = vox(gearGrid(14, 12, 2, 0x8a6440), 0.1, [17, 1, 17], 'gearW'); m.rotation.z = Math.PI / 2; m.position.set(s * 5.6, 3.5 + (k % 2) * 2, 2.5 + k * 4); N.add(m);
    }
    this.win = windowMesh(); this.win.position.set(0, 1.4, 0.25); N.add(this.win);
    const th = ironThrone(0.035); this.thB = vox(th.g, th.v, th.origin, 'iron', { roughness: 0.45, metalness: 0.75 }); this.thB.position.set(0, 0.5, 1.6); N.add(this.thB);
    this.bLight = new THREE.SpotLight(0xfff0dc, 45, 40, 0.45, 0.6, 1.2); this.bLight.position.set(0, 6, -2); this.bLight.target.position.set(0, 0, 14); N.add(this.bLight); N.add(this.bLight.target);
    this.bFill = new THREE.PointLight(0xffc890, 5, 18, 1.4); this.bFill.position.set(0, 3, 6); N.add(this.bFill);
    this.bAmb = new THREE.HemisphereLight(0x6a5444, 0x140c08, 0.45); N.add(this.bAmb);
    this.bBeam = new THREE.PointLight(0xffe8c8, 6, 12, 1.5); this.bBeam.position.set(-5, 7, 12); N.add(this.bBeam);
  }

  update(lt, cam, st, t) {
    const where = st.where || 'map';
    this.out.visible = where === 'map';
    this.inA.visible = where === 'mech';
    this.inB.visible = where === 'nave';
    if (where === 'map') {
      const sc = st.shadow || [0, 0, 0, 30];
      const s = this.sun.shadow.camera; s.left = -sc[3]; s.right = sc[3]; s.top = sc[3]; s.bottom = -sc[3]; s.near = 1; s.far = 400; s.updateProjectionMatrix();
      this.sun.target.position.set(sc[0], sc[1], sc[2]); this.sun.position.set(sc[0] + 50, sc[1] + 70, sc[2] + 60);
      const rise = st.towerRise ?? 1;
      this.towers.forEach((m) => { m.scale.y = 0.2 + 0.8 * rise; });
      this.gateGears.forEach((m, i) => (m.rotation.y = lt * (i ? 1.2 : -1.2)));
      this.clouds.visible = !!st.clouds;
      this.lbl.visible = st.lbl !== false;
    } else if (where === 'mech') {
      const op = st.roofOpen ?? 0;
      this.roof.forEach((h) => (h.rotation.x = op * 1.4));
      this.rollers.forEach((m, i) => (m.rotation.z = lt * (i % 2 ? 1.5 : -1.5)));
      this.mechGears.forEach((m, i) => (m.rotation.y = lt * (i % 2 ? 1 : -1) * (0.6 + i * 0.2)));
      this.shaft.children.forEach((m, i) => (m.rotation.y = lt * (i % 2 ? 1.1 : -0.9)));
      this.wallGears.forEach((m, i) => (m.rotation.x = lt * (i % 2 ? 0.25 : -0.25)));
      this.aAmb.intensity = st.amb ?? 0.5;
      this.shaft.visible = st.shaft !== false;
      this.mechSun.intensity = st.sunI ?? 1.6;
    }
  }
}
function g4(g, x, y, z, c) { g.set(x, y, z, c); }
