// Creditos en capa 2D: tiempos, posiciones e iconos con emblema pixelado.
import { emoji, clamp } from './kit.js';

// [t0, t1, x, y, lineas]  ; linea: [icono, titulo(opc), nombre] ; x,y = posicion del icono (fraccion)
// dy entre lineas en fraccion de alto
export const CREDITS = [
  [4.0, 6.4, 0.405, 0.64, [['🦁', '', 'Peter Dinklage']]],
  [6.6, 8.6, 0.11, 0.63, [['🦁', '', 'Nikolaj Coster-Waldau']]],
  [8.8, 10.9, 0.165, 0.80, [['🦁', '', 'Lena Headey']]],
  [11.2, 13.4, 0.535, 0.83, [['🐉', '', 'Emilia Clarke']]],
  [13.7, 16.3, 0.085, 0.26, [['🐺', '', 'Kit Harington']]],
  [16.6, 18.8, 0.565, 0.82, [['🐺', '', 'Sophie Turner']]],
  [19.0, 21.0, 0.12, 0.32, [['🗡️', '', 'Maisie Williams']]],
  [21.1, 23.0, 0.495, 0.83, [['🧅', '', 'Liam Cunningham']]],
  [23.3, 25.4, 0.135, 0.81, [['🦋', '', 'Nathalie Emmanuel']]],
  [25.6, 28.0, 0.105, 0.33, [['🦑', '', 'Alfie Allen'], ['🏹', '', 'John Bradley', 0.06], ['🌳', '', 'Isaac Hempstead Wright', 0.02]]],
  [28.1, 30.4, 0.45, 0.15, [['🛡️', '', 'Gwendoline Christie'], ['🕷️', '', 'Conleth Hill', 0.1]]],
  [30.6, 32.6, 0.505, 0.15, [['🐕', '', 'Rory McCann'], ['🪙', '', 'Jerome Flynn', 0.08]]],
  [33.0, 35.6, 0.525, 0.69, [['🐾', '', 'Kristofer Hivju'], ['🔨', '', 'Joe Dempsie', 0.045], ['🛡️', '', 'Jacob Anderson', 0.0]]],
  [35.9, 37.8, 0.17, 0.81, [['🐻', 'with', 'Iain Glen']]],
  [38.0, 40.1, 0.18, 0.29, [['🎭', 'casting by', 'Nina Gold'], ['', '', 'Robert Sterne', 0.02]]],
  [40.3, 42.3, 0.545, 0.17, [['🌀', 'visual effects supervisor', 'Stefen Fangmeier'], ['✨', 'visual effects producer', 'Steve Kullback', 0.04]]],
  [42.8, 44.6, 0.145, 0.34, [['🧵', 'costume designer', 'Michele Clapton']]],
  [44.9, 46.8, 0.12, 0.81, [['🎼', 'music by', 'Ramin Djawadi']]],
  [47.3, 49.1, 0.57, 0.66, [['✂️', 'editor', 'Crispin Green']]],
  [49.4, 51.5, 0.14, 0.77, [['📐', 'production designer', 'Deborah Riley']]],
  [51.9, 53.4, 0.575, 0.67, [['🎥', 'director of photography', 'David Franco']]],
  [56.3, 58.1, 0.125, 0.19, [['📜', 'producers', 'Duncan Muggoch'], ['🪶', '', 'Lisa McAtackney', 0.04]]],
  [58.3, 60.1, 0.115, 0.67, [['🛡️', 'producer', 'Greg Spence']]],
  [60.4, 62.2, 0.165, 0.81, [['⭐', 'producer', 'Chris Newman']]],
  [62.6, 64.9, 0.12, 0.71, [['🦁', 'co-executive producer', 'Bryan Cogman']]],
  [65.2, 67.1, 0.495, 0.66, [['🍀', 'co-executive producer', 'George R.R. Martin']]],
  [67.4, 69.3, 0.125, 0.24, [['🌸', 'co-executive producer', 'Guymon Casady']]],
  [69.8, 71.8, 0.50, 0.81, [['❌', 'co-executive producer', 'Vince Gerardis']]],
  [72.0, 74.3, 0.105, 0.78, [['🔥', 'executive producers', 'David Nutter'], ['🦅', '', 'Miguel Sapochnik', 0.04]]],
  [74.6, 76.9, 0.12, 0.75, [['💠', 'executive producer', 'Frank Doelger']]],
  [77.2, 79.1, 0.42, 0.80, [['🐗', 'executive producer', 'Bernadette Caulfield']]],
  [79.4, 81.3, 0.12, 0.82, [['🌹', 'executive producer', 'Carolyn Strauss']]],
  [81.7, 83.9, 0.12, 0.65, [['🐉', 'executive producers', 'David Benioff'], ['', '', 'D.B. Weiss', 0.0]]],
  [85.4, 87.9, 0.535, 0.82, [['', 'based on', 'A Song Of Ice And Fire'], ['', '', 'by george r.r. martin', 0.07, 'small']]],
  [89.8, 92.5, 0.205, 0.855, [['👑', 'created by', 'David Benioff & D.B. Weiss']]],
  [101.2, 103.6, 0.5, 0.5, [['', 'written for television by', 'Dave Hill', 0, 'center']]],
  [104.0, 106.3, 0.5, 0.5, [['', 'directed by', 'David Nutter', 0, 'center']]],
];

