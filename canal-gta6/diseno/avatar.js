// Foto de perfil detallada del canal. Uso: node avatar.js -> ../foto-perfil.png (1920x1920) y ../foto-perfil.jpg
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const defs = fs.readFileSync(path.join(__dirname, 'scene.svg.txt'), 'utf8');
const OUT = 1920, U = 1000; // se diseña en 1000x1000 y se exporta a 1920x1920

function grid(hy) {
  let g = '';
  for (let i = -16; i <= 16; i++) g += `<line x1="${500 + i * 8}" y1="${hy}" x2="${500 + i * 150}" y2="1000"/>`;
  for (let k = 1; k <= 9; k++) { const y = hy + (1000 - hy) * Math.pow(k / 9, 2); g += `<line x1="0" y1="${y}" x2="1000" y2="${y}"/>`; }
  return g;
}
function sun(cx, cy, r) {
  // franjas retro en la mitad inferior del sol
  let bands = '', y = cy - r, gap = 0, h;
  const out = [];
  while (y < cy + r) {
    const rel = (y - (cy - r)) / (2 * r);
    h = rel < 0.5 ? r * 1.15 : 26 - rel * 12;
    gap = rel < 0.5 ? 6 : 6 + (rel - 0.5) * 30;
    out.push(`<rect x="${cx - r}" y="${y}" width="${2 * r}" height="${h}"/>`);
    y += h + gap;
  }
  return `<clipPath id="sunclip"><circle cx="${cx}" cy="${cy}" r="${r}"/></clipPath>
  <g clip-path="url(#sunclip)" fill="url(#sun)" style="filter:drop-shadow(0 0 30px #ff4f9a)">${out.join('')}</g>`;
}

const hy = 650;
const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Montserrat:wght@900&family=Mr+Dafoe&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:${U}px;height:${U}px;position:relative;overflow:hidden;background:#120626}
.abs{position:absolute;left:0;right:0;text-align:center}
.top{top:96px;font:900 64px Montserrat,sans-serif;letter-spacing:.32em;padding-left:.32em;color:#e9fdff;
  text-shadow:0 0 6px #34e1ff,0 0 18px #18b8ff,0 0 40px #0f8cff}
.six{top:185px;font:500px/1 Anton,sans-serif;
  background:linear-gradient(180deg,#ffffff 0%,#fff3b0 18%,#ffe066 36%,#ff9a3d 58%,#ff3f8e 80%,#b01cff 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
  -webkit-text-stroke:10px #1a0633;paint-order:stroke fill;
  filter:drop-shadow(0 0 18px #ff3fb4) drop-shadow(0 10px 0 #1a0633)}
.shine{top:185px;font:500px/1 Anton,sans-serif;color:transparent;
  background:linear-gradient(115deg,transparent 40%,#ffffffcc 47%,transparent 54%);-webkit-background-clip:text;background-clip:text}
.vice{top:575px;font:250px/1 'Mr Dafoe',cursive;color:#fff;transform:rotate(-9deg);
  text-shadow:0 0 4px #fff,0 0 12px #ff3fb4,0 0 28px #ff3fb4,0 0 60px #ff2a8a,0 0 90px #ff2a8a;
  -webkit-text-stroke:2px #ffd1ec}
.badge{top:842px}
.badge span{display:inline-block;font:900 38px Montserrat,sans-serif;letter-spacing:.22em;padding:10px 22px 10px 30px;
  color:#120626;background:#ffe066;border-radius:10px;box-shadow:0 0 22px #ffe06699,0 5px 0 #1a0633}
</style></head><body>
<svg width="${U}" height="${U}" viewBox="0 0 ${U} ${U}" style="position:absolute;inset:0">
  ${defs}
  <radialGradient id="vig" cx=".5" cy=".5" r=".7"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>
  <rect width="${U}" height="${hy}" fill="url(#sky)"/>
  <g fill="#fff" opacity=".7">${Array.from({length:40},(_,i)=>{const x=(i*137)%1000,y=(i*89)%300;return `<circle cx="${x}" cy="${y}" r="${(i%3)+1}"/>`}).join('')}</g>
  ${sun(500, 470, 300)}
  <rect y="${hy}" width="${U}" height="${U - hy}" fill="url(#sea)"/>
  <g stroke="#ff3fb4" stroke-width="2.5" opacity=".8">${grid(hy)}</g>
  <rect y="${hy - 2}" width="${U}" height="4" fill="#ffb3e0"/>
  <use href="#palm" x="-40" y="${hy - 430}" width="230" height="460"/>
  <use href="#palm" x="20" y="${hy - 300}" width="150" height="300" transform="translate(190,0) scale(-1,1)" />
  <g transform="translate(1000,0) scale(-1,1)"><use href="#palm" x="-40" y="${hy - 430}" width="230" height="460"/>
  <use href="#palm" x="20" y="${hy - 300}" width="150" height="300" transform="translate(190,0) scale(-1,1)"/></g>
  <rect width="${U}" height="${U}" fill="url(#vig)"/>
  <circle cx="500" cy="500" r="478" fill="none" stroke="#5ef2ff" stroke-width="12" style="filter:drop-shadow(0 0 12px #34e1ff) drop-shadow(0 0 30px #0f8cff)"/>
  <circle cx="500" cy="500" r="458" fill="none" stroke="#ff3fb4" stroke-width="4" opacity=".9" style="filter:drop-shadow(0 0 10px #ff3fb4)"/>
</svg>
<div class="abs top">SEIS EN</div>
<div class="abs six">6</div>
<div class="abs shine">6</div>
<div class="abs vice">Vice</div>
<div class="abs badge"><span>CLIPS</span></div>
</body></html>`;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: U, height: U }, deviceScaleFactor: OUT / U });
  await p.setContent(html, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  const png = path.join(__dirname, '..', 'foto-perfil.png');
  await p.screenshot({ path: png });
  await b.close();
  execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-i', png, '-q:v', '2', path.join(__dirname, '..', 'foto-perfil.jpg')]);
  console.log('ok');
})();
