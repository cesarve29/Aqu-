// Monta cada Short de la cuenta atrás:
//   [gancho: 4 cortes rápidos del tráiler] + [segmento animado del día] + [cierre del canal]
// Audio: SOLO efectos de sonido (el usuario añade la música después). El audio del tráiler se elimina.
// Uso: node componer-cuenta-atras.js <trailer.mp4> [dia ...]
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const { mix } = require('./sfx');

const TRAILER = process.argv[2];
const DAYS = process.argv.slice(3).map(Number);
const LIST = DAYS.length ? DAYS : [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0];
const CUT = 0.55, NCUTS = 4, HOOK = CUT * NCUTS, CIERRE = 2.0;
const ROOT = path.join(__dirname, '..');
// Momentos elegidos del tráiler (segundo de inicio), ordenados por impacto
const MOMENTOS = [1223.1, 721.6, 1567.8, 1086.7, 1043.0, 1275.6, 1116.5, 1082.0, 524.0, 992.2, 1236.3, 1433.0,
  568.0, 1028.0, 719.4, 1073.5, 593.4, 1144.2, 711.4, 1068.0, 800.0, 1151.0, 950.1, 1210.0];

const ff = (args) => execFileSync('ffmpeg', ['-nostdin', '-y', '-loglevel', 'error', ...args]);

function cortesDelDia(day) {
  const k = 12 - day; // día 12 -> 0
  return Array.from({ length: NCUTS }, (_, j) => {
    const idx = (k * NCUTS + j) % MOMENTOS.length;
    const vuelta = Math.floor((k * NCUTS + j) / MOMENTOS.length);
    return MOMENTOS[idx] + vuelta * 1.2; // en la segunda vuelta, otro instante del mismo plano
  });
}

function gancho(day, tmp) {
  const parts = cortesDelDia(day).map((t, j) => {
    const out = path.join(tmp, `g${j}.mp4`);
    // fondo desenfocado + banda central con zoom de impacto + bordes de neón + destello al entrar
    ff(['-ss', String(t), '-t', String(CUT), '-i', TRAILER, '-an', '-filter_complex',
      `[0:v]fps=30,eq=saturation=1.35:contrast=1.08,colorbalance=rs=.10:bs=.12,split[a][b];` +
      `[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:2,eq=brightness=-0.18[bg];` +
      `[b]scale=2133:1200,zoompan=z='1.14-0.14*min(on/${Math.round(CUT * 30)},1)':d=1:s=2133x1200:fps=30,crop=1080:1200[fg];` +
      `[bg][fg]overlay=0:360,drawbox=x=0:y=352:w=1080:h=8:color=0xff3fb4:t=fill,drawbox=x=0:y=1560:w=1080:h=8:color=0x5ef2ff:t=fill,` +
      `fade=in:st=0:d=0.07:color=white,setsar=1,format=yuv420p[v]`,
      '-map', '[v]', '-c:v', 'libx264', '-crf', '18', '-r', '30', out]);
    return out;
  });
  return parts;
}

function sonidosCierre(t0) {
  // mismo ritmo que la animación del cierre: VICE se enciende a los 0,25 s
  return [{ t: t0, fx: 'whoosh', gain: 0.6 }, { t: t0 + 0.05, fx: 'neon', gain: 0.5 }, { t: t0 + 0.25, fx: 'impacto', gain: 0.7 },
    { t: t0 + 0.25, fx: 'neon', gain: 0.4, pan: -0.3 }, { t: t0 + 0.55, fx: 'pop', gain: 0.6 }];
}

for (const day of LIST) {
  const name = `dia-${String(day).padStart(2, '0')}`;
  const seg = path.join(ROOT, 'cuenta-atras', 'segmentos', `${name}.mp4`);
  const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'cuenta-atras', 'segmentos', `${name}.json`)));
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'comp-'));
  const parts = [...gancho(day, tmp), seg, path.join(ROOT, 'intro', 'cierre-shorts-9x16.mp4')];

  // línea de tiempo de sonido
  const ev = [];
  for (let j = 0; j < NCUTS; j++) {
    const t = j * CUT;
    ev.push(j === 0 ? { t: 0, fx: 'impacto', gain: 0.85 } : { t, fx: 'glitch', gain: 0.7, pan: j % 2 ? 0.3 : -0.3 });
    ev.push({ t: Math.max(0, t - 0.12), fx: 'whoosh', args: [0.3], gain: 0.7, pan: j % 2 ? -0.4 : 0.4 });
  }
  for (const e of meta.eventos) ev.push({ ...e, t: e.t + HOOK });
  ev.push(...sonidosCierre(HOOK + meta.dur));
  const total = HOOK + meta.dur + CIERRE;
  const wav = path.join(tmp, 'sfx.wav');
  mix(ev, total, wav);

  const outDir = path.join(ROOT, 'cuenta-atras', 'final');
  fs.mkdirSync(outDir, { recursive: true });
  const inputs = parts.flatMap(p => ['-i', p]);
  const pre = parts.map((_, i) => `[${i}:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[v${i}]`).join(';');
  const cat = parts.map((_, i) => `[v${i}]`).join('') + `concat=n=${parts.length}:v=1:a=0[v]`;
  ff([...inputs, '-i', wav, '-filter_complex', `${pre};${cat}`, '-map', '[v]', '-map', `${parts.length}:a`,
    '-c:v', 'libx264', '-crf', '19', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest',
    '-movflags', '+faststart', path.join(outDir, `cuenta-atras-${name}.mp4`)]);
  fs.rmSync(tmp, { recursive: true });
  console.log('ok', name, total.toFixed(1) + 's');
}
