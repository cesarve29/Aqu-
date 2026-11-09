// Montador de Shorts de clips (vertical 1080x1920) con el estilo de Seis en Vice.
// Uso: node edit-short.js <video_origen> <config.json>
// config: { salida, titulo: [linea1, linea2], transicion, clips: [{ t, dur, texto }] }
//  - El primer clip es el gancho: lleva el título grande encima (sin intro, regla 1).
//  - Cada clip siguiente puede llevar una etiqueta ("texto").
//  - Audio original de los clips + efectos de la biblioteca ../sfx por debajo (reglas 7 y 8).
//  - Termina con el cierre del canal (regla 2).
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const { mezclar } = require('./biblioteca-sfx');

const [SRC, CFG] = process.argv.slice(2);
const cfg = JSON.parse(fs.readFileSync(CFG));
const ROOT = path.join(__dirname, '..');
const CIERRE = path.join(ROOT, 'intro', 'cierre-shorts-9x16.mp4');
const XF = cfg.transicion ?? 0.3, VOL_SFX = 0.3;
const ff = (args) => execFileSync('ffmpeg', ['-nostdin', '-y', '-loglevel', 'error', ...args]);

// --- textos superpuestos (PNG transparentes) ---
const CSS = `@import url('https://fonts.googleapis.com/css2?family=Anton&family=Montserrat:wght@800;900&family=Mr+Dafoe&display=swap');
*{margin:0;padding:0;box-sizing:border-box}body{width:1080px;height:1920px;position:relative;background:transparent}
.titulo{position:absolute;left:0;right:0;top:230px;text-align:center;font:150px/1 Anton,sans-serif;color:#fff;letter-spacing:.02em;
  -webkit-text-stroke:14px #120626;paint-order:stroke fill;text-shadow:0 0 30px #ff3fb4,0 10px 0 #120626}
.titulo .b{color:#ffe066}
.etq{position:absolute;left:0;right:0;top:1380px;text-align:center}
.etq span{display:inline-block;font:900 58px Montserrat,sans-serif;letter-spacing:.04em;color:#120626;background:#ffe066;
  padding:16px 34px;border-radius:16px;box-shadow:0 0 34px #ff3fb4aa,0 8px 0 #120626}
.marca{position:absolute;left:0;right:0;top:120px;text-align:center;font:900 34px Montserrat,sans-serif;letter-spacing:.28em;color:#e9fdff;
  text-shadow:0 0 8px #34e1ff,0 0 20px #18b8ff,0 3px 6px #000}
.marca b{font:86px/0 'Mr Dafoe',cursive;letter-spacing:0;color:#fff;text-shadow:0 0 10px #ff3fb4,0 0 26px #ff2a8a;vertical-align:-6px;margin-left:4px}`;
async function pngs(tmp) {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  const shot = async (html, file) => {
    await p.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${html}</body></html>`, { waitUntil: 'networkidle' });
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: file, omitBackground: true });
    return file;
  };
  const out = { marca: await shot(`<div class="marca">SEIS EN <b>Vice</b></div>`, path.join(tmp, 'marca.png')) };
  out.titulo = await shot(`<div class="titulo">${cfg.titulo[0]}<br><span class="b">${cfg.titulo[1] || ''}</span></div>`, path.join(tmp, 'titulo.png'));
  out.etq = [];
  for (const [i, c] of cfg.clips.entries()) out.etq.push(c.texto ? await shot(`<div class="etq"><span>${c.texto}</span></div>`, path.join(tmp, `e${i}.png`)) : null);
  await b.close();
  return out;
}

// --- cada clip: fondo desenfocado + vídeo grande fundido, zoom lento, audio original ---
function clip(c, i, tmp, mask) {
  const out = path.join(tmp, `c${i}.mp4`), n = Math.round(c.dur * 30);
  ff(['-ss', String(c.t), '-t', String(c.dur), '-i', SRC, '-loop', '1', '-i', mask, '-filter_complex',
    `[0:v]fps=30,eq=saturation=1.25:contrast=1.05,split[a][b];` +
    `[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:2,eq=brightness=-0.12[bg];` +
    `[b]scale=2667:1500,zoompan=z='1+0.05*on/${n}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=2667x1500:fps=30,crop=1080:1500,format=rgba[fg0];` +
    `[1:v]format=gray,scale=1080:1500[m];[fg0][m]alphamerge[fg];[bg][fg]overlay=0:210:shortest=1,setsar=1,format=yuv420p[v];` +
    `[0:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur=${c.dur}[a0]`,
    '-map', '[v]', '-map', '[a0]', '-t', String(c.dur), '-c:v', 'libx264', '-crf', '17', '-r', '30', '-c:a', 'pcm_s16le', out]);
  return out;
}

