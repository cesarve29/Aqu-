// Monta cada Short de la cuenta atrás (16 s, vertical 1080x1920):
//   0-4,8 s     gancho: 3 cortes de 1,6 s del tráiler (lo más fuerte primero)
//   4,8-10,8 s  número del día con reloj de neón
//   10,8-14 s   2 cortes más de 1,6 s
//   14-16 s     cierre "SUSCRÍBETE @SeisEnVice"
// Audio: audio original de cada corte del tráiler + efectos de la biblioteca (../sfx) a volumen moderado.
// La música la pone el usuario encima.
// Uso: node componer-cuenta-atras.js <trailer.mp4> [dia ...]
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const { mezclar } = require('./biblioteca-sfx');

const TRAILER = process.argv[2];
const DAYS = process.argv.slice(3).map(Number);
const LIST = DAYS.length ? DAYS : [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0];
const ROOT = path.join(__dirname, '..');
// Formato por día: hasta el día 10, cortes rápidos (0,8 s); desde el día 9, cortes largos (1,6 s) y transiciones suaves
const FORMATOS = {
  rapido: { gancho: { n: 5, dur: 0.8 }, puente: { n: 4, dur: 0.75 }, zoom: 0.12, entrada: 'fade=in:st=0:d=0.06:color=white' },
  largo: { gancho: { n: 3, dur: 1.6 }, puente: { n: 2, dur: 1.6 }, zoom: 0.06, entrada: 'fade=in:st=0:d=0.12:color=black' },
};
let GANCHO, PUENTE, T_CUENTA, T_PUENTE, T_CIERRE, TOTAL, POR_DIA, F;
const SEG = 6.0;
function usarFormato(day) {
  F = day >= 10 ? FORMATOS.rapido : FORMATOS.largo;
  GANCHO = F.gancho; PUENTE = F.puente;
  T_CUENTA = GANCHO.n * GANCHO.dur; T_PUENTE = T_CUENTA + SEG; T_CIERRE = T_PUENTE + PUENTE.n * PUENTE.dur; TOTAL = T_CIERRE + 2.0;
  POR_DIA = GANCHO.n + PUENTE.n;
}
// Momentos elegidos del tráiler (segundo de inicio), ordenados por impacto
const MOMENTOS = [1223.1, 1126.1, 721.6, 1567.8, 1086.7, 1065.0, 1043.0, 1275.6, 543.5, 1116.5, 832.8, 1045.5, 1082.0, 524.0,
  992.2, 1569.0, 1236.3, 1433.0, 769.4, 371.3, 1030.5, 1553.0, 568.0, 1028.0, 552.2, 1109.3, 719.4, 1160.5, 1073.5, 732.3,
  593.4, 468.1, 1144.2, 1050.4, 711.4, 1068.0, 545.0, 1573.9, 800.0, 1151.0, 1172.3, 950.1, 570.0, 1210.0];
const ff = (args) => execFileSync('ffmpeg', ['-nostdin', '-y', '-loglevel', 'error', ...args]);

// Cambios de plano del tráiler (detectados con ffmpeg scdet) para que ningún corte cruce un cambio de cámara
const PLANOS = JSON.parse(fs.readFileSync(path.join(__dirname, 'cambios-de-plano.json')));
function encajar(t, dur) {
  let a = 0, b = Infinity;
  for (const c of PLANOS) { if (c <= t) a = c; else { b = c; break; } }
  if (t + dur > b - 0.05) t = Math.max(a + 0.05, b - 0.05 - dur);
  return Math.round(t * 100) / 100;
}
function momentos(day) {
  const k = 12 - day;
  return Array.from({ length: POR_DIA }, (_, j) => {
    // formato largo: continúa después de los 27 momentos usados en los días 12-10
    const i = day >= 10 ? k * POR_DIA + j : 27 + (9 - day) * POR_DIA + j;
    const t = MOMENTOS[i % MOMENTOS.length] + Math.floor(i / MOMENTOS.length) * 1.3; // en otra vuelta, otro instante del plano
    if (day >= 10) return t; // formato rápido: igual que los vídeos ya entregados
    return encajar(t, j < GANCHO.n ? GANCHO.dur : PUENTE.dur);
  });
}

