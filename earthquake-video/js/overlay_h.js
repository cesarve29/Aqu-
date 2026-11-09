import { T, NARRATION, smooth, clamp, lerp, groundMotion, shakeEnvelope, rng } from './timeline.js';

const W = 1920, H = 1080;
const ACC = '#ff6a1a';
const F = (w, s) => `${w} ${s}px Inter, "Inter Display", sans-serif`;

function win(t, a, b, fi = 0.5, fo = 0.5) { return smooth(a, a + fi, t) * (1 - smooth(b - fo, b, t)); }
function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }

// Subtitle cues: split each narration segment into its '|' parts, timed by length.
const CUES = [];
for (const [start, f0, f1, text] of NARRATION) {
  const parts = text.split('|');
  const total = parts.reduce((s, p) => s + p.length, 0);
  let t = start + 0.05;
  const dur = f1 - f0;
  for (const p of parts) { const d = dur * p.length / total; CUES.push([t, t + d, p]); t += d; }
}

export class Overlay {
  constructor() {
    this.trace = [];
    const r = rng(9);
    const [c, g] = [document.createElement('canvas'), null];
    c.width = 512; c.height = 512;
    const gx = c.getContext('2d');
    const img = gx.createImageData(512, 512);
    for (let i = 0; i < 512 * 512; i++) { const v = r() * 255; img.data[i * 4] = img.data[i * 4 + 1] = img.data[i * 4 + 2] = v; img.data[i * 4 + 3] = 255; }
    gx.putImageData(img, 0, 0);
    this.grain = c;
    this.gm = { x: 0, y: 0, z: 0 };
  }

  fade(t) {
    // black between shots
    const cuts = [T.introEnd, T.beachCut, T.hillCut, T.globeCut, T.endingCut];
    let a = 1 - smooth(0, 1.5, t);
    for (const c of cuts) a = Math.max(a, 1 - smooth(0, 0.45, Math.abs(t - c)));
    a = Math.max(a, smooth(140.4, 141.8, t));
    return a;
  }

