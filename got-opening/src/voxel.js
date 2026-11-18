// Motor voxel: rejillas de voxeles, voxelizacion por SDF y mallado con AO estilo Minecraft.
import * as THREE from 'three';

// ---------------------------------------------------------------------------
// utilidades deterministas
// ---------------------------------------------------------------------------
export function hash3(x, y, z) {
  let h = (x * 374761393 + y * 668265263 + z * 2147483647) | 0;
  h = (h ^ (h >>> 13)) * 1274126177;
  h = h ^ (h >>> 16);
  return (h >>> 0) / 4294967295;
}
export function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
export const smoother = (t) => { t = clamp(t); return t * t * t * (t * (t * 6 - 15) + 10); };
export const range = (t, a, b) => clamp((t - a) / (b - a));

// ruido de valor 3D suave
export function vnoise(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
  const c = (a, b, d) => hash3(xi + a, yi + b, zi + d);
  const x00 = lerp(c(0, 0, 0), c(1, 0, 0), u), x10 = lerp(c(0, 1, 0), c(1, 1, 0), u);
  const x01 = lerp(c(0, 0, 1), c(1, 0, 1), u), x11 = lerp(c(0, 1, 1), c(1, 1, 1), u);
  return lerp(lerp(x00, x10, v), lerp(x01, x11, v), w);
}
export function fbm(x, y, z, oct = 4) {
  let a = 0.5, s = 0, f = 1;
  for (let i = 0; i < oct; i++) { s += a * vnoise(x * f, y * f, z * f); f *= 2.03; a *= 0.5; }
  return s;
}

// colores: enteros 0xRRGGBB
export function rgb(r, g, b) { return (clamp(Math.round(r), 0, 255) << 16) | (clamp(Math.round(g), 0, 255) << 8) | clamp(Math.round(b), 0, 255); }
export function hex2arr(c) { return [(c >> 16) & 255, (c >> 8) & 255, c & 255]; }
export function shade(c, k) { const a = hex2arr(c); return rgb(a[0] * k, a[1] * k, a[2] * k); }
export function mix(c1, c2, t) { const a = hex2arr(c1), b = hex2arr(c2); return rgb(lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)); }
export function jitter(c, amt, x, y, z) { return shade(c, 1 + (hash3(x, y, z) - 0.5) * amt); }

// ---------------------------------------------------------------------------
// Rejilla
// ---------------------------------------------------------------------------
export class Grid {
  constructor(nx, ny, nz) {
    this.nx = nx; this.ny = ny; this.nz = nz;
    this.c = new Int32Array(nx * ny * nz).fill(-1); // -1 vacio, si no color
    this.e = null; // emisivo opcional (Uint8Array)
  }
  idx(x, y, z) { return x + this.nx * (y + this.ny * z); }
  in(x, y, z) { return x >= 0 && y >= 0 && z >= 0 && x < this.nx && y < this.ny && z < this.nz; }
  get(x, y, z) { return this.in(x, y, z) ? this.c[this.idx(x, y, z)] : -1; }
  solid(x, y, z) { return this.in(x, y, z) && this.c[this.idx(x, y, z)] >= 0; }
  set(x, y, z, col) { if (this.in(x, y, z)) this.c[this.idx(x, y, z)] = col; }
  clear(x, y, z) { if (this.in(x, y, z)) this.c[this.idx(x, y, z)] = -1; }
  setE(x, y, z, v) { if (!this.e) this.e = new Uint8Array(this.c.length); if (this.in(x, y, z)) this.e[this.idx(x, y, z)] = v; }
  box(x0, y0, z0, x1, y1, z1, colFn) {
    for (let z = Math.max(0, z0); z <= Math.min(this.nz - 1, z1); z++)
      for (let y = Math.max(0, y0); y <= Math.min(this.ny - 1, y1); y++)
        for (let x = Math.max(0, x0); x <= Math.min(this.nx - 1, x1); x++)
          this.set(x, y, z, typeof colFn === 'function' ? colFn(x, y, z) : colFn);
  }
  // rellena donde sdf(p)<0 ; p en coordenadas de voxel (centro)
  sdf(fn, colFn, bounds) {
    const [x0, y0, z0, x1, y1, z1] = bounds || [0, 0, 0, this.nx - 1, this.ny - 1, this.nz - 1];
    for (let z = Math.max(0, z0); z <= Math.min(this.nz - 1, z1); z++)
      for (let y = Math.max(0, y0); y <= Math.min(this.ny - 1, y1); y++)
        for (let x = Math.max(0, x0); x <= Math.min(this.nx - 1, x1); x++) {
          const d = fn(x + 0.5, y + 0.5, z + 0.5);
          if (d < 0) {
            const col = typeof colFn === 'function' ? colFn(x, y, z, d) : colFn;
            if (col !== null && col !== undefined) this.set(x, y, z, col);
          }
        }
  }
  carve(fn, bounds) {
    const [x0, y0, z0, x1, y1, z1] = bounds || [0, 0, 0, this.nx - 1, this.ny - 1, this.nz - 1];
    for (let z = Math.max(0, z0); z <= Math.min(this.nz - 1, z1); z++)
      for (let y = Math.max(0, y0); y <= Math.min(this.ny - 1, y1); y++)
        for (let x = Math.max(0, x0); x <= Math.min(this.nx - 1, x1); x++)
          if (fn(x + 0.5, y + 0.5, z + 0.5) < 0) this.clear(x, y, z);
  }
  // repinta voxeles solidos
  paint(fn) {
    for (let z = 0; z < this.nz; z++) for (let y = 0; y < this.ny; y++) for (let x = 0; x < this.nx; x++) {
      const i = this.idx(x, y, z); if (this.c[i] < 0) continue;
      const r = fn(x, y, z, this.c[i]); if (r !== undefined && r !== null) this.c[i] = r;
    }
  }
}

