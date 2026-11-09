import * as THREE from 'three';
import { rng } from './timeline.js';

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return [c, c.getContext('2d')];
}

function tex(c, repeat = true, srgb = true) {
  const t = new THREE.CanvasTexture(c);
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; }
  t.anisotropy = 8;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.needsUpdate = true;
  return t;
}

function noiseFill(ctx, w, h, base, amp, r, scale = 1) {
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  for (let i = 0; i < w * h; i++) {
    const n = (r() - 0.5) * amp;
    d[i * 4] = Math.max(0, Math.min(255, base[0] + n));
    d[i * 4 + 1] = Math.max(0, Math.min(255, base[1] + n));
    d[i * 4 + 2] = Math.max(0, Math.min(255, base[2] + n));
    d[i * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}

// Facade: one texture tile = 4 window columns x 4 floors (12 m x 12.8 m).
export function facadeTexture(style, seed) {
  const r = rng(seed);
  const W = 512, H = 512;
  const [c, g] = canvas(W, H);
  const cols = 4, rows = 4;
  const cw = W / cols, rh = H / rows;
  if (style === 'glass') {
    // curtain wall
    const grd = g.createLinearGradient(0, 0, 0, H);
    grd.addColorStop(0, '#7f9fb6'); grd.addColorStop(1, '#4d6b82');
    g.fillStyle = grd; g.fillRect(0, 0, W, H);
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols * 2; x++) {
      const v = 0.85 + r() * 0.3;
      g.fillStyle = `rgba(${150 * v},${185 * v},${210 * v},0.35)`;
      g.fillRect(x * cw / 2 + 2, y * rh + 6, cw / 2 - 4, rh - 10);
      if (r() < 0.25) { g.fillStyle = 'rgba(240,230,200,0.18)'; g.fillRect(x * cw / 2 + 2, y * rh + 6, cw / 2 - 4, rh * 0.5); }
    }
    g.fillStyle = '#2b3640';
    for (let y = 0; y <= rows; y++) g.fillRect(0, y * rh - 3, W, 7);
    for (let x = 0; x <= cols * 2; x++) g.fillRect(x * cw / 2 - 2, 0, 4, H);
    return tex(c);
  }
  // masonry / concrete with punched windows
  const base = style === 'brick' ? [150, 92, 70] : style === 'stucco' ? [214, 202, 182] : [176, 172, 165];
  noiseFill(g, W, H, base, 26, r);
  if (style === 'brick') {
    g.strokeStyle = 'rgba(70,40,30,0.25)'; g.lineWidth = 1;
    for (let y = 0; y < H; y += 8) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
  }
  for (let y = 0; y < rows; y++) {
    // floor slab line
    g.fillStyle = 'rgba(0,0,0,0.12)'; g.fillRect(0, y * rh + rh - 6, W, 6);
    for (let x = 0; x < cols; x++) {
      const wx = x * cw + cw * 0.18, wy = y * rh + rh * 0.2, ww = cw * 0.64, wh = rh * 0.56;
      g.fillStyle = 'rgba(0,0,0,0.35)'; g.fillRect(wx - 4, wy - 4, ww + 8, wh + 8);
      const lit = r();
      const sky = g.createLinearGradient(0, wy, 0, wy + wh);
      sky.addColorStop(0, lit < 0.15 ? '#c9b98f' : '#8ea7bb');
      sky.addColorStop(1, lit < 0.15 ? '#7a6a4c' : '#33434f');
      g.fillStyle = sky; g.fillRect(wx, wy, ww, wh);
      // curtains / frames
      if (r() < 0.4) { g.fillStyle = `rgba(${200 + r() * 50},${190 + r() * 40},${160 + r() * 40},0.75)`; g.fillRect(wx, wy, ww * (0.2 + r() * 0.3), wh); }
      g.fillStyle = '#e8e4dc'; g.fillRect(wx + ww / 2 - 2, wy, 4, wh); g.fillRect(wx, wy + wh * 0.35, ww, 3);
      // sill
      g.fillStyle = 'rgba(255,255,255,0.5)'; g.fillRect(wx - 6, wy + wh + 2, ww + 12, 5);
      if (style === 'stucco' && r() < 0.35) { // balcony
        g.fillStyle = 'rgba(40,40,40,0.8)'; g.fillRect(wx - 8, wy + wh * 0.62, ww + 16, 3);
        for (let k = 0; k < 9; k++) g.fillRect(wx - 8 + k * (ww + 16) / 8, wy + wh * 0.62, 2, wh * 0.38);
      }
    }
  }
  return tex(c);
}

export function shopTexture(seed) {
  const r = rng(seed);
  const W = 512, H = 192;
  const [c, g] = canvas(W, H);
  noiseFill(g, W, H, [120, 116, 110], 18, r);
  const n = 2;
  const colors = ['#c0392b', '#2e86c1', '#27ae60', '#d68910', '#7d3c98', '#1f618d', '#a04000'];
  for (let i = 0; i < n; i++) {
    const x0 = i * W / n + 10, w = W / n - 20;
    g.fillStyle = colors[Math.floor(r() * colors.length)];
    g.fillRect(x0, 18, w, 34); // sign band
    g.fillStyle = 'rgba(255,255,255,0.85)';
    g.font = 'bold 22px Inter, sans-serif';
    const names = ['CAFÉ', 'FARMACIA', 'PANADERÍA', 'LIBRERÍA', 'MERCADO', 'ÓPTICA', 'FLORES', 'BAR', 'BANCO', 'MODA'];
    g.fillText(names[Math.floor(r() * names.length)], x0 + 12, 44);
    const gl = g.createLinearGradient(0, 60, 0, H);
    gl.addColorStop(0, '#9fb4c2'); gl.addColorStop(0.5, '#40525e'); gl.addColorStop(1, '#2a343b');
    g.fillStyle = gl; g.fillRect(x0, 60, w, H - 64);
    g.fillStyle = 'rgba(255,240,210,0.25)'; g.fillRect(x0 + 6, 80, w * 0.6, 40);
    g.fillStyle = '#222'; g.fillRect(x0 + w * 0.7, 70, w * 0.22, H - 74); // door
    g.fillStyle = '#ddd'; g.fillRect(x0, 60, w, 3);
  }
  return tex(c);
}

export function asphaltTexture() {
  const r = rng(11);
  const W = 512, H = 512;
  const [c, g] = canvas(W, H);
  noiseFill(g, W, H, [62, 63, 66], 30, r);
  for (let i = 0; i < 40; i++) { // patches / stains
    g.fillStyle = `rgba(${r() < 0.5 ? 30 : 90},${r() < 0.5 ? 30 : 90},${r() < 0.5 ? 32 : 92},0.08)`;
    g.beginPath(); g.ellipse(r() * W, r() * H, 10 + r() * 50, 5 + r() * 30, r() * 3, 0, 7); g.fill();
  }
  return tex(c);
}

export function roadMarkTexture() {
  // 10 m wide road along v. u across road. 1 tile = 10 m x 12 m
  const W = 256, H = 256;
  const [c, g] = canvas(W, H);
  g.clearRect(0, 0, W, H);
  g.fillStyle = 'rgba(240,240,230,0.92)';
  g.fillRect(W / 2 - 3, 0, 6, H * 0.5); // dashed center
  g.fillStyle = 'rgba(240,240,230,0.85)';
  g.fillRect(6, 0, 4, H); g.fillRect(W - 10, 0, 4, H);
  const t = tex(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function sidewalkTexture() {
  const r = rng(12);
  const W = 512, H = 512;
  const [c, g] = canvas(W, H);
  noiseFill(g, W, H, [178, 174, 166], 22, r);
  g.strokeStyle = 'rgba(80,78,72,0.45)'; g.lineWidth = 3;
  for (let i = 0; i <= 8; i++) { g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64, H); g.stroke(); g.beginPath(); g.moveTo(0, i * 64); g.lineTo(W, i * 64); g.stroke(); }
  for (let i = 0; i < 64; i++) { const v = r() * 20 - 10; g.fillStyle = `rgba(${128 + v},${120 + v},${110 + v},0.12)`; g.fillRect((i % 8) * 64, Math.floor(i / 8) * 64, 64, 64); }
  return tex(c);
}

export function plazaTexture() {
  const r = rng(13);
  const W = 512, H = 512;
  const [c, g] = canvas(W, H);
  noiseFill(g, W, H, [190, 170, 140], 20, r);
  g.strokeStyle = 'rgba(110,90,70,0.5)'; g.lineWidth = 2;
  for (let y = 0; y < 16; y++) for (let x = 0; x < 8; x++) {
    const off = (y % 2) * 32;
    g.strokeRect(x * 64 + off, y * 32, 64, 32);
    const v = r() * 30 - 15; g.fillStyle = `rgba(${170 + v},${140 + v},${110 + v},0.25)`; g.fillRect(x * 64 + off + 1, y * 32 + 1, 62, 30);
  }
  return tex(c);
}

export function sandTexture() {
  const r = rng(14);
  const [c, g] = canvas(512, 512);
  noiseFill(g, 512, 512, [205, 186, 150], 30, r);
  return tex(c);
}

export function grassTexture() {
  const r = rng(15);
  const [c, g] = canvas(512, 512);
  noiseFill(g, 512, 512, [86, 122, 60], 40, r);
  for (let i = 0; i < 4000; i++) {
    const v = r();
    g.strokeStyle = `rgba(${50 + v * 80},${100 + v * 70},${30 + v * 40},0.6)`;
    const x = r() * 512, y = r() * 512;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 3, y - 4 - r() * 6); g.stroke();
  }
  return tex(c);
}

export function waterNormalTexture() {
  // tileable normal map from summed sines
  const W = 256, H = 256;
  const [c, g] = canvas(W, H);
  const img = g.createImageData(W, H);
  const r = rng(16);
  const waves = [];
  for (let i = 0; i < 18; i++) waves.push([Math.floor(1 + r() * 6) * (r() < 0.5 ? -1 : 1), Math.floor(1 + r() * 6) * (r() < 0.5 ? -1 : 1), r() * 6.28, 1 / (1 + i * 0.35)]);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    let dx = 0, dy = 0;
    for (const [kx, ky, ph, a] of waves) {
      const v = Math.cos((kx * x / W + ky * y / H) * 6.2832 + ph) * a;
      dx += v * kx; dy += v * ky;
    }
    const nx = -dx * 0.06, ny = -dy * 0.06;
    const l = Math.hypot(nx, ny, 1);
    const i = (y * W + x) * 4;
    img.data[i] = (nx / l * 0.5 + 0.5) * 255;
    img.data[i + 1] = (ny / l * 0.5 + 0.5) * 255;
    img.data[i + 2] = (1 / l * 0.5 + 0.5) * 255;
    img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  return tex(c, true, false);
}

export function softDotTexture() {
  const [c, g] = canvas(128, 128);
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)');
  gr.addColorStop(0.4, 'rgba(255,255,255,0.55)');
  gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return tex(c, false);
}

