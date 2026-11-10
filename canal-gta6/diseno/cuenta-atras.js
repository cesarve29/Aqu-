// Segmentos animados de la cuenta atrás (vertical 1080x1920, sin audio).
// Uso: node cuenta-atras.js [dia ...]   (por defecto 12..0; 0 = "HOY"). Desde el día 8 se renderiza a 1440x2560.
// Salida: ../cuenta-atras/segmentos/dia-XX.mp4  (+ eventos de sonido en dia-XX.json)
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const defs = fs.readFileSync(path.join(__dirname, 'scene.svg.txt'), 'utf8');

const W = 1080, H = 1920, FPS = 30, DUR = 6.0, HY = 1300, CX = 540, CY = 900, RING = 400, SEG = 24;
const clamp = x => Math.max(0, Math.min(1, x));
const ease = x => 1 - Math.pow(1 - clamp(x), 3);
const back = x => { x = clamp(x); const c = 1.7; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); };
const TICKS = Array.from({ length: 8 }, (_, i) => 0.6 + i * 0.5);   // 8 tics → 3 segmentos cada uno
const FINAL = 4.85;

function sun(cx, cy, r) {
  let y = cy - r; const out = [];
  while (y < cy + r) { const rel = (y - (cy - r)) / (2 * r);
    const h = rel < 0.5 ? r * 1.15 : 30 - rel * 14, gap = rel < 0.5 ? 8 : 8 + (rel - 0.5) * 36;
    out.push(`<rect x="${cx - r}" y="${y}" width="${2 * r}" height="${h}"/>`); y += h + gap; }
  return `<clipPath id="sc"><circle cx="${cx}" cy="${cy}" r="${r}"/></clipPath><g clip-path="url(#sc)" fill="url(#sun)" style="filter:drop-shadow(0 0 40px #ff4f9a)">${out.join('')}</g>`;
}
let ss = 5; const sr = () => (ss = (ss * 16807) % 2147483647) / 2147483647;
const STARS = Array.from({ length: 80 }, () => `<circle cx="${sr() * W}" cy="${sr() * 800}" r="${1 + sr() * 2.2}" opacity="${0.4 + sr() * 0.6}"/>`).join('');
const palm = (x, s, flip) => `<use href="#palm" x="${x}" y="${HY - 400 * s}" width="${200 * s}" height="${400 * s}" ${flip ? `transform="translate(${2 * x + 200 * s},0) scale(-1,1)"` : ''}/>`;

