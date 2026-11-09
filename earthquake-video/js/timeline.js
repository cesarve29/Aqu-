// Global timeline (seconds of video). Everything in the film is a pure
// function of these constants plus a deterministic simulation stepped at FPS.
// mode=h (query string) renders the full horizontal 16:9 cut at 30 fps; default is vertical 9:16 at 60 fps
export const H_MODE = typeof location !== 'undefined' && location.search.includes('mode=h');
export const FPS = H_MODE ? 30 : 60; // simulation & output frame rate
export const DURATION = 142;    // full story length (s)

// Vertical cut (~1:14): story-time ranges played back to back.
const CUTS_V = [[3.0, 17.4], [37.2, 75.4], [89.2, 97.8], [101.0, 111.2]];
export const CUTS = H_MODE ? [[0, 142]] : CUTS_V;
export const VIDEO_DURATION = CUTS.reduce((s, [a, b]) => s + b - a, 0);
export const VIDEO_CUT_TIMES = CUTS.slice(1).map((_, i) => CUTS.slice(0, i + 1).reduce((s, [a, b]) => s + b - a, 0));
// video time at which a story instant is shown (null if it was cut out)
export function videoTimeOf(st) {
  let acc = 0;
  for (const [a, b] of CUTS) { if (st >= a && st < b) return acc + st - a; acc += b - a; }
  return null;
}
// narration segments that survive the vertical cut, in video time: [vStart, fileStart, fileEnd, text]
export function narrationVideo() {
  return NARRATION.map(([st, f0, f1, txt]) => [videoTimeOf(st), f0, f1, txt]).filter(n => n[0] !== null);
}
export function storyTime(vt) {
  let acc = 0;
  for (const [a, b] of CUTS) {
    if (vt < acc + (b - a)) return a + (vt - acc);
    acc += b - a;
  }
  const [a, b] = CUTS[CUTS.length - 1];
  return b + (vt - acc);
}

export const T = {
  introEnd: 18,
  scaleEnd: 35.5,
  walkStart: 18,
  alert: 40.2,       // phone vibrates
  pStart: 41.2,      // P waves arrive
  sStart: 49.0,      // S waves arrive
  collapse: 55.2,    // building across the street fails
  poleFall: 58.6,
  runStart: 60.0,
  crouch: 63.6,
  cracks: 76.5,
  shakeEnd: 84.5,
  standUp: 86.0,
  beachCut: 89.0,
  recedeStart: 89.0,
  tsunamiAlarm: 93.0,
  runInland: 97.0,
  hillCut: 101.0,
  waveHitCoast: 107.0,
  globeCut: 112.0,
  endingCut: 124.0,
  endCard: 136.8,
};

// Narration segments: [startInVideo, startInFile, endInFile, text]
export const NARRATION = [
  [4.0, 0.0, 13.10, '¿Qué pasaría si mañana ocurriera un terremoto de magnitud diez?|Nunca se ha registrado uno.|El más fuerte de la historia fue el de Valdivia, en Chile, en 1960: magnitud 9,5.'],
  [18.6, 14.36, 30.48, 'La escala es logarítmica: cada punto libera unas 32 veces más energía.|Un terremoto de magnitud 10 liberaría más de cinco veces la energía de Valdivia.|Para producirlo, una falla de más de 4.000 km tendría que romperse de golpe.'],
  [37.6, 31.57, 41.46, 'Estás caminando por la ciudad.|De pronto, tu teléfono vibra: alerta sísmica.|Primero llegan las ondas P, rápidas y suaves.|Tienes apenas unos segundos.'],
  [49.6, 42.44, 53.04, 'Luego llegan las ondas S. El suelo se mueve como el mar.|Los edificios se balancean, los cristales estallan,|y las estructuras más débiles se derrumban.'],
  [62.6, 54.02, 66.41, 'Aléjate de las fachadas y de los cables.|Agáchate, cúbrete la cabeza y sujétate.|Lo peor es la duración: mientras la falla se rompe,|el temblor podría durar diez, quince, incluso veinte minutos.'],
  [76.4, 67.42, 77.84, 'El suelo saturado de agua se licúa y se comporta como arena movediza.|Se abren grietas enormes.|Cuando por fin todo se detiene, la ciudad está irreconocible.'],
  [89.6, 78.77, 91.92, 'Pero no ha terminado. El mar se retira de la costa.|Es la señal de un tsunami. Sube a terreno alto, ahora.|Olas de decenas de metros podrían cruzar océanos enteros|y golpear costas a miles de kilómetros.'],
  [112.6, 92.84, 102.48, 'El planeta entero vibraría como una campana durante días.|El eje de la Tierra se desplazaría varios centímetros,|y el día se acortaría unos microsegundos.'],
  [124.6, 103.39, 115.36, 'Un terremoto de magnitud 10 es extremadamente improbable, pero no imposible.|La mejor defensa es estar preparado:|conoce tu zona segura, ten un plan familiar y una mochila de emergencia.'],
];

export function smooth(e0, e1, x) {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}
export function clamp(x, a, b) { return Math.min(b, Math.max(a, x)); }
export function lerp(a, b, t) { return a + (b - a) * t; }

// Ground-shaking intensity envelope (0..1) as felt in the city.
export function shakeEnvelope(t) {
  const p = smooth(T.pStart, T.pStart + 2.5, t) * 0.12 * (1 - smooth(T.sStart - 0.3, T.sStart, t));
  let s = smooth(T.sStart - 0.2, T.sStart + 1.2, t) * (1 - smooth(T.shakeEnd - 3.5, T.shakeEnd, t));
  // pulses of extra violence
  s *= 0.78 + 0.22 * Math.sin(t * 0.9) * Math.sin(t * 0.37 + 1.0);
  if (t > T.collapse - 0.5 && t < T.collapse + 2) s = Math.max(s, 1.0);
  return Math.max(p, s);
}

// Smooth pseudo-random ground displacement (meters) along x, y, z.
export function groundMotion(t, out) {
  const e = shakeEnvelope(t);
  const n = (f, ph) => Math.sin(t * f + ph);
  out.x = e * (0.32 * n(7.1, 0.3) + 0.21 * n(11.3, 1.7) + 0.12 * n(17.9, 2.2) + 0.25 * n(3.3, 0.9));
  out.y = e * (0.10 * n(9.7, 0.5) + 0.07 * n(15.1, 2.9) + 0.06 * n(4.4, 1.3));
  out.z = e * (0.28 * n(6.3, 2.0) + 0.18 * n(12.7, 0.1) + 0.11 * n(19.3, 1.1) + 0.2 * n(2.9, 0.4));
  return out;
}

export function seaLevel(t) {
  return -0.4 - 7.5 * smooth(T.recedeStart, T.recedeStart + 8, t);
}

// Tsunami front position (z, decreasing z = sea side). Returns null if not yet.
export function waveFront(t) {
  if (t < 99) return null;
  if (t < T.waveHitCoast) return lerp(-720, -170, smooth(99, T.waveHitCoast, t) * 0.4 + (t - 99) / (T.waveHitCoast - 99) * 0.6);
  // inland, decelerating
  const k = t - T.waveHitCoast;
  return -170 + 165 * (1 - Math.exp(-k / 3.2));
}
export function waveHeight(t) {
  const f = waveFront(t);
  if (f === null) return 0;
  if (f < -170) return 32;
  return lerp(32, 10, clamp((f + 170) / 160, 0, 1));
}

export function rng(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
