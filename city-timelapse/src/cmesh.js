// Mundo "con historia": cada celda guarda intervalos de existencia [s, e) de sus bloques.
// La malla se genera UNA vez con todas las caras que alguna vez son visibles y su intervalo
// de visibilidad; el shader esconde/anima cada cara segun uTime (timelapse sin rehacer mallas).
import * as THREE from 'three';
import { T } from './catlas.js';

export const B = {};
const DEF = [];
const def = (name, tiles, o = {}) => { const id = DEF.length + 1; B[name] = id; DEF[id] = { tiles, ...o }; };
def('GRASS', [T.GRASS, T.GRASS_SIDE, T.DIRT]);
def('DIRT', [T.DIRT, T.DIRT, T.DIRT]);
def('STONE', [T.STONE, T.STONE, T.STONE]);
def('SAND', [T.SAND, T.SAND, T.SAND]);
def('LOG', [T.LOG_TOP, T.LOG, T.LOG_TOP]);
def('LEAVES', [T.LEAVES, T.LEAVES, T.LEAVES], { transp: true });
def('CHERRY', [T.CHERRY, T.CHERRY, T.CHERRY], { transp: true });
def('PLANKS', [T.PLANKS, T.PLANKS, T.PLANKS]);
def('DARK_PLANKS', [T.DARK_PLANKS, T.DARK_PLANKS, T.DARK_PLANKS]);
def('ASPHALT', [T.ASPHALT, T.STONE, T.STONE]);
def('LINE_Z', [T.ROAD_LINE, T.STONE, T.STONE]);
def('LINE_X', [T.ROAD_LINE, T.STONE, T.STONE], { rot: true });
def('CROSS_Z', [T.CROSSWALK, T.STONE, T.STONE]);
def('CROSS_X', [T.CROSSWALK, T.STONE, T.STONE], { rot: true });
def('SIDEWALK', [T.SIDEWALK, T.SIDEWALK, T.SIDEWALK]);
def('CONCRETE', [T.CONCRETE, T.CONCRETE, T.CONCRETE]);
def('CONCRETE_GRAY', [T.CONCRETE_GRAY, T.CONCRETE_GRAY, T.CONCRETE_GRAY]);
def('GLASS', [T.CONCRETE, T.GLASS, T.CONCRETE], { emis: 2 });
def('GLASS_DARK', [T.CONCRETE_GRAY, T.GLASS_DARK, T.CONCRETE_GRAY], { emis: 2 });
def('GLASS_BLUE', [T.CONCRETE, T.GLASS_BLUE, T.CONCRETE], { emis: 2 });
def('BRICK', [T.BRICK, T.BRICK, T.BRICK]);
def('ROOF', [T.ROOF, T.ROOF, T.ROOF]);
def('ROOF_RED', [T.ROOF_RED, T.ROOF_RED, T.ROOF_RED]);
def('STONE_BRICK', [T.STONE_BRICK, T.STONE_BRICK, T.STONE_BRICK]);
def('QUARTZ', [T.QUARTZ, T.QUARTZ, T.QUARTZ]);
def('TERRACOTTA', [T.TERRACOTTA, T.TERRACOTTA, T.TERRACOTTA]);
def('LAMP', [T.LAMP, T.LAMP, T.LAMP], { emis: 1 });
def('FIELD', [T.FIELD, T.GRASS_SIDE, T.DIRT]);
def('FIELD_LINE', [T.FIELD_LINE, T.GRASS_SIDE, T.DIRT]);
def('FIELD_LINE_X', [T.FIELD_LINE, T.GRASS_SIDE, T.DIRT], { rot: true });
def('GRAVEL', [T.GRAVEL, T.GRAVEL, T.GRAVEL]);
def('HOUSE_WINDOW', [T.QUARTZ, T.HOUSE_WINDOW, T.QUARTZ], { emis: 2 });
def('COPPER', [T.COPPER, T.COPPER, T.COPPER]);
def('BLACK', [T.BLACK, T.BLACK, T.BLACK]);
def('SANDSTONE', [T.SANDSTONE, T.SANDSTONE, T.SANDSTONE]);
def('HEDGE', [T.HEDGE, T.HEDGE, T.HEDGE]);
def('COBBLE', [T.COBBLE, T.COBBLE, T.COBBLE]);
export const BDEF = DEF;

