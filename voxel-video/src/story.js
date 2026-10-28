// Guion: todos los tiempos (en segundos) y posiciones de la historia.
export const DUR = 335;
export const T_END = 200;      // entrada a la dimension del Fin
export const T_CREDITS = 303;  // creditos finales
export const SEA = 12;
export const MEADOW = [64, 66];
export const GROUND = 16;      // y del bloque superior de la pradera (los pies estan en 17)

export const CABIN = { x0: 50, x1: 56, z0: 50, z1: 55, y: 17 };
export const TABLE = { x: 60, y: 17, z: 56 };
export const TREE = { x: 70, z: 58, y0: 17, h: 5 };
export const LOG_BREAK = [50.2, 51.9, 53.6, 55.3, 57.0];
export const PORTAL = { x0: 62, y0: 17, z: 80 };
export const PORTAL_PLACE = Array.from({ length: 14 }, (_, i) => 176 + i * 0.8);
export const PORTAL_LIT = 189;
export const CRATER = { x: 72, y: 16, z: 68, r: 3.3, t: 143.5 };

// --- Fin ---
export const END_C = [48, 48];
export const END_TOP = 30;
export const PILLAR_H = [16, 22, 18, 24, 15, 20];
export const PILLARS = PILLAR_H.map((h, k) => {
  const a = (k * 60 + 30) * Math.PI / 180;
  return { x: Math.round(48 + 25 * Math.cos(a)), z: Math.round(48 + 25 * Math.sin(a)), h };
});
export const SHOOT_SPOT = [48.5, 58.0];
export const RELEASE = [218.6, 222.1, 225.6, 229.1, 232.6, 236.1];
export const ARROW_FLIGHT = 1.0;
export const CRYSTAL_BOOM = RELEASE.map((r) => r + ARROW_FLIGHT);
export const DRAGON_HITS = [258.0, 259.2, 260.4, 261.6, 262.8, 264.0];
export const DRAGON_CRIT = 274.9;
export const DRAGON_DIE = [275.2, 290.0];
export const EXIT_PORTAL = 291.0;

// golpes de espada / punos del jugador
export const PUNCHES = [];
for (let t = 48.6; t < 57.3; t += 0.42) PUNCHES.push(+t.toFixed(2));
export const SWINGS = [
  101.0, 102.2, 103.4, 106.0, 107.2, 108.4, 111.0, 112.2, 113.4,
  130.0, 131.2, 132.4, 155.2, 156.4, 157.6,
  ...DRAGON_HITS, DRAGON_CRIT - 0.15,
];
export const PLACES = [...PORTAL_PLACE, 188.5];

// Monstruos del mundo normal. keys: [t, x, z]
export const MOBS = [
  { id: 'z1', type: 'zombie', spawn: 86, rise: true, keys: [[86, 64.5, 77.2], [92, 64.5, 77.2], [100.5, 64.5, 68.3]], hits: [101.15, 102.35, 103.55], die: 103.7 },
  { id: 'z2', type: 'zombie', spawn: 87, rise: true, keys: [[87, 77.5, 66.4], [93, 77.5, 66.4], [105.4, 66.3, 66.5]], hits: [106.15, 107.35, 108.55], die: 108.7, attack: [105.3] },
  { id: 'z3', type: 'zombie', spawn: 88, rise: true, keys: [[88, 53.0, 72.5], [94, 53.0, 72.5], [110.4, 62.9, 67.4]], hits: [111.15, 112.35, 113.55], die: 113.7 },
  { id: 'sk', type: 'skeleton', spawn: 90, keys: [[90, 80.5, 57.5]], hits: [130.15, 131.35, 132.55], die: 132.7, shots: [119.5, 122.0, 124.5] },
  { id: 'cr', type: 'creeper', spawn: 131, keys: [[131, 79.5, 73.5], [136, 79.5, 73.5], [141, 72.3, 67.2]], fuse: 141, boom: CRATER.t },
  { id: 'sp', type: 'spider', spawn: 145, keys: [[145, 55.0, 75.5], [152.4, 58.2, 71.2]], leap: [153.3, 154.3, 63.6, 66.0], hits: [155.35, 156.55, 157.75], die: 157.9, attack: [155.7] },
];
// flechas del esqueleto: [disparo, llegada, x, y, z de destino]
export const SK_ARROWS = [
  [119.5, 120.4, 65.9, 17.1, 64.8],
  [122.0, 122.9, 63.1, 17.1, 67.9],
  [124.5, 125.2, 64.5, 18.3, 66.5],
];

