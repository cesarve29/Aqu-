// Salon del trono en ruinas, cubierto de ceniza, con la ciudad destruida alrededor.
import * as THREE from 'three';
import { Grid, voxMesh, voxMaterial, sd, jitter, mix, shade, hash3, fbm, rng, clamp, lerp } from './voxel.js';

export const WV = 0.25; // tamano de voxel del mundo (m)
// Coordenadas del mundo (m): Dany yace cerca del origen; el trono en z = -12 sobre la tarima.
export const THRONE_POS = new THREE.Vector3(0, 2.0, -13.0);

const ASH = 0xd2d6da, ASH2 = 0xbfc4c9, STONE = 0x6a5a55, STONE_D = 0x3e3533, REDSTONE = 0x6b3b33, DARK = 0x2a2626;

function ashCover(g, amt = 1) {
  // pinta de ceniza las caras superiores expuestas
  for (let z = 0; z < g.nz; z++) for (let x = 0; x < g.nx; x++) {
    for (let y = g.ny - 1; y >= 0; y--) {
      const i = g.idx(x, y, z);
      if (g.c[i] >= 0) {
        if (hash3(x, y, z * 7) < 0.92 * amt) g.c[i] = jitter(hash3(x, z, 3) < 0.5 ? ASH : ASH2, 0.08, x, y, z);
        if (y > 0 && hash3(x, y - 1, z) < 0.5 * amt) { const j = g.idx(x, y - 1, z); if (g.c[j] >= 0) g.c[j] = jitter(ASH2, 0.12, x, y, z); }
        break;
      }
    }
  }
}

