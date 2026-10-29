// Mundo de voxeles: solo se generan las caras visibles, con oclusion ambiental por vertice.
import * as THREE from 'three';
import { blockTex, blockEmit, BLOCK_EMIT } from './textures.js';

// nombre -> {faces:[+x,-x,+y,-y,+z,-z] texturas, opaque, cross}
const DEFS = {
  grass: { side: 'grass_side', top: 'grass_top', bottom: 'dirt' },
  dirt: { all: 'dirt' },
  path: { side: 'dirt', top: 'path_top', bottom: 'dirt' },
  podzol: { side: 'dirt', top: 'podzol_top', bottom: 'dirt' },
  mud: { all: 'mud' },
  gravel: { all: 'gravel' },
  stone: { all: 'stone' },
  cobble: { all: 'cobble' },
  mossy_cobble: { all: 'mossy_cobble' },
  stone_bricks: { all: 'stone_bricks' },
  mossy_bricks: { all: 'mossy_bricks' },
  deepslate: { all: 'deepslate' },
  deepslate_bricks: { all: 'deepslate_bricks' },
  oak_planks: { all: 'oak_planks' },
  spruce_planks: { all: 'spruce_planks' },
  dark_planks: { all: 'dark_planks' },
  oak_log: { side: 'oak_log', top: 'oak_log_top', bottom: 'oak_log_top' },
  dark_log: { side: 'dark_log', top: 'dark_log_top', bottom: 'dark_log_top' },
  leaves_orange: { all: 'leaves_orange' },
  leaves_red: { all: 'leaves_red' },
  leaves_dark: { all: 'leaves_dark' },
  hay: { side: 'hay_side', top: 'hay_top', bottom: 'hay_top' },
  pumpkin: { side: 'pumpkin_side', top: 'pumpkin_top', bottom: 'pumpkin_top' },
  soul_sand: { all: 'soul_sand' },
  soul_soil: { all: 'soul_soil' },
  bone: { side: 'bone_side', top: 'bone_top', bottom: 'bone_top' },
  window: { all: 'window', glow: 1.6 },
  door: { all: 'door' },
  black_wool: { all: 'black_wool' },
  obsidian: { all: 'obsidian' },
  rune1: { all: 'rune_stone', glowKey: 'rune1' },
  rune2: { all: 'rune_stone', glowKey: 'rune2' },
  rune3: { all: 'rune_stone', glowKey: 'rune3' },
  rune4: { all: 'rune_stone', glowKey: 'rune4' },
  dead_bush: { cross: 'dead_bush' },
  tall_grass: { cross: 'tall_grass' },
  cobweb: { cross: 'cobweb' },
  mushroom_glow: { cross: 'mushroom_glow', glow: 2.5 },
  mushroom_red: { cross: 'mushroom_red' },
  dripstone: { cross: 'dripstone', hang: true },
  chain: { cross: 'chain' },
};

export const BLOCKS = [null];
export const B = {};
for (const name in DEFS) {
  const d = DEFS[name];
  const id = BLOCKS.length;
  B[name] = id;
  const faces = d.cross ? null : [d.side || d.all, d.side || d.all, d.top || d.all, d.bottom || d.all, d.side || d.all, d.side || d.all];
  BLOCKS.push({ name, faces, cross: d.cross, opaque: !d.cross, glow: d.glow || 0, glowKey: d.glowKey, hang: d.hang });
}

// Materiales compartidos (uno por textura / variante emisiva)
const matCache = {};
const LAMBERT = !new URLSearchParams(location.search).has('standard');
export const glowMats = {}; // para animar runas
export function blockMaterial(texName, cross, glow, glowKey) {
  const key = texName + (cross ? '_x' : '') + (glowKey || '');
  if (matCache[key]) return matCache[key];
  const p = { map: blockTex(texName), vertexColors: true, roughness: texName === 'deepslate' ? 0.75 : 0.92, metalness: 0 };
  if (cross) Object.assign(p, { alphaTest: 0.5, side: THREE.DoubleSide, transparent: false });
  if (BLOCK_EMIT[texName] && (glow || glowKey)) {
    p.emissiveMap = blockEmit(texName);
    p.emissive = new THREE.Color(1, 1, 1);
    p.emissiveIntensity = glowKey ? 0 : glow;
  }
  if (LAMBERT) { delete p.roughness; delete p.metalness; }
  const m = LAMBERT ? new THREE.MeshLambertMaterial(p) : new THREE.MeshStandardMaterial(p);
  if (glowKey) glowMats[glowKey] = m;
  matCache[key] = m;
  return m;
}

// esquinas por cara (BL, BR, TR, TL) vistas desde fuera
const FACES = [
  { n: [1, 0, 0], c: [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]] },
  { n: [-1, 0, 0], c: [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]] },
  { n: [0, 1, 0], c: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]] },
  { n: [0, -1, 0], c: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]] },
  { n: [0, 0, 1], c: [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]] },
  { n: [0, 0, -1], c: [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]] },
];
const UVS = [[0, 0], [1, 0], [1, 1], [0, 1]];
const AO = [0.32, 0.55, 0.78, 1.0];

