// Mundo de voxeles: datos, mallado por caras visibles con oclusion ambiental por vertice
// y "versiones" de chunk para ediciones con marca de tiempo (talar, construir, explotar).
import * as THREE from 'three';
import { TILE } from './atlas.js';

export const B = {
  AIR: 0, GRASS: 1, DIRT: 2, STONE: 3, SAND: 4, LOG: 5, LEAVES: 6, PLANKS: 7, OBSIDIAN: 8,
  ENDSTONE: 9, COBBLE: 10, ORE: 11, SNOW: 12, TABLE: 13, GLOW: 14,
};
// [arriba, lado, abajo]
const TILES = {
  [B.GRASS]: [TILE.GRASS_TOP, TILE.GRASS_SIDE, TILE.DIRT],
  [B.DIRT]: [TILE.DIRT, TILE.DIRT, TILE.DIRT],
  [B.STONE]: [TILE.STONE, TILE.STONE, TILE.STONE],
  [B.SAND]: [TILE.SAND, TILE.SAND, TILE.SAND],
  [B.LOG]: [TILE.LOG_TOP, TILE.LOG_SIDE, TILE.LOG_TOP],
  [B.LEAVES]: [TILE.LEAVES, TILE.LEAVES, TILE.LEAVES],
  [B.PLANKS]: [TILE.PLANKS, TILE.PLANKS, TILE.PLANKS],
  [B.OBSIDIAN]: [TILE.OBSIDIAN, TILE.OBSIDIAN, TILE.OBSIDIAN],
  [B.ENDSTONE]: [TILE.ENDSTONE, TILE.ENDSTONE, TILE.ENDSTONE],
  [B.COBBLE]: [TILE.COBBLE, TILE.COBBLE, TILE.COBBLE],
  [B.ORE]: [TILE.ORE, TILE.ORE, TILE.ORE],
  [B.SNOW]: [TILE.SNOW, TILE.SNOW, TILE.DIRT],
  [B.TABLE]: [TILE.TABLE_TOP, TILE.PLANKS, TILE.PLANKS],
  [B.GLOW]: [TILE.GLOW, TILE.GLOW, TILE.GLOW],
};
export const BLOCK_TILE = (b) => TILES[b][1];
const TRANSP = new Set([B.LEAVES]);
const EMISSIVE = new Set([B.GLOW]);
const AO = [0.42, 0.62, 0.82, 1.0];
const SHADE = [0.86, 0.86, 1.0, 0.62, 0.76, 0.76]; // +x -x +y -y +z -z
const CH = 16;

export class World {
  constructor(sx, sy, sz) {
    this.sx = sx; this.sy = sy; this.sz = sz;
    this.data = new Uint8Array(sx * sy * sz);
  }
  get(x, y, z) {
    if (x < 0 || y < 0 || z < 0 || x >= this.sx || y >= this.sy || z >= this.sz) return 0;
    return this.data[(x * this.sz + z) * this.sy + y];
  }
  set(x, y, z, b) {
    if (x < 0 || y < 0 || z < 0 || x >= this.sx || y >= this.sy || z >= this.sz) return;
    this.data[(x * this.sz + z) * this.sy + y] = b;
  }
  top(x, z) {
    for (let y = this.sy - 1; y >= 0; y--) { const b = this.get(x, y, z); if (b && b !== B.LEAVES) return y; }
    return -1;
  }
}

