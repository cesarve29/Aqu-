// Interfaz 2D: fuente pixelada, corazones, barra de objetos, logros, barra del jefe y creditos.
const F = {
  A: '.###.|#...#|#...#|#####|#...#|#...#|#...#', B: '####.|#...#|#...#|####.|#...#|#...#|####.',
  C: '.###.|#...#|#....|#....|#....|#...#|.###.', D: '####.|#...#|#...#|#...#|#...#|#...#|####.',
  E: '#####|#....|#....|####.|#....|#....|#####', F: '#####|#....|#....|####.|#....|#....|#....',
  G: '.###.|#...#|#....|#.###|#...#|#...#|.####', H: '#...#|#...#|#...#|#####|#...#|#...#|#...#',
  I: '.###.|..#..|..#..|..#..|..#..|..#..|.###.', J: '..###|...#.|...#.|...#.|#..#.|#..#.|.##..',
  K: '#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#', L: '#....|#....|#....|#....|#....|#....|#####',
  M: '#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#', N: '#...#|##..#|#.#.#|#..##|#...#|#...#|#...#',
  O: '.###.|#...#|#...#|#...#|#...#|#...#|.###.', P: '####.|#...#|#...#|####.|#....|#....|#....',
  Q: '.###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#', R: '####.|#...#|#...#|####.|#.#..|#..#.|#...#',
  S: '.####|#....|#....|.###.|....#|....#|####.', T: '#####|..#..|..#..|..#..|..#..|..#..|..#..',
  U: '#...#|#...#|#...#|#...#|#...#|#...#|.###.', V: '#...#|#...#|#...#|#...#|#...#|.#.#.|..#..',
  W: '#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#', X: '#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#',
  Y: '#...#|#...#|.#.#.|..#..|..#..|..#..|..#..', Z: '#####|....#|...#.|..#..|.#...|#....|#####',
  0: '.###.|#...#|#..##|#.#.#|##..#|#...#|.###.', 1: '..#..|.##..|..#..|..#..|..#..|..#..|.###.',
  2: '.###.|#...#|....#|...#.|..#..|.#...|#####', 3: '####.|....#|....#|.###.|....#|....#|####.',
  4: '...#.|..##.|.#.#.|#..#.|#####|...#.|...#.', 5: '#####|#....|####.|....#|....#|#...#|.###.',
  6: '.###.|#....|#....|####.|#...#|#...#|.###.', 7: '#####|....#|...#.|..#..|.#...|.#...|.#...',
  8: '.###.|#...#|#...#|.###.|#...#|#...#|.###.', 9: '.###.|#...#|#...#|.####|....#|....#|.###.',
  '!': '..#..|..#..|..#..|..#..|..#..|.....|..#..', '?': '.###.|#...#|....#|...#.|..#..|.....|..#..',
  '¡': '..#..|.....|..#..|..#..|..#..|..#..|..#..', '¿': '..#..|.....|..#..|.#...|#....|#...#|.###.',
  ':': '.....|..#..|.....|.....|.....|..#..|.....', '.': '.....|.....|.....|.....|.....|.....|..#..',
  ',': '.....|.....|.....|.....|.....|..#..|.#...', '+': '.....|..#..|..#..|#####|..#..|..#..|.....',
  '-': '.....|.....|.....|#####|.....|.....|.....', ' ': '.....|.....|.....|.....|.....|.....|.....',
  '\'': '..#..|..#..|.....|.....|.....|.....|.....', '/': '....#|...#.|...#.|..#..|.#...|.#...|#....',
  'Ñ': '.###.|.....|#...#|##..#|#.#.#|#..##|#...#', '(': '...#.|..#..|.#...|.#...|.#...|..#..|...#.',
  ')': '.#...|..#..|...#.|...#.|...#.|..#..|.#...', '&': '.##..|#..#.|.##..|.#...|#.#.#|#..#.|.##.#',
};
const GLY = {};
for (const k in F) GLY[k] = F[k].split('|');
const norm = (s) => s.toUpperCase().replace(/Á/g, 'A').replace(/É/g, 'E').replace(/Í/g, 'I').replace(/Ó/g, 'O').replace(/Ú/g, 'U').replace(/Ü/g, 'U');

export function textWidth(s, sc) { return norm(s).length * 6 * sc - sc; }

