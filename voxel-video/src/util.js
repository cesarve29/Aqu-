// Utilidades deterministas: todo depende solo del tiempo t, nunca del frame anterior.
import * as THREE from 'three';

export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
export const ramp = (t, a, b) => clamp((t - a) / (b - a));
export const sramp = (t, a, b) => smooth(ramp(t, a, b));
export const pulse = (t, a, b, f = 0.3) => sramp(t, a, a + f) * (1 - sramp(t, b - f, b));
export const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hash2(x, y, s = 0) {
  let h = Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(s | 0, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

export function vnoise(x, y, s = 0) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash2(xi, yi, s), b = hash2(xi + 1, yi, s), c = hash2(xi, yi + 1, s), d = hash2(xi + 1, yi + 1, s);
  return lerp(lerp(a, b, u), lerp(c, d, u), v);
}

export function fbm(x, y, oct = 4, s = 0) {
  let v = 0, a = 0.5, f = 1, n = 0;
  for (let i = 0; i < oct; i++) { v += a * vnoise(x * f, y * f, s + i * 17); n += a; a *= 0.5; f *= 2; }
  return v / n;
}

// angulo mas corto
export function lerpAngle(a, b, t) {
  let d = ((b - a + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI;
  return a + d * t;
}

// keys: [[t, ...valores]]; interpolacion suavizada por tramo (para paradas naturales)
export function keyed(keys, t, easeFn = smooth) {
  if (t <= keys[0][0]) return keys[0].slice(1);
  const last = keys[keys.length - 1];
  if (t >= last[0]) return last.slice(1);
  let i = 0;
  while (i < keys.length - 2 && t > keys[i + 1][0]) i++;
  const k0 = keys[i], k1 = keys[i + 1];
  const u = easeFn((t - k0[0]) / (k1[0] - k0[0]));
  const out = [];
  for (let j = 1; j < k0.length; j++) out.push(lerp(k0[j], k1[j], u));
  return out;
}

// Catmull-Rom sobre claves [[t,x,y,z]] -> Vector3 (vuelo y camaras suaves)
export function spline(keys, t) {
  if (t <= keys[0][0]) return V(keys[0][1], keys[0][2], keys[0][3]);
  const n = keys.length;
  if (t >= keys[n - 1][0]) return V(keys[n - 1][1], keys[n - 1][2], keys[n - 1][3]);
  let i = 0;
  while (i < n - 2 && t > keys[i + 1][0]) i++;
  const p0 = keys[Math.max(0, i - 1)], p1 = keys[i], p2 = keys[i + 1], p3 = keys[Math.min(n - 1, i + 2)];
  const u = (t - p1[0]) / (p2[0] - p1[0]);
  const u2 = u * u, u3 = u2 * u;
  const c = (a, b, cc, d) => 0.5 * ((2 * b) + (-a + cc) * u + (2 * a - 5 * b + 4 * cc - d) * u2 + (-a + 3 * b - 3 * cc + d) * u3);
  return V(c(p0[1], p1[1], p2[1], p3[1]), c(p0[2], p1[2], p2[2], p3[2]), c(p0[3], p1[3], p2[3], p3[3]));
}

// progreso de una accion corta (golpe, disparo) a partir de una lista de instantes
export function actionProgress(times, t, dur) {
  for (let i = times.length - 1; i >= 0; i--) {
    const d = t - times[i];
    if (d >= 0 && d <= dur) return d / dur;
    if (d > dur) break;
  }
  return -1;
}
