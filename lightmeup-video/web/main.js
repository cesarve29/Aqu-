// Light Me Up — EchoBot : voxel music video renderer.
// Every frame is a pure function of time, so frames can be rendered in any
// order and in parallel by several browser workers.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

const params = new URLSearchParams(location.search);
const W = +(params.get('w') || 1920), H = +(params.get('h') || 1080);
const FPS = 30;
const N = 7600;                 // voxel instances
const INTRO = 6.0;              // seconds of title intro before the song
const BEAT = 60 / 131;          // 131 BPM
const BAR = BEAT * 4;
const DOWNBEAT = INTRO + 52.40; // a known downbeat (first drop), video time

let FEAT, LYR;

// ------------------------------------------------------------------ utils
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeIO = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeOut = t => 1 - Math.pow(1 - t, 3);
const fract = x => x - Math.floor(x);
const h1 = n => fract(Math.sin(n * 12.9898 + 78.233) * 43758.5453);
const h2 = (x, y) => h1(x * 127.1 + y * 311.7);
const TAU = Math.PI * 2;

function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = h2(xi, yi), b = h2(xi + 1, yi), c = h2(xi, yi + 1), d = h2(xi + 1, yi + 1);
  return lerp(lerp(a, b, u), lerp(c, d, u), v);
}
function fbm(x, y) { let s = 0, a = 0.5, f = 1; for (let i = 0; i < 4; i++) { s += a * vnoise(x * f, y * f); f *= 2.03; a *= 0.5; } return s / 0.9375; }
function h3(x, y, z) { return h1(x * 127.1 + y * 311.7 + z * 74.7); }
function vnoise3(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
  const c = (i, j, k) => h3(xi + i, yi + j, zi + k);
  return lerp(lerp(lerp(c(0, 0, 0), c(1, 0, 0), u), lerp(c(0, 1, 0), c(1, 1, 0), u), v),
              lerp(lerp(c(0, 0, 1), c(1, 0, 1), u), lerp(c(0, 1, 1), c(1, 1, 1), u), v), w);
}
function fbm3(x, y, z) { let s = 0, a = 0.5, f = 1; for (let i = 0; i < 4; i++) { s += a * vnoise3(x * f, y * f, z * f); f *= 2.1; a *= 0.5; } return s / 0.9375; }
function hsv(h, s, v) {
  h = fract(h) * 6; const i = Math.floor(h), f = h - i;
  const p = v * (1 - s), q = v * (1 - s * f), r = v * (1 - s * (1 - f));
  return [[v, r, p], [q, v, p], [p, v, r], [p, q, v], [r, p, v], [v, p, q]][i % 6];
}
const mixc = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
function grad(stops, x) {
  x = clamp(x) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  return mixc(stops[i], stops[i + 1], x - i);
}

// ------------------------------------------------------------------ audio features (video time)
function fv(arr, t) {
  const x = t * FPS, i = Math.floor(x);
  if (i <= 0) return arr[0];
  if (i >= arr.length - 1) return arr[arr.length - 1];
  return lerp(arr[i], arr[i + 1], x - i);
}
const bass = t => fv(FEAT.bass, t), mid = t => fv(FEAT.mid, t), high = t => fv(FEAT.high, t);
const energy = t => fv(FEAT.energy, t), onset = t => fv(FEAT.onset, t);
function spec(b, t) {
  const i = clamp(Math.round(t * FPS), 1, FEAT.spec.length - 1);
  return 0.6 * FEAT.spec[i][b] + 0.4 * FEAT.spec[i - 1][b];
}
const lastBeat = t => DOWNBEAT + Math.floor((t - DOWNBEAT) / BEAT) * BEAT;
const sinceBeat = t => t - lastBeat(t);
const pulse = t => Math.exp(-sinceBeat(t) * 7) * clamp(bass(lastBeat(t) + 0.04) * 1.3);

// ------------------------------------------------------------------ sections (video time)
const I = INTRO;
const SEC = [
  { t: 0, m: 'title' },
  { t: I + 0.0, m: 'city', p: { v: 0 }, lift: 26 },
  { t: I + 30.41, m: 'terrain', lift: 18 },
  { t: I + 45.07, m: 'orb', p: { calm: 0 }, lift: 20 },
  { t: I + 52.40, m: 'eq', p: { pal: 0 }, flash: 1, cut: true, lift: 30 },
  { t: I + 79.88, m: 'orb', p: { calm: 1 }, lift: 14 },
  { t: I + 85.37, m: 'planet', flash: 0.5, lift: 16 },
  { t: I + 99.99, m: 'city', p: { v: 1 }, flash: 0.6, lift: 20 },
  { t: I + 114.65, m: 'tunnel', flash: 1, cut: true, lift: 10 },
  { t: I + 129.34, m: 'orb', p: { calm: 0 }, lift: 20 },
  { t: I + 136.67, m: 'eq', p: { pal: 1 }, flash: 1, cut: true, lift: 30 },
  { t: I + 164.15, m: 'outro', lift: 12 },
];
let END = 0;
const TR_PRE = 0.9, TR_POST = 0.4;

// ------------------------------------------------------------------ instance buffers
function mkBuf() {
  return { pos: new Float32Array(N * 3), scl: new Float32Array(N * 3), col: new Float32Array(N * 3),
           acc: new Float32Array(N * 3), dat: new Float32Array(N * 4) };
}
function put(o, i, x, y, z, sx, sy, sz, c, a, emis = 0, win = 0, top = 0, seed = 0) {
  const j = i * 3, k = i * 4;
  o.pos[j] = x; o.pos[j + 1] = y; o.pos[j + 2] = z;
  o.scl[j] = sx; o.scl[j + 1] = sy; o.scl[j + 2] = sz;
  o.col[j] = c[0]; o.col[j + 1] = c[1]; o.col[j + 2] = c[2];
  o.acc[j] = a[0]; o.acc[j + 1] = a[1]; o.acc[j + 2] = a[2];
  o.dat[k] = emis; o.dat[k + 1] = win; o.dat[k + 2] = top; o.dat[k + 3] = seed;
}
function hide(o, i, x = 0, y = 0, z = 0) {
  const j = i * 3;
  o.pos[j] = x; o.pos[j + 1] = y; o.pos[j + 2] = z;
  o.scl[j] = 0; o.scl[j + 1] = 0; o.scl[j + 2] = 0;
}
function hideFrom(o, n) { for (let i = n; i < N; i++) hide(o, i, o.pos[i * 3], o.pos[i * 3 + 1], o.pos[i * 3 + 2]); }

// ring-buffer helper: slot s of n covering cells [base, base+n)
const ringCell = (s, n, base) => s + n * Math.ceil((base - s) / n);

// ------------------------------------------------------------------ text voxels
let TITLE = [];       // {x,y,z,nx,grp}
function rasterText(text, font, spacing, thr = 120) {
  const c = document.createElement('canvas'); c.width = 600; c.height = 120;
  const g = c.getContext('2d');
  g.font = font; g.letterSpacing = spacing; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillStyle = '#fff'; g.fillText(text, 300, 60);
  const d = g.getImageData(0, 0, 600, 120).data;
  const pts = []; let minx = 1e9, maxx = -1e9, miny = 1e9, maxy = -1e9;
  for (let y = 0; y < 120; y++) for (let x = 0; x < 600; x++) {
    if (d[(y * 600 + x) * 4 + 3] > thr) { pts.push([x, y]); minx = Math.min(minx, x); maxx = Math.max(maxx, x); miny = Math.min(miny, y); maxy = Math.max(maxy, y); }
  }
  const cx = (minx + maxx) / 2, cy = (miny + maxy) / 2;
  return pts.map(([x, y]) => [x - cx, -(y - cy), (x - minx) / (maxx - minx)]);
}
function buildTitle() {
  const a = rasterText('LIGHT ME UP', '400 25px "Russo One"', '2px');
  const b = rasterText('EchoBot', '400 15px "Russo One"', '1px');
  TITLE = [];
  for (const [x, y, nx] of a) for (let z = 0; z < 2; z++) TITLE.push({ x, y: y + 27, z: -z, nx, grp: 0 });
  for (const [x, y, nx] of b) TITLE.push({ x, y: y + 8, z: 0, nx, grp: 1 });
}
const TITLE_COLS = [[1.0, 0.1, 0.5], [1.0, 0.35, 0.1], [1.0, 0.8, 0.15]];
const ECHO_COL = [0.1, 0.85, 1.0];

