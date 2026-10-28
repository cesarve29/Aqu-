// Generacion procedural de los dos mundos y de sus ediciones en el tiempo.
import { World, B } from './voxel.js';
import { fbm, hash2, smooth, lerp, clamp } from './util.js';
import * as S from './story.js';

export function genOverworld() {
  const SX = 128, SY = 48, SZ = 128;
  const w = new World(SX, SY, SZ);
  const heights = new Int16Array(SX * SZ);
  const [mx, mz] = S.MEADOW;
  for (let x = 0; x < SX; x++) for (let z = 0; z < SZ; z++) {
    const n = fbm(x / 46, z / 46, 4, 1);
    const m = fbm(x / 80 + 10, z / 80, 3, 7);
    const d = Math.hypot(x - mx, z - mz);
    let h = 3 + n * 24 + Math.max(0, m - 0.5) * 60 * smooth((d - 26) / 22);
    h = lerp(h, S.GROUND, 1 - smooth((d - 20) / 22));
    const e = Math.min(x, z, SX - 1 - x, SZ - 1 - z);
    h = lerp(S.SEA - 5, h, smooth(e / 22));
    h = Math.floor(clamp(h, 3, SY - 8));
    heights[x * SZ + z] = h;
    for (let y = 0; y <= h; y++) {
      let b;
      if (y === h) b = h <= S.SEA + 1 ? B.SAND : h >= 30 ? B.SNOW : B.GRASS;
      else if (y > h - 4) b = h <= S.SEA + 1 ? B.SAND : B.DIRT;
      else b = hash2(x * 7 + y, z, 3) < 0.012 ? B.ORE : B.STONE;
      w.set(x, y, z, b);
    }
  }
  const H = (x, z) => heights[x * SZ + z];
  const tree = (x, z, th) => {
    const y0 = H(x, z) + 1;
    for (let y = y0; y < y0 + th; y++) w.set(x, y, z, B.LOG);
    const top = y0 + th - 1;
    for (let dy = -2; dy <= 1; dy++) {
      const r = dy <= -1 ? 2 : 1;
      for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) {
        if (Math.abs(dx) === r && Math.abs(dz) === r && hash2(x + dx, z + dz, dy + 40) < 0.6) continue;
        if (dy === 1 && Math.abs(dx) + Math.abs(dz) > 1) continue;
        if (!w.get(x + dx, top + dy, z + dz)) w.set(x + dx, top + dy, z + dz, B.LEAVES);
      }
    }
  };
  // arboles aleatorios
  for (let x = 3; x < SX - 3; x++) for (let z = 3; z < SZ - 3; z++) {
    const d = Math.hypot(x - mx, z - mz);
    if (d < 21) continue;
    const h = H(x, z);
    if (h <= S.SEA + 1 || h >= 28) continue;
    if (hash2(x, z, 77) < 0.022) tree(x, z, 4 + Math.floor(hash2(x, z, 78) * 3));
  }
  // un par de arboles decorativos cerca de la cabana
  tree(46, 61, 5); tree(47, 47, 6); tree(S.TREE.x, S.TREE.z, S.TREE.h);
  // cabana
  const C = S.CABIN;
  for (let x = C.x0; x <= C.x1; x++) for (let z = C.z0; z <= C.z1; z++) {
    w.set(x, C.y - 1, z, B.PLANKS);
    for (let y = C.y; y <= C.y + 3; y++) {
      const edge = x === C.x0 || x === C.x1 || z === C.z0 || z === C.z1;
      const corner = (x === C.x0 || x === C.x1) && (z === C.z0 || z === C.z1);
      if (y === C.y + 3) w.set(x, y, z, B.LOG);
      else if (corner) w.set(x, y, z, B.LOG);
      else if (edge) w.set(x, y, z, B.PLANKS);
    }
  }
  for (let x = C.x0 + 1; x < C.x1; x++) for (let z = C.z0 + 1; z < C.z1; z++) w.set(x, C.y + 4, z, B.PLANKS);
  w.set(53, C.y, C.z1, B.AIR); w.set(53, C.y + 1, C.z1, B.AIR); // puerta
  w.set(51, C.y + 1, C.z1, B.AIR); w.set(55, C.y + 1, C.z1, B.AIR); // ventanas
  w.set(C.x1, C.y + 1, 52, B.AIR); w.set(C.x0, C.y + 1, 52, B.AIR);
  w.set(52, C.y + 1, C.z1 + 1, B.GLOW); w.set(54, C.y + 1, C.z1 + 1, B.GLOW); // farolillos
  w.set(52, C.y, C.z1 + 1, B.COBBLE); w.set(54, C.y, C.z1 + 1, B.COBBLE);
  w.set(S.TABLE.x, S.TABLE.y, S.TABLE.z, B.TABLE);
  // anillo de piedra para el portal
  for (let x = 60; x <= 67; x++) for (let z = 79; z <= 81; z++) w.set(x, S.GROUND, z, B.COBBLE);

  // --- ediciones en el tiempo ---
  const edits = [];
  S.LOG_BREAK.forEach((t, i) => edits.push({ t, x: S.TREE.x, y: S.TREE.y0 + i, z: S.TREE.z, b: B.AIR }));
  const P = S.PORTAL;
  const frame = [];
  for (let x = P.x0; x <= P.x0 + 3; x++) frame.push([x, P.y0]);
  for (let y = P.y0 + 1; y <= P.y0 + 3; y++) frame.push([P.x0, y]);
  for (let y = P.y0 + 1; y <= P.y0 + 3; y++) frame.push([P.x0 + 3, y]);
  for (let x = P.x0; x <= P.x0 + 3; x++) frame.push([x, P.y0 + 4]);
  frame.forEach(([x, y], i) => edits.push({ t: S.PORTAL_PLACE[i], x, y, z: P.z, b: B.OBSIDIAN }));
  const K = S.CRATER;
  for (let x = K.x - 5; x <= K.x + 5; x++) for (let z = K.z - 5; z <= K.z + 5; z++) for (let y = K.y - 4; y <= K.y + 6; y++) {
    const d = Math.hypot(x - K.x, (y - K.y) * 1.3, z - K.z) + (hash2(x * 3 + y, z, 91) - 0.5) * 1.4;
    if (d < K.r && w.get(x, y, z)) edits.push({ t: K.t, x, y, z, b: B.AIR });
  }
  return { world: w, edits, heights, H, SX, SZ };
}