export const INF = 1e6;
const POP = 0.22;
const AO = [0.45, 0.64, 0.83, 1.0];
const SHADE = [0.86, 0.86, 1.0, 0.62, 0.76, 0.76];

export class TimedGrid {
  constructor(sx, sy, sz) {
    this.sx = sx; this.sy = sy; this.sz = sz;
    this.cells = new Map();
  }
  key(x, y, z) { return (x * this.sz + z) * this.sy + y; }
  inb(x, y, z) { return x >= 0 && y >= 0 && z >= 0 && x < this.sx && y < this.sy && z < this.sz; }
  occ(x, y, z) { return this.inb(x, y, z) ? this.cells.get(this.key(x, y, z)) : undefined; }
  // coloca b en el instante t, sustituyendo lo que hubiera
  place(x, y, z, b, t = -1) {
    if (!this.inb(x, y, z)) return;
    const k = this.key(x, y, z);
    let l = this.cells.get(k);
    if (!l) { l = []; this.cells.set(k, l); }
    for (const o of l) if (o.e >= INF) o.e = t;
    l.push({ s: t, e: INF, b });
  }
  finalSolid(x, y, z) {
    const l = this.occ(x, y, z);
    if (!l) return 0;
    for (const o of l) if (o.e >= INF) return 1;
    return 0;
  }
}

function subtract(s, e, covers) {
  let segs = [[s, e]];
  for (const [a, b] of covers) {
    const next = [];
    for (const [p, q] of segs) {
      if (b <= p || a >= q) { next.push([p, q]); continue; }
      if (a > p) next.push([p, a]);
      if (b < q) next.push([b, q]);
    }
    segs = next;
    if (!segs.length) break;
  }
  return segs.filter(([p, q]) => q - p > 0.005);
}