// precomputed voxel spheres
function shell(R) { const out = []; const r = Math.ceil(R + 1); for (let x = -r; x <= r; x++) for (let y = -r; y <= r; y++) for (let z = -r; z <= r; z++) { const d = Math.hypot(x, y, z); if (d >= R - 0.5 && d < R + 0.5) out.push([x, y, z]); } return out; }
let ORB, PLANET, MOON;

// dust shared by title/outro
function dust(o, from, count, u, rise = 1.5) {
  let i = from;
  for (let j = 0; j < count && i < N; j++, i++) {
    const a = h1(j * 1.11 + 3), b = h1(j * 2.37 + 5), c = h1(j * 3.91 + 7);
    const x = (a - 0.5) * 320, z = (b - 0.5) * 240 - 30;
    const y = (c * 90 + u * rise * (0.5 + a)) % 90;
    const s = 0.28 * smooth(0, 6, y) * smooth(90, 80, y);
    const tw = 1.2 + Math.sin(u * 3 + j) * 0.8;
    put(o, i, x, y, z, s, s, s, [0.3, 0.4, 0.8], [0.5, 0.7, 1.0], tw, 0, 0, a);
  }
  return i;
}

function titleFill(o, u, mode) {
  let i = 0;
  const n = TITLE.length;
  for (let k = 0; k < n; k++, i++) {
    const v = TITLE[k];
    const hk = h1(k * 0.917 + 1.3);
    const c0 = v.grp ? ECHO_COL : grad(TITLE_COLS, v.nx);
    let x = v.x, y = v.y, z = v.z, s = 1, emis = 0.35;
    if (mode === 'title') {
      const arrive = v.grp ? 2.5 + 0.9 * v.nx + 0.3 * hk : 0.3 + 1.9 * v.nx + 0.5 * hk;
      const q = clamp((u - arrive + 1.2) / 1.2);
      const th = hk * TAU, ph = (h1(k * 3.3) - 0.5) * 2.2, R = 70 + 90 * h1(k * 5.1);
      const sx = Math.cos(ph) * Math.cos(th) * R, sy = 20 + Math.sin(ph) * R * 0.6, sz = Math.cos(ph) * Math.sin(th) * R - 40;
      const e = easeOut(q);
      x = lerp(sx, v.x, e); y = lerp(sy, v.y, e); z = lerp(sz, v.z, e);
      s = lerp(0.3, 1, e) * (q > 0 ? 1 : 0);
      emis = 0.35 + (1 - e) * 2.5;
      const sweep = lerp(-110, 110, smooth(3.4, 5.0, u));
      emis += 3.0 * Math.exp(-Math.pow((v.x - sweep) / 9, 2)) * (u > 3.3 && u < 5.2 ? 1 : 0);
      emis += pulse(u) * 0.4;
    } else { // outro: drift away
      const d = 1.2 + v.nx * 2.2 + hk * 0.6;
      const q = clamp((u - d) / 1.8);
      y += q * q * 30 * (0.5 + hk); x += q * (hk - 0.5) * 12; z += q * q * 10 * (h1(k * 7.7) - 0.5);
      s = 1 - q;
      emis = 0.5 + q * 3;
    }
    put(o, i, x, y, z, s, s, s, mixc(c0, [0.05, 0.05, 0.08], 0.45), c0, emis, 0, 0, hk);
  }
  i = dust(o, i, 1500, u + (mode === 'outro' ? 40 : 0));
  hideFrom(o, i);
}

// ------------------------------------------------------------------ modes
const MODES = {};

MODES.title = {
  fill(t, u, p, o) { titleFill(o, u, 'title'); },
  cam(t, u) {
    return { pos: [Math.sin(u * 0.35) * 8, lerp(14, 22, smooth(0, 6, u)), lerp(225, 190, easeOut(clamp(u / 6)))],
             look: [0, 19, 0], fov: 40, roll: 0 };
  },
  env() { return { fog: [0.03, 0.01, 0.06], fogD: 0.0032, top: [0.0, 0.0, 0.02], hor: [0.10, 0.02, 0.16], stars: 1, aurora: 0, sun: 0, ground: 1, gridCol: [0.6, 0.1, 0.9], cell: 4, seam: 0.5, lit: 0, exposure: 1.0, bloom: [0.6, 0.4, 0.85] }; },
};
MODES.outro = {
  fill(t, u, p, o) { titleFill(o, u, 'outro'); },
  cam(t, u) { return { pos: [Math.sin(u * 0.3) * 8, 20, 185 + u * 6], look: [0, 19, 0], fov: 40, roll: 0 }; },
  env: MODES.title.env,
};

// ---- city
const CC = 6, CNX = 25, CNZ = 48;
const CITY_BASE = [[0.06, 0.07, 0.14], [0.10, 0.06, 0.16], [0.05, 0.10, 0.13], [0.12, 0.12, 0.17]];
const NEON = [[1.0, 0.1, 0.6], [0.1, 0.8, 1.0], [1.0, 0.5, 0.1], [0.6, 0.3, 1.0]];
function cityZ(u, v) { return v ? -2400 - 21 * u : -12 * u; }
function cityLit(u, v) { return v ? 1 : 0.04 + 0.96 * smooth(3, 28, u); }
MODES.city = {
  fill(t, u, p, o) {
    const v = p.v, zc = cityZ(u, v), lit = cityLit(u, v);
    const camCell = Math.floor(-zc / CC), pl = pulse(t);
    let i = 0;
    for (let iz = 0; iz < CNZ; iz++) {
      const k = ringCell(iz, CNZ, camCell - 3);
      for (let ix = 0; ix < CNX; ix++, i++) {
        const cx = ix - (CNX >> 1);
        const vo = v * 91.7;
        const a = h2(cx * 3.1 + vo, k * 1.7), b = h2(cx * 5.3 + vo, k * 2.9 + 1), c = h2(cx * 7.7 + vo, k * 4.1 + 2);
        const d = h2(cx * 1.9 + vo, k * 6.3 + 3), e = h2(cx * 9.1 + vo, k * 0.7 + 4), f = h2(cx * 2.3 + vo, k * 8.9 + 5);
        const zx = -k * CC;
        if (cx === 0 || a < 0.1) { hide(o, i, cx * CC, 0, zx); continue; }
        const w = 2 + Math.floor(b * 4), dd = 2 + Math.floor(c * 4);
        const district = fbm(k * 0.045 + vo, cx * 0.09);
        let Hh = 2 + Math.floor(Math.pow(d, 1.7) * (10 + 34 * district));
        if (Math.abs(cx) === 1) Hh = Math.min(Hh, 6 + Math.floor(d * 22));
        Hh += Math.round(pl * (e > 0.6 ? 1 : 0) * 3 * lit);
        const x = cx * CC + (e - 0.5) * (CC - w - 1), z = zx + (f - 0.5) * (CC - dd - 1);
        const nn = NEON[Math.floor(f * 4) % 4];
        const accI = 0.12 + 0.88 * lit * (0.6 + 0.4 * Math.sin(t * 2 + k));
        put(o, i, x, Hh / 2, z, w, Hh, dd, CITY_BASE[Math.floor(e * 4) % 4], [nn[0] * accI, nn[1] * accI, nn[2] * accI],
            0, 1, d > 0.8 ? 0.6 * lit : 0, a);
      }
    }
    // embers
    const ne = Math.floor(1300 * (0.15 + 0.85 * lit)), dist = -zc, S = 220;
    for (let j = 0; j < 1300 && i < N; j++, i++) {
      const a = h1(j * 1.73 + 11), b = h1(j * 2.91 + 13), c = h1(j * 4.37 + 17);
      const D = a * S + S * Math.ceil((dist + 4 - a * S) / S);
      const x = (b - 0.5) * 70, y = (c * 40 + u * (0.6 + b) * 1.6) % 40 + 0.5;
      const s = j < ne ? 0.22 * smooth(0, 3, y) * smooth(40, 34, y) : 0;
      const col = b > 0.5 ? [1.0, 0.55, 0.2] : [0.3, 0.8, 1.0];
      put(o, i, x, y, -D, s, s, s, col, col, 3 + 2 * Math.sin(t * 5 + j), 0, 0, c);
    }
    hideFrom(o, i);
  },
  cam(t, u, p) {
    const v = p.v, zc = cityZ(u, v);
    if (!v) {
      const rise = easeIO(smooth(14, 28.5, u));
      const y = lerp(3.4, 34, rise), x = Math.sin(u * 0.25) * 1.2;
      return { pos: [x, y, zc], look: [x * 0.4, lerp(4.5, 10, rise), zc - lerp(40, 70, rise)], fov: lerp(64, 56, rise), roll: Math.sin(u * 0.4) * 0.03 };
    }
    const y = 20 + Math.sin(u * 0.35) * 6 + 14 * smooth(10, 14.6, u);
    return { pos: [Math.sin(u * 0.2) * 3, y, zc], look: [0, y - 12, zc - 60], fov: 60, roll: Math.sin(u * 0.5) * 0.06 };
  },
  env(t, u, p) {
    const lit = cityLit(u, p.v);
    return { fog: [0.015, 0.012, 0.05], fogD: 0.0082, top: [0.0, 0.0, 0.025], hor: [0.05 + 0.06 * lit, 0.03, 0.13 + 0.05 * lit], stars: 1, aurora: 0.2 * lit, sun: 0, ground: 1,
             gridCol: [0.1 + 0.5 * lit, 0.2, 0.5 + 0.4 * lit], cell: CC, seam: 0.65, lit, exposure: 1.0, bloom: [0.55, 0.45, 0.85] };
  },
};