export function genEnd() {
  const SX = 96, SY = 64, SZ = 96;
  const w = new World(SX, SY, SZ);
  const [cx, cz] = S.END_C;
  const top = new Int16Array(SX * SZ).fill(-1);
  for (let x = 0; x < SX; x++) for (let z = 0; z < SZ; z++) {
    const d = Math.hypot(x - cx, z - cz);
    const R = 35 + (fbm(x / 14, z / 14, 3, 5) - 0.5) * 12;
    if (d > R) continue;
    const t = S.END_TOP + Math.round((fbm(x / 20, z / 20, 2, 9) - 0.5) * 2 * smooth(d / 12));
    const bot = S.END_TOP - Math.pow(1 - d / R, 0.55) * 24 - 2;
    for (let y = Math.max(1, Math.floor(bot)); y <= t; y++) w.set(x, y, z, B.ENDSTONE);
    top[x * SZ + z] = t;
  }
  // pilares de obsidiana
  for (const p of S.PILLARS) {
    const base = S.END_TOP;
    for (let dx = -3; dx <= 3; dx++) for (let dz = -3; dz <= 3; dz++) {
      if (dx * dx + dz * dz > 7.5) continue;
      for (let y = base - 3; y <= base + p.h; y++) w.set(p.x + dx, y, p.z + dz, B.OBSIDIAN);
    }
    w.set(p.x, base + p.h + 1, p.z, B.GLOW);
  }
  // fuente del portal de salida
  for (let dx = -4; dx <= 4; dx++) for (let dz = -4; dz <= 4; dz++) {
    const d = Math.hypot(dx, dz);
    if (d > 4.2) continue;
    const x = cx + dx, z = cz + dz;
    if (d > 3.0) w.set(x, S.END_TOP + 1, z, B.COBBLE);
    else { w.set(x, S.END_TOP, z, B.AIR); w.set(x, S.END_TOP - 1, z, B.COBBLE); }
  }
  for (let y = S.END_TOP - 1; y <= S.END_TOP + 4; y++) w.set(cx, y, cz, B.COBBLE);
  w.set(cx + 1, S.END_TOP + 3, cz, B.GLOW); w.set(cx - 1, S.END_TOP + 3, cz, B.GLOW);
  w.set(cx, S.END_TOP + 3, cz + 1, B.GLOW); w.set(cx, S.END_TOP + 3, cz - 1, B.GLOW);
  const H = (x, z) => {
    const v = top[Math.floor(x) * SZ + Math.floor(z)];
    return v < 0 ? S.END_TOP : v;
  };
  return { world: w, edits: [], H, SX, SZ };
}
