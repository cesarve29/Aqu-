// Clips largos (1:00-1:20) de vídeos de otros creadores, con subtítulos en español.
// Uso: node clip-largo.js <video.mp4> <config.json>
// config: {
//   salida, titulo: "texto (admite <br>)", credito: "🎥 Vídeo original: IGN",
//   partes: [[ini, fin], ...]          // tramos del vídeo original (s); se unen con un fundido suave
//   subtitulos: [[ini, fin, "texto"]]  // tiempos del vídeo ORIGINAL; se recolocan solos
// }
// Formato 1440x2560: título arriba, vídeo 1440x1080 a resolución nativa (centro del 16:9),
// subtítulos grandes debajo, crédito, y cierre del canal al final (reglas 1, 2, 4, 9).
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const { mezclar } = require('./biblioteca-sfx');

const [SRC, CFG] = process.argv.slice(2);
const cfg = JSON.parse(fs.readFileSync(CFG));
const ROOT = path.join(__dirname, '..');
const W = 1440, H = 2560, VY = 640, VH = 1080, XF = 0.4;
const ff = (args) => execFileSync('ffmpeg', ['-nostdin', '-y', '-loglevel', 'error', ...args]);

async function overlay(file) {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: W / 2, height: H / 2 }, deviceScaleFactor: 2 });
  await p.setContent(`<!doctype html><html><head><meta charset="utf-8">
  <link href="https://fonts.googleapis.com/css2?family=Anton&family=Montserrat:wght@800;900&family=Mr+Dafoe&display=swap" rel="stylesheet">
  <style>*{margin:0;padding:0}body{width:${W / 2}px;height:${H / 2}px;position:relative;background:transparent}
  .marca{position:absolute;left:0;right:0;top:62px;text-align:center;font:900 19px Montserrat,sans-serif;letter-spacing:.28em;color:#e9fdff;
    text-shadow:0 0 6px #34e1ff,0 0 14px #18b8ff,0 2px 4px #000}.marca b{font:50px/0 'Mr Dafoe',cursive;letter-spacing:0;color:#fff;text-shadow:0 0 8px #ff3fb4,0 0 18px #ff2a8a;vertical-align:-4px;margin-left:3px}
  .titulo{position:absolute;left:24px;right:24px;top:110px;height:${VY / 2 - 130}px;display:flex;align-items:center;justify-content:center;text-align:center;
    font:56px/1.05 Anton,sans-serif;color:#fff;-webkit-text-stroke:7px #120626;paint-order:stroke fill;text-shadow:0 0 18px #ff3fb4,0 5px 0 #120626}
  .titulo .a{color:#ffe066}
  .linea{position:absolute;left:0;right:0;height:3px;background:#ff3fb4;box-shadow:0 0 10px #ff3fb4}
  .credito{position:absolute;left:0;right:0;top:${(VY + VH) / 2 + 195}px;text-align:center;font:800 17px Montserrat,sans-serif;color:#fff;opacity:.9;text-shadow:0 1px 4px #000}
  </style></head><body>
  <div class="marca">SEIS EN <b>Vice</b></div>
  <div class="titulo"><div>${cfg.titulo}</div></div>
  <div class="linea" style="top:${VY / 2 - 3}px"></div><div class="linea" style="top:${(VY + VH) / 2}px;background:#5ef2ff;box-shadow:0 0 10px #34e1ff"></div>
  <div class="credito">${cfg.credito || ''}</div></body></html>`, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  await p.screenshot({ path: file, omitBackground: true });
  await b.close();
}

