// Plano de la ciudad "Nueva Santander" y calendario de construccion bloque a bloque.
import { B, TimedGrid } from './cmesh.js';
import { hash2, rng } from '../../voxel-video/src/util.js';

export const SX = 168, SY = 100, SZ = 168, G = 9; // G = y del suelo (cesped)
export const WATER_Y = 8.72;
export const riverZ = (x) => 23 + 1.5 * Math.sin(x / 22);
export const ROADS_X = [36, 72, 108, 144];          // avenidas a lo largo de x (z inicial, 7 de ancho)
export const ROADS_Z = [8, 44, 80, 116, 152];       // calles a lo largo de z (x inicial)
export const MAIN = 80;
export const BX = [15, 51, 87, 123];                 // manzanas (x inicial, 29 de ancho)
export const BZ = [43, 79, 115, 151];

export function genCity() {
  const grid = new TimedGrid(SX, SY, SZ);
  // ---------------- terreno inicial: llanura con rio
  for (let x = 0; x < SX; x++) for (let z = 0; z < SZ; z++) {
    const d = Math.abs(z - riverZ(x));
    if (d <= 9) {
      grid.place(x, 4, z, B.STONE); grid.place(x, 5, z, B.SAND);
    } else {
      for (let y = 6; y < G; y++) grid.place(x, y, z, y < 7 ? B.STONE : B.DIRT);
      grid.place(x, G, z, d <= 11 ? B.SAND : B.GRASS);
      if (d <= 10.5) grid.place(x, 5, z, B.SAND);
    }
  }
  // algunos arboles salvajes antes de construir (en la orilla norte)
  const tasks = [];
  const task = (name, focus) => { const t = { name, focus, blocks: [] }; tasks.push(t); return t; };
  const put = (tk, x, y, z, b) => tk.blocks.push([x, y, z, b]);

  // ---------------- carreteras
  const inRoadX = (z) => ROADS_X.some((r) => z >= r && z < r + 7);
  const inRoadZ = (x) => ROADS_Z.some((r) => x >= r && x < r + 7);
  const roadCell = (tk, x, z, along) => {
    const r0 = along === 'x' ? ROADS_X.find((r) => z >= r && z < r + 7) : ROADS_Z.find((r) => x >= r && x < r + 7);
    if (r0 === undefined) return;
    const i = along === 'x' ? z - r0 : x - r0;
    const cross = along === 'x' ? inRoadZ(x) : inRoadX(z);
    let b;
    if (i === 0 || i === 6) b = cross ? B.ASPHALT : B.SIDEWALK;
    else if (cross) b = B.ASPHALT;
    else if (i === 3) b = ((along === 'x' ? x : z) % 4 < 2) ? (along === 'x' ? B.LINE_X : B.LINE_Z) : B.ASPHALT;
    else b = B.ASPHALT;
    // pasos de cebra junto a los cruces
    const near = along === 'x' ? (inRoadZ(x - 2) || inRoadZ(x + 2)) && !cross : (inRoadX(z - 2) || inRoadX(z + 2)) && !cross;
    if (near && i > 0 && i < 6) b = along === 'x' ? B.CROSS_Z : B.CROSS_X;
    put(tk, x, G, z, b);
  };
  const tMain = task('principal', [MAIN + 3, G, 90]);
  for (let z = 36; z < SZ; z++) for (let i = 0; i < 7; i++) roadCell(tMain, MAIN + i, z, 'z');
  for (const r of ROADS_X) {
    const tk = task('avenida ' + r, [84, G, r + 3]);
    for (let x = 0; x < SX; x++) for (let i = 0; i < 7; i++) if (!(x >= MAIN && x < MAIN + 7)) roadCell(tk, x, r + i, 'x');
  }
  for (const r of ROADS_Z) {
    if (r === MAIN) continue;
    const tk = task('calle ' + r, [r + 3, G, 100]);
    for (let z = 36; z < SZ; z++) for (let i = 0; i < 7; i++) if (!inRoadX(z)) roadCell(tk, r + i, z, 'z');
  }
  // puente sobre el rio
  const tBridge = task('puente', [MAIN + 3, G + 1, 24]);
  for (let z = 0; z < 36; z++) {
    const d = Math.abs(z - riverZ(MAIN + 3));
    for (let i = -1; i < 8; i++) {
      const x = MAIN + i;
      if (d <= 11.5) {
        if (i === -1 || i === 7) { put(tBridge, x, G, z, B.STONE_BRICK); put(tBridge, x, G + 1, z, z % 6 === 0 ? B.LAMP : B.STONE_BRICK); }
        else put(tBridge, x, G, z, i === 3 && z % 4 < 2 ? B.LINE_Z : B.ASPHALT);
      } else if (i >= 0 && i < 7) roadCell(tBridge, x, z, 'z');
    }
    if (Math.abs(z - riverZ(MAIN + 3)) < 1) for (let y = 5; y < G; y++) for (const i of [0, 3, 6]) put(tBridge, MAIN + i, y, z, B.STONE_BRICK);
  }

  // ---------------- generadores
  const R = rng(42);
  function tree(tk, x, z, kind = 'oak', h = 4) {
    const leaf = kind === 'cherry' ? B.CHERRY : B.LEAVES;
    for (let y = G + 1; y <= G + h; y++) put(tk, x, y, z, B.LOG);
    const top = G + h;
    const rad = kind === 'cherry' ? 3 : 2;
    for (let dy = -1; dy <= 2; dy++) {
      const r = dy <= 0 ? rad : dy === 1 ? rad - 1 : 1;
      for (let dx = -r; dx <= r; dx++) for (let dz = -r; dz <= r; dz++) {
        if (Math.abs(dx) === r && Math.abs(dz) === r && hash2(x + dx, z + dz, dy + 7) < 0.7) continue;
        if (dy === 2 && Math.abs(dx) + Math.abs(dz) > 1) continue;
        if (dx === 0 && dz === 0 && dy <= 0) continue;
        put(tk, x + dx, top + dy, z + dz, leaf);
      }
    }
  }
  function lamp(tk, x, z, h = 3) {
    for (let y = G + 1; y < G + 1 + h; y++) put(tk, x, y, z, B.BLACK);
    put(tk, x, G + 1 + h, z, B.LAMP);
  }
  // torre: capas de abajo arriba, perimetro hueco, techo, remate
  function tower(name, x0, z0, w, d, h, st) {
    const tk = task(name, [x0 + w / 2, G + h / 2, z0 + d / 2]);
    tk.tower = true;
    const band = st.band || 4;
    for (let k = 0; k < h; k++) {
      const y = G + 1 + k;
      let ins = 0;
      for (const [hf, i] of st.setbacks || []) if (k >= Math.floor(h * hf)) ins = i;
      const xa = x0 + ins, xb = x0 + w - 1 - ins, za = z0 + ins, zb = z0 + d - 1 - ins;
      const ring = [];
      for (let x = xa; x <= xb; x++) ring.push([x, za]);
      for (let z = za + 1; z <= zb; z++) ring.push([xb, z]);
      for (let x = xb - 1; x >= xa; x--) ring.push([x, zb]);
      for (let z = zb - 1; z > za; z--) ring.push([xa, z]);
      for (const [x, z] of ring) {
        const corner = (x === xa || x === xb) && (z === za || z === zb);
        if (st.oct && corner) continue;
        const side = x === xa || x === xb ? z - za : x - xa;
        let b = st.wall;
        if (corner || (st.oct && ((x === xa + 1 || x === xb - 1) && (z === za || z === zb) || (z === za + 1 || z === zb - 1) && (x === xa || x === xb)))) b = st.frame;
        else if (k % band === 0) b = st.frame;
        else if (st.cols && side % st.cols === 0) b = st.frame;
        if (k === 0 && !corner) b = side % 3 === 1 ? st.frame : B.GLASS;
        put(tk, x, y, z, b);
      }
      // techos intermedios en cada retranqueo
      let nextIns = ins;
      for (const [hf, i] of st.setbacks || []) if (k + 1 >= Math.floor(h * hf)) nextIns = i;
      if (nextIns !== ins || k === h - 1) {
        for (let x = xa; x <= xb; x++) for (let z = za; z <= zb; z++) {
          if (st.oct && (x === xa || x === xb) && (z === za || z === zb)) continue;
          if (x > xa + nextIns - ins - 1 && x < xb - (nextIns - ins) + 1 && z > za + nextIns - ins - 1 && z < zb - (nextIns - ins) + 1 && k !== h - 1) continue;
          put(tk, x, y + 1, z, st.roof || B.CONCRETE_GRAY);
        }
      }
    }
    // remate
    const cx = Math.floor(x0 + w / 2), cz = Math.floor(z0 + d / 2), top = G + h + 2;
    let ins = 0;
    for (const [, i] of st.setbacks || []) ins = i;
    if (st.crown === 'spire') {
      for (let y = top; y < top + 12; y++) put(tk, cx, y, cz, B.BLACK);
      put(tk, cx, top + 12, cz, B.LAMP);
      tk.beacon = [cx + 0.5, top + 13, cz + 0.5];
    } else if (st.crown === 'copper') {
      for (let j = 0; j < 4; j++) for (let x = x0 + ins + 1 + j; x <= x0 + w - 2 - ins - j; x++) for (let z = z0 + ins + 1 + j; z <= z0 + d - 2 - ins - j; z++) put(tk, x, top + j, z, B.COPPER);
    } else {
      for (let x = x0 + ins; x < x0 + w - ins; x++) for (const z of [z0 + ins, z0 + d - 1 - ins]) put(tk, x, top, z, st.frame);
      for (let z = z0 + ins; z < z0 + d - ins; z++) for (const x of [x0 + ins, x0 + w - 1 - ins]) put(tk, x, top, z, st.frame);
      put(tk, cx, top, cz, B.CONCRETE_GRAY); put(tk, cx, top + 1, cz, B.CONCRETE_GRAY);
    }
    return tk;
  }
  // casa con tejado escalonado
  function house(x0, z0, face, st) {
    const w = 7, d = 6;
    const tk = task('casa', [x0 + 3.5, G + 3, z0 + 3]);
    for (let x = x0 - 1; x <= x0 + w; x++) for (let z = z0 - 1; z <= z0 + d; z++) put(tk, x, G, z, B.COBBLE);
    for (let k = 0; k < 3; k++) {
      const y = G + 1 + k;
      for (let x = x0; x < x0 + w; x++) for (let z = z0; z < z0 + d; z++) {
        const edge = x === x0 || x === x0 + w - 1 || z === z0 || z === z0 + d - 1;
        if (!edge) continue;
        const corner = (x === x0 || x === x0 + w - 1) && (z === z0 || z === z0 + d - 1);
        const front = face > 0 ? z === z0 + d - 1 : z === z0;
        let b = corner ? st.corner : st.wall;
        if (!corner && k === 1 && ((x - x0) % 3 !== 0 || (z - z0) % 3 === 1) && !(front && x === x0 + 3)) b = B.HOUSE_WINDOW;
        if (front && x === x0 + 3 && k < 2) continue; // puerta
        put(tk, x, y, z, b);
      }
    }
    for (let j = 0; j < 4; j++) {
      const y = G + 4 + j;
      const xa = x0 - 1 + j, xb = x0 + w - j, za = z0 - 1 + j, zb = z0 + d - j;
      if (xa > xb || za > zb) break;
      for (let x = xa; x <= xb; x++) for (let z = za; z <= zb; z++) {
        const ring = x === xa || x === xb || z === za || z === zb;
        if (ring || j === 3 || xb - xa < 2 || zb - za < 2) put(tk, x, y, z, st.roof);
      }
    }
    for (let y = G + 4; y < G + 8; y++) put(tk, x0 + w - 2, y, z0 + 1, B.BRICK);
    // jardin
    const fz = face > 0 ? z0 + d + 1 : z0 - 2;
    for (let z = Math.min(fz, z0 + 3); z <= Math.max(fz, z0 + 3); z++) if (z < z0 || z > z0 + d - 1) put(tk, x0 + 3, G, z, B.GRAVEL);
    for (let x = x0 - 2; x <= x0 + w + 1; x++) if (x !== x0 + 3) put(tk, x, G + 1, fz, B.HEDGE);
    tree(tk, x0 - 1, face > 0 ? z0 - 2 : z0 + d + 1, R() < 0.35 ? 'cherry' : 'oak', 4 + Math.floor(R() * 2));
    lamp(tk, x0 + w + 2, fz, 3);
    return tk;
  }

  // ---------------- centro: rascacielos junto al rio
  const glassD = { wall: B.GLASS_DARK, frame: B.CONCRETE_GRAY, band: 4, roof: B.CONCRETE_GRAY };
  const glassB = { wall: B.GLASS_BLUE, frame: B.CONCRETE, band: 5, roof: B.CONCRETE, cols: 3 };
  const grid2 = { wall: B.GLASS, frame: B.CONCRETE, band: 3, cols: 2, roof: B.CONCRETE_GRAY };
  const sand = { wall: B.GLASS_DARK, frame: B.SANDSTONE, band: 3, cols: 2, roof: B.SANDSTONE };
  const brick = { wall: B.HOUSE_WINDOW, frame: B.BRICK, band: 3, cols: 2, roof: B.STONE_BRICK };
  const stoneB = { wall: B.GLASS, frame: B.STONE_BRICK, band: 4, cols: 3, roof: B.STONE_BRICK };
  const towers = [];
  towers.push(tower('torre A', 17, 46, 12, 12, 44, { ...glassD, setbacks: [[0.75, 1]] }));
  towers.push(tower('torre B', 31, 58, 11, 12, 30, grid2));
  towers.push(tower('torre central', 57, 46, 15, 15, 74, { ...glassB, setbacks: [[0.55, 1], [0.8, 3]], crown: 'spire' }));
  towers.push(tower('torre D', 52, 63, 6, 7, 22, brick));
  towers.push(tower('torre E', 89, 45, 12, 12, 58, { ...glassD, crown: 'copper', setbacks: [[0.85, 1]] }));
  towers.push(tower('torre F', 103, 57, 11, 13, 38, { ...grid2, wall: B.GLASS_BLUE }));
  towers.push(tower('torre G', 125, 46, 12, 12, 34, sand));
  towers.push(tower('torre H', 139, 58, 11, 11, 50, { ...glassB, oct: true, crown: 'copper' }));
  towers.splice(2, 0, tower('torre A2', 32, 45, 10, 10, 26, stoneB));
  towers.push(tower('torre C2', 61, 64, 10, 7, 18, brick));
  towers.push(tower('torre E2', 89, 60, 11, 10, 28, { ...glassB, band: 4 }));
  towers.push(tower('torre F2', 104, 45, 10, 10, 20, sand));
  towers.push(tower('torre G2', 126, 61, 10, 9, 24, grid2));
  towers.push(tower('torre H2', 140, 45, 10, 10, 32, { ...glassD, setbacks: [[0.7, 1]] }));
  // centro medio
  const mids = [];
  mids.push(tower('edificio M1', 17, 81, 11, 10, 18, brick));
  mids.push(tower('edificio M2', 31, 93, 10, 12, 14, stoneB));
  mids.push(tower('edificio M3', 89, 81, 12, 10, 26, { ...glassB, band: 4 }));
  mids.push(tower('edificio M4', 104, 92, 10, 13, 16, sand));
  mids.push(tower('edificio M5', 125, 81, 11, 11, 22, stoneB));
  mids.push(tower('edificio M6', 139, 94, 11, 11, 12, brick));
  // plaza con fuente
  const tPlaza = task('plaza', [65, G, 93]);
  for (let x = 51; x < 80; x++) for (let z = 79; z < 108; z++) {
    const r = Math.hypot(x - 65, z - 93);
    put(tPlaza, x, G, z, r < 10 ? ((Math.floor(x / 2) + Math.floor(z / 2)) % 2 ? B.STONE_BRICK : B.SIDEWALK) : (x % 7 === 0 || z % 7 === 0 ? B.SIDEWALK : B.GRASS));
  }
  for (let x = 58; x <= 72; x++) for (let z = 86; z <= 100; z++) {
    const r = Math.hypot(x - 65, z - 93);
    if (r > 3.2 && r <= 4.3) put(tPlaza, x, G + 1, z, B.STONE_BRICK);
    else if (r <= 3.2) put(tPlaza, x, G + 1, z, B.GLASS_BLUE);
  }
  for (let y = G + 2; y < G + 5; y++) put(tPlaza, 65, y, 93, B.QUARTZ);
  put(tPlaza, 65, G + 5, 93, B.LAMP);
  for (const [x, z] of [[54, 82], [76, 82], [54, 104], [76, 104], [54, 93], [76, 93], [65, 82], [65, 104]]) tree(tPlaza, x, z, (x + z) % 3 ? 'oak' : 'cherry', 4);

  // ---------------- suburbios
  const houses = [];
  const HST = [
    { wall: B.BRICK, corner: B.DARK_PLANKS, roof: B.ROOF },
    { wall: B.PLANKS, corner: B.LOG, roof: B.ROOF_RED },
    { wall: B.QUARTZ, corner: B.STONE_BRICK, roof: B.ROOF },
    { wall: B.TERRACOTTA, corner: B.DARK_PLANKS, roof: B.ROOF },
  ];
  for (const [bi, bx] of BX.entries()) {
    if (bi === 2) continue;
    for (let i = 0; i < 3; i++) {
      houses.push(house(bx + 1 + i * 10, 117, -1, HST[(bi + i) % 4]));
      houses.push(house(bx + 1 + i * 10, 136, 1, HST[(bi + i + 2) % 4]));
    }
  }
  for (const [bi, bx] of BX.entries()) for (let i = 0; i < 3; i++) houses.push(house(bx + 1 + i * 10, 155, -1, HST[(bi + i + 1) % 4]));
  // parque con campo de futbol
  const tPark = task('campo de futbol', [101, G, 129]);
  for (let x = 88; x <= 114; x++) for (let z = 116; z <= 142; z++) {
    const fx = x - 89, fz = z - 120;
    const inField = fx >= 0 && fx <= 24 && fz >= 0 && fz <= 18;
    if (!inField) continue;
    const line = fx === 0 || fx === 24 || fz === 0 || fz === 18 || fx === 12 || (Math.abs(Math.hypot(fx - 12, fz - 9) - 3.5) < 0.5);
    put(tPark, x, G, z, line ? (fx === 0 || fx === 24 || fx === 12 ? B.FIELD_LINE : B.FIELD_LINE_X) : B.FIELD);
  }
  for (const gx of [89, 113]) for (let z = 127; z <= 131; z++) for (let y = G + 1; y <= G + 3; y++) if (z === 127 || z === 131 || y === G + 3) put(tPark, gx, y, z, B.QUARTZ);
  for (let x = 92; x <= 110; x++) for (let k = 0; k < 3; k++) for (let y = G + 1; y <= G + 1 + k; y++) put(tPark, x, y, 118 - k, B.CONCRETE_GRAY);
  for (const [x, z] of [[88, 116], [114, 116], [88, 142], [114, 142], [100, 142]]) tree(tPark, x, z, 'oak', 5);
  for (const [x, z] of [[94, 141], [106, 141]]) lamp(tPark, x, z, 4);

  // ---------------- paseo del rio (orilla norte), farolas y arboles en avenidas
  const tProm = task('paseo del rio', [60, G, 10]);
  for (let x = 0; x < SX; x++) {
    if (x >= MAIN - 1 && x <= MAIN + 7) continue;
    for (let z = 9; z <= 11; z++) put(tProm, x, G, z, B.SIDEWALK);
    if (x % 9 === 4) tree(tProm, x, 5, 'cherry', 4);
    if (x % 9 === 0) lamp(tProm, x, 13, 3);
    if (x % 9 === 7) for (const dx of [0, 1]) put(tProm, x + dx, G + 1, 8, B.DARK_PLANKS);
  }
  const tStreet = task('farolas y arboles', [84, G, 100]);
  for (const r of ROADS_X) for (let x = 2; x < SX; x += 10) if (!inRoadZ(x)) { lamp(tStreet, x, r - 1, 3); if (x % 20 === 2) tree(tStreet, x + 5, r + 8, 'oak', 4); }
  for (const r of ROADS_Z) for (let z = 40; z < SZ; z += 10) if (!inRoadX(z)) lamp(tStreet, r - 1, z, 3);

  // ---------------- calendario
  const byName = (n) => tasks.filter((t) => t.name.startsWith(n));
  const phases = [
    [8, 24, [tMain, ...byName('avenida '), ...byName('calle '), tBridge]],
    [24, 94, towers],
    [94, 114, [...mids, tPlaza]],
    [114, 142, [...houses.slice(0, 18), tPark, ...houses.slice(18)]],
    [142, 156, [tProm, tStreet]],
  ];
  const placements = [];
  for (const [t0, t1, list] of phases) {
    const total = list.reduce((s, tk) => s + tk.blocks.length, 0);
    let i = 0;
    for (const tk of list) {
      tk.t0 = t0 + (i / total) * (t1 - t0);
      for (const [x, y, z, b] of tk.blocks) {
        const t = t0 + (i / total) * (t1 - t0);
        if (b === B.LEAVES || b === B.CHERRY || b === B.HEDGE) {
          const l = grid.occ(x, y, z);
          if (l && l.some((o) => o.s >= 0)) { i++; continue; }
        }
        grid.place(x, y, z, b, t);
        placements.push([t, x + 0.5, y + 0.5, z + 0.5, b]);
        i++;
      }
      tk.t1 = t0 + (i / total) * (t1 - t0);
    }
  }
  placements.sort((a, b) => a[0] - b[0]);
  const beacon = towers.find((t) => t.beacon);
  return { grid, tasks, placements, beacon, towers, phases };
}