// Máscara con bordes difuminados para fundir el vídeo con el fondo (sin líneas)
function mascara(tmp) {
  const m = path.join(tmp, 'mask.png');
  ff(['-f', 'lavfi', '-i', 'color=white:s=1080x1500', '-frames:v', '1', '-vf',
    "format=gray,geq=lum='255*min(1,min(Y/170,(H-1-Y)/170))'", m]);
  return m;
}

const VOL_SFX = 0.32;   // efectos claramente por debajo del audio de los clips
const VOL_CLIP = 1.0;

function audioCorte(t, dur, out) {
  ff(['-ss', String(t), '-t', String(dur), '-i', TRAILER, '-vn', '-af',
    `aresample=48000,aformat=channel_layouts=stereo,afade=in:st=0:d=0.03,afade=out:st=${(dur - 0.05).toFixed(2)}:d=0.05,apad=whole_dur=${dur}`,
    '-t', String(dur), '-c:a', 'pcm_s16le', out]);
  return out;
}
function silencio(dur, out) {
  ff(['-f', 'lavfi', '-i', `anullsrc=r=48000:cl=stereo`, '-t', String(dur), '-c:a', 'pcm_s16le', out]);
  return out;
}

function corte(t, dur, out, mask) {
  ff(['-ss', String(t), '-t', String(dur), '-i', TRAILER, '-loop', '1', '-i', mask, '-an', '-filter_complex',
    `[0:v]fps=30,eq=saturation=1.3:contrast=1.06,colorbalance=rs=.06:bs=.08,split[a][b];` +
    `[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:2,eq=brightness=-0.12[bg];` +
    `[b]scale=2667:1500,zoompan=z='${1 + F.zoom}-${F.zoom}*min(on/${Math.round(dur * 30)},1)':d=1:s=2667x1500:fps=30,crop=1080:1500,format=rgba[fg0];` +
    `[1:v]format=gray,scale=1080:1500[m];[fg0][m]alphamerge[fg];` +
    `[bg][fg]overlay=0:210:shortest=1,${F.entrada},setsar=1,format=yuv420p[v]`,
    '-map', '[v]', '-t', String(dur), '-c:v', 'libx264', '-crf', '17', '-r', '30', out]);
  return out;
}

function sonidos() {
  const ev = [];
  for (let j = 0; j < GANCHO.n; j++) {
    const t = j * GANCHO.dur;
    if (j === 0) ev.push({ t: 0, sfx: 'impacto', gain: 1 }, { t: 0, sfx: 'whoosh', gain: 0.5 });
    else ev.push({ t: t - 0.08, sfx: 'whoosh', gain: 0.65, pan: j % 2 ? 0.35 : -0.35, variante: j }, { t, sfx: 'glitch', gain: 0.45, variante: j });
  }
  // cuenta atrás (tiempos de cuenta-atras.js)
  const C = T_CUENTA;
  ev.push({ t: C, sfx: 'braam', gain: 0.9 }, { t: C, sfx: 'impacto', gain: 0.7, variante: 1 }, { t: C + 0.05, sfx: 'neon', gain: 0.45 },
    { t: C + 1.0, sfx: 'whoosh', gain: 0.55, variante: 2 }, { t: C + 1.6, sfx: 'pop', gain: 0.6 });
  for (let i = 0; i < 8; i++) ev.push({ t: C + 0.6 + i * 0.5, sfx: 'tic', gain: 0.7, pan: i % 2 ? 0.2 : -0.2, variante: i });
  ev.push({ t: C + 4.85, sfx: 'subida', gain: 0.6, alFinal: true }, { t: C + 4.85, sfx: 'impacto', gain: 0.85, variante: 2 },
    { t: C + 4.85, sfx: 'stinger', gain: 0.7 });
  for (let j = 0; j < PUENTE.n; j++) {
    const t = T_PUENTE + j * PUENTE.dur;
    ev.push({ t: t - 0.08, sfx: 'whoosh', gain: 0.6, pan: j % 2 ? -0.35 : 0.35, variante: j + 1 });
    if (j % 2 === 0) ev.push({ t, sfx: 'glitch', gain: 0.4, variante: j + 2 });
  }
  ev.push({ t: T_CIERRE - 0.05, sfx: 'whoosh', gain: 0.5, variante: 3 }, { t: T_CIERRE + 0.05, sfx: 'neon', gain: 0.45, variante: 1 },
    { t: T_CIERRE + 0.25, sfx: 'impacto', gain: 0.6, variante: 3 }, { t: T_CIERRE + 0.55, sfx: 'pop', gain: 0.6, variante: 1 });
  return ev;
}

