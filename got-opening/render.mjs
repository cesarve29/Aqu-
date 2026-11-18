// Driver de render: sirve el proyecto, abre Chromium headless y vuelca frames a ffmpeg.
// Uso:
//   node render.mjs --stills 3.5,40,120 [--w 1280 --h 720]        -> out/still_<t>.png
//   node render.mjs --from 0 --to 15 --fps 60 --out out/part.mp4  -> video sin audio
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');

const HERE = path.dirname(new URL(import.meta.url).pathname);
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => {
  if (v.startsWith('--')) a.push([v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return a;
}, []));
const W = +(args.w || 1280), H = +(args.h || 720), FPS = +(args.fps || 60);
fs.mkdirSync(path.join(HERE, 'out'), { recursive: true });

const MIME = { '.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json', '.png': 'image/png', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const p = path.join(HERE, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(HERE) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const browser = await chromium.launch({
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--use-gl=angle', '--disable-gpu-sandbox'],
});
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning' || args.verbose) console.log('[page]', m.text()); });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.goto(`http://127.0.0.1:${port}/index.html?w=${W}&h=${H}&ms=${args.ms ?? 0}&debug=${args.debug || ''}`, { waitUntil: 'commit' });
const tInit = Date.now();
await page.waitForFunction(() => window.ready === true, null, { timeout: 900000, polling: 500 });
console.log('scene ready in', ((Date.now() - tInit) / 1000).toFixed(1), 's');

if (args.info) {
  for (const ts of String(args.info).split(',')) { const t0 = Date.now(); await page.evaluate((t) => window.renderPNG(t), +ts); const i = await page.evaluate(() => window.info()); console.log(ts, JSON.stringify(i), Date.now() - t0, 'ms'); }
} else if (args.stills) {
  const cams = args.cam ? String(args.cam).split(';').map((c) => c.split(',').map(Number)) : [null];
  for (const ts of String(args.stills).split(',')) for (let ci = 0; ci < cams.length; ci++) {
    const t = +ts, cam = cams[ci];
    const t0 = Date.now();
    const url = await page.evaluate(([t, cam]) => window.renderPNG(t, cam), [t, cam]);
    const f = path.join(HERE, 'out', `still_${t.toFixed(2)}${args.tag ? '_' + args.tag : ''}${cams.length > 1 ? '_' + ci : ''}.png`);
    fs.writeFileSync(f, Buffer.from(url.split(',')[1], 'base64'));
    console.log(f, Date.now() - t0, 'ms');
  }
} else {
  const from = +(args.from || 0), to = +(args.to || 5);
  const f0 = Math.round(from * FPS), f1 = Math.round(to * FPS);
  const out = path.join(HERE, args.out || `out/part_${f0}_${f1}.mp4`);
  const outTmp = out.replace(/\.mp4$/, '.tmp.mp4');
  const ff = spawn('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', `${W}x${H}`, '-r', String(FPS), '-i', '-',
    '-vf', 'vflip', '-c:v', 'libx264', '-preset', 'medium', '-crf', String(args.crf || 17), '-pix_fmt', 'yuv420p', outTmp], { stdio: ['pipe', 'inherit', 'inherit'] });
  const tStart = Date.now();
  for (let f = f0; f < f1; f++) {
    const b64 = await page.evaluate(([t, f]) => window.renderFrame(t, f), [f / FPS, f]);
    const buf = Buffer.from(b64, 'base64');
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if ((f - f0) % 30 === 0) {
      const el = (Date.now() - tStart) / 1000, done = f - f0 + 1;
      console.log(`frame ${f} (${(f / FPS).toFixed(2)}s) ${(el / done).toFixed(2)} s/frame, eta ${((f1 - f) * el / done / 60).toFixed(1)} min`);
    }
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  fs.renameSync(outTmp, out);
  console.log('wrote', out, ((Date.now() - tStart) / 1000).toFixed(1), 's');
}
await browser.close();
server.close();