export class VoxelGrid {
  constructor(x0, y0, z0, sx, sy, sz) {
    Object.assign(this, { x0, y0, z0, sx, sy, sz });
    this.data = new Uint8Array(sx * sy * sz);
  }
  idx(x, y, z) {
    x -= this.x0; y -= this.y0; z -= this.z0;
    if (x < 0 || y < 0 || z < 0 || x >= this.sx || y >= this.sy || z >= this.sz) return -1;
    return (y * this.sz + z) * this.sx + x;
  }
  get(x, y, z) {
    const i = this.idx(x, y, z);
    return i < 0 ? 0 : this.data[i];
  }
  set(x, y, z, t) {
    const i = this.idx(Math.floor(x), Math.floor(y), Math.floor(z));
    if (i >= 0) this.data[i] = typeof t === 'string' ? B[t] : t;
  }
  fill(x1, y1, z1, x2, y2, z2, t) {
    for (let y = Math.min(y1, y2); y <= Math.max(y1, y2); y++)
      for (let z = Math.min(z1, z2); z <= Math.max(z1, z2); z++)
        for (let x = Math.min(x1, x2); x <= Math.max(x1, x2); x++) this.set(x, y, z, t);
  }
  solid(x, y, z) {
    const t = this.get(x, y, z);
    return t && BLOCKS[t].opaque ? 1 : 0;
  }
  // altura de la superficie (primer bloque solido desde arriba)
  top(x, z) {
    for (let y = this.y0 + this.sy - 1; y >= this.y0; y--) if (this.solid(x, y, z)) return y;
    return this.y0 - 1;
  }

  build(chunk = 24) {
    const group = new THREE.Group();
    for (let cz = this.z0; cz < this.z0 + this.sz; cz += chunk)
      for (let cx = this.x0; cx < this.x0 + this.sx; cx += chunk) {
        const m = this.buildChunk(cx, cz, chunk);
        if (m) group.add(m);
      }
    return group;
  }

  buildChunk(cx, cz, size) {
    const buckets = new Map(); // material -> {pos, nrm, uv, col}
    const bucket = (mat) => {
      if (!buckets.has(mat)) buckets.set(mat, { pos: [], nrm: [], uv: [], col: [], idx: [] });
      return buckets.get(mat);
    };
    for (let y = this.y0; y < this.y0 + this.sy; y++)
      for (let z = cz; z < Math.min(cz + size, this.z0 + this.sz); z++)
        for (let x = cx; x < Math.min(cx + size, this.x0 + this.sx); x++) {
          const t = this.get(x, y, z);
          if (!t) continue;
          const def = BLOCKS[t];
          if (def.cross) {
            const bk = bucket(blockMaterial(def.cross, true, def.glow));
            this.emitCross(bk, x, y, z, def.hang);
            continue;
          }
          for (let f = 0; f < 6; f++) {
            const F = FACES[f];
            const nx = x + F.n[0], ny = y + F.n[1], nz = z + F.n[2];
            if (this.solid(nx, ny, nz)) continue;
            const bk = bucket(blockMaterial(def.faces[f], false, def.glow, def.glowKey));
            this.emitFace(bk, x, y, z, F);
          }
        }
    if (!buckets.size) return null;
    const pos = [], nrm = [], uv = [], col = [], idx = [];
    const geo = new THREE.BufferGeometry();
    const mats = [];
    let start = 0;
    for (const [mat, b] of buckets) {
      const base = pos.length / 3;
      pos.push(...b.pos); nrm.push(...b.nrm); uv.push(...b.uv); col.push(...b.col);
      for (const i of b.idx) idx.push(i + base);
      geo.addGroup(start, b.idx.length, mats.length);
      start += b.idx.length;
      mats.push(mat);
    }
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    geo.setIndex(idx.length > 65535 ? new THREE.Uint32BufferAttribute(idx, 1) : new THREE.Uint16BufferAttribute(idx, 1));
    geo.computeBoundingSphere();
    geo.computeBoundingBox();
    const mesh = new THREE.Mesh(geo, mats);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }

  emitFace(b, x, y, z, F) {
    const base = b.pos.length / 3;
    const ax = F.n[0] ? 0 : F.n[1] ? 1 : 2;
    const ta = ax === 0 ? 1 : 0, tb = ax === 2 ? 1 : 2;
    const L = [x + F.n[0], y + F.n[1], z + F.n[2]];
    const ao = [];
    for (let k = 0; k < 4; k++) {
      const c = F.c[k];
      const da = c[ta] ? 1 : -1, db = c[tb] ? 1 : -1;
      const p1 = L.slice(), p2 = L.slice(), p3 = L.slice();
      p1[ta] += da; p2[tb] += db; p3[ta] += da; p3[tb] += db;
      const s1 = this.solid(...p1), s2 = this.solid(...p2), s3 = this.solid(...p3);
      const v = s1 && s2 ? 0 : 3 - (s1 + s2 + s3);
      ao.push(v);
      b.pos.push(x + c[0], y + c[1], z + c[2]);
      b.nrm.push(...F.n);
      b.uv.push(...UVS[k]);
      const a = AO[v];
      b.col.push(a, a, a);
    }
    if (ao[0] + ao[2] < ao[1] + ao[3]) b.idx.push(base + 1, base + 2, base + 3, base + 1, base + 3, base);
    else b.idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
  }

  emitCross(b, x, y, z) {
    const quads = [
      [[0.15, 0, 0.15], [0.85, 0, 0.85]],
      [[0.85, 0, 0.15], [0.15, 0, 0.85]],
    ];
    for (const [a, c] of quads) {
      const base = b.pos.length / 3;
      const pts = [[a[0], 0, a[2]], [c[0], 0, c[2]], [c[0], 1, c[2]], [a[0], 1, a[2]]];
      for (let k = 0; k < 4; k++) {
        b.pos.push(x + pts[k][0], y + pts[k][1], z + pts[k][2]);
        b.nrm.push(0, 1, 0);
        b.uv.push(...UVS[k]);
        b.col.push(0.9, 0.9, 0.9);
      }
      b.idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
  }
}