function background(t) {
  let g = '';
  for (let i = -16; i <= 16; i++) g += `<line x1="${CX + i * 10}" y1="${HY}" x2="${CX + i * 170}" y2="${H}"/>`;
  for (let k = 0; k < 10; k++) { const p = ((k + t * 1.6) % 10) / 10; const y = HY + (H - HY) * p * p; g += `<line x1="0" y1="${y}" x2="${W}" y2="${y}"/>`; }
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="position:absolute;inset:0">${defs}
  <radialGradient id="vig" cx=".5" cy=".45" r=".8"><stop offset=".5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".65"/></radialGradient>
  <rect width="${W}" height="${HY}" fill="url(#sky)"/><g fill="#fff">${STARS}</g>
  ${sun(CX, 1060, 380)}
  <rect y="${HY}" width="${W}" height="${H - HY}" fill="url(#sea)"/>
  <g stroke="#ff3fb4" stroke-width="3" opacity=".8">${g}</g><rect y="${HY - 3}" width="${W}" height="6" fill="#ffb3e0"/>
  ${palm(-120, 1.7)}${palm(60, 1.1, 1)}${palm(880, 1.6, 1)}${palm(760, 1.0)}
  <rect width="${W}" height="${H}" fill="url(#vig)"/></svg>`;
}

function ring(t) {
  let lit = 0; for (const tk of TICKS) if (t >= tk) lit += 3;
  if (t >= FINAL) lit = SEG;
  let s = '';
  for (let i = 0; i < SEG; i++) {
    const a0 = -Math.PI / 2 + (i / SEG) * 2 * Math.PI + 0.04, a1 = -Math.PI / 2 + ((i + 1) / SEG) * 2 * Math.PI - 0.04;
    const p = (r, a) => `${CX + r * Math.cos(a)},${CY + r * Math.sin(a)}`;
    const on = i < lit;
    s += `<path d="M${p(RING, a0)} A${RING},${RING} 0 0 1 ${p(RING, a1)}" stroke="${on ? '#5ef2ff' : '#ffffff33'}" stroke-width="${on ? 22 : 14}" fill="none" stroke-linecap="round" ${on ? 'style="filter:drop-shadow(0 0 10px #34e1ff)"' : ''}/>`;
  }
  return `<svg width="${W}" height="${H}" style="position:absolute;inset:0">${s}</svg>`;
}

function frame(day, t) {
  const hoy = day === 0;
  const big = hoy ? 'HOY' : String(day);
  const top = hoy ? 'POR FIN' : day === 1 ? 'FALTA' : 'FALTAN';
  const sub = hoy ? 'SALE GTA 6' : day === 1 ? 'DÍA PARA GTA 6' : 'DÍAS PARA GTA 6';
  const slam = back(t / 0.28);
  const scale = 2.2 - 1.2 * slam;
  let pulse = 0; for (const tk of TICKS) if (t >= tk) pulse = Math.max(pulse, 0.05 * Math.exp(-(t - tk) * 9));
  const fin = t >= FINAL ? 0.12 * Math.exp(-(t - FINAL) * 6) : 0;
  const shake = (t < 0.35 ? (0.35 - t) * 60 : 0) + (t >= FINAL && t < FINAL + 0.3 ? (FINAL + 0.3 - t) * 50 : 0);
  const sx = Math.sin(t * 90) * shake, sy = Math.cos(t * 77) * shake;
  const flash = Math.max(clamp(1 - t / 0.25), t >= FINAL ? clamp(1 - (t - FINAL) / 0.3) * 0.7 : 0);
  const fl = (st) => { const d = t - st; if (d < 0) return 0; const p = [1, 0, 1, 1, 0, 1]; const i = Math.floor(d / 0.05); return i < p.length ? p[i] : 1; };
  const subIn = ease((t - 1.0) / 0.35), pill = back((t - 1.6) / 0.3);
  const numSize = hoy ? 400 : big.length > 1 ? 560 : 640;
  const fadeOut = clamp((t - (DUR - 0.25)) / 0.25);
  return `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Montserrat:wght@800;900&family=Mr+Dafoe&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box}body{width:${W}px;height:${H}px;position:relative;overflow:hidden;background:#120626}
.c{position:absolute;left:0;right:0;text-align:center}
.brand{top:150px;font:900 44px Montserrat,sans-serif;letter-spacing:.3em;color:#e9fdff;text-shadow:0 0 8px #34e1ff,0 0 22px #18b8ff}
.brand b{font:120px/0 'Mr Dafoe',cursive;letter-spacing:0;color:#fff;text-shadow:0 0 10px #ff3fb4,0 0 30px #ff2a8a;vertical-align:-8px;margin-left:6px}
.top{top:330px;font:900 92px Montserrat,sans-serif;letter-spacing:.18em;padding-left:.18em;color:#e9fdff;text-shadow:0 0 8px #34e1ff,0 0 26px #18b8ff,0 0 50px #0f8cff,0 6px 0 #1a0633}
.num{top:${CY}px;transform:translateY(-50%) scale(${scale + pulse + fin});font:${numSize}px/1 Anton,sans-serif;
  background:linear-gradient(180deg,#fff 0%,#fff3b0 18%,#ffe066 36%,#ff9a3d 58%,#ff3f8e 80%,#b01cff 100%);-webkit-background-clip:text;background-clip:text;color:transparent;
  -webkit-text-stroke:14px #1a0633;paint-order:stroke fill;filter:drop-shadow(0 0 ${30 + fin * 300}px #ff3fb4) drop-shadow(0 14px 0 #1a0633)}
.sub{top:1390px;font:900 76px Montserrat,sans-serif;color:#fff;letter-spacing:.03em;text-shadow:0 0 18px #ff3fb4,0 5px 0 #1a0633}
.pill{top:1510px}.pill span{display:inline-block;font:900 50px Montserrat,sans-serif;letter-spacing:.14em;color:#120626;background:#ffe066;padding:14px 34px;border-radius:14px;box-shadow:0 0 30px #ffe06699,0 7px 0 #1a0633}
</style></head><body>
<div style="position:absolute;inset:0;transform:translate(${sx}px,${sy}px)">
${background(t)}
${ring(t)}
<div class="c brand" style="opacity:${fl(0.05)}">SEIS EN <b>Vice</b></div>
<div class="c top" style="opacity:${fl(0.15)}">${top}</div>
<div class="c num">${big}</div>
<div class="c sub" style="opacity:${subIn};transform:translateY(${(1 - subIn) * 60}px)">${sub}</div>
<div class="c pill" style="opacity:${clamp((t - 1.6) / 0.1)};transform:scale(${pill})"><span>19 NOVIEMBRE</span></div>
</div>
<div style="position:absolute;inset:0;background:#fff;opacity:${flash}"></div>
<div style="position:absolute;inset:0;background:#000;opacity:${fadeOut}"></div>
</body></html>`;
}

// Eventos de sonido del segmento (tiempos relativos al inicio del segmento)
function sonidos() {
  const ev = [{ t: 0, fx: 'impacto', gain: 1 }, { t: 0.05, fx: 'neon', gain: 0.5 }, { t: 0.15, fx: 'neon', gain: 0.4, pan: 0.3 },
    { t: 1.0, fx: 'whoosh', gain: 0.8 }, { t: 1.6, fx: 'pop', gain: 0.7 }];
  TICKS.forEach((tk, i) => ev.push({ t: tk, fx: 'tic', args: [i % 2 ? 1700 : 2500], gain: 0.75, pan: i % 2 ? 0.25 : -0.25 }));
  ev.push({ t: FINAL - 0.85, fx: 'subida', args: [0.85], gain: 0.6 }, { t: FINAL, fx: 'impacto', gain: 1 }, { t: FINAL, fx: 'stab', gain: 0.6 });
  return ev;
}

async function render(day, browser) {
  const out = path.join(__dirname, '..', 'cuenta-atras', 'segmentos');
  fs.mkdirSync(out, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ca-'));
  const p = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: day <= 8 ? 4 / 3 : 1 }); // desde el día 8: 1440x2560
  const n = Math.round(DUR * FPS);
  for (let i = 0; i < n; i++) {
    await p.setContent(frame(day, i / FPS), { waitUntil: i === 0 ? 'networkidle' : 'load' });
    if (i === 0) await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(tmp, `f${String(i).padStart(4, '0')}.png`) });
  }
  await p.close();
  const name = `dia-${String(day).padStart(2, '0')}`;
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(tmp, 'f%04d.png'),
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', path.join(out, `${name}.mp4`)]);
  fs.writeFileSync(path.join(out, `${name}.json`), JSON.stringify({ dur: DUR, eventos: sonidos() }, null, 1));
  fs.rmSync(tmp, { recursive: true });
  console.log('ok', name);
}

module.exports = { sonidos, DUR };
if (require.main === module) (async () => {
  const days = process.argv.slice(2).map(Number);
  const list = days.length ? days : [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0];
  const b = await chromium.launch();
  for (const d of list) await render(d, b);
  await b.close();
})();
