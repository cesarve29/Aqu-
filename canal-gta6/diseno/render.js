// Genera banner, avatar y miniatura del canal a partir de HTML + SVG.
// Uso: node render.js  (desde esta carpeta). Cambia NAME/TAG para otro nombre.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const NAME_A = process.env.NAME_A || 'SEIS EN';
const NAME_B = process.env.NAME_B || 'VICE';
const TAG = process.env.TAG || 'LO MEJOR DE GTA 6 EN MENOS DE 1 MINUTO';
const INITIALS = process.env.INITIALS || '6V';
const css = fs.readFileSync(path.join(__dirname, 'common.css'), 'utf8');
const defs = fs.readFileSync(path.join(__dirname, 'scene.svg.txt'), 'utf8');

function scene(W, H, o) {
  const hy = o.horizon, r = o.sunR, cx = o.sunX, rise = o.sunRise || 0, gridOff = o.gridOff || 0;
  let grid = '';
  const n = 28;
  for (let i = -n; i <= n; i++) {
    const x2 = W / 2 + i * (W / n) * 2.2;
    grid += `<line x1="${W / 2 + i * 6}" y1="${hy}" x2="${x2}" y2="${H}" />`;
  }
  for (let k = 1; k <= 12; k++) {
    const y = hy + (H - hy) * Math.pow(((k - gridOff) % 12 + 12) % 12 / 12, 2.2);
    grid += `<line x1="0" y1="${y}" x2="${W}" y2="${y}" />`;
  }
  const palms = (o.palms || []).map(p =>
    `<use href="#palm" x="${p.x}" y="${p.y}" width="${p.s * 200}" height="${p.s * 400}" ${p.flip ? `transform="translate(${2 * p.x + p.s * 200},0) scale(-1,1)"` : ''}/>`).join('');
  const city = (o.city !== false) ? (() => {
    let s = '', x = 0, seed = 7;
    const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
    while (x < W) {
      const w = (0.018 + rnd() * 0.035) * W, h = (0.03 + rnd() * rnd() * 0.16) * H;
      s += `<rect x="${x}" y="${hy - h}" width="${w + 1}" height="${h}" />`;
      x += w;
    }
    return `<g fill="#2a0a45" opacity=".85">${s}</g>`;
  })() : '';
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0">
  ${defs}
  <rect width="${W}" height="${hy}" fill="url(#sky)"/>
  <g mask="url(#sunmask)"></g>
  <svg x="${cx - r}" y="${hy - r * 1.35 + rise}" width="${2 * r}" height="${2 * r}" viewBox="0 0 1 1" overflow="visible">
    <circle cx=".5" cy=".5" r=".5" fill="url(#sun)" mask="url(#sunstripes)" style="filter:drop-shadow(0 0 .06px #ff5fa8)"/>
  </svg>
  ${city}
  <rect y="${hy}" width="${W}" height="${H - hy}" fill="url(#sea)"/>
  <g stroke="#ff3fb4" stroke-width="${Math.max(1.5, W / 900)}" opacity=".75">${grid}</g>
  <rect y="${hy - 2}" width="${W}" height="4" fill="#ff8fd0" opacity=".9"/>
  ${palms}
  </svg>`;
}

const page = (W, H, body) => `<!doctype html><html><head><meta charset="utf-8"><style>${css}
body{width:${W}px;height:${H}px;position:relative}</style></head><body>${body}</body></html>`;

const banner = (() => {
  const W = 2560, H = 1440;
  const s = scene(W, H, { horizon: 860, sunR: 300, sunX: W / 2, palms: [
    { x: 300, y: 380, s: 1.3 }, { x: 520, y: 520, s: .95, flip: 1 }, { x: 1880, y: 420, s: 1.2, flip: 1 }, { x: 2100, y: 560, s: .9 } ] });
  // Zona segura de YouTube: 1546x423 centrada
  return page(W, H, `${s}
  <div style="position:absolute;left:${(W - 1546) / 2}px;top:${(H - 423) / 2}px;width:1546px;height:423px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center">
    <div class="title" style="font-size:200px"><span class="neon-pink">${NAME_A}</span> <span class="neon-cyan">${NAME_B}</span></div>
    <div class="sub" style="font-size:44px;margin-top:22px;letter-spacing:.08em;text-shadow:0 3px 12px #000a">${TAG}</div>
    <div class="sub" style="font-size:30px;margin-top:16px;color:#ffe066;letter-spacing:.2em;text-shadow:0 2px 10px #000a">SHORTS NUEVOS CADA DÍA</div>
  </div>`);
})();

const avatar = (() => {
  const W = 800, H = 800;
  const s = scene(W, H, { horizon: 520, sunR: 230, sunX: 400, city: false, palms: [
    { x: -40, y: 170, s: .95 }, { x: 650, y: 230, s: .8, flip: 1 } ] });
  return page(W, H, `${s}
  <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">
    <div class="title neon-cyan" style="font-size:330px;color:#fff;-webkit-text-stroke:6px #120626;paint-order:stroke fill;margin-top:-30px">${INITIALS}</div>
  </div>`);
})();

const thumb = (() => {
  const W = 1280, H = 720;
  const s = scene(W, H, { horizon: 470, sunR: 170, sunX: 960, palms: [{ x: 1080, y: 150, s: .8, flip: 1 }] });
  return page(W, H, `${s}
  <div style="position:absolute;left:40px;top:50px;width:820px">
    <div class="title" style="font-size:150px;-webkit-text-stroke:10px #120626;paint-order:stroke fill;transform:rotate(-3deg);transform-origin:left">NADIE<br><span style="color:#ffe066">ESPERABA</span><br>ESTO 😱</div>
  </div>
  <div class="sub" style="position:absolute;left:44px;bottom:36px;background:#ff2a8a;padding:10px 22px;font-size:40px;border-radius:10px;box-shadow:0 6px 0 #120626">GTA 6</div>
  <div style="position:absolute;right:30px;bottom:30px;width:360px;height:240px;border:6px dashed #fff8;border-radius:16px;display:flex;align-items:center;justify-content:center" class="sub"><span style="font-size:26px;opacity:.8;text-align:center">AQUÍ VA UN<br>FOTOGRAMA DEL CLIP</span></div>`);
})();

module.exports = { scene, css, defs, NAME_A, NAME_B, TAG, INITIALS };

if (require.main === module) (async () => {
  const outDir = path.join(__dirname, '..');
  const browser = await chromium.launch();
  for (const [name, html, W, H] of [['banner', banner, 2560, 1440], ['foto-perfil', avatar, 800, 800], ['miniatura-plantilla', thumb, 1280, 720]]) {
    const p = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    await p.setContent(html, { waitUntil: 'networkidle' });
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(outDir, `${name}.png`) });
    await p.close();
  }
  await browser.close();
  console.log('ok');
})();