(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'edit-'));
  const mask = path.join(tmp, 'mask.png');
  ff(['-f', 'lavfi', '-i', 'color=white:s=1080x1500', '-frames:v', '1', '-vf', "format=gray,geq=lum='255*min(1,min(Y/170,(H-1-Y)/170))'", mask]);
  const img = await pngs(tmp);
  const files = cfg.clips.map((c, i) => clip(c, i, tmp, mask));

  // inicio de cada clip en la línea de tiempo (con fundidos encadenados)
  const starts = []; let acc = 0;
  cfg.clips.forEach((c, i) => { starts.push(acc); acc += c.dur - (i < cfg.clips.length - 1 ? XF : 0); });
  const DUR_CLIPS = acc, TOTAL = DUR_CLIPS + 2.0;

  // cadena de fundidos (vídeo xfade + audio acrossfade)
  let fv = '[0:v]', fa = '[0:a]', g = '';
  for (let i = 1; i < files.length; i++) {
    g += `${fv}[${i}:v]xfade=transition=fade:duration=${XF}:offset=${(starts[i]).toFixed(3)}[v${i}];`;
    g += `${fa}[${i}:a]acrossfade=d=${XF}[a${i}];`;
    fv = `[v${i}]`; fa = `[a${i}]`;
  }
  // textos superpuestos
  const N = files.length; let k = N; let over = fv;
  const inputsImg = [];
  const addImg = (file, t0, t1) => { inputsImg.push(file); const idx = k++; const o = `[o${idx}]`;
    g += `${over}[${idx}:v]overlay=0:0:enable='between(t,${t0.toFixed(2)},${t1.toFixed(2)})'${o};`; over = o; };
  addImg(img.marca, 0, DUR_CLIPS);
  addImg(img.titulo, 0, cfg.clips[0].dur - XF);
  cfg.clips.forEach((c, i) => { if (img.etq[i]) addImg(img.etq[i], starts[i] + 0.15, starts[i] + c.dur - XF); });
  g += `${over}format=yuv420p[vc]`;
  const cuerpo = path.join(tmp, 'cuerpo.mp4');
  ff([...files.flatMap(f => ['-i', f]), ...inputsImg.flatMap(f => ['-i', f]), '-filter_complex', g,
    '-map', '[vc]', '-map', fa, '-c:v', 'libx264', '-crf', '18', '-r', '30', '-c:a', 'pcm_s16le', cuerpo]);

  // efectos de sonido por debajo
  const ev = [{ t: 0, sfx: 'impacto', gain: 0.9 }, { t: 0.05, sfx: 'whoosh', gain: 0.5 }];
  cfg.clips.forEach((c, i) => {
    if (i > 0) ev.push({ t: starts[i] - 0.15, sfx: 'whoosh', gain: 0.7, pan: i % 2 ? 0.3 : -0.3, variante: i });
    if (img.etq[i]) ev.push({ t: starts[i] + 0.15, sfx: 'pop', gain: 0.6, variante: i });
  });
  ev.push({ t: DUR_CLIPS - 0.05, sfx: 'whoosh', gain: 0.6, variante: 3 }, { t: DUR_CLIPS + 0.05, sfx: 'neon', gain: 0.5, variante: 1 },
    { t: DUR_CLIPS + 0.25, sfx: 'impacto', gain: 0.7, variante: 3 }, { t: DUR_CLIPS + 0.55, sfx: 'pop', gain: 0.6, variante: 1 });
  const sfx = path.join(tmp, 'sfx.wav');
  mezclar(ev, TOTAL, sfx);

  const outDir = path.join(ROOT, 'edits', 'final');
  fs.mkdirSync(outDir, { recursive: true });
  const out = path.join(outDir, cfg.salida);
  ff(['-i', cuerpo, '-i', CIERRE, '-i', sfx, '-filter_complex',
    `[0:v]setsar=1[v0];[1:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[v1];[v0][v1]concat=n=2:v=1:a=0[v];` +
    `[0:a]apad=whole_dur=${TOTAL}[ca];[2:a]volume=${VOL_SFX}[fx];[ca][fx]amix=inputs=2:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11[a]`,
    '-map', '[v]', '-map', '[a]', '-t', String(TOTAL), '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', out]);
  fs.rmSync(tmp, { recursive: true });
  console.log('ok', out, TOTAL.toFixed(1) + 's');
})();