for (const day of LIST) {
  usarFormato(day);
  const name = `dia-${String(day).padStart(2, '0')}`;
  const seg = path.join(ROOT, 'cuenta-atras', 'segmentos', `${name}.mp4`);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'comp-'));
  const mask = mascara(tmp);
  const ts = momentos(day);
  const gancho = ts.slice(0, GANCHO.n).map((t, j) => corte(t, GANCHO.dur, path.join(tmp, `g${j}.mp4`), mask));
  const puente = ts.slice(GANCHO.n).map((t, j) => corte(t, PUENTE.dur, path.join(tmp, `p${j}.mp4`), mask));
  const parts = [...gancho, seg, ...puente, path.join(ROOT, 'intro', 'cierre-shorts-9x16.mp4')];
  const sfx = path.join(tmp, 'sfx.wav');
  mezclar(sonidos(), TOTAL, sfx);
  // pista con el audio original de los cortes (silencio durante la cuenta atrás y el cierre)
  const pistas = [
    ...ts.slice(0, GANCHO.n).map((t, j) => audioCorte(t, GANCHO.dur, path.join(tmp, `ag${j}.wav`))),
    silencio(SEG, path.join(tmp, 's1.wav')),
    ...ts.slice(GANCHO.n).map((t, j) => audioCorte(t, PUENTE.dur, path.join(tmp, `ap${j}.wav`))),
    silencio(TOTAL - T_CIERRE, path.join(tmp, 's2.wav'))];
  const wav = path.join(tmp, 'mezcla.wav');
  ff([...pistas.flatMap(p => ['-i', p]), '-i', sfx, '-filter_complex',
    `${pistas.map((_, i) => `[${i}:a]`).join('')}concat=n=${pistas.length}:v=0:a=1,volume=${VOL_CLIP}[clip];` +
    `[${pistas.length}:a]volume=${VOL_SFX}[fx];[clip][fx]amix=inputs=2:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11[a]`,
    '-map', '[a]', '-ar', '48000', '-t', String(TOTAL), wav]);
  const outDir = path.join(ROOT, 'cuenta-atras', 'final');
  fs.mkdirSync(outDir, { recursive: true });
  const pre = parts.map((_, i) => `[${i}:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[v${i}]`).join(';');
  const cat = parts.map((_, i) => `[v${i}]`).join('') + `concat=n=${parts.length}:v=1:a=0[v]`;
  ff([...parts.flatMap(p => ['-i', p]), '-i', wav, '-filter_complex', `${pre};${cat}`, '-map', '[v]', '-map', `${parts.length}:a`,
    '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-t', String(TOTAL),
    '-movflags', '+faststart', path.join(outDir, `cuenta-atras-${name}.mp4`)]);
  fs.rmSync(tmp, { recursive: true });
  console.log('ok', name, TOTAL.toFixed(1) + 's');
}