// Jugador: [t, x, z, yaw]   (yaw 0 = mirando a +z)
const PI = Math.PI;
export const PLAYER_OVER = [
  [0, 53.5, 57.0, 0], [40, 53.5, 57.0, 0.6],
  [48, 68.3, 58.5, PI / 2], [57.6, 68.3, 58.5, PI / 2],
  [61, 60.5, 57.9, PI], [66, 60.5, 57.9, PI],
  [73, 64.5, 66.5, 0], [100, 64.5, 66.5, 0],
  [104.6, 64.5, 66.5, PI / 2], [109.6, 64.5, 66.5, -1.06], [116, 64.5, 66.5, 2.08], [125.5, 64.5, 66.5, 2.08],
  [129.6, 79.2, 58.3, 2.08], [132.9, 79.2, 58.3, 2.08],
  [138.5, 70.5, 66.0, -PI / 2], [141.8, 70.5, 66.0, -PI / 2], [142.4, 70.5, 66.0, 0.98],
  [143.4, 68.9, 65.1, 0.98], [144.1, 66.3, 63.5, 0.98], [148, 66.3, 63.5, 0.98],
  [151, 64.8, 64.6, -0.71], [158.2, 64.8, 64.6, -0.71], [159.5, 64.8, 64.6, 0.5], [168, 64.8, 64.6, 0.5],
  [175, 64.5, 77.6, 0], [194.5, 64.5, 77.6, 0], [197.5, 64.5, 80.6, 0],
];
const yawTo = (x, z, tx, tz) => Math.atan2(tx - x, tz - z);
const S = SHOOT_SPOT;
const shootKeys = [];
RELEASE.forEach((r, k) => {
  const y = yawTo(S[0], S[1], PILLARS[k].x + 0.5, PILLARS[k].z + 0.5);
  shootKeys.push([r - 1.4, S[0], S[1], y], [r + 0.4, S[0], S[1], y]);
});
export const PLAYER_END = [
  [200, 55.5, 80.5, -2.9], [212.5, 55.5, 80.5, -2.9], [216.8, 48.5, 58.0, PI],
  ...shootKeys,
  [240, 48.5, 58.0, PI], [245.3, 48.5, 58.0, PI], [246.0, 51.6, 57.4, PI],
  [248.4, 51.6, 57.4, -2.6], [251.5, 54.2, 54.6, -2.4], [254.5, 54.2, 54.6, -2.4],
  [257.0, 48.5, 60.3, PI], [265.4, 48.5, 60.3, PI], [266.3, 48.5, 64.6, PI],
  [273.0, 48.5, 64.6, PI], [274.7, 48.5, 60.4, PI], [292.0, 48.5, 60.4, PI],
  [298.6, 48.5, 51.8, PI], [300.2, 48.5, 50.6, PI],
];
// salud del jugador (20 = 10 corazones)
export const DAMAGE = [[105.5, 3], [125.2, 2], [143.6, 7], [155.8, 2], [250.0, 3], [265.6, 2]];
export const REGEN = [[160, 168], [279, 290]];

export const TOASTS = [
  [63.0, 'LOGRO CONSEGUIDO', 'ESPADA DE DIAMANTE', 'sword'],
  [104.0, 'LOGRO CONSEGUIDO', 'PRIMER MONSTRUO DERROTADO', 'sword'],
  [159.0, 'LOGRO CONSEGUIDO', 'CAZADOR DE MONSTRUOS', 'bow'],
  [190.0, 'LOGRO CONSEGUIDO', 'VIAJERO DIMENSIONAL', 'obsidian'],
  [291.5, 'DESAFIO COMPLETADO', 'LIBERA EL FIN', 'egg'],
];
export const CHAPTERS = [
  [13, 'CAPITULO 1', 'EL AMANECER'],
  [76, 'CAPITULO 2', 'LA NOCHE'],
  [169, 'CAPITULO 3', 'EL PORTAL'],
  [201.5, 'CAPITULO 4', 'EL FIN'],
];
export const CREDITS = [
  ['big', 'BLOCKCRAFT'],
  ['sub', 'LA LEYENDA DE LA DRAGONA'],
  ['gap'],
  ['head', 'IDEA ORIGINAL'], ['name', 'CESARVE29'],
  ['gap'],
  ['head', 'DIRECCION, GUION Y PROGRAMACION'], ['name', 'CLAUDE CODE'],
  ['gap'],
  ['head', 'MOTOR 3D'], ['name', 'THREE.JS + WEBGL'],
  ['gap'],
  ['head', 'SHADERS'],
  ['name', 'CIELO DINAMICO DIA Y NOCHE'], ['name', 'AGUA CON REFLEJOS Y OLAS'],
  ['name', 'NUBES VOLUMETRICAS DE BLOQUES'], ['name', 'SOMBRAS EN TIEMPO REAL'],
  ['name', 'OCLUSION AMBIENTAL'], ['name', 'BLOOM Y GRADACION DE COLOR'],
  ['name', 'PORTALES DIMENSIONALES'],
  ['gap'],
  ['head', 'REPARTO'],
  ['name', 'EL HEROE'], ['name', 'LOS ZOMBIS'], ['name', 'EL ESQUELETO ARQUERO'],
  ['name', 'EL EXPLOSIVO VERDE'], ['name', 'LA ARANA DE LA NOCHE'], ['name', 'LA DRAGONA DEL FIN'],
  ['gap'],
  ['head', 'MUSICA Y EFECTOS'], ['name', 'SINTETIZADOS CON PYTHON'],
  ['gap'],
  ['head', 'MUNDO'], ['name', 'GENERADO PROCEDURALMENTE BLOQUE A BLOQUE'],
  ['gap'],
  ['small', 'VIDEO DE FANS INSPIRADO EN LOS JUEGOS DE BLOQUES.'],
  ['small', 'SIN AFILIACION CON MOJANG NI MICROSOFT.'],
  ['gap'], ['gap'],
  ['big', 'FIN'],
  ['sub', 'GRACIAS POR JUGAR'],
];