// ---- terrain (chorus 1)
const TN = 72, TC = 2;
function terrH(x, z) {
  const n = fbm(x * 0.011 + 50, z * 0.011 + 20);
  const r = 1 - Math.abs(fbm(x * 0.028 + 7, z * 0.028) * 2 - 1);
  let h = n * 40 + r * 10 - 18;
  const valley = smooth(8, 46, Math.abs(x));
  h = h * (0.2 + 0.8 * valley) - (1 - valley) * 3;
  return Math.floor(h);
}
const terrZ = u => -5000 - 16 * u;
MODES.terrain = {
  fill(t, u, p, o) {
    const zc = terrZ(u), base = Math.floor(-zc / TC) - 4;
    let i = 0;
    const en = energy(t);
    for (let iz = 0; iz < TN; iz++) {
      const k = ringCell(iz, TN, base);
      const z = -k * TC;
      for (let ix = 0; ix < TN; ix++, i++) {
        const x = (ix - TN / 2 + 0.5) * TC;
        let h = terrH(x, z);
        const water = h < 1;
        let base_, acc, emis = 0, top = 0;
        if (water) {
          h = 1;
          const sh = 0.5 + 0.5 * Math.sin(t * 2.2 + x * 0.3 + z * 0.21);
          base_ = [0.02, 0.06, 0.18]; acc = [0.1, 0.55, 1.0]; emis = 0.08 + 0.25 * sh * sh;
        } else {
          const band = Math.min(31, Math.floor(Math.abs(x) / (TN * TC / 2) * 28));
          h += Math.round(spec(band, t) * 4 * en);
          if (h < 6) { base_ = [0.04, 0.22, 0.24]; acc = [0.1, 0.9, 0.7]; }
          else if (h < 13) { base_ = [0.22, 0.07, 0.33]; acc = [0.7, 0.2, 1.0]; }
          else if (h < 20) { base_ = [0.55, 0.14, 0.38]; acc = [1.0, 0.3, 0.6]; }
          else { base_ = [0.8, 0.8, 0.92]; acc = [1.0, 0.8, 0.95]; top = 0.35; }
        }
        const sy = h + 6;
        put(o, i, x, (h - 6) / 2, z, TC, sy, TC, base_, acc, emis, 0, top, h2(x, z));
      }
    }
    // lanterns rising to the sky
    const S = 170, dist = -zc, nl = Math.floor(lerp(350, 1200, smooth(0, 10, u)));
    for (let j = 0; j < 1200 && i < N; j++, i++) {
      const a = h1(j * 1.37 + 21), b = h1(j * 2.11 + 23), c = h1(j * 3.77 + 29);
      const D = a * S + S * Math.ceil((dist + 6 - a * S) / S);
      const x = (b - 0.5) * 130;
      const g = Math.max(1, terrH(x, -D));
      const y = g + (c * 70 + u * (2 + 3 * b)) % 70;
      const s = j < nl ? 0.75 * smooth(g, g + 4, y) : 0;
      const fl = 3.5 + 1.5 * Math.sin(t * 6 + j * 1.7);
      put(o, i, x, y, -D, s, s * 1.3, s, [1.0, 0.45, 0.12], [1.0, 0.55, 0.15], fl, 0, 0, a);
    }
    hideFrom(o, i);
  },
  cam(t, u) {
    const zc = terrZ(u), x = Math.sin(u * 0.2) * 9;
    const y = 30 + u * 1.3;
    const up = smooth(11, 15, u);
    return { pos: [x, y, zc], look: [x * 0.5, lerp(y - 14, y + 18, up), zc - 60], fov: 60, roll: Math.sin(u * 0.3) * 0.05 };
  },
  env() { return { fog: [0.20, 0.06, 0.18], fogD: 0.0062, top: [0.02, 0.01, 0.09], hor: [0.42, 0.09, 0.24], stars: 0.7, aurora: 0.0, sun: 1, ground: 0, gridCol: [0, 0, 0], cell: 4, seam: 0.35, lit: 0, exposure: 1.0, bloom: [0.5, 0.45, 0.85] }; },
};

// ---- orb (builds / breaks)
const ORB_C = [0, 25, 0];
MODES.orb = {
  fill(t, u, p, o, sec) {
    const calm = p.calm, pr = calm ? 0.15 : clamp(u / sec.dur);
    const pl = pulse(t);
    const s = (calm ? 0.55 + 0.08 * bass(t) : 0.65 + 0.55 * pr) + pl * 0.06;
    const rot = calm ? u * 0.25 : u * (0.4 + pr * 2.5);
    const cr = Math.cos(rot), sr = Math.sin(rot);
    let i = 0;
    for (let k = 0; k < ORB.length; k++, i++) {
      const [px, py, pz] = ORB[k];
      const hk = h1(k * 0.73);
      const jit = 1 + (hk - 0.5) * 0.2 * pr * pl;
      const x = (px * cr - pz * sr) * s * jit, z = (px * sr + pz * cr) * s * jit, y = py * s * jit;
      const hot = calm ? 0.1 : pr;
      const c = mixc([0.25, 0.08, 0.5], [1.0, 0.75, 0.45], hot);
      const a = calm ? [0.2, 0.5, 1.0] : mixc([0.6, 0.2, 1.0], [1.0, 0.6, 0.3], hot);
      const em = (calm ? 0.15 + 0.6 * pl : 0.2 + 1.5 * pr * pr) * (0.7 + 0.6 * h1(k * 1.9 + Math.floor(t * 8)));
      put(o, i, ORB_C[0] + x, ORB_C[1] + y, ORB_C[2] + z, s, s, s, c, a, em, 0, 0, hk);
    }
    const np = calm ? 700 : Math.floor(lerp(1200, 2800, pr));
    for (let j = 0; j < 4200 && i < N; j++, i++) {
      if (j >= np) { hide(o, i, ORB_C[0], ORB_C[1], ORB_C[2]); continue; }
      const a = h1(j * 1.91 + 31), b = h1(j * 2.73 + 37), c = h1(j * 3.17 + 41), d = h1(j * 5.03 + 43);
      const rate = (calm ? 0.05 : 0.18 + 0.3 * pr) * (0.6 + a);
      const ph = fract(u * rate + b);
      const r = 150 * Math.pow(1 - ph, 1.6) + 12 * s;
      const th = c * TAU + ph * 5, el = (d - 0.5) * 2.4;
      const x = Math.cos(el) * Math.cos(th) * r, y = Math.sin(el) * r * 0.7, z = Math.cos(el) * Math.sin(th) * r;
      const sz = 0.3 + 0.35 * ph;
      const col = calm ? [0.3, 0.6, 1.0] : (a > 0.66 ? [1, 1, 1] : a > 0.33 ? [0.6, 0.3, 1.0] : [0.2, 0.8, 1.0]);
      put(o, i, ORB_C[0] + x, ORB_C[1] + y, ORB_C[2] + z, sz, sz, sz, col, col, 0.8 + 1.2 * ph, 0, 0, a);
    }
    hideFrom(o, i);
  },
  cam(t, u, p, sec) {
    const calm = p.calm, pr = calm ? 0.1 : clamp(u / sec.dur);
    const ang = 0.6 + u * (calm ? 0.12 : 0.25 + 0.3 * pr), r = calm ? 46 : lerp(62, 36, easeIO(pr));
    const sh = calm ? 0 : pr * pulse(t) * 0.8;
    const y = ORB_C[1] + 6 + 9 * Math.sin(u * 0.25);
    return { pos: [Math.sin(ang) * r + sh * (h1(t) - 0.5), y + sh * (h1(t + 1) - 0.5), Math.cos(ang) * r],
             look: ORB_C, fov: 50, roll: calm ? 0 : Math.sin(u * 0.7) * 0.05 * pr };
  },
  env(t, u, p) { return { fog: [0.01, 0.0, 0.03], fogD: 0.0028, top: [0.0, 0.0, 0.012], hor: [0.04, 0.0, 0.07], stars: 1.2, aurora: 0, sun: 0, ground: 0, gridCol: [0, 0, 0], cell: 4, seam: 0.4, lit: 0, exposure: 1.0, bloom: [0.7, 0.5, 0.8] }; },
};

