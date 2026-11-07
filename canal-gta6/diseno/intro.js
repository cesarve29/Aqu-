// Genera la animación de logo del canal (intro) en horizontal y vertical.
// Uso: node intro.js   -> ../intro/intro-logo-16x9.mp4 y ../intro/intro-logo-9x16.mp4
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const { scene, css, NAME_A, NAME_B, TAG } = require('./render');

const FPS = 30;
const clamp = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => 1 - Math.pow(1 - clamp(x), 3);
// Parpadeo de neón: se enciende con fallos y queda fijo
const flicker = (t, start) => {
  const d = t - start;
  if (d < 0) return 0;
  const pattern = [1, 0, 1, 1, 0, 0, 1, 0.3, 1];
  const i = Math.floor(d / 0.045);
  return i < pattern.length ? pattern[i] : 1;
};

function frame(W, H, t, dur, vertical, outro) {
  const hy = vertical ? H * 0.6 : H * 0.6;
  const r = vertical ? 330 : 260;
  const rise = outro ? 0 : (1 - ease(t / 1.2)) * r * 1.6;
  const fadeIn = ease(t / (outro ? 0.12 : 0.4));
  const fadeOut = clamp((t - (dur - 0.35)) / 0.35);
  const a = flicker(t, outro ? 0.05 : 0.7), b = flicker(t, outro ? 0.25 : 1.15);
  const scale = 1 + 0.12 * (1 - ease((t - 0.7) / 0.8));
  const tag = ease((t - (outro ? 0.55 : 1.7)) / 0.3);
  const flash = Math.max(0, 1 - Math.abs(t - (outro ? 0.25 : 1.15)) / 0.12) * 0.5;
  const palms = vertical
    ? [{ x: -80, y: hy - 520, s: 1.3 }, { x: 820, y: hy - 440, s: 1.1, flip: 1 }]
    : [{ x: 120, y: hy - 520, s: 1.3 }, { x: 1560, y: hy - 470, s: 1.15, flip: 1 }];
  const s = scene(W, H, { horizon: hy, sunR: r, sunX: W / 2, sunRise: rise, gridOff: t * 2.2, palms });
  const titleSize = vertical ? 230 : 190;
  const nameHtml = vertical
    ? `<span class="neon-pink" style="opacity:${a}">${NAME_A}</span><br><span class="neon-cyan" style="opacity:${b}">${NAME_B}</span>`
    : `<span class="neon-pink" style="opacity:${a}">${NAME_A}</span> <span class="neon-cyan" style="opacity:${b}">${NAME_B}</span>`;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${css}
  body{width:${W}px;height:${H}px;position:relative}</style></head><body>
  <div style="position:absolute;inset:0;opacity:${fadeIn}">${s}</div>
  <div style="position:absolute;left:0;right:0;top:${vertical ? H * 0.2 : H * 0.28}px;text-align:center">
    <div class="title" style="font-size:${titleSize}px;transform:scale(${scale})">${nameHtml}</div>
    <div class="sub" style="font-size:${vertical ? 46 : 38}px;margin-top:${vertical ? 40 : 26}px;letter-spacing:.08em;opacity:${tag};transform:translateY(${(1 - tag) * 30}px);text-shadow:0 3px 12px #000a;padding:0 40px">${outro ? `<span style="display:inline-block;background:#ff2a8a;padding:18px 44px;border-radius:999px;box-shadow:0 0 30px #ff3fb4">SUSCRÍBETE 🔔</span><div style="margin-top:26px">@SeisEnVice</div>` : vertical ? TAG.replace(/ EN MENOS/, '<br>EN MENOS') : TAG}</div>
  </div>
  <div style="position:absolute;inset:0;background:#fff;opacity:${flash}"></div>
  <div style="position:absolute;inset:0;background:#000;opacity:${fadeOut}"></div>
  </body></html>`;
}

// Música: arpegio synthwave + golpe de bajo, sintetizado aquí mismo (sin derechos de terceros)
function audio(out, dur, offset = 0) {
  const SR = 48000, n = Math.round(SR * dur);
  const notes = [220, 277.18, 329.63, 440, 329.63, 277.18, 220, 277.18, 329.63, 440, 554.37, 659.25];
  const step = 0.1;
  const L = new Float32Array(n), R = new Float32Array(n);
  let seed = 1; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;
  for (let i = 0; i < n; i++) {
    const t = i / SR + offset, lt = i / SR; let v = 0;
    const k = Math.floor(t / step);
    if (k < notes.length) { const tt = t - k * step; const f = notes[k];
      v += 0.28 * Math.exp(-10 * tt) * (Math.sin(2 * Math.PI * f * t) + 0.5 * Math.sign(Math.sin(2 * Math.PI * f * 1.005 * t)) * 0.4); }
    if (t >= 1.15) { const d = t - 1.15;
      v += 0.7 * Math.exp(-2.5 * d) * Math.sin(2 * Math.PI * (55 + 60 * Math.exp(-20 * d)) * d);   // golpe de bajo
      v += 0.16 * Math.exp(-1.0 * d) * (Math.sin(2 * Math.PI * 220 * t) + Math.sin(2 * Math.PI * 277.18 * t) + Math.sin(2 * Math.PI * 329.63 * t)) / 3 * 1.5; } // acorde pad
    v += 0.25 * rnd() * (Math.exp(-40 * Math.abs(t - 0.7)) + Math.exp(-40 * Math.abs(t - 1.15)));  // chispazos de neón
    const fade = Math.min(1, (dur - lt) / 0.4, lt / 0.02);
    L[i] = v * fade; R[i] = v * fade;
  }
  // eco estéreo
  const dl = Math.round(SR * 0.18);
  for (let i = dl; i < n; i++) { L[i] += 0.35 * R[i - dl]; R[i] += 0.3 * L[i - dl]; }
  const buf = Buffer.alloc(44 + n * 4);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 4, 4); buf.write('WAVEfmt ', 8);
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24);
  buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 4, 40);
  let peak = 0; for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
  const g = 0.89 / peak;
  for (let i = 0; i < n; i++) { buf.writeInt16LE(Math.round(L[i] * g * 32767), 44 + i * 4); buf.writeInt16LE(Math.round(R[i] * g * 32767), 46 + i * 4); }
  fs.writeFileSync(out, buf);
}

async function render(name, W, H, dur, vertical, outro = false) {
  const outDir = path.join(__dirname, '..', 'intro');
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'intro-'));
  const browser = await chromium.launch();
  const p = await browser.newPage({ viewport: { width: W, height: H } });
  const n = Math.round(dur * FPS);
  for (let i = 0; i < n; i++) {
    await p.setContent(frame(W, H, i / FPS, dur, vertical, outro), { waitUntil: i === 0 ? 'networkidle' : 'load' });
    if (i === 0) await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(tmp, `f${String(i).padStart(4, '0')}.png`) });
  }
  await browser.close();
  const wav = path.join(tmp, 'a.wav');
  audio(wav, dur, outro ? 0.9 : 0);
  fs.mkdirSync(outDir, { recursive: true });
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(tmp, 'f%04d.png'), '-i', wav,
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-shortest', path.join(outDir, name)]);
  fs.rmSync(tmp, { recursive: true });
  console.log('ok', name);
}

(async () => {
  await render('intro-logo-16x9.mp4', 1920, 1080, 3.2, false);
  await render('intro-logo-9x16.mp4', 1080, 1920, 3.0, true);
  // Cierre para Shorts (va SIEMPRE al final, nunca al principio)
  await render('cierre-shorts-9x16.mp4', 1080, 1920, 2.0, true, true);
})();