const iconCache = {};
function iconCanvas(ch, px) {
  const k = ch + px;
  if (iconCache[k]) return iconCache[k];
  const c = document.createElement('canvas'); c.width = c.height = px;
  const x = c.getContext('2d');
  // fondo rojo oscuro con marco punteado (estilo del original)
  x.fillStyle = '#1c0f0a'; x.fillRect(0, 0, px, px);
  x.fillStyle = '#6d1d12'; x.fillRect(3, 3, px - 6, px - 6);
  x.fillStyle = '#c9a46a';
  for (let i = 0; i < px; i += 3) { x.fillRect(i, 0, 1, 1); x.fillRect(i, px - 1, 1, 1); x.fillRect(0, i, 1, 1); x.fillRect(px - 1, i, 1, 1); }
  if (ch) {
    // emoji pixelado: dibujo en 10x10 y escalo sin suavizado
    const s = document.createElement('canvas'); s.width = s.height = 12;
    const sx = s.getContext('2d'); emoji(sx, ch, 6, 6.5, 10);
    const d = sx.getImageData(0, 0, 12, 12).data;
    for (let i = 0; i < 144; i++) {
      const a = d[i * 4 + 3] / 255; if (a < 0.4) continue;
      const l = (d[i * 4] + d[i * 4 + 1] + d[i * 4 + 2]) / 765;
      const r = Math.round(150 + 105 * l), g = Math.round(70 + 120 * l), b = Math.round(30 + 60 * l);
      x.fillStyle = `rgb(${r},${g},${b})`;
      const q = (px - 6) / 12;
      x.fillRect(3 + (i % 12) * q, 3 + Math.floor(i / 12) * q, Math.ceil(q), Math.ceil(q));
    }
  }
  iconCache[k] = c; return c;
}

export function drawCredits(ctx2, W, H, t) {
  ctx2.clearRect(0, 0, W, H);
  for (const [t0, t1, x0, y0, lines] of CREDITS) {
    if (t < t0 - 0.05 || t > t1 + 0.05) continue;
    const fi = clamp((t - t0) / 0.45), fo = clamp((t1 - t) / 0.55);
    const a = Math.min(fi, fo);
    if (a <= 0) continue;
    // ligera deriva como en el original
    const drift = (t - t0) * 0.004;
    let y = y0 * H;
    const fs = H * 0.04; // tamano del nombre
    const isz = Math.round(fs * 1.15);
    lines.forEach(([ic, title, name, dx = 0, style], li) => {
      if (li > 0) y += fs * 1.75;
      const center = style === 'center';
      const small = style === 'small';
      const xi = (x0 + dx + drift) * W;
      ctx2.globalAlpha = a;
      ctx2.textBaseline = 'alphabetic';
      if (center) {
        ctx2.textAlign = 'center';
        ctx2.fillStyle = '#d9c39a';
        ctx2.font = `600 ${fs * 0.32}px Cinzel`;
        if (title) spaced(ctx2, title.toUpperCase(), W * x0, y - fs * 0.55, fs * 0.08, 'center');
        ctx2.font = `600 ${fs * 0.62}px Cinzel`;
        spaced(ctx2, name, W * x0, y + fs * 0.25, fs * 0.16, 'center');
        return;
      }
      let tx = xi;
      if (ic !== '' || li === 0) {
        if (ic) ctx2.drawImage(iconCanvas(ic, isz), xi - isz / 2, y - isz / 2);
        tx = xi + isz * 0.9;
      } else tx = xi + isz * 0.9;
      ctx2.textAlign = 'left';
      ctx2.shadowColor = 'rgba(0,0,0,0.85)'; ctx2.shadowBlur = fs * 0.35;
      if (title) {
        ctx2.font = `700 ${fs * 0.36}px Cinzel`; ctx2.fillStyle = '#cdb98f';
        spaced(ctx2, title.toUpperCase(), tx, y - fs * 0.48, fs * 0.09);
      }
      ctx2.font = `600 ${small ? fs * 0.6 : fs * 0.86}px Cinzel`;
      ctx2.fillStyle = '#e9d7ad';
      spaced(ctx2, name, tx, y + fs * 0.32, fs * (small ? 0.16 : 0.22));
      ctx2.shadowBlur = 0;
    });
  }
  ctx2.globalAlpha = 1;
}

// texto con espaciado entre letras
function spaced(c, s, x, y, sp, align = 'left') {
  let w = 0; for (const ch of s) w += c.measureText(ch).width + sp; w -= sp;
  let px = align === 'center' ? x - w / 2 : x;
  const ta = c.textAlign; c.textAlign = 'left';
  for (const ch of s) { c.fillText(ch, px, y); px += c.measureText(ch).width + sp; }
  c.textAlign = ta;
}
