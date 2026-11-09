// Renders frames [start, end) of the film and pipes them as JPEGs to ffmpeg.
// usage: node render.js <start> <end> <out.mp4> [scale]
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const [start, end, outFile, scale = '1'] = [parseInt(process.argv[2]), parseInt(process.argv[3]), process.argv[4], process.argv[5]];
const root = __dirname;
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  fs.readFile(p, (err, data) => {
    if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' });
    res.end(data);
  });
});

(async () => {
  await new Promise(r => server.listen(0, r));
  const port = server.address().port;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[pageerror]', e));
  await page.goto(`http://localhost:${port}/index.html?scale=${scale}`);
  await page.waitForFunction(() => window.ready === true, null, { timeout: 300000 });
  let ff = null;
  if (outFile.endsWith('.mp4')) {
    ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '60', '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', outFile], { stdio: ['pipe', 'inherit', 'inherit'] });
  } else fs.mkdirSync(outFile, { recursive: true });
  const t0 = Date.now();
  await page.evaluate((f) => window.advanceTo(Math.round(window.storyFrame(f)) - 1), start);
  console.error(`seek to ${start} took ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  for (let f = start; f < end; f++) {
    const url = await page.evaluate((f) => window.renderFrame(f), f);
    const buf = Buffer.from(url.slice(url.indexOf(',') + 1), 'base64');
    if (ff) { if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r)); }
    else fs.writeFileSync(path.join(outFile, `f${String(f).padStart(5, '0')}.jpg`), buf);
    if ((f - start) % 60 === 0) console.error(`frame ${f} (${((Date.now() - t0) / 1000 / (f - start + 1)).toFixed(2)} s/frame)`);
  }
  if (ff) { ff.stdin.end(); await new Promise(r => ff.on('close', r)); }
  await browser.close();
  server.close();
})().catch(e => { console.error(e); process.exit(1); });
