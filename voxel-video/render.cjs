#!/usr/bin/env node
// Renderiza el video fotograma a fotograma en Chromium headless (WebGL por SwiftShader)
// y lo envia a ffmpeg.
//   node render.js --stills 5 30 120          -> stills/t_XXX.jpg
//   node render.js --from 0 --to 60 --out segments/a.mp4 [--fps 24]
//   node render.js --events                   -> events.json (para la banda sonora)
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const { spawn } = require('child_process');

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const W = +opt('w', 1920), H = +opt('h', 1080), FPS = +opt('fps', 24);
const ROOT = __dirname;
const TYPES = { '.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json' };

function serve() {
  return new Promise((res) => {
    const srv = http.createServer((q, s) => {
      const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
      if (!f.startsWith(ROOT)) { s.writeHead(403); return s.end(); }
      fs.readFile(f, (e, d) => {
        if (e) { s.writeHead(404); return s.end(); }
        s.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
        s.end(d);
      });
    });
    srv.listen(0, () => res(srv));
  });
}

(async () => {
  const srv = await serve();
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto(`http://localhost:${srv.address().port}/index.html?w=${W}&h=${H}`);
  await page.waitForFunction('window.ready === true', null, { timeout: 300000 });
  const dec = (u) => Buffer.from(u.slice(u.indexOf(',') + 1), 'base64');

  if (args.includes('--events')) {
    const ev = await page.evaluate('window.EVENTS');
    fs.writeFileSync(path.join(ROOT, 'events.json'), JSON.stringify(ev));
    console.log('events:', ev.length);
  } else if (args.includes('--stills')) {
    const ts = args.slice(args.indexOf('--stills') + 1).filter((a, i, arr) => !a.startsWith('--') && !isNaN(+a) && arr[i - 1] !== '--w' && arr[i - 1] !== '--h');
    fs.mkdirSync(path.join(ROOT, 'stills'), { recursive: true });
    const dc = opt('debugcam');
    if (dc) await page.evaluate((v) => { window.DEBUGCAM = v; }, dc.split(',').map(Number));
    for (const t of ts) {
      const t0 = Date.now();
      const d = await page.evaluate((tt) => window.grab(tt, 0.9), +t);
      const f = path.join(ROOT, 'stills', `t_${String(t).padStart(6, '0')}.jpg`);
      fs.writeFileSync(f, dec(d));
      console.log(f, Date.now() - t0, 'ms');
    }
  } else {
    const from = +opt('from', 0), to = +opt('to', 335), outF = opt('out', 'segments/out.mp4');
    fs.mkdirSync(path.dirname(path.resolve(ROOT, outF)), { recursive: true });
    const f0 = Math.round(from * FPS), f1 = Math.round(to * FPS);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(FPS), path.resolve(ROOT, outF)], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let f = f0; f < f1; f++) {
      const d = await page.evaluate((tt) => window.grab(tt, 0.95), f / FPS);
      if (!ff.stdin.write(dec(d))) await new Promise((r) => ff.stdin.once('drain', r));
      if ((f - f0) % 48 === 0) {
        const el = (Date.now() - t0) / 1000, done = f - f0 + 1;
        console.log(`${outF} frame ${done}/${f1 - f0}  ${(el / done).toFixed(2)} s/frame  eta ${((f1 - f) * el / done / 60).toFixed(1)} min`);
      }
    }
    ff.stdin.end();
    await new Promise((r) => ff.on('close', r));
    console.log('done', outF, ((Date.now() - t0) / 1000).toFixed(0), 's');
  }
  await browser.close();
  srv.close();
})().catch((e) => { console.error(e); process.exit(1); });