export function buildWorld(scene) {
  const group = new THREE.Group();
  // rejilla: x -24..24 m, y 0..28 m, z -34..18 m
  const NX = 192, NY = 112, NZ = 208;
  const OX = 96, OZ = 136; // origen en voxeles (x=0,z=0 del mundo)
  const g = new Grid(NX, NY, NZ);
  const W2V = (m) => m / WV;
  const vx = (m) => Math.round(m / WV) + OX, vz = (m) => Math.round(m / WV) + OZ, vy = (m) => Math.round(m / WV);
  const R = rng(1234);
  const BB = (x0, y0, z0, x1, y1, z1, pad = 3) => [Math.floor(Math.min(x0, x1)) - pad, Math.max(0, Math.floor(Math.min(y0, y1)) - pad), Math.floor(Math.min(z0, z1)) - pad, Math.ceil(Math.max(x0, x1)) + pad, Math.ceil(Math.max(y0, y1)) + pad, Math.ceil(Math.max(z0, z1)) + pad];

  // --- suelo: losas oscuras + ceniza ondulada
  for (let z = 0; z < NZ; z++) for (let x = 0; x < NX; x++) {
    const wx = (x - OX) * WV, wz = (z - OZ) * WV;
    const n = fbm(wx * 0.18, 0, wz * 0.18, 3);
    const flat = Math.abs(wx) < 6 && wz > -9 && wz < 7;
    const h = flat ? 2 + (n > 0.62 && (Math.abs(wx) > 3.5 || wz > 4) ? 1 : 0) : 2 + Math.floor(n * 3.2);
    for (let y = 0; y < h; y++) g.set(x, y, z, jitter(y < h - 1 ? STONE_D : ASH, 0.1, x, y, z));
  }

  // --- tarima del trono: escalones
  const steps = 7;
  for (let s = 0; s < steps; s++) {
    const zf = -8.2 - s * 0.6; // borde frontal del escalon
    g.box(vx(-7 + s * 0.35), 2, vz(-19), vx(7 - s * 0.35), 2 + s + 1, vz(zf), (x, y, z) => jitter(y === 2 + s ? STONE : STONE_D, 0.12, x, y, z));
  }
  // --- muro del fondo con grandes vanos
  g.box(vx(-24), 2, vz(-24), vx(24), vy(22), vz(-22.5), (x, y, z) => jitter(REDSTONE, 0.18, x, y, z));
  // vanos (ventanales) y destruccion
  for (const cx of [-15, -7.5, 7.5, 15]) {
    g.carve((x, y, z) => sd.box(x, y, z, vx(cx), vy(11), vz(-23), W2V(2.6), W2V(7), W2V(3)), BB(vx(cx - 3), 0, vz(-26), vx(cx + 3), vy(21), vz(-20)));
    g.carve((x, y, z) => sd.sphere(x, y, z, vx(cx), vy(18), vz(-23), W2V(2.6)), BB(vx(cx - 3), vy(15), vz(-26), vx(cx + 3), vy(21), vz(-20)));
  }
  // gran rosetón circular (marco) a la izquierda al fondo
  const ring = (cx, cy, cz, r, th) => (x, y, z) => {
    const dx = x - cx, dy = y - cy, dz = z - cz;
    const rr = Math.hypot(dx, dy);
    return Math.max(Math.abs(rr - r) - th, Math.abs(dz) - th);
  };
  const RB = BB(vx(-8), vy(9), vz(-25), vx(2), vy(19), vz(-21));
  g.carve((x, y, z) => sd.sphere(x, y, z, vx(-3), vy(14), vz(-23), W2V(4.6)), RB);
  g.sdf(ring(vx(-3), vy(14), vz(-23), W2V(4.2), W2V(0.45)), (x, y, z) => jitter(STONE, 0.15, x, y, z), RB);
  // radios del rosetón
  for (let k = 0; k < 8; k++) {
    const a = k * Math.PI / 4;
    if (k === 3 || k === 6) continue; // rotos
    g.sdf((x, y, z) => sd.cone(x, y, z, vx(-3), vy(14), vz(-23), vx(-3) + Math.cos(a) * W2V(4.2), vy(14) + Math.sin(a) * W2V(4.2), vz(-23), 0.9, 0.9), (x, y, z) => jitter(STONE, 0.15, x, y, z), RB);
  }

  // --- columnas laterales (algunas rotas), dos hileras
  for (const side of [-1, 1]) {
    for (let i = 0; i < 6; i++) {
      const cx = side * 11, cz = -19 + i * 6;
      const broken = hash3(i, side, 9) < 0.55;
      const top = broken ? 4 + hash3(i, side, 1) * 9 : 20;
      g.sdf((x, y, z) => sd.box(x, y, z, vx(cx), vy(top / 2), vz(cz), W2V(1.0), W2V(top / 2), W2V(1.0)) - 0.5, (x, y, z) => jitter(REDSTONE, 0.2, x, y, z), BB(vx(cx - 1.2), 0, vz(cz - 1.2), vx(cx + 1.2), vy(top), vz(cz + 1.2)));
      // capitel
      if (!broken) g.box(vx(cx - 1.5), vy(19.5), vz(cz - 1.5), vx(cx + 1.5), vy(20.5), vz(cz + 1.5), (x, y, z) => jitter(STONE, 0.15, x, y, z));
      // escombro al pie de las rotas
      if (broken) for (let k = 0; k < 6; k++) {
        const bx = cx + (R() - 0.5) * 5 - side * 2, bz = cz + (R() - 0.5) * 5, br = 0.5 + R() * 1.1;
        g.sdf((x, y, z) => sd.box(x, y, z, vx(bx), vy(br * 0.6 + 0.4), vz(bz), W2V(br), W2V(br * 0.6), W2V(br * 0.8)) - 0.3, (x, y, z) => jitter(REDSTONE, 0.25, x, y, z), BB(vx(bx - br), 0, vz(bz - br), vx(bx + br), vy(br * 1.3 + 0.5), vz(bz + br)));
      }
    }
    // muro lateral bajo, muy destruido
    g.sdf((x, y, z) => {
      const wz = (z - OZ) * WV;
      const hmax = 3 + 6 * fbm(wz * 0.15, side * 5, 1, 3);
      return Math.max(sd.box(x, y, z, vx(side * 13.5), 0, vz(-6), W2V(0.9), 999, W2V(17)), y - vy(hmax));
    }, (x, y, z) => jitter(REDSTONE, 0.2, x, y, z), BB(vx(side * 13.5 - 1), 0, vz(-24), vx(side * 13.5 + 1), vy(10), vz(12)));
  }

  // --- celosias metalicas caidas (ventanales) apoyadas en diagonal
  const lattice = (cx, cz, ang, h, w) => {
    const ca = Math.cos(ang), sa = Math.sin(ang);
    g.sdf((x, y, z) => {
      const lx = (x - vx(cx)), ly = y - 2, lz = z - vz(cz);
      // rotacion en el plano xy (inclinada)
      const u = lx * ca + ly * sa, v = -lx * sa + ly * ca;
      if (v < 0 || v > W2V(h) || Math.abs(u) > W2V(w) || Math.abs(lz) > 0.6) return 1;
      const gu = ((u / W2V(0.9)) % 1 + 1) % 1, gv = ((v / W2V(0.9)) % 1 + 1) % 1;
      return (gu < 0.22 || gv < 0.22) ? -1 : 1;
    }, (x, y, z) => jitter(0x3a3836, 0.2, x, y, z), BB(vx(cx) - W2V(h + w), 0, vz(cz) - 2, vx(cx) + W2V(h + w), vy(h + 2), vz(cz) + 2));
  };
  lattice(-17, -9, 0.45, 13, 2.5);
  lattice(18, -14, -0.35, 15, 2.5);
  lattice(-9, 12, 0.6, 9, 2);

  // --- montones de escombro y vigas sobre el suelo
  for (let k = 0; k < 70; k++) {
    const bx = (R() - 0.5) * 44, bz = -20 + R() * 36;
    if (Math.abs(bx) < 4.5 && bz > -8 && bz < 6) continue; // area de los personajes despejada
    const br = 0.4 + R() * 1.4;
    g.sdf((x, y, z) => sd.ellip(x, y, z, vx(bx), 2, vz(bz), W2V(br * 1.4), W2V(br * 0.8), W2V(br)) + fbm(x * 0.3, y * 0.3, z * 0.3, 2) * 2 - 1,
      (x, y, z) => jitter(hash3(x >> 2, y >> 2, z >> 2) < 0.5 ? REDSTONE : STONE, 0.3, x, y, z), BB(vx(bx - br * 1.6), 0, vz(bz - br * 1.2), vx(bx + br * 1.6), vy(br + 1), vz(bz + br * 1.2)));
  }
  // vigas caidas
  for (let k = 0; k < 10; k++) {
    const ax = (R() - 0.5) * 40, az = -18 + R() * 30;
    if (Math.abs(ax) < 5 && az > -9 && az < 6) continue;
    const ang = R() * Math.PI, L = 3 + R() * 5;
    const bx = ax + Math.cos(ang) * L, bz = az + Math.sin(ang) * L;
    g.sdf((x, y, z) => sd.cone(x, y, z, vx(ax), 3.5, vz(az), vx(bx), 3, vz(bz), 1.3, 1.1), (x, y, z) => jitter(0x4a3a30, 0.2, x, y, z), BB(vx(ax), 0, vz(az), vx(bx), 6, vz(bz)));
  }

  ashCover(g, 1);
  const mesh = voxMesh(g, { scale: WV, origin: [OX, 2, OZ], roughness: 0.95 });
  group.add(mesh);

  // --- ciudad en ruinas exterior (bloques gruesos, mas alla de los muros)
  const city = new Grid(200, 60, 200);
  const C = 1.0, COX = 100, COZ = 100;
  const R2 = rng(77);
  for (let k = 0; k < 340; k++) {
    let bx = (R2() - 0.5) * 190, bz = (R2() - 0.5) * 190;
    if (Math.abs(bx) < 30 && bz > -40 && bz < 26) continue;
    const w = 3 + R2() * 7, d = 3 + R2() * 7;
    const far = Math.hypot(bx, bz);
    const h = (2 + R2() * 12) * (far > 70 ? 1.2 : 1);
    const ruined = R2();
    city.sdf((x, y, z) => {
      const b = sd.box(x, y, z, bx + COX, h / 2, bz + COZ, w / 2, h / 2, d / 2);
      const cut = y - (h * (0.5 + 0.5 * fbm(x * 0.3, z * 0.3, k, 2)) + (ruined < 0.5 ? -h * 0.3 : 0));
      return Math.max(b, cut);
    }, (x, y, z) => jitter(mix(0x8a7468, 0x6b5a52, hash3(k, 1, 1)), 0.25, x, y, z), [Math.floor(bx + COX - w), 0, Math.floor(bz + COZ - d), Math.ceil(bx + COX + w), 40, Math.ceil(bz + COZ + d)]);
  }
  // torres altas lejanas
  for (let k = 0; k < 14; k++) {
    const a = R2() * Math.PI * 2, r = 55 + R2() * 35;
    const bx = Math.cos(a) * r, bz = Math.sin(a) * r, h = 18 + R2() * 22, w = 2.5 + R2() * 3;
    city.sdf((x, y, z) => Math.max(sd.box(x, y, z, bx + COX, h / 2, bz + COZ, w, h / 2, w), y - h * (0.6 + 0.4 * hash3(k, 2, 2)) - fbm(x, z, k) * 4),
      (x, y, z) => jitter(0x7a6a62, 0.2, x, y, z), [Math.floor(bx + COX - w - 1), 0, Math.floor(bz + COZ - w - 1), Math.ceil(bx + COX + w + 1), 59, Math.ceil(bz + COZ + w + 1)]);
  }
  ashCover(city, 0.85);
  const cityMesh = voxMesh(city, { scale: C, origin: [COX, 1.5, COZ], cast: false });
  group.add(cityMesh);

  // suelo exterior extenso
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(1600, 1600), new THREE.MeshStandardMaterial({ color: 0x9aa0a6, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -1.0; ground.receiveShadow = true;
  group.add(ground);

  scene.add(group);
  return { group, mesh, cityMesh };
}

// --- Trono de hierro (rejilla propia, se puede fundir)
export function buildThroneGrid() {
  const v = 0.06; // m
  const g = new Grid(64, 80, 48);
  const cx = 32, cz = 24;
  const IRON = 0x2b2b2d, IRON2 = 0x3a3836, RUST = 0x4a3a30;
  const col = (x, y, z) => jitter(hash3(x, y >> 1, z) < 0.3 ? RUST : (hash3(x >> 1, y, z) < 0.5 ? IRON : IRON2), 0.3, x, y, z);
  // base escalonada
  g.box(cx - 18, 0, cz - 14, cx + 18, 5, cz + 14, col);
  g.box(cx - 14, 6, cz - 11, cx + 14, 9, cz + 11, col);
  // asiento
  g.box(cx - 9, 10, cz - 8, cx + 9, 15, cz + 8, col);
  // brazos
  g.box(cx - 12, 10, cz - 7, cx - 9, 22, cz + 9, col);
  g.box(cx + 9, 10, cz - 7, cx + 12, 22, cz + 9, col);
  // respaldo
  g.box(cx - 10, 15, cz - 9, cx + 10, 40, cz - 6, col);
  const R = rng(55);
  // espadas del respaldo en abanico
  for (let k = 0; k < 46; k++) {
    const a = -1.25 + (k / 45) * 2.5 + (R() - 0.5) * 0.08;
    const L = 22 + R() * 22 * (1 - Math.abs(a) * 0.45);
    const bx = cx + Math.sin(a) * 5, by = 28, bz = cz - 8 + (R() - 0.5) * 3;
    const ex = bx + Math.sin(a) * L, ey = by + Math.cos(a) * L;
    g.sdf((x, y, z) => sd.cone(x, y, z, bx, by, bz, ex, ey, bz - 1, 1.1, 0.35), col);
  }
  // espadas sueltas alrededor de la base y los brazos
  for (let k = 0; k < 60; k++) {
    const a = R() * Math.PI * 2;
    const bx = cx + Math.cos(a) * (8 + R() * 10), bz = cz + Math.sin(a) * (6 + R() * 8), by = 2 + R() * 14;
    const dx = (R() - 0.5) * 12, dy = 2 + R() * 8, dz = (R() - 0.5) * 12;
    g.sdf((x, y, z) => sd.cone(x, y, z, bx, by, bz, bx + dx, by + dy, bz + dz, 0.8, 0.3), col);
  }
  return { grid: g, v, origin: [cx, 0, cz] };
}