// ---- equalizer city (drops)
const EN = 56, ES = 1.3;
const EQ_PAL0 = [[0.25, 0.05, 0.55], [0.95, 0.1, 0.6], [1.0, 0.45, 0.1], [1.0, 0.9, 0.3]];
MODES.eq = {
  fill(t, u, p, o, sec) {
    const fin = p.pal === 1;
    let i = 0;
    const beats = [];
    for (let b = 0; b < 4; b++) { const bt = lastBeat(t) - b * BEAT; beats.push([t - bt, clamp(bass(bt + 0.04) * 1.2)]); }
    const Rmax = (EN / 2) * ES * 1.414;
    for (let iz = 0; iz < EN; iz++) for (let ix = 0; ix < EN; ix++, i++) {
      const x = (ix - EN / 2 + 0.5) * ES, z = (iz - EN / 2 + 0.5) * ES;
      const d = Math.hypot(x, z), dn = d / Rmax;
      const band = Math.min(31, Math.floor(Math.pow(dn, 0.85) * 31));
      const v = spec(band, t);
      let h = 1 + v * (17 - dn * 7);
      for (const [dt, amp] of beats) { const r = dt * 30; h += 5 * amp * Math.exp(-((d - r) * (d - r)) / 7) * Math.exp(-dt * 1.3); }
      h = Math.max(1, Math.round(h));
      const hn = clamp(h / 18);
      let c;
      if (fin) { const ang = Math.atan2(z, x) / TAU; c = hsv(ang + t * 0.07 + dn * 0.35, 0.85, 1.0); }
      else c = grad(EQ_PAL0, hn);
      const base_ = [c[0] * 0.25, c[1] * 0.25, c[2] * 0.25];
      put(o, i, x, h / 2, z, ES * 0.78, h, ES * 0.78, base_, c, 0, 0, 0.6, h2(ix, iz));
    }
    if (fin) {
      // floating title, turned to face the camera
      const cam = this.cam(t, u, p, sec);
      const ang = Math.atan2(cam.pos[0], cam.pos[2]);
      const ca = Math.cos(ang), sa = Math.sin(ang);
      const bob = Math.sin(u * 0.8) * 1.5;
      for (let k = 0; k < TITLE.length && i < N; k++, i++) {
        const v = TITLE[k];
        const c0 = v.grp ? ECHO_COL : grad(TITLE_COLS, v.nx);
        const sc = 0.55, lx = v.x * sc, ly = v.y * sc + 44 + bob, lz = v.z * sc;
        const em = 0.6 + 1.2 * pulse(t) + 2.5 * Math.exp(-Math.pow((v.x - lerp(-120, 120, fract(u / (BAR * 2)))) / 10, 2));
        put(o, i, lx * ca + lz * sa, ly, -lx * sa + lz * ca, sc, sc, sc, mixc(c0, [0, 0, 0], 0.4), c0, em, 0, 0, h1(k));
      }
    }
    // sparks launched on beats
    const nsp = N - i;
    for (let j = 0; j < nsp; j++, i++) {
      const bi = j % 6;
      const bt = lastBeat(t) - bi * BEAT, dt = t - bt;
      const amp = bass(bt + 0.04);
      const a = h1(j * 1.31 + Math.round(bt * 10) * 0.37), b = h1(j * 2.17 + Math.round(bt * 10) * 0.11), c = h1(j * 3.7 + 1);
      const r0 = Math.sqrt(a) * 30, th = b * TAU;
      const x0 = Math.cos(th) * r0, z0 = Math.sin(th) * r0;
      const vy = 16 + 16 * c, vx = (a - 0.5) * 8, vz = (b - 0.5) * 8;
      const y = 3 + vy * dt - 12 * dt * dt;
      if (amp < 0.45 || y < 0 || h1(j * 0.13) > 0.55) { hide(o, i, x0, 2, z0); continue; }
      const col = fin ? hsv(th / TAU + t * 0.07, 0.7, 1) : (c > 0.5 ? [1.0, 0.5, 0.15] : [1.0, 0.2, 0.7]);
      const s = 0.35 * (1 - dt / 3);
      put(o, i, x0 + vx * dt, y, z0 + vz * dt, s, s, s, col, col, 3, 0, 0, a);
    }
  },
  cam(t, u, p) {
    const fin = p.pal === 1;
    const seg = Math.floor(u / (BAR * 4)), w = u - seg * BAR * 4;
    const pre = fin ? [0, 4, 2, 0, 3, 4, 1, 0][seg % 8] : [0, 1, 2, 3][seg % 4];
    const pl = pulse(t);
    let r;
    switch (pre) {
      case 0: { const a = 0.4 + u * 0.16; r = { pos: [Math.sin(a) * 72, 34, Math.cos(a) * 72], look: [0, 4, 0], fov: 50 }; if (fin) { r.pos = [Math.sin(a) * 92, 26, Math.cos(a) * 92]; r.look = [0, 24, 0]; r.fov = 52; } break; }
      case 1: r = { pos: [-55 + w * 9, 9, 26 - w * 2], look: [-30 + w * 9, 6, -20], fov: 58 }; break;
      case 2: { const a = u * 0.25; r = { pos: [Math.sin(a) * 6, 80 - w * 3, Math.cos(a) * 6], look: [0, 0, 0], fov: 55, roll: a }; break; }
      case 3: { const a = 2.0 - u * 0.28; r = { pos: [Math.sin(a) * 40, 13, Math.cos(a) * 40], look: [0, 9, 0], fov: 60 }; break; }
      case 4: { const a = 1.2 + u * 0.12; r = { pos: [Math.sin(a) * 60, 8, Math.cos(a) * 60], look: [0, 40, 0], fov: 62 }; break; }
    }
    r.fov -= pl * 3; r.roll = r.roll || 0;
    return r;
  },
  env(t, u, p) {
    const fin = p.pal === 1;
    return { fog: fin ? [0.02, 0.0, 0.05] : [0.04, 0.0, 0.06], fogD: 0.0042, top: [0.0, 0.0, 0.02], hor: fin ? [0.06, 0.02, 0.14] : [0.12, 0.01, 0.12], stars: 1, aurora: fin ? 0.5 : 0, sun: 0, ground: 1,
             gridCol: fin ? [0.3, 0.6, 1.0] : [1.0, 0.2, 0.6], cell: ES, seam: 0.55, lit: 0, exposure: 1.0, bloom: [0.6, 0.45, 0.85] };
  },
};