  draw(c, t, frame) {
    c.save();
    // vignette
    const vg = c.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95);
    vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,0.42)');
    c.fillStyle = vg; c.fillRect(0, 0, W, H);
    // film grain
    c.globalAlpha = 0.035; c.globalCompositeOperation = 'overlay';
    const ox = (frame * 137) % 512, oy = (frame * 251) % 512;
    for (let y = -oy; y < H; y += 512) for (let x = -ox; x < W; x += 512) c.drawImage(this.grain, x, y);
    c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';

    this.title(c, t);
    this.scaleInfo(c, t);
    this.labels(c, t);
    this.seismo(c, t);
    this.tips(c, t);
    this.timer(c, t);
    this.tsunami(c, t);
    this.globeLabels(c, t);
    this.checklist(c, t);
    this.endCard(c, t);
    this.subs(c, t);

    const f = this.fade(t);
    if (f > 0.001) { c.fillStyle = `rgba(0,0,0,${f})`; c.fillRect(0, 0, W, H); }
    c.restore();
  }

  shadowText(c, txt, x, y, blur = 18) {
    c.save(); c.shadowColor = 'rgba(0,0,0,0.65)'; c.shadowBlur = blur; c.shadowOffsetY = 3; c.fillText(txt, x, y); c.restore();
  }

  title(c, t) {
    const a = win(t, 1.0, 9.0, 1.2, 1.0);
    if (a > 0) {
      c.save(); c.globalAlpha = a; c.textAlign = 'center';
      const sc = 1 + (t - 1) * 0.006;
      c.translate(W / 2, H * 0.42); c.scale(sc, sc);
      c.fillStyle = '#fff'; c.font = F(800, 168);
      c.letterSpacing = '18px';
      this.shadowText(c, 'MAGNITUD 10', 0, 0, 30);
      c.letterSpacing = '0px';
      c.fillStyle = ACC; c.fillRect(-260 * smooth(1.5, 3, t), 40, 520 * smooth(1.5, 3, t), 8);
      c.fillStyle = 'rgba(255,255,255,0.92)'; c.font = F(500, 46);
      c.globalAlpha = a * smooth(2.4, 3.4, t);
      this.shadowText(c, '¿Qué pasaría si ocurriera hoy?', 0, 120);
      c.restore();
    }
    this.lowerThird(c, t, 10.2, 17.4, 'VALDIVIA, CHILE · 22 DE MAYO DE 1960', 'Magnitud 9,5 — el terremoto más fuerte jamás registrado');
    this.lowerThird(c, t, 104.0, 110.8, 'TSUNAMI', 'Olas de 20 a 30 metros avanzan tierra adentro');
  }

  lowerThird(c, t, a0, a1, head, sub) {
    const a = win(t, a0, a1, 0.6, 0.6);
    if (a <= 0) return;
    const sl = (1 - smooth(a0, a0 + 0.7, t)) * -60;
    c.save(); c.globalAlpha = a; c.translate(sl, 0);
    c.font = F(800, 40); const w1 = c.measureText(head).width;
    c.font = F(500, 32); const w2 = c.measureText(sub).width;
    const w = Math.max(w1, w2) + 80;
    const g = c.createLinearGradient(90, 0, 90 + w, 0);
    g.addColorStop(0, 'rgba(10,14,20,0.82)'); g.addColorStop(1, 'rgba(10,14,20,0.0)');
    c.fillStyle = g; c.fillRect(90, 740, w, 130);
    c.fillStyle = ACC; c.fillRect(90, 740, 8, 130);
    c.fillStyle = '#fff'; c.font = F(800, 40); c.textAlign = 'left'; c.fillText(head, 124, 795);
    c.fillStyle = 'rgba(255,255,255,0.88)'; c.font = F(500, 32); c.fillText(sub, 124, 845);
    c.restore();
  }

  panel(c, x, y, w, h, a) {
    c.save(); c.globalAlpha = a * 0.86;
    c.fillStyle = 'rgba(9,13,20,0.9)'; rr(c, x, y, w, h, 22); c.fill();
    c.globalAlpha = a; c.strokeStyle = 'rgba(255,255,255,0.12)'; c.lineWidth = 2; rr(c, x, y, w, h, 22); c.stroke();
    c.restore();
  }

  scaleInfo(c, t) {
    // energy bars
    const a = win(t, 19.2, 27.4, 0.7, 0.6);
    if (a > 0) {
      const x = 90, y = 150, w = 760, h = 560;
      this.panel(c, x, y, w, h, a);
      c.save(); c.globalAlpha = a;
      c.fillStyle = ACC; c.font = F(800, 26); c.textAlign = 'left'; c.fillText('ENERGÍA LIBERADA', x + 40, y + 62);
      c.fillStyle = 'rgba(255,255,255,0.75)'; c.font = F(500, 24); c.fillText('Cada grado de magnitud ≈ ×32 de energía', x + 40, y + 100);
      const rows = [['M 7,0', 7.0, 'Fuerte'], ['M 8,0', 8.0, 'Gran terremoto'], ['M 9,0', 9.0, 'Japón 2011'], ['M 9,5', 9.5, 'Valdivia 1960'], ['M 10', 10.0, 'Hipotético']];
      rows.forEach(([lab, m, note], i) => {
        const ry = y + 160 + i * 76;
        const frac = Math.pow(10, 1.5 * (m - 10));
        const grow = smooth(20 + i * 0.9, 21.6 + i * 0.9, t);
        const bw = Math.max(4, 480 * frac) * grow;
        c.fillStyle = '#fff'; c.font = F(700, 30); c.fillText(lab, x + 40, ry + 30);
        c.fillStyle = m === 10 ? ACC : m === 9.5 ? '#ffb070' : 'rgba(255,255,255,0.65)';
        rr(c, x + 170, ry + 6, bw, 32, 8); c.fill();
        c.fillStyle = 'rgba(255,255,255,0.7)'; c.font = F(500, 22);
        const ratio = Math.round(Math.pow(10, 1.5 * (m - 7)));
        c.fillText(`${note} · ×${ratio.toLocaleString('es-ES')}`, x + 180 + Math.max(bw, 4) + (m === 10 ? -470 : 8), ry + 30 + (m === 10 ? 46 : 0));
      });
      c.restore();
    }
    // rupture length
    const b = win(t, 27.6, 35.0, 0.7, 0.6);
    if (b > 0) {
      const x = 90, y = 170, w = 760, h = 470;
      this.panel(c, x, y, w, h, b);
      c.save(); c.globalAlpha = b;
      c.fillStyle = ACC; c.font = F(800, 26); c.textAlign = 'left'; c.fillText('LONGITUD DE LA RUPTURA', x + 40, y + 62);
      const L = 620;
      const k1 = smooth(28.2, 29.6, t), k2 = smooth(29.4, 32.4, t);
      c.fillStyle = 'rgba(255,255,255,0.85)'; c.font = F(600, 26); c.fillText('Valdivia 1960', x + 40, y + 140);
      c.strokeStyle = '#ffb070'; c.lineWidth = 12; c.lineCap = 'round';
      c.beginPath(); c.moveTo(x + 40, y + 175); c.lineTo(x + 40 + L * 0.24 * k1, y + 175); c.stroke();
      c.fillStyle = 'rgba(255,255,255,0.8)'; c.font = F(500, 24); c.fillText('~1.000 km', x + 60 + L * 0.24, y + 184);
      c.fillStyle = 'rgba(255,255,255,0.85)'; c.font = F(600, 26); c.fillText('Magnitud 10', x + 40, y + 260);
      c.strokeStyle = ACC;
      c.beginPath();
      for (let i = 0; i <= 60; i++) { const px = x + 40 + L * k2 * i / 60; const py = y + 295 + Math.sin(i * 0.9 + t * 6) * 3 * k2; if (i === 0) c.moveTo(px, py); else c.lineTo(px, py); }
      c.stroke();
      c.fillStyle = '#fff'; c.font = F(800, 44); c.fillText(`${Math.round(4000 * k2).toLocaleString('es-ES')}+ km`, x + 40, y + 380);
      c.fillStyle = 'rgba(255,255,255,0.7)'; c.font = F(500, 24); c.fillText('≈ toda la costa de Chile rompiéndose a la vez', x + 40, y + 425);
      c.restore();
    }
  }

  tag(c, t, a0, a1, big, small, color = ACC) {
    const a = win(t, a0, a1, 0.4, 0.6);
    if (a <= 0) return;
    c.save(); c.globalAlpha = a;
    c.font = F(800, 46); const w1 = c.measureText(big).width;
    c.font = F(500, 26); const w2 = c.measureText(small).width;
    const w = Math.max(w1, w2) + 70;
    c.fillStyle = 'rgba(8,11,16,0.75)'; rr(c, 90, 110, w, 128, 16); c.fill();
    c.fillStyle = color; c.fillRect(90, 110, 8, 128);
    c.fillStyle = '#fff'; c.font = F(800, 46); c.textAlign = 'left'; c.fillText(big, 122, 166);
    c.fillStyle = 'rgba(255,255,255,0.85)'; c.font = F(500, 26); c.fillText(small, 122, 210);
    c.restore();
  }

  labels(c, t) {
    this.tag(c, t, 41.4, 47.6, 'ONDAS P', 'Compresión · ~6 km/s · llegan primero', '#ffd23f');
    this.tag(c, t, 49.3, 56.0, 'ONDAS S', 'Cizalla · ~3,5 km/s · las más destructivas', '#ff3b30');
    this.tag(c, t, 77.0, 83.0, 'LICUEFACCIÓN', 'El suelo saturado pierde su firmeza', '#4fc3f7');
    const a = win(t, 89.2, 92.0, 0.5, 0.6);
    if (a > 0) {
      c.save(); c.globalAlpha = a; c.textAlign = 'center'; c.fillStyle = '#fff'; c.font = F(500, 40);
      this.shadowText(c, 'Minutos después…', W / 2, 160); c.restore();
    }
  }

  seismo(c, t) {
    const a = win(t, 38.5, 88.6, 0.8, 0.6);
    // keep trace history even when hidden
    if (a <= 0) return;
    this.trace = [];
    for (let i = 0; i < 240; i++) {
      const tt = t - (239 - i) / 30;
      groundMotion(tt, this.gm);
      this.trace.push(this.gm.x + this.gm.z * 0.5 + Math.sin(tt * 40) * 0.004);
    }
    const x = W - 520, y = 90, w = 430, h = 150;
    c.save(); c.globalAlpha = a;
    c.fillStyle = 'rgba(245,242,232,0.92)'; rr(c, x, y, w, h, 14); c.fill();
    c.strokeStyle = 'rgba(0,0,0,0.12)'; c.lineWidth = 1;
    for (let i = 1; i < 6; i++) { c.beginPath(); c.moveTo(x, y + i * h / 6); c.lineTo(x + w, y + i * h / 6); c.stroke(); }
    c.strokeStyle = '#b3001b'; c.lineWidth = 2.2; c.beginPath();
    const n = this.trace.length;
    for (let i = 0; i < n; i++) {
      const px = x + 10 + (w - 20) * i / 239, py = y + h / 2 + clamp(this.trace[i] * 95, -h / 2 + 6, h / 2 - 6);
      if (i === 0) c.moveTo(px, py); else c.lineTo(px, py);
    }
    c.stroke();
    c.fillStyle = '#222'; c.font = F(700, 18); c.textAlign = 'left'; c.fillText('SISMÓGRAFO', x + 14, y + 26);
    const e = shakeEnvelope(t);
    c.textAlign = 'right';
    c.fillStyle = e > 0.3 ? '#b3001b' : '#444'; c.font = F(800, 22);
    c.fillText(t > T.sStart ? 'M 10,0' : t > T.pStart ? 'Ondas P' : 'Normal', x + w - 14, y + 28);
    c.restore();
  }

  tips(c, t) {
    const a = win(t, 64.6, 70.6, 0.4, 0.6);
    if (a <= 0) return;
    const items = [['AGÁCHATE', '⬇'], ['CÚBRETE', '⛉'], ['SUJÉTATE', '✊']];
    c.save();
    items.forEach(([txt, ic], i) => {
      const k = smooth(65.0 + i * 0.7, 65.5 + i * 0.7, t) * a;
      const bx = W / 2 - 560 + i * 330, by = 150;
      c.globalAlpha = k;
      c.fillStyle = 'rgba(8,11,16,0.78)'; rr(c, bx, by - (1 - k) * 20, 300, 110, 18); c.fill();
      c.fillStyle = ACC; rr(c, bx, by - (1 - k) * 20, 300, 8, 4); c.fill();
      c.fillStyle = '#fff'; c.textAlign = 'center'; c.font = F(800, 40); c.fillText(txt, bx + 150, by + 72 - (1 - k) * 20);
    });
    c.restore();
  }

  timer(c, t) {
    const a = win(t, 70.6, 76.4, 0.4, 0.6);
    if (a <= 0) return;
    const k = smooth(71.2, 75.6, t);
    const secs = Math.floor(Math.pow(k, 1.6) * 1200);
    const mm = String(Math.floor(secs / 60)).padStart(2, '0'), ss = String(secs % 60).padStart(2, '0');
    c.save(); c.globalAlpha = a;
    c.fillStyle = 'rgba(8,11,16,0.78)'; rr(c, W / 2 - 250, 130, 500, 170, 20); c.fill();
    c.fillStyle = 'rgba(255,255,255,0.8)'; c.font = F(600, 24); c.textAlign = 'center'; c.fillText('DURACIÓN DEL TEMBLOR', W / 2, 175);
    c.fillStyle = '#fff'; c.font = F(800, 92); c.fillText(`${mm}:${ss}`, W / 2, 270);
    c.fillStyle = 'rgba(255,255,255,0.55)'; c.font = F(500, 20); c.fillText('Un sismo típico: 30 s – 2 min', W / 2, 330 - 8);
    c.restore();
  }

  tsunami(c, t) {
    const a = win(t, T.tsunamiAlarm, 100.6, 0.25, 0.5);
    if (a <= 0) return;
    const blink = 0.75 + 0.25 * Math.sin(t * 10);
    c.save(); c.globalAlpha = a;
    c.fillStyle = `rgba(200,16,24,${0.88 * blink})`; c.fillRect(0, 96, W, 112);
    c.fillStyle = '#fff'; c.textAlign = 'center'; c.font = F(800, 50);
    c.fillText('⚠  ALERTA DE TSUNAMI  ·  EVACÚA A ZONA ALTA  ⚠', W / 2, 170);
    c.restore();
  }

  globeLabels(c, t) {
    const items = [
      [113.2, 118.0, 'LA TIERRA VIBRA', 'Las ondas sísmicas recorren el planeta durante días', W - 900, 160],
      [116.6, 122.6, 'EJE TERRESTRE', 'Se desplazaría varios centímetros', W - 900, 330],
      [118.6, 123.6, 'DURACIÓN DEL DÍA', '− unos microsegundos', W - 900, 500],
    ];
    for (const [a0, a1, h, s, x, y] of items) {
      const a = win(t, a0, a1, 0.6, 0.6);
      if (a <= 0) continue;
      c.save(); c.globalAlpha = a; c.textAlign = 'left';
      c.fillStyle = 'rgba(10,16,30,0.6)'; rr(c, x, y, 780, 130, 16); c.fill();
      c.fillStyle = '#7fc8ff'; c.fillRect(x, y, 6, 130);
      c.fillStyle = '#fff'; c.font = F(800, 40); c.fillText(h, x + 34, y + 58);
      c.fillStyle = 'rgba(255,255,255,0.85)'; c.font = F(500, 28); c.fillText(s, x + 34, y + 102);
      c.restore();
    }
  }

  checklist(c, t) {
    const a = win(t, 128.4, 136.6, 0.6, 0.6);
    if (a <= 0) return;
    const items = [[130.0, 'Conoce tu zona segura'], [131.4, 'Ten un plan familiar'], [132.8, 'Prepara una mochila de emergencia']];
    const x = 90, y = 140;
    this.panel(c, x, y, 720, 360, a);
    c.save(); c.globalAlpha = a; c.textAlign = 'left';
    c.fillStyle = ACC; c.font = F(800, 28); c.fillText('ESTAR PREPARADO', x + 40, y + 62);
    items.forEach(([t0, txt], i) => {
      const k = smooth(t0, t0 + 0.5, t);
      const yy = y + 130 + i * 80;
      c.globalAlpha = a * k;
      c.fillStyle = '#2ecc71'; c.beginPath(); c.arc(x + 62, yy - 10, 22, 0, 7); c.fill();
      c.strokeStyle = '#fff'; c.lineWidth = 5; c.lineCap = 'round'; c.lineJoin = 'round';
      c.beginPath(); c.moveTo(x + 51, yy - 10); c.lineTo(x + 59, yy - 2); c.lineTo(x + 74, yy - 19); c.stroke();
      c.fillStyle = '#fff'; c.font = F(600, 34); c.fillText(txt, x + 104, yy);
    });
    c.restore();
  }

  endCard(c, t) {
    const a = smooth(T.endCard, T.endCard + 1.2, t);
    if (a <= 0) return;
    c.save();
    c.fillStyle = `rgba(0,0,0,${0.62 * a})`; c.fillRect(0, 0, W, H);
    c.globalAlpha = a; c.textAlign = 'center'; c.fillStyle = '#fff';
    c.font = F(800, 120); c.letterSpacing = '14px'; c.fillText('MAGNITUD 10', W / 2, H / 2 - 20); c.letterSpacing = '0px';
    c.fillStyle = ACC; c.fillRect(W / 2 - 200, H / 2 + 20, 400, 6);
    c.fillStyle = 'rgba(255,255,255,0.9)'; c.font = F(500, 40); c.fillText('Infórmate. Prepárate. Protégete.', W / 2, H / 2 + 100);
    c.restore();
  }

  subs(c, t) {
    if (t > T.endCard) return;
    for (const [a0, a1, txt] of CUES) {
      if (t < a0 - 0.1 || t > a1 + 0.25) continue;
      const a = win(t, a0 - 0.1, a1 + 0.25, 0.15, 0.2);
      c.save(); c.globalAlpha = a;
      c.font = F(600, 40); c.textAlign = 'center';
      const w = c.measureText(txt).width + 48;
      c.fillStyle = 'rgba(0,0,0,0.55)'; rr(c, W / 2 - w / 2, H - 150, w, 64, 12); c.fill();
      c.fillStyle = '#fff'; c.fillText(txt, W / 2, H - 104);
      c.restore();
    }
  }
}
