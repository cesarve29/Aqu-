// Utilidades compartidas: materiales, mallas voxel, bitmaps de texto/emoji, keyframes.
import * as THREE from 'three';
import { Grid, meshGrid, voxMaterial, hash3, clamp, lerp, smooth } from './voxel.js';
export * from './voxel.js';

const MATS = {};
export function mat(key, opts = {}) {
  if (!MATS[key]) MATS[key] = voxMaterial({ key, ...opts });
  return MATS[key];
}
export function vox(g, v, origin = [0, 0, 0], matKey = 'base', matOpts = {}) {
  const geo = meshGrid(g, { scale: v, origin });
  const m = new THREE.Mesh(geo, mat(matKey, matOpts));
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

// ---------------------------------------------------------------------------
// bitmaps 2D (alfa) desde canvas: texto y emoji
// ---------------------------------------------------------------------------
export async function loadFonts() {
  const fonts = [
    new FontFace('Cinzel', 'url(/fonts/cinzel.woff2)', { weight: '400 900' }),
    new FontFace('Uncial', 'url(/fonts/uncial.woff2)'),
  ];
  for (const f of fonts) { await f.load(); document.fonts.add(f); }
  await document.fonts.ready;
}

// devuelve {w,h,a:Float32Array} alfa 0..1 (fila 0 = arriba)
export function bitmap(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.clearRect(0, 0, w, h);
  draw(x, w, h);
  const d = x.getImageData(0, 0, w, h).data;
  const a = new Float32Array(w * h), r = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) { a[i] = d[i * 4 + 3] / 255; r[i] = (d[i * 4] + d[i * 4 + 1] + d[i * 4 + 2]) / 765; }
  return { w, h, a, l: r, at(px, py) { px = Math.floor(px); py = Math.floor(py); return px < 0 || py < 0 || px >= w || py >= h ? 0 : a[px + py * w]; }, lum(px, py) { px = Math.floor(px); py = Math.floor(py); return px < 0 || py < 0 || px >= w || py >= h ? 0 : r[px + py * w]; } };
}
export function emoji(x, ch, cx, cy, size) {
  x.font = `${size}px "Noto Color Emoji"`;
  x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillText(ch, cx, cy);
}

// ---------------------------------------------------------------------------
// animacion
// ---------------------------------------------------------------------------
// kf(t, [[t0, v0], [t1, v1], ...], ease) ; v numeros o arrays
export function kf(t, keys, ease = smooth) {
  if (t <= keys[0][0]) return keys[0][1];
  if (t >= keys[keys.length - 1][0]) return keys[keys.length - 1][1];
  let i = 0; while (t > keys[i + 1][0]) i++;
  const [ta, va] = keys[i], [tb, vb] = keys[i + 1];
  const u = ease((t - ta) / (tb - ta));
  if (Array.isArray(va)) return va.map((a, k) => lerp(a, vb[k], u));
  return lerp(va, vb, u);
}
// spline Catmull-Rom con tiempos: suave y con velocidad continua
export function spline(t, keys) {
  const n = keys.length;
  if (t <= keys[0][0]) return keys[0][1].slice ? keys[0][1].slice() : keys[0][1];
  if (t >= keys[n - 1][0]) return keys[n - 1][1].slice ? keys[n - 1][1].slice() : keys[n - 1][1];
  let i = 0; while (t > keys[i + 1][0]) i++;
  const p0 = keys[Math.max(0, i - 1)], p1 = keys[i], p2 = keys[i + 1], p3 = keys[Math.min(n - 1, i + 2)];
  const u = (t - p1[0]) / (p2[0] - p1[0]);
  const f = (a, b, c, d) => {
    // tangentes escaladas por intervalo (no uniforme)
    const m1 = p2[0] - p0[0] > 0 ? (c - a) / (p2[0] - p0[0]) * (p2[0] - p1[0]) : 0;
    const m2 = p3[0] - p1[0] > 0 ? (d - b) / (p3[0] - p1[0]) * (p2[0] - p1[0]) : 0;
    const u2 = u * u, u3 = u2 * u;
    return (2 * u3 - 3 * u2 + 1) * b + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * c + (u3 - u2) * m2;
  };
  const A = p1[1], B = p2[1];
  if (Array.isArray(A)) return A.map((_, k) => f(p0[1][k], A[k], B[k], p3[1][k]));
  return f(p0[1], A, B, p3[1]);
}
export const rad = (d) => d * Math.PI / 180;
export { THREE, Grid, hash3, clamp, lerp, smooth };
