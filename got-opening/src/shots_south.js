// Tomas del Sur (58.3 - 92.68 s)
import { kf, spline, rad } from './kit.js';
import { SI, SN } from './south.js';

const SSKY = { top: 0x0a0a0e, hor: 0x2a2a30, cloud: 0.8, cloudCol: 0x3a3c44 };
const base = (o) => ({ set: 'south', sky: SSKY, fogCol: 0x2a221c, fog: 0.006, bloom: 0.3, bloomTh: 0.9, sat: 0.72, tint: [1.06, 1.0, 0.92], contrast: 1.1, vignette: 0.65, ...o });
const A = (p) => [p[0] + SI[0], p[1] + SI[1], p[2] + SI[2]];
const B = (p) => [p[0] + SN[0], p[1] + SN[1], p[2] + SN[2]];
const AK = (k) => k.map(([t, p]) => [t, A(p)]);
const BK = (k) => k.map(([t, p]) => [t, B(p)]);
// geometria del mapa
const KEEP = [-9, 0, -3], F = [0.955, 0, 0.296];
const kp = (d, y, s = 0) => [KEEP[0] + F[0] * d - F[2] * s, y, KEEP[2] + F[2] * d + F[0] * s];

export const SOUTH_SHOTS = [
  {
    t0: 58.3, t1: 62.062, f: (lt) => {
      const T = lt + 58.3;
      const pos = spline(T, [[58.3, [0, 150, 4]], [59.5, [0, 90, 6]], [60.4, [3, 120, 30]], [61.2, [5, 80, 70]], [62.062, [6, 72, 78]]]);
      const look = spline(T, [[58.3, [0, 0, 2]], [60.4, [0, 0, 1]], [61.2, [0, 0, -1]], [62.062, [0, 0, -2]]]);
      return base({ cam: { pos, look, fov: 40, up: T < 60.6 ? [0, 0, -1] : undefined }, fade: kf(T, [[58.3, 0.15], [59.0, 0.6], [60.0, 1]]), aperture: 0.0004,
        state: { where: 'map', clouds: T < 60.2, shadow: [0, 0, 0, 26], towerRise: 0.2 } });
    },
  },
  {
    t0: 62.062, t1: 71.78, f: (lt) => {
      const T = lt + 62.062;
      const pos = spline(T, [[62.062, [23.8, 0.35, 9.3]], [63.0, [23.0, 0.38, 8.9]], [64.4, [20.4, 0.5, 7.6]], [65.0, [17.6, 0.55, 6.3]], [65.6, [14.5, 0.7, 4.9]],
        [66.5, [10, 0.9, 3.0]], [67.5, [5, 1.0, 1.0]], [68.5, kp(13, 1.1)], [69.5, kp(6.5, 1.2)], [70.6, kp(9.5, 2.6)], [71.78, kp(12, 3.4)]]);
      const look = spline(T, [[62.062, [17, 1.6, 6]], [64.4, [17, 2.2, 6]], [65.0, [12, 1.2, 4]], [66.0, [0, 1.0, -1]], [67.5, kp(0, 1.4)], [68.5, kp(2, 1.4)], [69.5, kp(1, 2.2)], [70.6, kp(0, 2.0)], [71.78, kp(0, 2.0)]]);
      return base({ cam: { pos, look, fov: 42 }, aperture: 0.003, maxblur: 0.014, fog: 0.012, exposure: 1.2,
        state: { where: 'map', shadow: T < 65.5 ? [17, 0, 6, 8] : [-4, 0, -2, 12], towerRise: kf(T, [[62.062, 0.55], [64.4, 1]]) } });
    },
  },
  {
    t0: 71.78, t1: 80.4, f: (lt) => {
      const T = lt + 71.78;
      const pos = spline(T, AK([[71.78, [0.4, 13, 0.6]], [73.0, [0.3, 11, 0.4]], [74.4, [0.1, 8.0, 0.1]], [76.0, [0, 4.0, 0]], [77.8, [0, 0.3, 0]], [78.8, [0, -3.2, -1.9]], [79.6, [0, -6.2, -2.0]], [80.4, [0, -7.5, 1.5]]]));
      const look = spline(T, AK([[71.78, [0, 5, 0]], [74.4, [0, 0, 0]], [77.8, [0, -8, 0]], [78.8, [0, -11, -2.3]], [80.4, [0, -10, -2.3]]]));
      const ang = T * 0.9;
      const up = T < 79.9 ? [Math.cos(ang), 0, Math.sin(ang)] : undefined;
      return base({ cam: { pos, look, fov: 44, up }, skyOn: false, bg: 0x120c08, fog: kf(T, [[71.78, 0.01], [75, 0.04]]), fogCol: 0x140e0a, aperture: 0.002, maxblur: 0.014, exposure: 1.15,
        fade: kf(T, [[74.6, 1], [75.4, 0.7], [77.5, 0.7], [78.2, 1]]),
        state: { where: 'mech', shaft: T > 74, roofOpen: kf(T, [[72.8, 0], [74.4, 1]]), amb: T < 75 ? 0.7 : 0.35, sunI: T < 75 ? 1.6 : 0.3 } });
    },
  },
  {
    t0: 80.4, t1: 84.3, f: (lt) => {
      const T = lt + 80.4;
      const pos = spline(T, AK([[80.4, [0, -9.6, 5.5]], [81.6, [0, -10.1, 3.5]], [82.8, [0, -10.0, 1.4]], [83.5, [0, -9.2, -0.6]], [84.3, [0, -8.6, -3.5]]]));
      const look = spline(T, AK([[80.4, [0, -9.4, -2.3]], [82.8, [0, -9.3, -2.3]], [83.5, [0, -9.0, -4]], [84.3, [0, -9, -8]]]));
      return base({ cam: { pos, look, fov: 44 }, skyOn: false, bg: 0x0c0806, fog: 0.05, fogCol: 0x140e0a, aperture: 0.0025, maxblur: 0.014, exposure: 1.2,
        fade: kf(T, [[83.6, 1], [84.3, 0.3]]),
        state: { where: 'mech', amb: 0.9, sunI: 0.0 } });
    },
  },
  {
    t0: 84.3, t1: 92.676, f: (lt) => {
      const T = lt + 84.3;
      const pos = spline(T, BK([[84.3, [-1.6, 0.6, 27]], [85.3, [-1.0, 0.5, 24]], [86.3, [0, 0.55, 20]], [88.0, [0, 0.7, 15]], [89.5, [0, 1.0, 11]], [91.0, [0, 1.3, 8.6]], [92.676, [0, 1.4, 7.8]]]));
      const look = spline(T, BK([[84.3, [0, 1.6, 0]], [88.0, [0, 1.8, 0]], [91.0, [0, 2.4, 0]], [92.676, [0, 2.5, 0]]]));
      return base({ cam: { pos, look, fov: 42 }, skyOn: false, bg: 0x0c0806, fog: 0.03, fogCol: 0x1e140e, aperture: 0.0025, maxblur: 0.014, exposure: 1.0,
        fade: kf(T, [[84.3, 0.3], [84.9, 1]]), bloom: 0.3, bloomTh: 0.9,
        state: { where: 'nave' } });
    },
  },
];
