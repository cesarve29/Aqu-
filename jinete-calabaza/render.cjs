// Renderiza cuadros con Chromium headless (WebGL por software) y los envia a ffmpeg.
// Uso:
//   node render.cjs stills 12.5 40 ...          -> stills/t_XXXX.jpg
//   node render.cjs range <inicio> <fin> <salida.mp4> [fps]
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = __dirname;
const TYPES = { '.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json' };

function serve() {
  return new Promise((res) => {
    const srv = http.createServer((q, s) => {
      const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
      fs.readFile(f, (e, d) => {
        if (e) { s.writeHead(404); return s.end(); }
        s.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
        s.end(d);
      });
    });
    srv.listen(0, () => res(srv));
  });
}

async function open(srv, w = 1920, h = 1080) {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on('console', (m) => console.log('[page]', m.text()));
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  await page.goto(`http://localhost:${srv.address().port}/index.html?w=${w}&h=${h}`);
  await page.waitForFunction('window.ready || window.initError', null, { timeout: 600000 });
  const err = await page.evaluate('window.initError');
  if (err) throw new Error(err);
  return { browser, page };
}

(async () => {
  const [mode, ...args] = process.argv.slice(2);
  const srv = await serve();
  const { browser, page } = await open(srv);
  if (mode === 'stills') {
    fs.mkdirSync(path.join(ROOT, 'stills'), { recursive: true });
    for (const a of args) {
      const t = parseFloat(a);
      const t0 = Date.now();
      const url = await page.evaluate((t) => window.renderAt(t, 0.9), t);
      const out = path.join(ROOT, 'stills', `t_${t.toFixed(2).padStart(7, '0')}.jpg`);
      fs.writeFileSync(out, Buffer.from(url.split(',')[1], 'base64'));
      console.log(out, Date.now() - t0, 'ms');
    }
  } else if (mode === 'range') {
    const [a, b, out, fpsArg] = args;
    const fps = +(fpsArg || 60);
    const start = Math.round(+a * fps), end = Math.round(+b * fps);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-r', String(fps), out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let f = start; f < end; f++) {
      const url = await page.evaluate((t) => window.renderAt(t, 0.95), f / fps);
      const buf = Buffer.from(url.split(',')[1], 'base64');
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
      if ((f - start) % 60 === 0) {
        const el = (Date.now() - t0) / 1000, done = f - start + 1;
        console.log(`${out}: ${done}/${end - start} (${(el / done).toFixed(2)} s/cuadro)`);
      }
    }
    ff.stdin.end();
    await new Promise((r) => ff.on('close', r));
    console.log('listo', out, ((Date.now() - t0) / 1000).toFixed(0), 's');
  }
  await browser.close();
  srv.close();
})().catch((e) => { console.error(e); process.exit(1); });
