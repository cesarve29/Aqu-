// Render individual frames for previewing: node snap.js outdir f1 f2 ...
const { chromium } = require('playwright');
const http = require('http'); const fs = require('fs'); const path = require('path');
const [outDir, ...frames] = process.argv.slice(2);
const query = process.env.Q || '';
const root = __dirname;
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  fs.readFile(p, (err, data) => { if (err) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': p.endsWith('.js') ? 'text/javascript' : 'text/html' }); res.end(data); });
});
(async () => {
  await new Promise(r => server.listen(0, r));
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[pageerror]', e));
  await page.goto(`http://localhost:${server.address().port}/index.html?${query}`);
  await page.waitForFunction(() => window.ready === true, null, { timeout: 300000 });
  fs.mkdirSync(outDir, { recursive: true });
  for (const fs_ of frames.map(Number).sort((a, b) => a - b)) {
    const t0 = Date.now();
    const url = await page.evaluate((f) => window.renderFrame(f), fs_);
    fs.writeFileSync(path.join(outDir, `f${String(fs_).padStart(5, '0')}.jpg`), Buffer.from(url.split(',')[1], 'base64'));
    const st = await page.evaluate(() => { const p = {...window.prof}; for (const k in window.prof) window.prof[k] = 0; return p; });
    console.error(fs_, ((Date.now() - t0) / 1000).toFixed(2) + 's', JSON.stringify(st));
  }
  await browser.close(); server.close();
})().catch(e => { console.error(e); process.exit(1); });