export function drawText(g, s, x, y, sc, color, o = {}) {
  s = norm(s);
  const w = textWidth(s, sc);
  if (o.align === 'center') x -= w / 2;
  else if (o.align === 'right') x -= w;
  x = Math.round(x); y = Math.round(y);
  const pass = (dx, dy, col) => {
    g.fillStyle = col;
    for (let i = 0; i < s.length; i++) {
      const gl = GLY[s[i]] || GLY[' '];
      for (let r = 0; r < 7; r++) for (let c = 0; c < 5; c++) if (gl[r][c] === '#') g.fillRect(x + (i * 6 + c) * sc + dx, y + r * sc + dy, sc, sc);
    }
  };
  if (o.outline) for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, 1], [-1, 1], [1, -1]]) pass(dx * o.outline, dy * o.outline, o.outlineCol || '#000');
  if (o.shadow !== false) pass(sc, sc, o.shadowCol || 'rgba(40,40,40,0.9)');
  if (o.depth) for (let k = o.depth; k > 0; k--) pass(0, k * sc * 0.5, o.depthCol || '#333');
  pass(0, 0, color);
  return w;
}

const HEART = ['.##.##.', '#######', '#######', '#######', '.#####.', '..###..', '...#...'];
function heart(g, x, y, sc, fill) {
  for (let r = 0; r < 7; r++) for (let c = 0; c < 7; c++) {
    if (HEART[r][c] !== '#') continue;
    const inside = !(r === 0 || c === 0 || c === 6 || (r === 4 && (c === 1 || c === 5)) || (r === 5 && (c === 2 || c === 4)) || r === 6);
    let col = '#1a1a1a';
    if (inside) {
      const full = fill >= 1 || (fill > 0 && c < 4);
      col = full ? (r === 1 && c === 2 ? '#ffb3b3' : '#e01b1b') : '#3a1010';
    }
    g.fillStyle = col;
    g.fillRect(x + c * sc, y + r * sc, sc, sc);
  }
}

function pix(g, rows, pal, x, y, sc) {
  rows.forEach((row, r) => [...row].forEach((ch, c) => { if (pal[ch]) { g.fillStyle = pal[ch]; g.fillRect(x + c * sc, y + r * sc, sc, sc); } }));
}
const ICONS = {
  sword: [['..........##', '.........#c#', '........#c#.', '.......#c#..', '......#c#...', '.....#c#....', '.#..#c#.....', '.##c#.......', '..##........', '.#w##.......', '#w#.##......', '##..........'],
    { '#': '#0e3b36', c: '#5ff2e2', w: '#6b4a26' }],
  bow: [['......###...', '.....#..w#..', '....#....#..', '...#.....#..', '..#......w..', '.#.......w..', '.#.......w..', '..#......w..', '...#.....#..', '....#....#..', '.....#..w#..', '......###...'],
    { '#': '#7a5530', w: '#e0e0e0' }],
  arrow: [['.........##.', '........#g#.', '.......#g#..', '......#w#...', '.....#w#....', '....#w#.....', '...#w#......', '.f#w#.......', '.ff#........', 'f.ff........', '...f........', '............'],
    { '#': '#3a2a18', w: '#8a6a40', g: '#999', f: '#eee' }],
  flint: [['............', '..##........', '.#gg#.......', '.#ggg#......', '..#gg#......', '...##.......', '.......###..', '......#sss#.', '.....#s..s#.', '.....#s..s#.', '......#ss#..', '.......##...'],
    { '#': '#222', g: '#555', s: '#aaa' }],
  bread: [['............', '............', '...######...', '..#oyoyoy#..', '.#oyoyoyoo#.', '.#oooooooo#.', '..########..', '............'],
    { '#': '#6b3e10', o: '#c08030', y: '#e0b050' }],
  egg: [['....####....', '...#pppp#...', '..#pkppkp#..', '.#ppppkppp#.', '.#pkpppppp#.', '#pppppkpppp#', '#ppkpppppkp#', '#pppppppppp#', '.#ppkpppp#..', '..########..'],
    { '#': '#0c0612', p: '#2a1636', k: '#8a3ab0' }],
};

