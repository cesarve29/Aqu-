// Meme vertical partido (1440x2560): arriba una toma del tráiler (cámara lenta en ida y vuelta), abajo otro vídeo.
// Uso: node meme.js <trailer.mp4> <video_abajo.mp4|-> <config.json>
//   Si "abajo" tiene { t, dur } en la config, la parte de abajo también sale del tráiler (pasa "-" como vídeo).
// Audio: el del vídeo de abajo, o el de la toma indicada en "audio" (en bucle). Sin intro; termina con el cierre.
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const { mezclar } = require('./biblioteca-sfx');

const [TRAILER, ABAJO, CFG] = process.argv.slice(2);
const cfg = JSON.parse(fs.readFileSync(CFG));
const ROOT = path.join(__dirname, '..');
const W = 1440, H = 2560;
// Distribución: texto 1 (220) + panel de arriba (860) | texto 2 (200) + panel de abajo (1280, más grande para el vídeo)
const T1 = 220, P1 = 860, T2 = 200, Y2 = T1 + P1, P2 = H - Y2 - T2;
const ff = (args) => execFileSync('ffmpeg', ['-nostdin', '-y', '-loglevel', 'error', ...args]);
const dur = cfg.duracion || parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ABAJO]).toString());

async function overlay(file) {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: W / 2, height: H / 2 }, deviceScaleFactor: 2 }); // se dibuja a la mitad
  const caja = (top, h, txt) => `<div style="position:absolute;left:0;right:0;top:${top}px;height:${h}px;display:flex;align-items:center;justify-content:center;text-align:center;
    font:900 46px/1.1 Montserrat,sans-serif;color:#fff;-webkit-text-stroke:7px #000;paint-order:stroke fill;padding:0 30px">${txt}</div>`;
  await p.setContent(`<!doctype html><html><head><meta charset="utf-8">
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@900&family=Mr+Dafoe&display=swap" rel="stylesheet">
  <style>*{margin:0;padding:0}body{width:${W / 2}px;height:${H / 2}px;position:relative;background:transparent}
  .marca{position:absolute;right:16px;top:${Y2 / 2 - 34}px;font:900 15px Montserrat,sans-serif;letter-spacing:.25em;color:#e9fdff;
    text-shadow:0 0 6px #34e1ff,0 2px 4px #000}.marca b{font:40px/0 'Mr Dafoe',cursive;letter-spacing:0;color:#fff;text-shadow:0 0 8px #ff3fb4}</style></head><body>
  ${caja(0, T1 / 2, cfg.arriba.texto)}${caja(Y2 / 2, T2 / 2, cfg.abajo.texto)}
  <div style="position:absolute;left:0;right:0;top:${Y2 / 2 - 2}px;height:4px;background:#ff3fb4;box-shadow:0 0 12px #ff3fb4"></div>
  <div class="marca">SEIS EN <b>Vice</b></div></body></html>`, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  await p.screenshot({ path: file, omitBackground: true });
  await b.close();
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'meme-'));
  const png = path.join(tmp, 'txt.png');
  await overlay(png);
  // toma del tráiler: cámara lenta + ida y vuelta, repetida hasta cubrir la duración
  const toma = (T, nombre) => {
    const ida = path.join(tmp, `${nombre}-ida.mp4`), vuelta = path.join(tmp, `${nombre}-vuelta.mp4`);
    const [rx, rw] = T.recorte || [T.recorte_x ?? 0, 836];
    ff(['-ss', String(T.t), '-t', String(T.dur), '-i', TRAILER, '-an', '-vf',
      `crop=${rw}:720:${rx}:0,hqdn3d=2:1.5:4:3,setpts=PTS/${T.velocidad || 1},minterpolate=fps=30:mi_mode=blend,` +
      `scale=${W}:-2:flags=lanczos,unsharp=5:5:0.7,eq=saturation=1.15`, '-c:v', 'libx264', '-crf', '14', ida]);
    ff(['-i', ida, '-vf', 'reverse', '-c:v', 'libx264', '-crf', '14', vuelta]);
    const lista = path.join(tmp, `${nombre}.txt`);
    fs.writeFileSync(lista, Array.from({ length: 12 }, (_, i) => `file '${i % 2 ? vuelta : ida}'`).join('\n'));
    const out = path.join(tmp, `${nombre}.mp4`);
    ff(['-f', 'concat', '-safe', '0', '-i', lista, '-t', String(dur), '-c:v', 'libx264', '-crf', '14', out]);
    return out;
  };
  const top = toma(cfg.arriba, 'arriba');
  let abajo = ABAJO;
  if (cfg.abajo.t !== undefined) {
    // vídeo de abajo sacado del tráiler + audio de la toma indicada (en bucle)
    const v = toma(cfg.abajo, 'abajo');
    const au = cfg.audio || cfg.abajo;
    abajo = path.join(tmp, 'abajo-con-audio.mp4');
    ff(['-i', v, '-ss', String(au.t), '-t', String(au.dur), '-i', TRAILER, '-filter_complex',
      `[1:a]aresample=48000,aformat=channel_layouts=stereo,afade=in:d=0.05,afade=out:st=${au.dur - 0.15}:d=0.15,aloop=loop=20:size=${Math.round(au.dur * 48000)},atrim=0:${dur}[a]`,
      '-map', '0:v', '-map', '[a]', '-t', String(dur), '-c:v', 'copy', '-c:a', 'pcm_s16le', abajo]);
  }

  const cuerpo = path.join(tmp, 'cuerpo.mp4');
  ff(['-i', top, '-i', abajo, '-loop', '1', '-i', png, '-filter_complex',
    // panel de arriba: Lucía recortada al panel; fondo morado de marca
    `color=c=0x120626:s=${W}x${H}:r=30:d=${dur}[base];` +
    `[0:v]scale=${W}:${P1}:force_original_aspect_ratio=increase,crop=${W}:${P1}[t];` +
    // panel de abajo: vídeo completo en el centro con fondo desenfocado a los lados
    // panel de abajo: vídeo ampliado a 1100 px de ancho (recortando un poco de los pies), fondo desenfocado a los lados
    `[1:v]fps=30,split[x][y];[x]scale=${W}:${P2}:force_original_aspect_ratio=increase,crop=${W}:${P2},boxblur=30:2,eq=brightness=-0.15[bb];` +
    (cfg.abajo.t !== undefined
      ? `[y]scale=${W}:${P2}:force_original_aspect_ratio=increase,crop=${W}:${P2}[bf];[bb][bf]overlay=0:0[b];`
      : `[y]scale=1100:-2:flags=lanczos,crop=1100:${P2}:0:110,unsharp=5:5:0.5[bf];[bb][bf]overlay=(W-w)/2:0[b];`) +
    `[base][t]overlay=0:${T1}[s1];[s1][b]overlay=0:${Y2 + T2}[s2];[s2][2:v]overlay=0:0:shortest=1,format=yuv420p[v]`,
    '-map', '[v]', '-map', '1:a', '-t', String(dur), '-c:v', 'libx264', '-crf', '14', '-r', '30', '-c:a', 'pcm_s16le', '-ar', '48000', cuerpo]);

  const TOTAL = dur + 2;
  const sfx = path.join(tmp, 'sfx.wav');
  mezclar([{ t: dur - 0.05, sfx: 'whoosh', gain: 0.6, variante: 3 }, { t: dur + 0.05, sfx: 'neon', gain: 0.5, variante: 1 },
    { t: dur + 0.25, sfx: 'impacto', gain: 0.7, variante: 3 }, { t: dur + 0.55, sfx: 'pop', gain: 0.6, variante: 1 }], TOTAL, sfx);
  const outDir = path.join(ROOT, 'memes', 'final');
  fs.mkdirSync(outDir, { recursive: true });
  const out = path.join(outDir, cfg.salida);
  ff(['-i', cuerpo, '-i', path.join(ROOT, 'intro', 'cierre-shorts-9x16.mp4'), '-i', sfx, '-filter_complex',
    `[0:v]setsar=1[v0];[1:v]fps=30,scale=${W}:${H}:flags=lanczos,setsar=1,format=yuv420p[v1];[v0][v1]concat=n=2:v=1:a=0[v];` +
    `[0:a]apad=whole_dur=${TOTAL}[ca];[2:a]volume=0.3[fx];[ca][fx]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5[a]`,
    '-map', '[v]', '-map', '[a]', '-t', String(TOTAL), '-c:v', 'libx264', '-crf', '16', '-preset', 'slow', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', out]);
  fs.rmSync(tmp, { recursive: true });
  console.log('ok', out, TOTAL.toFixed(1) + 's');
})();
