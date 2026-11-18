// Plan de tomas: cada toma devuelve set, camara y parametros de imagen.
import { kf, spline, rad, clamp, smooth } from './kit.js';
import { NORTH_SHOTS } from './shots_north.js';
import { SOUTH_SHOTS } from './shots_south.js';

const ASTRO_SKY = { top: 0x2e2722, hor: 0x4a4038, glow: 0x9a7e60, glowPow: 6, glowDir: [0, 0, -1], cloud: 0.0 };
const astroBase = (o) => ({ set: 'astro', skyOn: true, bloom: 0.28, bloomTh: 0.95, bloomR: 0.5, sat: 0.9, tint: [1.02, 0.98, 0.92], vignette: 0.5, ...o });

// direccion del sol desde la camara para el brillo del cielo
function glowTo(pos) { const l = Math.hypot(...pos); return [-pos[0] / l, -pos[1] / l, -pos[2] / l]; }

// banda heroe: tramo en z=2.4, inclinado. Los relieves estan en +z.
function heroCam(lt, P) {
  const pos = spline(lt, P.pos), look = spline(lt, P.look);
  return { pos, look, fov: P.fov || 32, roll: P.roll ? kf(lt, P.roll) : 0 };
}

export const SHOTS = [
  // ---------------- BLOQUE 1: astrolabio y dragones ----------------
  {
    t0: 0, t1: 2.336, f: (lt) => astroBase({
      cam: heroCam(lt, {
        pos: [[0, [0.25, -0.35, 4.25]], [1.4, [0.05, -0.3, 4.2]], [2.336, [-0.15, 0.1, 4.45]]],
        look: [[0, [0.2, 0.0, 3.0]], [1.4, [0.0, 0.0, 3.0]], [2.336, [-0.1, 0.25, 3.0]]], fov: 32,
      }),
      focus: 1.27, aperture: 0.004, maxblur: 0.01,
      sky: { ...ASTRO_SKY, glowDir: [0, -0.1, -1] },
      state: { hero: 'dragons', heroRot: 0.42, heroPos: [0.0, 0.0, 3.0], rings: false, bands: false, burst: 0.8, cross: kf(lt, [[1.3, 2.5], [2.336, 0.2]]) },
    }),
  },
  {
    t0: 2.336, t1: 4.3, f: (lt) => {
      const pos = spline(lt, [[0, [0.5, -1.6, 8.2]], [1.2, [0.35, -1.3, 7.0]], [1.96, [-0.6, -0.6, 4.4]]]);
      return astroBase({
        cam: { pos, look: kf(lt, [[0, [0.3, 0.3, 0]], [1.96, [0.9, 0.2, 0]]]), fov: 40, roll: kf(lt, [[0, rad(-6)], [1.96, rad(8)]]) },
        aperture: 0.0008, sky: { ...ASTRO_SKY, glowDir: glowTo(pos) },
        fade: kf(lt, [[0, 1], [1.5, 1], [1.96, 0.35]]),
        state: { rings: true, bands: true, burst: 0.6, bandSlope: kf(lt, [[0, rad(-14)], [1.96, rad(-24)]]) },
      });
    },
  },
  ...NORTH_SHOTS,
  // ---------------- BLOQUE 6: astrolabio con el leon ----------------
  {
    t0: 53.4, t1: 56.348, f: (lt) => astroBase({
      cam: heroCam(lt, {
        pos: [[0, [0.1, -0.6, 4.3]], [0.6, [0.08, -0.2, 4.25]], [2.95, [-0.06, -0.18, 4.25]]],
        look: [[0, [0.1, 0.1, 3.0]], [0.6, [0.08, 0.02, 3.0]], [2.95, [-0.06, 0.02, 3.0]]], fov: 33,
      }),
      focus: 1.27, aperture: 0.0035, maxblur: 0.01,
      fade: kf(lt, [[0, 0], [0.45, 1]]),
      sky: { ...ASTRO_SKY, glowDir: [0, 0.2, -1] },
      state: { hero: 'lion', heroRot: 0.0, heroPos: [0, 0, 3.0], rings: false, bands: false, cross: kf(lt, [[2.3, -1.6], [2.95, 0.1]]), burst: 0.8 },
    }),
  },
  {
    t0: 56.348, t1: 58.3, f: (lt) => {
      const pos = spline(lt, [[0, [-0.3, -1.5, 8.0]], [1.95, [0.2, -1.0, 5.6]]]);
      return astroBase({
        cam: { pos, look: [0.2, 0.4, 0], fov: 40, roll: kf(lt, [[0, rad(4)], [1.95, rad(-6)]]) },
        aperture: 0.0008, sky: { ...ASTRO_SKY, glowDir: glowTo(pos) },
        fade: kf(lt, [[0, 1], [1.3, 0.9], [1.95, 0.3]]),
        state: { rings: true, bands: true, burst: 0.6, bandSlope: rad(-3), band2: lt > 0.6 },
      });
    },
  },
  ...SOUTH_SHOTS,
  // ---------------- BLOQUE 9: banda targaryen y logo ----------------
  {
    t0: 92.676, t1: 95.4, f: (lt) => astroBase({
      cam: heroCam(lt, {
        pos: [[0, [0.15, -0.35, 4.22]], [2.0, [-0.05, -0.33, 4.22]], [2.72, [-0.15, -0.4, 4.6]]],
        look: [[0, [0.1, 0.0, 3.0]], [2.0, [-0.08, 0.0, 3.0]], [2.72, [-0.1, 0.05, 3.0]]], fov: 31,
      }),
      focus: 1.25, aperture: 0.004, maxblur: 0.01,
      sky: { ...ASTRO_SKY, glowDir: [0, 0.1, -1] },
      state: { hero: 'targ', heroRot: 0.5, heroPos: [0, 0, 3.0], rings: false, bands: false, burst: 0.8, cross: kf(lt, [[1.8, 1.8], [2.72, 0.0]]) },
    }),
  },
  {
    t0: 95.4, t1: 100.767, f: (lt) => astroBase({
      cam: { pos: kf(lt, [[0, [0.0, -0.3, 6.6]], [1.4, [0.0, -0.15, 6.2]], [5.4, [0.0, -0.1, 5.75]]]), look: [0, 0.02, 2.2], fov: 40 },
      aperture: 0.0008, bloom: 0.35, bloomTh: 0.9,
      sky: { ...ASTRO_SKY, glowDir: [0, 0, -1] },
      state: { logo: true, logoRot: kf(lt, [[0, -0.55], [1.5, 0]]), logoTilt: kf(lt, [[0, 0.5], [1.5, 0]]), rings: false, bands: false, burst: 1.0 },
    }),
  },
  // ---------------- BLOQUE 10: creditos en negro y poster ----------------
  { t0: 100.767, t1: 107.065, f: () => ({ set: 'none', cam: { pos: [0, 0, 5], look: [0, 0, 0] }, skyOn: false, fade: 0, aperture: 0 }) },
  {
    t0: 107.065, t1: 999, f: (lt) => ({
      set: 'poster', skyOn: false, bg: 0x000000, cam: { pos: [0, 1.15, 7.6], look: [0, 1.15, 0], fov: 32 },
      aperture: 0, bloom: 0.35, bloomTh: 0.9, vignette: 0.3, grain: 0.015, sat: 0.95, state: {},
    }),
  },
];

export function shotAt(t) {
  let s = SHOTS[SHOTS.length - 1];
  for (const sh of SHOTS) if (t >= sh.t0 && t < sh.t1) { s = sh; break; }
  const r = s.f(t - s.t0);
  r.lt = t - s.t0;
  return r;
}