// ---- planet (verse 2)
const PC = [0, 25, 0];
MODES.planet = {
  fill(t, u, p, o) {
    let i = 0;
    const rot = u * 0.14, cr = Math.cos(rot), sr = Math.sin(rot);
    const tilt = 0.3, ct = Math.cos(tilt), st = Math.sin(tilt);
    const lightFrac = smooth(0, 13, u) * 0.55;
    const pl = pulse(t);
    for (let k = 0; k < PLANET.length; k++, i++) {
      const [px, py, pz] = PLANET[k];
      const R = Math.hypot(px, py, pz), nx = px / R, ny = py / R, nz = pz / R;
      const n = PLANET_N[k];
      const land = n > 0.52, mount = n > 0.6;
      const band = Math.min(31, Math.floor(Math.abs(ny) * 30));
      const push = (mount ? 1 : 0) + spec(band, t) * 2.2 * (0.5 + energy(t));
      let x = px + nx * push, y = py + ny * push, z = pz + nz * push;
      // spin + tilt
      const x1 = x * cr - z * sr, z1 = x * sr + z * cr;
      const x2 = x1 * ct - y * st, y2 = x1 * st + y * ct;
      const hk = h1(k * 0.37 + 9);
      let c, a, em = 0;
      if (land) {
        c = PLANET_M[k] > 0.5 ? [0.22, 0.08, 0.32] : [0.08, 0.26, 0.22];
        a = [0.6, 0.25, 1.0];
        if (hk < lightFrac) { a = [1.0, 0.7, 0.3]; em = 1.8 + pl * 1.5; c = [0.8, 0.5, 0.2]; }
      } else {
        c = [0.02, 0.07, 0.24]; a = [0.1, 0.5, 1.0];
        em = 0.12 + 0.25 * Math.pow(0.5 + 0.5 * Math.sin(t * 1.7 + hk * 20), 4);
      }
      put(o, i, PC[0] + x2, PC[1] + y2, PC[2] + z1, 1, 1, 1, c, a, em, 0, 0, hk);
    }
    // moon
    const ma = u * 0.35 + 1, mx = Math.sin(ma) * 46, mz = Math.cos(ma) * 46, my = 8 * Math.sin(ma * 0.7);
    for (let k = 0; k < MOON.length; k++, i++) {
      const [px, py, pz] = MOON[k];
      put(o, i, PC[0] + mx + px, PC[1] + my + py, PC[2] + mz + pz, 1, 1, 1, [0.6, 0.6, 0.7], [0.8, 0.8, 1.0], 0.1, 0, 0, h1(k));
    }
    // ring
    const rt = 0.38, crt = Math.cos(rt), srt = Math.sin(rt);
    for (let j = 0; j < 1700 && i < N; j++, i++) {
      const a = h1(j * 1.17 + 51), b = h1(j * 2.39 + 53), c = h1(j * 3.53 + 57);
      const r = 24 + a * 10, th = b * TAU + u * (2.2 / r);
      let x = Math.cos(th) * r, y = (c - 0.5) * 1.4, z = Math.sin(th) * r;
      const y1 = y * crt - z * srt, z1 = y * srt + z * crt;
      const s = 0.35 + 0.8 * c * c;
      const sp = Math.exp(-sinceBeat(t) * 6) * (h1(j + Math.floor(lastBeat(t) * 3)) > 0.8 ? 3 : 0);
      put(o, i, PC[0] + x, PC[1] + y1, PC[2] + z1, s, s, s, [0.45, 0.55, 0.9], [0.4, 0.7, 1.0], 0.25 + sp, 0, 0, a);
    }
    hideFrom(o, i);
  },
  cam(t, u) {
    const a = 0.8 + u * 0.07, r = 74 - u * 1.3;
    return { pos: [Math.sin(a) * r, PC[1] + 14 + 8 * Math.sin(u * 0.17), Math.cos(a) * r], look: PC, fov: 45, roll: 0.05 * Math.sin(u * 0.2) };
  },
  env() { return { fog: [0.0, 0.0, 0.015], fogD: 0.0014, top: [0.0, 0.0, 0.015], hor: [0.04, 0.02, 0.1], stars: 1.4, aurora: 0.6, sun: 0, ground: 0, gridCol: [0, 0, 0], cell: 4, seam: 0.4, lit: 0, exposure: 1.0, bloom: [0.55, 0.45, 0.85] }; },
};
let PLANET_N, PLANET_M;

// ---- tunnel (chorus 2)
const TNR = 66, TPR = 40, TSP = 2.4, TR = 11, TY = 25;
const tunZ = u => -9000 - 38 * u;
MODES.tunnel = {
  fill(t, u, p, o) {
    const zc = tunZ(u), base = Math.floor(-zc / TSP) - 2;
    const sb = sinceBeat(t), amp = clamp(bass(lastBeat(t) + 0.04) * 1.3);
    let i = 0;
    for (let ir = 0; ir < TNR; ir++) {
      const k = ringCell(ir, TNR, base);
      const z = -k * TSP, dz = -zc - (-z) < 0 ? 0 : (k * TSP - (-zc));
      const twist = 0.5 * Math.sin(k * 0.045 + u * 0.6);
      const wave = Math.exp(-Math.pow((dz - sb * 110) / 6, 2)) * amp;
      const hue = 0.5 + 0.45 * (0.5 + 0.5 * Math.sin(k * 0.06 + u * 0.8));
      for (let j = 0; j < TPR; j++, i++) {
        const a = j / TPR * TAU + twist;
        const band = Math.min(31, Math.floor(Math.abs(fract(j / TPR + 0.25) - 0.5) * 2 * 30));
        const v = spec(band, t - dz * 0.006);
        const r = TR - v * 4.5;
        const x = Math.cos(a) * r, y = TY + Math.sin(a) * r;
        const s = 1.4 + v * 1.4;
        const c = hsv(hue + j * 0.004, 0.85, 1);
        put(o, i, x, y, z, s, s, s * 0.9, [c[0] * 0.2, c[1] * 0.2, c[2] * 0.2], c, 0.15 + 3 * wave, 0, 0.5 * v, h1(k * 40 + j));
      }
    }
    const S = 160, dist = -zc;
    for (let j = 0; j < 500 && i < N; j++, i++) {
      const a = h1(j * 1.53 + 61), b = h1(j * 2.29 + 67), c = h1(j * 3.19 + 71);
      const D = a * S + S * Math.ceil((dist + 3 - a * S) / S);
      const rr = 2 + b * 6, th = c * TAU;
      put(o, i, Math.cos(th) * rr, TY + Math.sin(th) * rr, -D, 0.07, 0.07, 3.5, [1, 1, 1], [0.8, 0.9, 1.0], 1.2, 0, 0, a);
    }
    hideFrom(o, i);
  },
  cam(t, u) {
    const zc = tunZ(u);
    const x = Math.sin(u * 0.7) * 2.4, y = TY + Math.cos(u * 0.5) * 2.4;
    return { pos: [x, y, zc], look: [Math.sin((u + 0.6) * 0.7) * 2, TY + Math.cos((u + 0.6) * 0.5) * 2, zc - 30], fov: 72 + pulse(t) * 5, roll: Math.sin(u * 0.33) * 0.6 };
  },
  env() { return { fog: [0.0, 0.0, 0.02], fogD: 0.0105, top: [0, 0, 0.02], hor: [0.02, 0.0, 0.05], stars: 0.5, aurora: 0, sun: 0, ground: 0, gridCol: [0, 0, 0], cell: 4, seam: 0.6, lit: 0, exposure: 1.0, bloom: [0.65, 0.5, 0.8] }; },
};

// ------------------------------------------------------------------ three.js setup
let renderer, scene, camera, composer, bloom, finalPass, voxMat, skyMat, groundMat, ground, sky, geo;
const ATTR = {};

const VOX_VS = /* glsl */`
attribute vec3 iPos; attribute vec3 iScale; attribute vec3 iColor; attribute vec3 iAcc; attribute vec4 iData;
varying vec3 vN; varying vec3 vW; varying vec3 vL; varying vec3 vC; varying vec3 vA; varying vec4 vD; varying vec3 vS;
void main(){
  vec3 p = position * iScale + iPos;
  vL = (position + 0.5) * iScale; vS = iScale;
  vN = normal; vW = p; vC = iColor; vA = iAcc; vD = iData;
  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
}`;
const VOX_FS = /* glsl */`
uniform vec3 uFog; uniform float uFogD; uniform vec3 uCam; uniform float uTime; uniform float uLit;
uniform float uSeam; uniform vec3 uLight; uniform float uPulse;
varying vec3 vN; varying vec3 vW; varying vec3 vL; varying vec3 vC; varying vec3 vA; varying vec4 vD; varying vec3 vS;
float h21(vec2 p){ p = fract(p*vec2(123.34,456.21)); p += dot(p, p+45.32); return fract(p.x*p.y); }
void main(){
  vec3 n = normalize(vN);
  vec2 uv, fs;
  if (abs(n.x) > 0.5) { uv = vL.zy; fs = vS.zy; }
  else if (abs(n.y) > 0.5) { uv = vL.xz; fs = vS.xz; }
  else { uv = vL.xy; fs = vS.xy; }
  // voxel seams every world unit (for small cubes: just the outline)
  vec2 vs = vec2(fs.x > 1.5 ? 1.0 : 1000.0, fs.y > 1.5 ? 1.0 : 1000.0);
  vec2 g = uv / vs;
  vec2 fw = max(fwidth(g), vec2(1e-4));
  vec2 e = min(fract(g), 1.0 - fract(g)) / fw;
  float seam = 1.0 - smoothstep(0.4, 1.4, min(e.x, e.y));
  vec2 fo = max(fwidth(uv), vec2(1e-4));
  vec2 eo = min(uv, fs - uv) / fo;
  float edge = 1.0 - smoothstep(0.5, 2.2, min(eo.x, eo.y));
  // lighting
  float diff = max(dot(n, uLight), 0.0);
  float hemi = 0.5 + 0.5 * n.y;
  vec3 base = vC * (0.16 + 0.62 * diff + 0.3 * hemi);
  float var = h21(floor(g) + vD.w * 17.0);
  base *= 0.82 + 0.36 * var;
  base *= 1.0 - 0.5 * seam;
  vec3 col = base;
  float top = vD.z * smoothstep(max(vS.y - 1.0, 0.0), vS.y, vL.y) * (n.y > 0.5 ? 1.6 : 1.0);
  col += vA * (vD.x + top * 1.4) * 0.6;
  col += vA * max(edge, seam * 0.3) * uSeam * 0.7 * (1.0 + 0.8 * uPulse);
  // windows
  if (vD.y > 0.0 && abs(n.y) < 0.5) {
    vec2 wc = uv; vec2 cell = floor(wc); vec2 f = fract(wc);
    float inWin = step(0.2, f.x) * step(f.x, 0.8) * step(0.22, f.y) * step(f.y, 0.72);
    inWin *= step(1.0, wc.y) * step(wc.y, vS.y - 0.5);
    float r = h21(cell + vD.w * 31.7 + n.xz * 7.13);
    float on = step(r, uLit * vD.y * 0.6);
    vec3 wcol = mix(vec3(1.0, 0.62, 0.28), vec3(0.35, 0.8, 1.0), step(0.72, h21(cell * 1.31 + vD.w)));
    float fl = 0.85 + 0.15 * sin(uTime * 3.0 + r * 40.0);
    col = mix(col, wcol * 1.3 * fl, inWin * on);
    col = mix(col, col * 0.5, inWin * (1.0 - on));
  }
  float d = length(vW - uCam);
  float f = 1.0 - exp(-pow(d * uFogD, 2.0));
  col = mix(col, uFog, clamp(f, 0.0, 1.0));
  gl_FragColor = vec4(col, 1.0);
}`;