// ---------------------------------------------------------------------------
// Mallado con oclusion ambiental por vertice
// ---------------------------------------------------------------------------
const FACES = [
  // dir, u, v  (normal, ejes tangentes)
  { n: [1, 0, 0], u: [0, 1, 0], v: [0, 0, 1] },
  { n: [-1, 0, 0], u: [0, 0, 1], v: [0, 1, 0] },
  { n: [0, 1, 0], u: [0, 0, 1], v: [1, 0, 0] },
  { n: [0, -1, 0], u: [1, 0, 0], v: [0, 0, 1] },
  { n: [0, 0, 1], u: [1, 0, 0], v: [0, 1, 0] },
  { n: [0, 0, -1], u: [0, 1, 0], v: [1, 0, 0] },
];
const AO_CURVE = [0.42, 0.62, 0.82, 1.0];

/**
 * opts: scale (tamano voxel), origin [ox,oy,oz] en voxeles (pivote), faceShade (bool)
 * devuelve BufferGeometry con position, normal, color (+ emissive attr 'emi')
 */
export function meshGrid(g, opts = {}) {
  const s = opts.scale ?? 1;
  const [ox, oy, oz] = opts.origin ?? [0, 0, 0];
  const pos = [], nor = [], col = [], emi = [], idx = [];
  let vc = 0;
  const S = (x, y, z) => (g.solid(x, y, z) ? 1 : 0);
  for (let z = 0; z < g.nz; z++) for (let y = 0; y < g.ny; y++) for (let x = 0; x < g.nx; x++) {
    const ci = g.idx(x, y, z);
    const c = g.c[ci];
    if (c < 0) continue;
    const r = ((c >> 16) & 255) / 255, gg = ((c >> 8) & 255) / 255, b = (c & 255) / 255;
    const ev = g.e ? g.e[ci] / 255 : 0;
    for (let f = 0; f < 6; f++) {
      const F = FACES[f];
      const nx = x + F.n[0], ny = y + F.n[1], nz = z + F.n[2];
      if (S(nx, ny, nz)) continue;
      // centro de cara
      const cx = x + 0.5 + F.n[0] * 0.5, cy = y + 0.5 + F.n[1] * 0.5, cz = z + 0.5 + F.n[2] * 0.5;
      const ao = [];
      const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
      for (let k = 0; k < 4; k++) {
        const [cu, cv] = corners[k];
        const px = cx + (F.u[0] * cu + F.v[0] * cv) * 0.5;
        const py = cy + (F.u[1] * cu + F.v[1] * cv) * 0.5;
        const pz = cz + (F.u[2] * cu + F.v[2] * cv) * 0.5;
        pos.push((px - ox) * s, (py - oy) * s, (pz - oz) * s);
        nor.push(F.n[0], F.n[1], F.n[2]);
        // AO
        const s1 = S(nx + F.u[0] * cu, ny + F.u[1] * cu, nz + F.u[2] * cu);
        const s2 = S(nx + F.v[0] * cv, ny + F.v[1] * cv, nz + F.v[2] * cv);
        const s3 = S(nx + F.u[0] * cu + F.v[0] * cv, ny + F.u[1] * cu + F.v[1] * cv, nz + F.u[2] * cu + F.v[2] * cv);
        const a = (s1 && s2) ? 0 : 3 - (s1 + s2 + s3);
        ao.push(a);
        const k2 = ev > 0 ? lerp(AO_CURVE[a], 1, ev) : AO_CURVE[a];
        col.push(r * k2, gg * k2, b * k2);
        emi.push(ev);
      }
      if (ao[0] + ao[2] > ao[1] + ao[3]) idx.push(vc, vc + 1, vc + 2, vc, vc + 2, vc + 3);
      else idx.push(vc + 1, vc + 2, vc + 3, vc + 1, vc + 3, vc);
      vc += 4;
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  geo.setAttribute('emi', new THREE.Float32BufferAttribute(emi, 1));
  geo.setIndex(vc > 65535 ? new THREE.Uint32BufferAttribute(idx, 1) : new THREE.Uint16BufferAttribute(idx, 1));
  geo.computeBoundingSphere();
  return geo;
}

// Material estandar con color por vertice y soporte de emisivo por vertice
export function voxMaterial(opts = {}) {
  const m = new THREE.MeshStandardMaterial({
    vertexColors: true, roughness: opts.roughness ?? 0.9, metalness: opts.metalness ?? 0.0,
    flatShading: false,
  });
  const emiGain = opts.emiGain ?? 4.0;
  m.userData.emiTint = { value: new THREE.Color(opts.emiTint ?? 0xffffff) };
  m.userData.emiGain = { value: emiGain };
  m.onBeforeCompile = (sh) => {
    sh.uniforms.emiTint = m.userData.emiTint;
    sh.uniforms.emiGain = m.userData.emiGain;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float emi;\nvarying float vEmi;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvEmi = emi;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vEmi;\nuniform vec3 emiTint;\nuniform float emiGain;')
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\ntotalEmissiveRadiance += vColor.rgb * vEmi * emiGain * emiTint;');
  };
  m.customProgramCacheKey = () => 'vox' + (opts.key || '');
  return m;
}

export function voxMesh(g, opts = {}, mat) {
  const geo = meshGrid(g, opts);
  const mesh = new THREE.Mesh(geo, mat || voxMaterial(opts));
  mesh.castShadow = opts.cast ?? true;
  mesh.receiveShadow = opts.receive ?? true;
  return mesh;
}

// ---------------------------------------------------------------------------
// primitivas SDF (coordenadas libres)
// ---------------------------------------------------------------------------
export const sd = {
  sphere: (px, py, pz, cx, cy, cz, r) => Math.hypot(px - cx, py - cy, pz - cz) - r,
  ellip: (px, py, pz, cx, cy, cz, rx, ry, rz) => {
    const k0 = Math.hypot((px - cx) / rx, (py - cy) / ry, (pz - cz) / rz);
    return (k0 - 1) * Math.min(rx, ry, rz);
  },
  box: (px, py, pz, cx, cy, cz, hx, hy, hz) => {
    const qx = Math.abs(px - cx) - hx, qy = Math.abs(py - cy) - hy, qz = Math.abs(pz - cz) - hz;
    return Math.hypot(Math.max(qx, 0), Math.max(qy, 0), Math.max(qz, 0)) + Math.min(Math.max(qx, qy, qz), 0);
  },
  // capsula de radio variable entre a y b
  cone: (px, py, pz, ax, ay, az, bx, by, bz, ra, rb) => {
    const bax = bx - ax, bay = by - ay, baz = bz - az;
    const pax = px - ax, pay = py - ay, paz = pz - az;
    const h = clamp((pax * bax + pay * bay + paz * baz) / (bax * bax + bay * bay + baz * baz));
    const r = lerp(ra, rb, h);
    return Math.hypot(pax - bax * h, pay - bay * h, paz - baz * h) - r;
  },
  // devuelve parametro h de la capsula (0..1)
  coneH: (px, py, pz, ax, ay, az, bx, by, bz) => {
    const bax = bx - ax, bay = by - ay, baz = bz - az;
    return clamp(((px - ax) * bax + (py - ay) * bay + (pz - az) * baz) / (bax * bax + bay * bay + baz * baz));
  },
  smin: (a, b, k) => { const h = clamp(0.5 + 0.5 * (b - a) / k); return lerp(b, a, h) - k * h * (1 - h); },
};