export function smokeTexture() {
  const r = rng(17);
  const [c, g] = canvas(256, 256);
  for (let i = 0; i < 60; i++) {
    const x = 128 + (r() - 0.5) * 120, y = 128 + (r() - 0.5) * 120, rad = 20 + r() * 60;
    const gr = g.createRadialGradient(x, y, 0, x, y, rad);
    gr.addColorStop(0, 'rgba(255,255,255,0.18)');
    gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  }
  // fade edges
  const img = g.getImageData(0, 0, 256, 256);
  for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
    const d = Math.hypot(x - 128, y - 128) / 128;
    img.data[(y * 256 + x) * 4 + 3] *= Math.max(0, 1 - d * d);
  }
  g.putImageData(img, 0, 0);
  return tex(c, false);
}

export function earthTexture() {
  // Stylised planet: value-noise continents, ice caps, cloud wisps.
  const W = 2048, H = 1024;
  const [c, g] = canvas(W, H);
  const img = g.createImageData(W, H);
  const r = rng(99);
  const P = [];
  for (let i = 0; i < 512; i++) P.push(r());
  const hash = (x, y, z) => P[((x * 73856093) ^ (y * 19349663) ^ (z * 83492791)) & 511];
  const vnoise = (x, y, z) => {
    const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
    const xf = x - xi, yf = y - yi, zf = z - zi;
    const s = (t) => t * t * (3 - 2 * t);
    const u = s(xf), v = s(yf), w = s(zf);
    let res = 0;
    for (let dz = 0; dz < 2; dz++) for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) {
      res += hash(xi + dx, yi + dy, zi + dz) * (dx ? u : 1 - u) * (dy ? v : 1 - v) * (dz ? w : 1 - w);
    }
    return res;
  };
  const fbm = (x, y, z) => { let a = 0.5, s = 0, f = 1; for (let i = 0; i < 6; i++) { s += a * vnoise(x * f, y * f, z * f); a *= 0.5; f *= 2.03; } return s; };
  for (let y = 0; y < H; y++) {
    const lat = (0.5 - y / H) * Math.PI;
    for (let x = 0; x < W; x++) {
      const lon = (x / W) * Math.PI * 2;
      const px = Math.cos(lat) * Math.cos(lon), py = Math.sin(lat), pz = Math.cos(lat) * Math.sin(lon);
      const h = fbm(px * 2.2 + 10, py * 2.2 + 10, pz * 2.2 + 10);
      const i = (y * W + x) * 4;
      let col;
      const ice = Math.abs(lat) > 1.25 + (h - 0.5) * 0.3;
      if (ice) col = [235, 240, 245];
      else if (h > 0.53) {
        const m = (h - 0.53) * 4;
        const dry = Math.abs(Math.abs(lat) - 0.4) < 0.18 ? 1 : 0;
        col = dry ? [190 - m * 40, 160 - m * 40, 110 - m * 30] : [70 + m * 60, 110 + m * 20, 50 + m * 20];
      } else {
        const d = Math.max(0, 0.53 - h) * 3;
        col = [18 - d * 10, 60 - d * 20, 120 - d * 25];
        if (h > 0.5) col = [40, 110, 150];
      }
      img.data[i] = col[0]; img.data[i + 1] = col[1]; img.data[i + 2] = col[2]; img.data[i + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  const t = tex(c, false);
  t.wrapS = THREE.RepeatWrapping;
  return t;
}

export function phoneScreenCanvas() {
  return canvas(360, 720);
}