const SKY_VS = `varying vec3 vDir; void main(){ vDir = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }`;
const SKY_FS = /* glsl */`
uniform vec3 uTop; uniform vec3 uHor; uniform float uStars; uniform float uAurora; uniform float uSun; uniform float uTime;
varying vec3 vDir;
float h3(vec3 p){ p = fract(p*0.3183099 + 0.1); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
void main(){
  vec3 d = normalize(vDir);
  float y = d.y;
  vec3 col = mix(uHor, uTop, smoothstep(-0.02, 0.55, y));
  col = mix(col, uHor * 0.5, smoothstep(0.0, -0.4, y));
  vec3 q = floor(d * 240.0);
  float s = h3(q);
  float star = step(0.9965, s) * smoothstep(-0.1, 0.15, y);
  col += vec3(0.8, 0.85, 1.0) * star * (0.55 + 0.45 * sin(uTime * 3.0 + s * 300.0)) * uStars * 1.6;
  if (uAurora > 0.001) {
    vec3 pd = floor(d * 70.0) / 70.0;
    float band = sin(pd.x * 5.0 + uTime * 0.25 + sin(pd.z * 3.5 + uTime * 0.18) * 1.8);
    float a = smoothstep(0.3, 1.0, band) * smoothstep(0.02, 0.3, pd.y) * smoothstep(0.9, 0.35, pd.y);
    col += mix(vec3(0.05, 0.9, 0.6), vec3(0.6, 0.15, 1.0), smoothstep(0.1, 0.6, pd.y)) * a * uAurora * 0.6;
  }
  if (uSun > 0.001) {
    vec2 pq = vec2(atan(d.x, -d.z), asin(clamp(d.y, -1.0, 1.0)) - 0.12);
    pq = floor(pq * 80.0) / 80.0;
    float r = length(pq);
    float disc = 1.0 - smoothstep(0.255, 0.265, r);
    float stripes = step(0.0, sin(pq.y * 140.0 - uTime * 1.5) + (pq.y + 0.25) * 6.0 - 0.6);
    float cut = pq.y < 0.0 ? stripes : 1.0;
    vec3 sc = mix(vec3(1.0, 0.1, 0.45), vec3(1.0, 0.85, 0.25), smoothstep(-0.25, 0.25, pq.y));
    col += sc * disc * cut * uSun * 2.2;
    col += sc * exp(-r * 4.0) * 0.4 * uSun;
  }
  gl_FragColor = vec4(col, 1.0);
}`;