export class HUD {
  constructor(W, H, atlas) {
    this.W = W; this.H = H; this.atlas = atlas;
    this.k = H / 1080;
  }
  blockIcon(g, tile, x, y, s) {
    const T = 16, N = 4;
    g.imageSmoothingEnabled = false;
    g.drawImage(this.atlas.canvas, (tile % N) * T, Math.floor(tile / N) * T, T, T, x, y, s, s);
  }
  icon(g, name, x, y, s) {
    if (name === 'obsidian') return this.blockIcon(g, 9, x, y, s);
    if (name === 'planks') return this.blockIcon(g, 8, x, y, s);
    if (name === 'torch') return this.blockIcon(g, 15, x + s * 0.3, y, s * 0.4);
    const ic = ICONS[name];
    if (!ic) return;
    pix(g, ic[0], ic[1], x, y, s / 12);
  }
  hotbar(g, sel, hasSword, health, xp) {
    const k = this.k, sz = Math.round(66 * k), n = 9;
    const x0 = Math.round(this.W / 2 - (sz * n) / 2), y0 = Math.round(this.H - sz - 16 * k);
    g.fillStyle = 'rgba(20,20,20,0.55)';
    g.fillRect(x0 - 3 * k, y0 - 3 * k, sz * n + 6 * k, sz + 6 * k);
    const items = [hasSword ? 'sword' : null, 'bow', 'arrow', 'obsidian', 'flint', 'bread', 'torch', 'planks', null];
    for (let i = 0; i < n; i++) {
      g.strokeStyle = 'rgba(140,140,140,0.9)';
      g.lineWidth = 3 * k;
      g.strokeRect(x0 + i * sz + 2 * k, y0 + 2 * k, sz - 4 * k, sz - 4 * k);
      if (items[i]) this.icon(g, items[i], x0 + i * sz + 12 * k, y0 + 12 * k, sz - 24 * k);
    }
    if (sel >= 0) {
      g.strokeStyle = '#ffffff'; g.lineWidth = 5 * k;
      g.strokeRect(x0 + sel * sz - 2 * k, y0 - 2 * k, sz + 4 * k, sz + 4 * k);
    }
    drawText(g, '64', x0 + 3 * sz + sz - 10 * k, y0 + sz - 26 * k, 3 * k, '#fff', { align: 'right' });
    // barra de experiencia
    const yb = y0 - 16 * k;
    g.fillStyle = '#111'; g.fillRect(x0, yb, sz * n, 9 * k);
    g.fillStyle = '#7fe33a'; g.fillRect(x0 + 2 * k, yb + 2 * k, (sz * n - 4 * k) * (xp % 1), 5 * k);
    drawText(g, String(Math.floor(xp) + 3), this.W / 2, yb - 22 * k, 3 * k, '#80ff20', { align: 'center', outline: 2 * k, outlineCol: '#000', shadow: false });
    // corazones
    const hs = 4 * k;
    for (let i = 0; i < 10; i++) {
      const f = Math.max(0, Math.min(1, (health - i * 2) / 2));
      heart(g, x0 + i * 30 * k, yb - 40 * k, hs, f >= 1 ? 1 : f > 0 ? 0.5 : 0);
    }
  }
  toast(g, a, title, text, icon) {
    if (a <= 0) return;
    const k = this.k, w = 560 * k, h = 110 * k;
    const x = this.W - w * a - 20 * k, y = 24 * k;
    g.fillStyle = 'rgba(16,16,24,0.92)'; g.fillRect(x, y, w, h);
    g.strokeStyle = '#5a5a7a'; g.lineWidth = 4 * k; g.strokeRect(x + 2 * k, y + 2 * k, w - 4 * k, h - 4 * k);
    this.icon(g, icon, x + 20 * k, y + 22 * k, 66 * k);
    drawText(g, title, x + 104 * k, y + 24 * k, 3 * k, '#ffff55');
    drawText(g, text, x + 104 * k, y + 64 * k, 3 * k, '#ffffff');
  }
  boss(g, a, frac, name) {
    if (a <= 0) return;
    const k = this.k, w = 760 * k, x = this.W / 2 - w / 2, y = 64 * k;
    g.globalAlpha = a;
    drawText(g, name, this.W / 2, 24 * k, 4 * k, '#ffffff', { align: 'center' });
    g.fillStyle = '#2a0a2a'; g.fillRect(x, y, w, 18 * k);
    g.fillStyle = '#ff4dd8'; g.fillRect(x + 3 * k, y + 3 * k, (w - 6 * k) * frac, 12 * k);
    g.fillStyle = 'rgba(255,255,255,0.35)'; g.fillRect(x + 3 * k, y + 3 * k, (w - 6 * k) * frac, 4 * k);
    g.fillStyle = '#2a0a2a';
    for (let i = 1; i < 20; i++) g.fillRect(x + (w / 20) * i, y + 3 * k, 2 * k, 12 * k);
    g.globalAlpha = 1;
  }
  crosshair(g) {
    const k = this.k, c = 14 * k, t = 3 * k;
    g.fillStyle = 'rgba(255,255,255,0.85)';
    g.fillRect(this.W / 2 - c, this.H / 2 - t / 2, c * 2, t);
    g.fillRect(this.W / 2 - t / 2, this.H / 2 - c, t, c * 2);
  }
  title(g, t) {
    const k = this.k;
    // logotipo con relieve de piedra
    const sc = 22 * k;
    const s = 'BLOCKCRAFT';
    const w = textWidth(s, sc);
    const x = this.W / 2 - w / 2, y = this.H * 0.2;
    drawText(g, s, this.W / 2, y, sc, '#3d3d3d', { align: 'center', shadow: false, outline: 4 * k, outlineCol: '#111' });
    const grad = g.createLinearGradient(0, y, 0, y + 7 * sc);
    grad.addColorStop(0, '#e8e8e8'); grad.addColorStop(0.5, '#9a9a9a'); grad.addColorStop(1, '#5e5e5e');
    drawText(g, s, this.W / 2, y - 8 * k, sc, grad, { align: 'center', shadow: false });
    drawText(g, 'LA LEYENDA DE LA DRAGONA', this.W / 2, y + 7 * sc + 34 * k, 7 * k, '#ffffff', { align: 'center' });
    g.save();
    g.translate(x + w - 30 * k, y - 4 * k);
    g.rotate(-0.35);
    const sp = 1 + Math.sin(t * 6) * 0.06;
    g.scale(sp, sp);
    drawText(g, '¡CON SHADERS!', 0, 0, 5 * k, '#ffff40', { align: 'center', shadowCol: '#3f3f00' });
    g.restore();
  }
  chapter(g, a, line1, line2) {
    if (a <= 0) return;
    const k = this.k;
    g.globalAlpha = a;
    g.fillStyle = 'rgba(0,0,0,0.35)';
    g.fillRect(0, this.H * 0.36, this.W, 210 * k);
    drawText(g, line1, this.W / 2, this.H * 0.36 + 40 * k, 5 * k, '#ffd84a', { align: 'center' });
    drawText(g, line2, this.W / 2, this.H * 0.36 + 100 * k, 12 * k, '#ffffff', { align: 'center' });
    g.globalAlpha = 1;
  }
  big(g, a, s, col = '#ffffff', sc = 16) {
    if (a <= 0) return;
    const k = this.k;
    g.globalAlpha = a;
    drawText(g, s, this.W / 2, this.H * 0.4, sc * k, col, { align: 'center', outline: 4 * k, outlineCol: '#2a0a3a', shadow: false });
    g.globalAlpha = 1;
  }
  credits(g, u, list) {
    const k = this.k;
    g.fillStyle = 'rgba(0,0,0,0.55)';
    g.fillRect(0, 0, this.W, this.H);
    const rowH = { big: 150, sub: 80, head: 70, name: 56, small: 48, gap: 70 };
    const before = list.slice(0, list.length - 2).reduce((s, r) => s + rowH[r[0]], 0);
    let y = this.H + 40 * k + u * (this.H * 0.36 - before * k - this.H - 40 * k);
    for (const [kind, s] of list) {
      const h = rowH[kind] * k;
      if (y > -h && y < this.H + h && s) {
        if (kind === 'big') drawText(g, s, this.W / 2, y, 16 * k, '#ffffff', { align: 'center', depth: 3, depthCol: '#555' });
        if (kind === 'sub') drawText(g, s, this.W / 2, y, 6 * k, '#ffd84a', { align: 'center' });
        if (kind === 'head') drawText(g, s, this.W / 2, y, 5 * k, '#ffd84a', { align: 'center' });
        if (kind === 'name') drawText(g, s, this.W / 2, y, 5 * k, '#ffffff', { align: 'center' });
        if (kind === 'small') drawText(g, s, this.W / 2, y, 3 * k, '#bbbbbb', { align: 'center' });
      }
      y += h;
    }
  }
}
