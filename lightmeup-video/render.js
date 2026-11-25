// Headless renderer: serves the project, drives web/index.html in Chromium
// (SwiftShader WebGL) and pipes PNG frames into ffmpeg.
//   node render.js --start 0 --end 100 --out seg.mp4         (video segment)
//   node render.js --stills 30,900,2000 --outdir shots        (preview PNGs)
const http = require('http'), fs = require('fs'), path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1]]]) : a), []));
const ROOT = __dirname;
const W = +(args.w || 1920), H = +(args.h || 1080);
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2' };

function serve() {
  return new Promise(res => {
    const srv = http.createServer((req, r) => {
      const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
      if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end(); }
      r.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
      fs.createReadStream(p).pipe(r);
    }).listen(0, '127.0.0.1', () => res(srv));
  });
}

(async () => {
  const srv = await serve();
  const port = srv.address().port;
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-vsync'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[pageerror]', e));
  await page.goto(`http://127.0.0.1:${port}/web/index.html?w=${W}&h=${H}&msaa=${args.msaa || 4}`);
  const info = await page.evaluate(() => window.ready);
  console.error('info', JSON.stringify(info));

  const grab = async f => Buffer.from((await page.evaluate(f => window.renderFrame(f), f)).split(',')[1], 'base64');

  if (args.stills) {
    fs.mkdirSync(args.outdir, { recursive: true });
    for (const f of args.stills.split(',').map(Number)) {
      const t0 = Date.now();
      const buf = await grab(f);
      fs.writeFileSync(path.join(args.outdir, `f${String(f).padStart(5, '0')}.png`), buf);
      console.error(`frame ${f} ${(Date.now() - t0)}ms`);
    }
  } else {
    const start = +args.start, end = Math.min(+args.end, info.frames);
    const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-preset', args.preset || 'slow', '-crf', args.crf || '12', '-pix_fmt', 'yuv420p', '-tune', 'film', args.out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let f = start; f < end; f++) {
      const buf = await grab(f);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if ((f - start) % 30 === 0) console.error(`[${args.out}] ${f - start}/${end - start} ${((Date.now() - t0) / (f - start + 1)).toFixed(0)}ms/f`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
  }
  await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