// Construye geometrias por chunk (CHxCH columnas)
export function buildTimedMeshes(grid, atlas, material, depthMat, CH = 32) {
  const buckets = new Map();
  const bucket = (x, z) => {
    const k = Math.floor(x / CH) + ',' + Math.floor(z / CH);
    if (!buckets.has(k)) buckets.set(k, { pos: [], nor: [], uv: [], col: [], life: [], ctr: [], em: [], idx: [] });
    return buckets.get(k);
  };
  const sy = grid.sy, sz = grid.sz;
  for (const [k, list] of grid.cells) {
    const y = k % sy, xz = (k - y) / sy, z = xz % sz, x = (xz - z) / sz;
    for (const o of list) {
      const D = DEF[o.b];
      for (let f = 0; f < 6; f++) {
        const d = f >> 1, s = f & 1 ? -1 : 1;
        const n = [0, 0, 0]; n[d] = s;
        const nl = grid.occ(x + n[0], y + n[1], z + n[2]);
        const covers = [];
        if (nl) for (const q of nl) {
          const ND = DEF[q.b];
          if (!ND.transp || q.b === o.b) covers.push([q.s + (q.s > 0 ? POP : 0), q.e]);
        }
        const vis = subtract(o.s, o.e, covers);
        if (!vis.length) continue;
        const u = (d + 1) % 3, v = (d + 2) % 3;
        const tile = D.tiles[d === 1 ? (s > 0 ? 0 : 2) : 1];
        const [tu0, tv0, tu1, tv1] = atlas.uv(tile);
        let corners = [[0, 0], [1, 0], [1, 1], [0, 1]];
        if (s < 0) corners = [[0, 0], [0, 1], [1, 1], [1, 0]];
        const p = [x, y, z];
        const aos = [], vp = [], vuv = [];
        for (const [cu, cv] of corners) {
          const q = [p[0] + n[0], p[1] + n[1], p[2] + n[2]];
          const e1 = [0, 0, 0], e2 = [0, 0, 0];
          e1[u] = cu ? 1 : -1; e2[v] = cv ? 1 : -1;
          const s1 = grid.finalSolid(q[0] + e1[0], q[1] + e1[1], q[2] + e1[2]);
          const s2 = grid.finalSolid(q[0] + e2[0], q[1] + e2[1], q[2] + e2[2]);
          const c = grid.finalSolid(q[0] + e1[0] + e2[0], q[1] + e1[1] + e2[1], q[2] + e1[2] + e2[2]);
          aos.push(D.emis === 1 ? 3 : (s1 && s2 ? 0 : 3 - (s1 + s2 + c)));
          const l = [0, 0, 0];
          l[d] = s > 0 ? 1 : 0; l[u] = cu; l[v] = cv;
          vp.push([x + l[0], y + l[1], z + l[2]]);
          let tx, ty;
          if (d === 1) { tx = l[0]; ty = l[2]; if (D.rot) { const tmp = tx; tx = ty; ty = tmp; } } else if (d === 0) { tx = l[2]; ty = l[1]; } else { tx = l[0]; ty = l[1]; }
          vuv.push([tu0 + tx * (tu1 - tu0), tv0 + ty * (tv1 - tv0)]);
        }
        const bk = bucket(x, z);
        for (const [a0, a1] of vis) {
          const base = bk.pos.length / 3;
          for (let i = 0; i < 4; i++) {
            bk.pos.push(...vp[i]);
            bk.nor.push(n[0], n[1], n[2]);
            bk.uv.push(...vuv[i]);
            const kk = AO[aos[i]] * SHADE[f];
            bk.col.push(kk, kk, kk);
            bk.life.push(o.s < 0 && a0 === o.s ? -INF : a0, a1);
            bk.ctr.push(x + 0.5, y + 0.5, z + 0.5);
            bk.em.push(D.emis || 0);
          }
          if (aos[0] + aos[2] < aos[1] + aos[3]) bk.idx.push(base + 1, base + 2, base + 3, base + 1, base + 3, base);
          else bk.idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
        }
      }
    }
  }
  // Agrupa caras: permanentes (ordenadas por aparicion) y temporales en cubos de 20 s
  // (ordenadas por desaparicion). Asi cada fotograma solo procesa caras que pueden verse.
  const group = new THREE.Group();
  const meshes = [];
  let faces = 0;
  const lb = (arr, v) => { let a = 0, b = arr.length; while (a < b) { const m2 = (a + b) >> 1; if (arr[m2] < v) a = m2 + 1; else b = m2; } return a; };
  const ub = (arr, v) => { let a = 0, b = arr.length; while (a < b) { const m2 = (a + b) >> 1; if (arr[m2] <= v) a = m2 + 1; else b = m2; } return a; };
  const makeMesh = (bk, ids, key) => {
    ids.sort((p, q) => key(p) - key(q));
    const A = (src, n) => { const o = new Float32Array(ids.length * 4 * n); ids.forEach((f, i) => { for (let j = 0; j < 4 * n; j++) o[i * 4 * n + j] = src[f * 4 * n + j]; }); return o; };
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(A(bk.pos, 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(A(bk.nor, 3), 3));
    g.setAttribute('uv', new THREE.BufferAttribute(A(bk.uv, 2), 2));
    g.setAttribute('color', new THREE.BufferAttribute(A(bk.col, 3), 3));
    g.setAttribute('aLife', new THREE.BufferAttribute(A(bk.life, 2), 2));
    g.setAttribute('aCenter', new THREE.BufferAttribute(A(bk.ctr, 3), 3));
    g.setAttribute('aEm', new THREE.BufferAttribute(A(bk.em, 1), 1));
    const idx = new Uint32Array(ids.length * 6);
    ids.forEach((f, i) => { for (let j = 0; j < 6; j++) idx[i * 6 + j] = bk.idx[f * 6 + j] - f * 4 + i * 4; });
    g.setIndex(new THREE.BufferAttribute(idx, 1));
    g.computeBoundingSphere();
    const m = new THREE.Mesh(g, material);
    m.customDepthMaterial = depthMat;
    m.castShadow = m.receiveShadow = true;
    m.userData.keys = Float32Array.from(ids.map(key));
    group.add(m);
    meshes.push(m);
    return m;
  };
  for (const bk of buckets.values()) {
    const nf = bk.idx.length / 6;
    if (!nf) continue;
    faces += nf;
    const a0 = (f) => bk.life[f * 8], a1 = (f) => bk.life[f * 8 + 1];
    const perm = [], trans = new Map();
    for (let f = 0; f < nf; f++) {
      if (a1(f) >= INF) perm.push(f);
      else { const b = Math.floor(Math.max(a0(f), -20) / 20); if (!trans.has(b)) trans.set(b, []); trans.get(b).push(f); }
    }
    if (perm.length) makeMesh(bk, perm, a0).userData.kind = 'perm';
    for (const [b, ids] of trans) { const m = makeMesh(bk, ids, a1); m.userData.kind = 'trans'; m.userData.b0 = b * 20; }
  }
  group.userData.faces = faces;
  group.userData.update = (t) => {
    for (const m of meshes) {
      const K = m.userData.keys;
      if (m.userData.kind === 'perm') {
        const n = ub(K, t);
        m.visible = n > 0;
        m.geometry.setDrawRange(0, n * 6);
      } else {
        const s = lb(K, t);
        m.visible = t >= m.userData.b0 && s < K.length;
        m.geometry.setDrawRange(s * 6, (K.length - s) * 6);
      }
    }
  };
  return group;
}

const VERT_HEAD = `attribute vec2 aLife; attribute vec3 aCenter; attribute float aEm; uniform float uTime;
varying float vEm; varying float vSeed;
`;
const BEGIN = `vec3 transformed = vec3(position);
{
  float age = uTime - aLife.x;
  if (age < 0.0 || uTime >= aLife.y) transformed = aCenter;
  else if (age < ${POP.toFixed(2)}) {
    float u = age / ${POP.toFixed(2)} - 1.0;
    float s = 1.0 + 2.70158 * u * u * u + 1.70158 * u * u;
    transformed = aCenter + (position - aCenter) * s;
  }
  vEm = aEm;
  vSeed = fract(sin(dot(aCenter, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
}
`;

export function cityMaterials(atlas, uniforms) {
  const mat = new THREE.MeshLambertMaterial({ map: atlas.texture, vertexColors: true, alphaTest: 0.5 });
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = uniforms.uTime;
    sh.uniforms.uNight = uniforms.uNight;
    sh.vertexShader = VERT_HEAD + sh.vertexShader.replace('#include <begin_vertex>', BEGIN);
    sh.fragmentShader = 'uniform float uNight; varying float vEm; varying float vSeed;\n' + sh.fragmentShader.replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
      if (vEm > 1.5) {
        float lit = step(0.58, vSeed) * uNight;
        vec3 warm = mix(vec3(1.0, 0.72, 0.38), vec3(1.0, 0.9, 0.7), fract(vSeed * 7.13));
        totalEmissiveRadiance += warm * lit * (0.35 + 0.35 * dot(diffuseColor.rgb, vec3(0.33)));
      } else if (vEm > 0.5) {
        totalEmissiveRadiance += diffuseColor.rgb * (0.35 + 1.6 * uNight);
      }`);
  };
  mat.customProgramCacheKey = () => 'city-lambert';
  const depth = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, map: atlas.texture, alphaTest: 0.5 });
  depth.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = uniforms.uTime;
    sh.vertexShader = VERT_HEAD + sh.vertexShader.replace('#include <begin_vertex>', BEGIN);
  };
  depth.customProgramCacheKey = () => 'city-depth';
  return { mat, depth };
}
