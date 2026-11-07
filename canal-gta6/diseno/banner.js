// Banner del canal con el estilo de la foto de perfil v2 (6 gigante + "Vice" en neón).
// Uso: node banner.js [--guia]  -> ../banner.png y ../banner.jpg (2560x1440)
// --guia dibuja la zona segura de YouTube (1546x423) para revisar.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const defs = fs.readFileSync(path.join(__dirname, 'scene.svg.txt'), 'utf8');
const W = 2560, H = 1440, SW = 1546, SH = 423, SX = (W - SW) / 2, SY = (H - SH) / 2;
const GUIA = process.argv.includes('--guia');
const HY = 960, CX = W / 2;

function grid() {
  let g = '';
  for (let i = -30; i <= 30; i++) g += `<line x1="${CX + i * 10}" y1="${HY}" x2="${CX + i * 230}" y2="${H}"/>`;
  for (let k = 1; k <= 10; k++) { const y = HY + (H - HY) * Math.pow(k / 10, 2); g += `<line x1="0" y1="${y}" x2="${W}" y2="${y}"/>`; }
  return g;
}
function sun(cx, cy, r) {
  let y = cy - r; const out = [];
  while (y < cy + r) {
    const rel = (y - (cy - r)) / (2 * r);
    const h = rel < 0.5 ? r * 1.15 : 34 - rel * 16;
    const gap = rel < 0.5 ? 8 : 8 + (rel - 0.5) * 40;
    out.push(`<rect x="${cx - r}" y="${y}" width="${2 * r}" height="${h}"/>`);
    y += h + gap;
  }
  return `<clipPath id="sc"><circle cx="${cx}" cy="${cy}" r="${r}"/></clipPath>
  <g clip-path="url(#sc)" fill="url(#sun)" style="filter:drop-shadow(0 0 50px #ff4f9a)">${out.join('')}</g>`;
}
function city() {
  let s = '', x = 0, seed = 11;
  const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  while (x < W) { const w = 40 + rnd() * 90, h = 40 + rnd() * rnd() * 230; s += `<rect x="${x}" y="${HY - h}" width="${w + 1}" height="${h}"/>`; x += w; }
  return `<g fill="#2a0a45" opacity=".9">${s}</g>`;
}
let ss = 3; const sr = () => (ss = (ss * 16807) % 2147483647) / 2147483647;
const stars = Array.from({ length: 110 }, () => `<circle cx="${sr() * W}" cy="${sr() * 600}" r="${1 + sr() * 2.4}" opacity="${0.4 + sr() * 0.6}"/>`).join('');
const palm = (x, s, flip) => `<use href="#palm" x="${x}" y="${HY - 400 * s}" width="${200 * s}" height="${400 * s}" ${flip ? `transform="translate(${2 * x + 200 * s},0) scale(-1,1)"` : ''}/>`;

const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Montserrat:wght@800;900&family=Mr+Dafoe&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:${W}px;height:${H}px;position:relative;overflow:hidden;background:#120626}
.safe{position:absolute;left:${SX}px;top:${SY}px;width:${SW}px;height:${SH}px}
.six,.shine{position:absolute;left:0;right:0;top:-82px;text-align:center;font:600px/1 Anton,sans-serif}
.six{background:linear-gradient(180deg,#fff 0%,#fff3b0 18%,#ffe066 36%,#ff9a3d 58%,#ff3f8e 80%,#b01cff 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-stroke:14px #1a0633;paint-order:stroke fill;
  filter:drop-shadow(0 0 34px #ff3fb4) drop-shadow(0 14px 0 #1a0633)}
.shine{color:transparent;background:linear-gradient(115deg,transparent 40%,#ffffffcc 47%,transparent 54%);-webkit-background-clip:text;background-clip:text}
.vice{position:absolute;left:0;right:0;top:70px;text-align:center;font:290px/1 'Mr Dafoe',cursive;color:#fff;transform:rotate(-9deg);
  -webkit-text-stroke:2px #ffd1ec;
  text-shadow:0 0 4px #fff,0 0 14px #ff3fb4,0 0 32px #ff3fb4,0 0 70px #ff2a8a,0 0 110px #ff2a8a,0 8px 0 #1a0633,0 14px 30px #1a0633}
.left{position:absolute;left:0;top:0;bottom:0;width:400px;display:flex;flex-direction:column;justify-content:center;align-items:flex-end;
  font:900 118px/1 Montserrat,sans-serif;letter-spacing:.06em;color:#e9fdff;text-shadow:0 0 8px #34e1ff,0 0 24px #18b8ff,0 0 50px #0f8cff,0 6px 0 #1a0633}
.right{position:absolute;right:0;top:0;bottom:0;width:470px;white-space:nowrap;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;gap:14px;
  font:800 33px/1.15 Montserrat,sans-serif;color:#fff;letter-spacing:.04em;text-shadow:0 3px 14px #000c}
.pill{margin-top:12px;font:900 23px Montserrat,sans-serif;letter-spacing:.1em;color:#120626;background:#ffe066;padding:12px 20px;border-radius:10px;
  box-shadow:0 0 24px #ffe06699,0 5px 0 #1a0633;text-shadow:none}
.guia{position:absolute;left:${SX}px;top:${SY}px;width:${SW}px;height:${SH}px;outline:4px dashed #0f0}
</style></head><body>
<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="position:absolute;inset:0">
  ${defs}
  <radialGradient id="vig" cx=".5" cy=".5" r=".75"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".6"/></radialGradient>
  <rect width="${W}" height="${HY}" fill="url(#sky)"/>
  <g fill="#fff" opacity=".7">${stars}</g>
  ${sun(CX, 700, 430)}
  ${city()}
  <rect y="${HY}" width="${W}" height="${H - HY}" fill="url(#sea)"/>
  <g stroke="#ff3fb4" stroke-width="3" opacity=".8">${grid()}</g>
  <rect y="${HY - 3}" width="${W}" height="6" fill="#ffb3e0"/>
  ${palm(120, 1.5)}${palm(330, 1.0, 1)}${palm(2140, 1.45, 1)}${palm(2090, 1.0)}
  <rect width="${W}" height="${H}" fill="url(#vig)"/>
</svg>
<div class="safe">
  <div class="left"><div>SEIS</div><div>EN</div></div>
  <div class="six">6</div><div class="shine">6</div>
  <div class="vice">Vice</div>
  <div class="right"><div>LO MEJOR DE GTA 6</div><div>EN MENOS DE 1 MINUTO</div><div class="pill">SHORTS NUEVOS CADA DÍA</div></div>
</div>
${GUIA ? '<div class="guia"></div>' : ''}
</body></html>`;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: W, height: H } });
  await p.setContent(html, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  const name = GUIA ? 'banner-guia' : 'banner';
  const out = path.join(__dirname, '..', `${name}.png`);
  await p.screenshot({ path: out });
  await b.close();
  if (!GUIA) execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-i', out, '-q:v', '2', path.join(__dirname, '..', 'banner.jpg')]);
  console.log('ok', name);
})();