function buildGeometry(w, x0, z0, x1, z1, atlas, emissive) {
  const pos = [], nor = [], uv = [], col = [], idx = [];
  const solid = (x, y, z) => (w.get(x, y, z) ? 1 : 0);
  for (let x = x0; x < x1; x++) for (let z = z0; z < z1; z++) for (let y = 0; y < w.sy; y++) {
    const b = w.get(x, y, z);
    if (!b || EMISSIVE.has(b) !== emissive) continue;
    const p = [x, y, z];
    for (let f = 0; f < 6; f++) {
      const d = f >> 1, s = f & 1 ? -1 : 1;
      const n = [0, 0, 0]; n[d] = s;
      const nb = w.get(x + n[0], y + n[1], z + n[2]);
      if (nb && !(TRANSP.has(nb) && nb !== b)) continue;
      const u = (d + 1) % 3, v = (d + 2) % 3;
      const tile = TILES[b][d === 1 ? (s > 0 ? 0 : 2) : 1];
      const [tu0, tv0, tu1, tv1] = atlas.uv(tile);
      let corners = [[0, 0], [1, 0], [1, 1], [0, 1]];
      if (s < 0) corners = [[0, 0], [0, 1], [1, 1], [1, 0]];
      const base = pos.length / 3;
      const aos = [];
      for (const [cu, cv] of corners) {
        const q = [p[0] + n[0], p[1] + n[1], p[2] + n[2]];
        const e1 = [0, 0, 0], e2 = [0, 0, 0];
        e1[u] = cu ? 1 : -1; e2[v] = cv ? 1 : -1;
        const s1 = solid(q[0] + e1[0], q[1] + e1[1], q[2] + e1[2]);
        const s2 = solid(q[0] + e2[0], q[1] + e2[1], q[2] + e2[2]);
        const c = solid(q[0] + e1[0] + e2[0], q[1] + e1[1] + e2[1], q[2] + e1[2] + e2[2]);
        const ao = emissive ? 3 : (s1 && s2 ? 0 : 3 - (s1 + s2 + c));
        aos.push(ao);
        const l = [0, 0, 0];
        l[d] = s > 0 ? 1 : 0; l[u] = cu; l[v] = cv;
        pos.push(x + l[0], y + l[1], z + l[2]);
        nor.push(n[0], n[1], n[2]);
        let tx, ty;
        if (d === 1) { tx = l[0]; ty = l[2]; } else if (d === 0) { tx = l[2]; ty = l[1]; } else { tx = l[0]; ty = l[1]; }
        uv.push(tu0 + tx * (tu1 - tu0), tv0 + ty * (tv1 - tv0));
        const k = emissive ? 0.95 : AO[ao] * SHADE[f];
        col.push(k, k, k);
      }
      if (aos[0] + aos[2] < aos[1] + aos[3]) idx.push(base + 1, base + 2, base + 3, base + 1, base + 3, base);
      else idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
  }
  if (!idx.length) return null;
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeBoundingSphere();
  return g;
}

export function worldMaterials(atlas) {
  return {
    opaque: new THREE.MeshLambertMaterial({ map: atlas.texture, vertexColors: true, alphaTest: 0.5 }),
    emissive: new THREE.MeshBasicMaterial({ map: atlas.texture, vertexColors: true, toneMapped: true }),
  };
}

// Mundo con ediciones en el tiempo: edits = [{t, x, y, z, b}]
export class TimedWorld {
  constructor(world, atlas, mats, edits = []) {
    this.group = new THREE.Group();
    this.chunks = new Map();
    const ncx = Math.ceil(world.sx / CH), ncz = Math.ceil(world.sz / CH);
    const build = (cx, cz) => {
      const g = new THREE.Group();
      const x0 = cx * CH, z0 = cz * CH, x1 = Math.min(world.sx, x0 + CH), z1 = Math.min(world.sz, z0 + CH);
      const go = buildGeometry(world, x0, z0, x1, z1, atlas, false);
      if (go) { const m = new THREE.Mesh(go, mats.opaque); m.castShadow = m.receiveShadow = true; g.add(m); }
      const ge = buildGeometry(world, x0, z0, x1, z1, atlas, true);
      if (ge) g.add(new THREE.Mesh(ge, mats.emissive));
      g.visible = false;
      this.group.add(g);
      return g;
    };
    for (let cx = 0; cx < ncx; cx++) for (let cz = 0; cz < ncz; cz++) {
      this.chunks.set(cx + ',' + cz, [{ t: -Infinity, g: build(cx, cz) }]);
    }
    const byT = new Map();
    for (const e of edits) { if (!byT.has(e.t)) byT.set(e.t, []); byT.get(e.t).push(e); }
    const times = [...byT.keys()].sort((a, b) => a - b);
    for (const t of times) {
      const touched = new Set();
      for (const e of byT.get(t)) {
        world.set(e.x, e.y, e.z, e.b);
        for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) {
          const cx = Math.floor((e.x + dx) / CH), cz = Math.floor((e.z + dz) / CH);
          if (cx >= 0 && cz >= 0 && cx < ncx && cz < ncz) touched.add(cx + ',' + cz);
        }
      }
      for (const k of touched) {
        const [cx, cz] = k.split(',').map(Number);
        this.chunks.get(k).push({ t, g: build(cx, cz) });
      }
    }
  }
  update(t) {
    for (const vers of this.chunks.values()) {
      let cur = vers[0];
      for (const v of vers) { v.g.visible = false; if (v.t <= t) cur = v; }
      cur.g.visible = true;
    }
  }
}