const ts = (x) => { const h = Math.floor(x / 3600), m = Math.floor(x / 60) % 60, s = (x % 60).toFixed(2).padStart(5, '0'); return `${h}:${String(m).padStart(2, '0')}:${s}`; };
function ass(file, subs) {
  // subtítulos debajo del vídeo: Montserrat Black, blanco con borde negro, máx. 2 líneas
  const head = `[Script Info]\nScriptType: v4.00+\nPlayResX: ${W}\nPlayResY: ${H}\nWrapStyle: 0\n\n[V4+ Styles]\n` +
    `Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n` +
    `Style: Sub,Montserrat Black,140,&H00FFFFFF,&H00FFFFFF,&H00260612,&H64000000,0,0,0,0,100,100,0,0,1,11,5,8,50,50,${VY + VH + 40},1\n\n` +
    `[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n`;
  fs.writeFileSync(file, head + subs.map(([a, b, t]) => `Dialogue: 0,${ts(a)},${ts(b)},Sub,,0,0,0,,{\\fad(60,60)}${t.replace(/\n/g, '\\N')}`).join('\n') + '\n');
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'clip-'));
  const png = path.join(tmp, 'ov.png');
  await overlay(png);
  // tramos -> cada uno a su archivo; se unen con fundido
  const partes = cfg.partes.map(([a, b], i) => {
    const out = path.join(tmp, `p${i}.mp4`);
    ff(['-ss', String(a), '-t', String(b - a), '-i', SRC, '-filter_complex',
      `[0:v]fps=30,split[x][y];[x]scale=360:640:force_original_aspect_ratio=increase,crop=360:640,boxblur=10:2,scale=${W}:${H},eq=brightness=-0.2:saturation=1.2[bg];` +
      `[y]crop=1440:1080:240:0,eq=saturation=1.08[v];[bg][v]overlay=0:${VY},setsar=1,format=yuv420p[o];` +
      `[0:a]aresample=48000,aformat=channel_layouts=stereo[ao]`,
      '-map', '[o]', '-map', '[ao]', '-c:v', 'libx264', '-crf', '15', '-preset', 'fast', '-c:a', 'pcm_s16le', out]);
    return out;
  });
  // línea de tiempo de salida y recolocación de subtítulos
  const offs = []; let acc = 0;
  cfg.partes.forEach(([a, b], i) => { offs.push(acc); acc += (b - a) - (i < cfg.partes.length - 1 ? XF : 0); });
  const DUR = acc;
  // frases largas -> se dividen en dos subtítulos seguidos (máx. ~2 líneas en pantalla)
  const MAX = 40, cortos = [];
  for (const [s, e, t] of cfg.subtitulos) {
    if (t.length <= MAX) { cortos.push([s, e, t]); continue; }
    const mid = t.length / 2; let k = -1;
    for (let i = 0; i < t.length; i++) if (t[i] === ' ' && (k < 0 || Math.abs(i - mid) < Math.abs(k - mid))) k = i;
    const f = k / t.length, m = s + (e - s) * f;
    cortos.push([s, m, t.slice(0, k)], [m, e, t.slice(k + 1)]);
  }
  const subs = [];
  for (const [s, e, t] of cortos) {
    cfg.partes.forEach(([a, b], i) => {
      const s2 = Math.max(s, a), e2 = Math.min(e, b);
      if (e2 - s2 > 0.15) subs.push([s2 - a + offs[i], e2 - a + offs[i], t]);
    });
  }
  const assFile = path.join(tmp, 'subs.ass');
  ass(assFile, subs);
  let g = '', fv = '[0:v]', fa = '[0:a]';
  for (let i = 1; i < partes.length; i++) {
    g += `${fv}[${i}:v]xfade=transition=fade:duration=${XF}:offset=${offs[i].toFixed(3)}[v${i}];${fa}[${i}:a]acrossfade=d=${XF}[a${i}];`;
    fv = `[v${i}]`; fa = `[a${i}]`;
  }
  const N = partes.length;
  g += `${fv}[${N}:v]overlay=0:0:shortest=1,ass=${assFile}:fontsdir=${path.join(__dirname, 'fuentes')},format=yuv420p[vc]`;
  const cuerpo = path.join(tmp, 'cuerpo.mp4');
  ff([...partes.flatMap(p => ['-i', p]), '-loop', '1', '-i', png, '-filter_complex', g, '-map', '[vc]', '-map', partes.length === 1 ? '0:a' : fa,
    '-t', String(DUR), '-c:v', 'libx264', '-crf', '15', '-preset', 'fast', '-c:a', 'pcm_s16le', cuerpo]);
  // cierre + efectos suaves solo en el cierre
  const TOTAL = DUR + 2;
  const sfx = path.join(tmp, 'sfx.wav');
  mezclar([{ t: DUR - 0.05, sfx: 'whoosh', gain: 0.6, variante: 3 }, { t: DUR + 0.05, sfx: 'neon', gain: 0.5, variante: 1 },
    { t: DUR + 0.25, sfx: 'impacto', gain: 0.7, variante: 3 }, { t: DUR + 0.55, sfx: 'pop', gain: 0.6, variante: 1 }], TOTAL, sfx);
  const outDir = path.join(ROOT, 'clips', 'final');
  fs.mkdirSync(outDir, { recursive: true });
  const out = path.join(outDir, cfg.salida);
  ff(['-i', cuerpo, '-i', path.join(ROOT, 'intro', 'cierre-shorts-9x16.mp4'), '-i', sfx, '-filter_complex',
    `[0:v]setsar=1[v0];[1:v]fps=30,scale=${W}:${H}:flags=lanczos,setsar=1,format=yuv420p[v1];[v0][v1]concat=n=2:v=1:a=0[v];` +
    `[0:a]afade=out:st=${(DUR - 0.4).toFixed(2)}:d=0.4,apad=whole_dur=${TOTAL}[ca];[2:a]volume=0.3[fx];[ca][fx]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5[a]`,
    '-map', '[v]', '-map', '[a]', '-t', String(TOTAL), '-c:v', 'libx264', '-crf', '17', '-preset', 'slow', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', out]);
  fs.rmSync(tmp, { recursive: true });
  console.log('ok', out, TOTAL.toFixed(1) + 's');
})();