const GROUND_VS = `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position,1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const GROUND_FS = /* glsl */`
uniform vec3 uGrid; uniform vec3 uFog; uniform vec3 uCam; uniform float uFogD; uniform float uPulse; uniform float uCell; uniform float uOpacity;
varying vec3 vW;
void main(){
  vec2 g = vW.xz / uCell;
  vec2 fw = max(fwidth(g), vec2(1e-4));
  vec2 e = abs(fract(g - 0.5) - 0.5) / fw;
  float line = 1.0 - min(min(e.x, e.y), 1.0);
  float fade = exp(-max(fw.x, fw.y) * 2.0);
  vec3 col = vec3(0.008, 0.006, 0.02);
  col += uGrid * line * fade * (0.5 + 1.3 * uPulse);
  float d = length(vW - uCam);
  float f = 1.0 - exp(-pow(d * uFogD, 2.0));
  col = mix(col, uFog, clamp(f, 0.0, 1.0));
  gl_FragColor = vec4(col, uOpacity);
}`;

const FINAL_FS = /* glsl */`
uniform sampler2D tDiffuse; uniform sampler2D tLyA; uniform sampler2D tLyB;
uniform vec4 uA; uniform vec4 uB; uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
uniform vec2 uRes; uniform float uTime; uniform float uCA; uniform float uGrain; uniform float uFade; uniform float uFlash; uniform float uSweep;
varying vec2 vUv;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void lyr(sampler2D T, vec4 P, vec2 uv, inout vec3 col){
  if (P.x <= 0.001) return;
  float vis = P.x, bs = P.y, seed = P.z, gl = P.w;
  vec2 px = uv * uRes;
  float tq = floor(uTime * 24.0);
  float rowH = 8.0 + 34.0 * hash(vec2(seed, tq));
  float row = floor(px.y / rowH);
  float on = step(1.0 - 0.35 * gl, hash(vec2(row * 1.7 + seed, tq)));
  px.x += (hash(vec2(row, tq + seed)) - 0.5) * 70.0 * gl * on;
  vec2 bp = (floor(px / bs) + 0.5) * bs;
  vec2 sp = bs > 1.5 ? bp : px;
  vec2 suv = sp / uRes;
  float n = hash(floor(px / max(bs, 12.0)) + seed * 13.0);
  float keep = vis >= 0.999 ? 1.0 : step(n, vis);
  vec4 c0 = texture2D(T, suv);
  float ca = 2.0 + gl * 14.0;
  float aR = texture2D(T, suv + vec2(ca, 0.0) / uRes).a;
  float aB = texture2D(T, suv - vec2(ca, 0.0) / uRes).a;
  float glow = 0.0, back = 0.0;
  for (int i = 0; i < 12; i++) {
    float a = float(i) / 12.0 * 6.2831853 + 0.3;
    vec2 o = vec2(cos(a), sin(a));
    vec4 s1 = texture2D(T, suv + o * 9.0 / uRes);
    vec4 s2 = texture2D(T, suv + o * 22.0 / uRes);
    glow += s1.r * s1.a + s2.r * s2.a * 0.6;
    back += s1.a + s2.a;
  }
  glow /= 19.2; back /= 24.0;
  float sung = c0.r * c0.a, uns = c0.g * c0.a, act = c0.b * c0.a;
  vec3 neon = mix(uC1, uC2, smoothstep(0.15, 0.85, suv.x + 0.12 * sin(uTime * 1.3 + suv.y * 4.0)));
  neon = mix(neon, uC3, act);
  float sw = exp(-pow((suv.x - uSweep) * 7.0, 2.0));
  vec3 bright = mix(vec3(1.0), neon, 0.18 + 0.25 * act) * (1.0 + 0.7 * sw);
  bright *= 0.9 + 0.1 * sin(px.y * 1.6);
  vec3 dim = vec3(0.85, 0.88, 1.0) * 0.55;
  col *= 1.0 - 0.78 * back * keep * vis;
  float shd = texture2D(T, suv + vec2(-3.0, -4.0) / uRes).a;
  col *= 1.0 - 0.65 * shd * keep * vis;
  col += neon * glow * 1.25 * keep * vis;
  col += vec3(aR, 0.0, aB) * neon * 0.55 * keep * gl;
  float ta = (c0.r + c0.g) > 0.0 ? c0.a : 0.0;
  vec3 tc = (sung * bright + uns * dim) / max(sung + uns, 1e-3);
  col = mix(col, tc, ta * keep * (uns > sung ? 0.75 : 1.0));
}
void main(){
  vec2 uv = vUv;
  vec2 d = (uv - 0.5) * uCA;
  vec3 col = vec3(texture2D(tDiffuse, uv + d).r, texture2D(tDiffuse, uv).g, texture2D(tDiffuse, uv - d).b);
  lyr(tLyA, uA, uv, col);
  lyr(tLyB, uB, uv, col);
  col += vec3(1.0, 0.92, 0.96) * uFlash * 0.65;
  float v = smoothstep(1.25, 0.35, length((uv - 0.5) * vec2(1.6, 1.0)));
  col *= mix(0.55, 1.0, v);
  col += (hash(uv * uRes + fract(uTime * 7.31) * 100.0) - 0.5) * uGrain;
  col *= 1.0 - uFade;
  gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}`;

// ------------------------------------------------------------------ lyrics
const LYC = [], LYT = [];
function mkLyr() {
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter; tex.magFilter = THREE.LinearFilter; tex.generateMipmaps = false;
  LYC.push(c); LYT.push(tex);
}
function drawLine(slot, L, t) {
  const c = LYC[slot], g = c.getContext('2d');
  g.clearRect(0, 0, W, H);
  const k = W / 1920;
  const big = L.chorus, size = (big ? 104 : 66) * k;
  g.font = `900 ${size}px Orbitron`;
  g.letterSpacing = `${(big ? 6 : 3) * k}px`;
  g.textBaseline = 'middle';
  const words = L.words.map(w => ({ ...w, txt: w.w.toUpperCase(), wd: g.measureText(w.w.toUpperCase()).width }));
  const space = size * 0.45, maxW = 1680 * k;
  const rows = [[]]; let rw = 0;
  for (const w of words) {
    if (rows[rows.length - 1].length && rw + space + w.wd > maxW) { rows.push([]); rw = 0; }
    rw += (rows[rows.length - 1].length ? space : 0) + w.wd; rows[rows.length - 1].push(w);
  }
  const lh = size * 1.3;
  const yc = (big ? 0.5 : 0.84) * H - (rows.length - 1) * lh / 2;
  rows.forEach((row, r) => {
    const tw = row.reduce((s, w) => s + w.wd, 0) + space * (row.length - 1);
    let x = (W - tw) / 2;
    const y = yc + r * lh;
    for (const w of row) {
      const s = w.s + I, e = w.e + I;
      if (t >= e) { g.fillStyle = 'rgb(255,0,0)'; g.fillText(w.txt, x, y); }
      else if (t < s) { g.fillStyle = 'rgb(0,255,0)'; g.fillText(w.txt, x, y); }
      else {
        const p = clamp((t - s) / Math.max(0.12, e - s));
        const pop = 1 + 0.16 * Math.sin(Math.min(1, p * 2.5) * Math.PI);
        g.save();
        g.translate(x + w.wd / 2, y - 6 * k * Math.sin(Math.min(1, p * 2.5) * Math.PI));
        g.scale(pop, pop); g.translate(-(x + w.wd / 2), -y);
        g.fillStyle = 'rgb(0,255,0)'; g.fillText(w.txt, x, y);
        g.beginPath(); g.rect(x - 10, 0, w.wd * Math.min(1, p * 1.6) + 10, H); g.clip();
        g.fillStyle = 'rgb(255,0,255)'; g.fillText(w.txt, x, y);
        g.restore();
      }
      x += w.wd + space;
    }
  });
  LYT[slot].needsUpdate = true;
}
function lyricsUniforms(t) {
  const out = [[0, 1, 0, 0], [0, 1, 0, 0]];
  for (let n = 0; n < LYR.length; n++) {
    const L = LYR[n], s = L.start + I, e = L.end + I;
    const next = LYR[n + 1];
    const exitAt = Math.min(e + 0.2, next ? next.start + I - 0.3 : 1e9);
    if (t < s - 0.4 || t > exitAt + 0.45) continue;
    const vin = smooth(s - 0.4, s - 0.05, t), vout = 1 - smooth(exitAt, exitAt + 0.4, t);
    const vis = Math.min(vin, vout);
    const slot = n % 2;
    drawLine(slot, L, t);
    const on = onset(t);
    const gl = clamp((1 - vis) * 1.0 + (on > 0.8 ? (on - 0.8) * 1.5 : 0) + Math.exp(-(t - s + 0.05) * 10) * 0.35 * (t > s - 0.05 ? 1 : 0));
    out[slot] = [vis, 1 + Math.pow(1 - vis, 1.5) * 40, n * 1.37 + 0.5, gl];
  }
  return out;
}
function lyricColors(m) {
  switch (m) {
    case 'city': return [[0.2, 0.85, 1.0], [1.0, 0.25, 0.75], [1.0, 0.9, 0.4]];
    case 'terrain': return [[1.0, 0.45, 0.2], [1.0, 0.2, 0.6], [1.0, 0.95, 0.5]];
    case 'eq': return [[1.0, 0.2, 0.7], [1.0, 0.6, 0.1], [1.0, 1.0, 0.6]];
    case 'planet': return [[0.3, 0.7, 1.0], [0.7, 0.35, 1.0], [0.6, 1.0, 0.9]];
    case 'tunnel': return [[0.2, 1.0, 0.9], [0.9, 0.2, 1.0], [1.0, 1.0, 0.6]];
    default: return [[0.6, 0.3, 1.0], [0.2, 0.8, 1.0], [1.0, 0.9, 0.5]];
  }
}

// ------------------------------------------------------------------ frame assembly
const BA = mkBuf(), BB = mkBuf();
function secAt(t) { let k = 0; for (let i = 0; i < SEC.length; i++) if (SEC[i].t - TR_PRE <= t) k = i; return k; }
function evalMode(sec, t, buf) {
  const u = t - sec.t, M = MODES[sec.m], p = sec.p || {};
  M.fill.call(M, t, u, p, buf, sec);
  return { cam: M.cam.call(M, t, u, p, sec), env: M.env.call(M, t, u, p, sec) };
}
function lerpObj(a, b, q) {
  if (typeof a === 'number') return lerp(a, b, q);
  if (Array.isArray(a)) return a.map((v, i) => lerpObj(v, b[i], q));
  const o = {}; for (const k in a) o[k] = lerpObj(a[k], b[k], q); return o;
}

function update(t) {
  const k = secAt(t), sec = SEC[k];
  let cam, env, mode = sec.m;
  const tb0 = sec.t - TR_PRE, tb1 = sec.t + TR_POST;
  if (k > 0 && t < tb1) {
    const prev = SEC[k - 1];
    const ra = evalMode(prev, t, BA), rb = evalMode(sec, t, BB);
    const p = clamp((t - tb0) / (tb1 - tb0));
    const lift = sec.lift || 12;
    const P = ATTR.pos.array, S = ATTR.scl.array, C = ATTR.col.array, Ac = ATTR.acc.array, D = ATTR.dat.array;
    for (let i = 0; i < N; i++) {
      const st = h1(i * 0.731 + 0.2) * 0.45;
      const q = easeIO(clamp((p - st) / 0.55));
      const j = i * 3;
      const aH = BA.scl[j] === 0 && BA.scl[j + 1] === 0, bH = BB.scl[j] === 0 && BB.scl[j + 1] === 0;
      const src = aH ? BB : BA, dst = bH ? BA : BB;
      const arc = Math.sin(Math.PI * q), hr = h1(i * 1.37 + 0.5);
      P[j] = lerp(src.pos[j], dst.pos[j], q) + arc * (hr - 0.5) * lift * 1.2;
      P[j + 1] = lerp(src.pos[j + 1], dst.pos[j + 1], q) + arc * lift * (0.4 + hr);
      P[j + 2] = lerp(src.pos[j + 2], dst.pos[j + 2], q) + arc * (h1(i * 2.11) - 0.5) * lift * 1.2;
      for (let c = 0; c < 3; c++) {
        S[j + c] = lerp(BA.scl[j + c], BB.scl[j + c], q);
        C[j + c] = lerp(src.col[j + c], dst.col[j + c], q);
        Ac[j + c] = lerp(src.acc[j + c], dst.acc[j + c], q);
      }
      // keep flying voxels at least visible-ish and glowing
      if (arc > 0.05 && !(aH && bH)) { const m = Math.max(S[j], S[j + 1], S[j + 2]); if (m < 0.3) { S[j] = S[j + 1] = S[j + 2] = Math.max(m, 0.3 * arc); } }
      const kk = i * 4;
      for (let c = 0; c < 4; c++) D[kk + c] = lerp(src.dat[kk + c], dst.dat[kk + c], q);
      D[kk] += arc * 1.6;
    }
    const pc = sec.cut ? (t >= sec.t ? 1 : 0) : easeIO(p);
    cam = lerpObj(ra.cam, rb.cam, pc);
    env = lerpObj(ra.env, rb.env, easeIO(p));
    if (p < 0.5) mode = prev.m;
  } else {
    const r = evalMode(sec, t, BA);
    ATTR.pos.array.set(BA.pos); ATTR.scl.array.set(BA.scl); ATTR.col.array.set(BA.col);
    ATTR.acc.array.set(BA.acc); ATTR.dat.array.set(BA.dat);
    cam = r.cam; env = r.env;
  }
  for (const a of Object.values(ATTR)) a.needsUpdate = true;

  // camera (+ beat shake)
  const pl = pulse(t);
  const shake = 0.12 * pl + 0.05 * onset(t);
  camera.position.set(cam.pos[0] + (vnoise(t * 9, 1) - 0.5) * shake, cam.pos[1] + (vnoise(t * 9, 7) - 0.5) * shake, cam.pos[2]);
  camera.up.set(Math.sin(cam.roll || 0), Math.cos(cam.roll || 0), 0);
  camera.lookAt(cam.look[0], cam.look[1], cam.look[2]);
  camera.fov = cam.fov; camera.updateProjectionMatrix();

  // environment
  const fog = new THREE.Vector3(...env.fog);
  voxMat.uniforms.uFog.value.copy(fog); voxMat.uniforms.uFogD.value = env.fogD;
  voxMat.uniforms.uCam.value.copy(camera.position); voxMat.uniforms.uTime.value = t;
  voxMat.uniforms.uLit.value = env.lit; voxMat.uniforms.uSeam.value = env.seam; voxMat.uniforms.uPulse.value = pl;
  skyMat.uniforms.uTop.value.set(...env.top); skyMat.uniforms.uHor.value.set(...env.hor);
  skyMat.uniforms.uStars.value = env.stars; skyMat.uniforms.uAurora.value = env.aurora; skyMat.uniforms.uSun.value = env.sun; skyMat.uniforms.uTime.value = t;
  sky.position.copy(camera.position);
  groundMat.uniforms.uGrid.value.set(...env.gridCol); groundMat.uniforms.uFog.value.copy(fog);
  groundMat.uniforms.uCam.value.copy(camera.position); groundMat.uniforms.uFogD.value = env.fogD;
  groundMat.uniforms.uPulse.value = pl; groundMat.uniforms.uCell.value = env.cell; groundMat.uniforms.uOpacity.value = env.ground;
  ground.visible = env.ground > 0.01;
  ground.position.set(Math.round(camera.position.x / 60) * 60, 0, Math.round(camera.position.z / 60) * 60);
  renderer.toneMappingExposure = env.exposure;
  bloom.strength = env.bloom[0] * (1 + 0.25 * pl); bloom.radius = env.bloom[1]; bloom.threshold = env.bloom[2];

  // post / lyrics
  const fu = finalPass.uniforms;
  const ly = lyricsUniforms(t);
  fu.uA.value.set(...ly[0]); fu.uB.value.set(...ly[1]);
  const lc = lyricColors(mode);
  fu.uC1.value.set(...lc[0]); fu.uC2.value.set(...lc[1]); fu.uC3.value.set(...lc[2]);
  fu.uTime.value = t; fu.uSweep.value = fract(t * 0.3) * 1.6 - 0.3;
  fu.uCA.value = 0.0025 + 0.006 * pl + 0.004 * onset(t);
  let flash = 0;
  for (const s of SEC) if (s.flash && t >= s.t && t < s.t + 1.5) flash = Math.max(flash, s.flash * Math.exp(-(t - s.t) * 5));
  fu.uFlash.value = flash;
  fu.uFade.value = Math.max(1 - smooth(0, 0.8, t), smooth(END - 1.6, END - 0.1, t));
}

async function setup() {
  await Promise.all(['900 66px Orbitron', '400 25px "Russo One"'].map(f => document.fonts.load(f)));
  [FEAT, LYR] = await Promise.all([fetch('../audio_features.json').then(r => r.json()), fetch('../lyrics.json').then(r => r.json())]);
  END = FEAT.nframes / FPS;
  for (let i = 0; i < SEC.length; i++) SEC[i].dur = (i + 1 < SEC.length ? SEC[i + 1].t : END) - SEC[i].t;
  buildTitle();
  ORB = shell(10); PLANET = shell(15); MOON = shell(3);
  PLANET_N = PLANET.map(([x, y, z]) => { const r = Math.hypot(x, y, z); return fbm3(x / r * 1.8 + 5, y / r * 1.8 + 3, z / r * 1.8 + 1); });
  PLANET_M = PLANET.map(([x, y, z]) => vnoise3(x * 0.15 + 9, y * 0.15, z * 0.15));

  renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(1); renderer.setSize(W, H);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  document.body.appendChild(renderer.domElement);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(50, W / H, 0.3, 3000);

  geo = new THREE.InstancedBufferGeometry();
  const box = new THREE.BoxGeometry(1, 1, 1);
  geo.index = box.index; geo.setAttribute('position', box.attributes.position); geo.setAttribute('normal', box.attributes.normal);
  const mk = (name, size) => { const a = new THREE.InstancedBufferAttribute(new Float32Array(N * size), size); a.setUsage(THREE.DynamicDrawUsage); geo.setAttribute(name, a); return a; };
  ATTR.pos = mk('iPos', 3); ATTR.scl = mk('iScale', 3); ATTR.col = mk('iColor', 3); ATTR.acc = mk('iAcc', 3); ATTR.dat = mk('iData', 4);
  geo.instanceCount = N;
  voxMat = new THREE.ShaderMaterial({
    vertexShader: VOX_VS, fragmentShader: VOX_FS,
    uniforms: { uFog: { value: new THREE.Vector3() }, uFogD: { value: 0 }, uCam: { value: new THREE.Vector3() }, uTime: { value: 0 }, uLit: { value: 0 },
                uSeam: { value: 0.5 }, uLight: { value: new THREE.Vector3(0.45, 0.8, 0.35).normalize() }, uPulse: { value: 0 } },
  });
  const vox = new THREE.Mesh(geo, voxMat); vox.frustumCulled = false; scene.add(vox);

  skyMat = new THREE.ShaderMaterial({ vertexShader: SKY_VS, fragmentShader: SKY_FS, side: THREE.BackSide, depthWrite: false,
    uniforms: { uTop: { value: new THREE.Color() }, uHor: { value: new THREE.Color() }, uStars: { value: 1 }, uAurora: { value: 0 }, uSun: { value: 0 }, uTime: { value: 0 } } });
  sky = new THREE.Mesh(new THREE.SphereGeometry(1000, 48, 24), skyMat); sky.renderOrder = -1; sky.frustumCulled = false; scene.add(sky);

  groundMat = new THREE.ShaderMaterial({ vertexShader: GROUND_VS, fragmentShader: GROUND_FS, transparent: true,
    uniforms: { uGrid: { value: new THREE.Color() }, uFog: { value: new THREE.Vector3() }, uCam: { value: new THREE.Vector3() }, uFogD: { value: 0 }, uPulse: { value: 0 }, uCell: { value: 4 }, uOpacity: { value: 1 } } });
  ground = new THREE.Mesh(new THREE.PlaneGeometry(2400, 2400), groundMat); ground.rotation.x = -Math.PI / 2; ground.position.y = -0.01; scene.add(ground);

  const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: +(params.get('msaa') || 4) });
  composer = new EffectComposer(renderer, rt);
  composer.setPixelRatio(1); composer.setSize(W, H);
  composer.addPass(new RenderPass(scene, camera));
  bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 1.0, 0.5, 0.75);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  mkLyr(); mkLyr();
  finalPass = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, tLyA: { value: LYT[0] }, tLyB: { value: LYT[1] }, uA: { value: new THREE.Vector4() }, uB: { value: new THREE.Vector4() },
      uC1: { value: new THREE.Vector3() }, uC2: { value: new THREE.Vector3() }, uC3: { value: new THREE.Vector3() }, uRes: { value: new THREE.Vector2(W, H) },
      uTime: { value: 0 }, uCA: { value: 0 }, uGrain: { value: 0.03 }, uFade: { value: 0 }, uFlash: { value: 0 }, uSweep: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: FINAL_FS,
  });
  finalPass.uniforms.tLyA.value = LYT[0]; finalPass.uniforms.tLyB.value = LYT[1];
  composer.addPass(finalPass);
  window.INFO = { frames: FEAT.nframes, fps: FPS, title: TITLE.length, orb: ORB.length, planet: PLANET.length, N };
}

window.renderFrame = (f, fmt = 'image/png', q = 1) => {
  update(f / FPS);
  composer.render();
  return renderer.domElement.toDataURL(fmt, q);
};
window.ready = setup().then(() => window.INFO);
