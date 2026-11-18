// Set del astrolabio: sol, corona de puntas, aros de cobre, bandas con relieves dorados y logo.
import { THREE, Grid, vox, mat, bitmap, emoji, hash3, clamp, lerp, rad } from './kit.js';

const BRONZE = [0x2c2018, 0x3a2a1e, 0x332519, 0x46331f];
const GOLD = [0xd7a640, 0xb8862c, 0xf0c560, 0x9c6d22];
const pick = (arr, h) => arr[Math.floor(h * arr.length) % arr.length];

// ---------------------------------------------------------------------------
// banda "heroe": tramo recto de banda con relieve, voxel fino
// bmp: bitmap alfa del relieve (w x h) ; L,Wd en voxeles
// ---------------------------------------------------------------------------
function heroBand(bmp, L, Wd, v) {
  const T = 7; // grosor base
  const g = new Grid(L, Wd, T + 4);
  const bx = (x, y) => bmp.at(x / L * bmp.w, (Wd - 1 - y) / Wd * bmp.h);
  for (let x = 0; x < L; x++) for (let y = 0; y < Wd; y++) {
    const edge = y < 2 || y >= Wd - 2;
    const grain = hash3(x >> 3, y, 7) * 0.5 + hash3(x, y >> 2, 3) * 0.5;
    const base = pick(BRONZE, grain);
    let top = T - 1 + (edge ? 1 : 0);
    // pequenos desniveles del bronce martillado
    for (let z = 0; z <= top; z++) g.set(x, y, z, base);
    const a = bx(x + 0.5, y + 0.5);
    if (a > 0.45 && !edge) {
      const lu = bmp.lum(x / L * bmp.w, (Wd - 1 - y) / Wd * bmp.h);
      const h = lu < 0.18 ? 1 : (lu < 0.45 ? 2 : 3);
      for (let z = top + 1; z <= top + h; z++) g.set(x, y, z, pick(GOLD, hash3(x, y, z)));
    }
  }
  return vox(g, v, [L / 2, Wd / 2, T], 'bronze', { roughness: 0.55, metalness: 0.45 });
}

// relieves: dibujados con emoji/simbolos sobre canvas
function reliefBitmap(kind) {
  const W = 1200, H = 120;
  return bitmap(W, H, (x) => {
    x.fillStyle = '#000';
    const orn = (cx) => { // volutas
      x.lineWidth = 6; x.strokeStyle = '#000';
      for (const s of [-1, 1]) { x.beginPath(); x.arc(cx + s * 28, 60 + s * 12, 22, 0, Math.PI * 1.6); x.stroke(); x.beginPath(); x.arc(cx + s * 28, 60 + s * 12, 9, 0, Math.PI * 1.8); x.stroke(); }
    };
    if (kind === 'dragons') {
      orn(90); orn(1110);
      emoji(x, '🐉', 330, 62, 92);
      emoji(x, '🏰', 560, 66, 84);
      emoji(x, '🔥', 455, 60, 54);
      x.save(); x.translate(800, 58); x.scale(-1, 1); emoji(x, '🐉', 0, 0, 98); x.restore();
      emoji(x, '🐲', 990, 60, 64);
    } else if (kind === 'lion') {
      orn(80); orn(1120);
      // muro de ladrillos al centro
      x.lineWidth = 3; x.strokeStyle = '#000';
      for (let r = 0; r < 5; r++) for (let c = 0; c < 6; c++) x.strokeRect(520 + c * 26 + (r % 2) * 13, 14 + r * 20, 26, 20);
      emoji(x, '🦁', 330, 62, 96);
      emoji(x, '🤺', 620, 64, 88);
      emoji(x, '🗡️', 860, 60, 70);
      emoji(x, '👑', 960, 60, 60);
    } else if (kind === 'targ') {
      orn(90); orn(1110);
      emoji(x, '☄️', 300, 40, 66);
      x.fillRect(150, 34, 140, 8);
      emoji(x, '🐉', 600, 66, 104);
      emoji(x, '🐲', 470, 54, 52);
      emoji(x, '🐲', 735, 50, 52);
      emoji(x, '🔥', 880, 62, 58);
    }
  });
}

// aro de seccion rectangular (voxel) radio R, ancho w, grosor t (en unidades)
function ringMesh(R, w, t, v, colors, key) {
  const n = Math.ceil((R + t) * 2 / v) + 2, nh = Math.ceil(w / v);
  const g = new Grid(n, n, nh);
  const c = n / 2;
  for (let x = 0; x < n; x++) for (let y = 0; y < n; y++) {
    const r = Math.hypot(x + 0.5 - c, y + 0.5 - c) * v;
    if (r < R - t / 2 || r > R + t / 2) continue;
    const ang = Math.atan2(y - c, x - c);
    for (let z = 0; z < nh; z++) g.set(x, y, z, pick(colors, hash3(Math.floor(ang * 40), z, 1) * 0.6 + hash3(x, y, z) * 0.4));
  }
  return vox(g, v, [c, c, nh / 2], key, { roughness: 0.4, metalness: 0.85 });
}

// corona de puntas: anillo con dientes triangulares hacia dentro
function crownMesh(R0, R1, nTeeth, v) {
  const n = Math.ceil(R1 * 2 / v) + 4, c = n / 2;
  const g = new Grid(n, n, 2);
  for (let x = 0; x < n; x++) for (let y = 0; y < n; y++) {
    const dx = (x + 0.5 - c) * v, dy = (y + 0.5 - c) * v;
    const r = Math.hypot(dx, dy), a = Math.atan2(dy, dx);
    const f = ((a / (Math.PI * 2)) * nTeeth % 1 + 1) % 1; // 0..1 en cada diente
    const tri = 1 - Math.abs(f - 0.5) * 2; // 0 en bordes, 1 en centro
    const inner = R1 - (R1 - R0) * tri; // punta hacia dentro
    const ring = r > R1 - 0.05 && r < R1 + 0.06;
    if ((r >= inner && r <= R1) || ring) for (let z = 0; z < 2; z++) g.set(x, y, z, hash3(x, y, z) < 0.5 ? 0x55514c : 0x625d56);
  }
  return vox(g, v, [c, c, 1], 'crown', { roughness: 0.35, metalness: 0.9 });
}

function sunburstTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 1024;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(512, 512, 0, 512, 512, 512);
  g.addColorStop(0, 'rgba(255,250,235,1)'); g.addColorStop(0.12, 'rgba(255,240,210,0.95)');
  g.addColorStop(0.3, 'rgba(255,225,180,0.35)'); g.addColorStop(1, 'rgba(255,210,160,0)');
  x.fillStyle = g; x.fillRect(0, 0, 1024, 1024);
  x.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 90; i++) {
    const a = (i / 90) * Math.PI * 2 + hash3(i, 1, 2) * 0.03;
    const L = 280 + hash3(i, 3, 4) * 220, wdt = 0.006 + hash3(i, 5, 6) * 0.01;
    const gr = x.createLinearGradient(512, 512, 512 + Math.cos(a) * L, 512 + Math.sin(a) * L);
    gr.addColorStop(0, 'rgba(255,245,220,0.35)'); gr.addColorStop(1, 'rgba(255,230,190,0)');
    x.fillStyle = gr; x.beginPath(); x.moveTo(512, 512);
    x.lineTo(512 + Math.cos(a - wdt) * L, 512 + Math.sin(a - wdt) * L);
    x.lineTo(512 + Math.cos(a + wdt) * L, 512 + Math.sin(a + wdt) * L); x.fill();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// ---------------------------------------------------------------------------
// logo GAME OF THRONES: medallon + barra con texto luminoso + cuatro cabezas
// ---------------------------------------------------------------------------
function logoMesh() {
  const v = 0.02;
  const L = 300, Hh = 170, D = 12; // 6 x 3.4 unidades
  const g = new Grid(L, Hh, D);
  const cx = L / 2, cy = Hh / 2;
  const R = 62; // radio del medallon (voxeles)
  const barH = 34;
  const text = bitmap(L * 2, barH * 2, (x, w, h) => {
    x.fillStyle = '#fff'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.font = `700 ${h * 0.62}px Cinzel`;
    const s1 = 'GAME', s2 = 'THRONES';
    x.font = `700 ${h * 0.56}px Cinzel`;
    const w1 = x.measureText(s1).width, w2 = x.measureText(s2).width;
    x.font = `700 ${h * 0.26}px Cinzel`; const wo = x.measureText('OF').width;
    const tot = w1 + w2 + wo + 16; let px = w / 2 - tot / 2;
    x.textAlign = 'left';
    x.font = `700 ${h * 0.56}px Cinzel`; x.fillText(s1, px, h * 0.55); px += w1 + 8;
    x.font = `700 ${h * 0.26}px Cinzel`; x.fillText('OF', px, h * 0.5); px += wo + 8;
    x.font = `700 ${h * 0.56}px Cinzel`; x.fillText(s2, px, h * 0.55);
  });
  const heads = bitmap(L, Hh, (x) => {
    const put = (ch, px, py, s, flip) => { x.save(); x.translate(px, py); if (flip) x.scale(-1, 1); emoji(x, ch, 0, 0, s); x.restore(); };
    put('🐉', cx - 44, cy - 54, 30, true);
    put('🦁', cx + 44, cy - 53, 28, false);
    put('🐺', cx - 44, cy + 54, 28, false);
    put('🦌', cx + 46, cy + 53, 30, true);
  });
  const IRON = [0x17110d, 0x1e1611, 0x251b14];
  for (let x = 0; x < L; x++) for (let y = 0; y < Hh; y++) {
    const dx = x + 0.5 - cx, dy = y + 0.5 - cy, r = Math.hypot(dx, dy);
    const inBar = Math.abs(dy) < barH / 2 && Math.abs(dx) < L / 2 - 4;
    const inDisc = r < R;
    const head = heads.at(x, Hh - 1 - y) > 0.5;
    if (!inBar && !inDisc && !head) continue;
    let d0 = 0, d1 = 5;
    if (inDisc && !inBar) { d1 = r > R - 5 ? 8 : 6; if (r > R - 9 && r < R - 6) d1 = 5; }
    if (inBar) d1 = Math.abs(dy) > barH / 2 - 3 ? 9 : 7;
    if (head && !inDisc && !inBar) { d0 = 2; d1 = 8; }
    for (let z = d0; z <= d1; z++) g.set(x, y, z, pick(IRON, hash3(x >> 1, y >> 1, z)));
    // chevrones con incrustaciones rojas en el disco
    if (inDisc && !inBar) {
      const ay = Math.abs(dy), ax = Math.abs(dx);
      const chev = Math.abs(ay - (R * 0.62 - ax * 0.55)) < 3 && ay > barH / 2 + 4 && ax < R * 0.6;
      const inlay = Math.abs(ay - (R * 0.48 - ax * 0.4)) < 2.2 && ax < R * 0.45 && ay > barH / 2 + 4;
      if (chev) for (let z = 7; z <= 8; z++) g.set(x, y, z, 0x4a3524);
      if (inlay) { g.set(x, y, 7, 0x8a2a14); g.setE(x, y, 7, 70); }
    }
  }
  // texto luminoso sobre la barra
  for (let x = 0; x < L; x++) for (let y = 0; y < Hh; y++) {
    const dy = y + 0.5 - cy;
    if (Math.abs(dy) >= barH / 2 - 3) continue;
    const ty = (barH / 2 - dy) / barH * text.h;
    const a = text.at(x * 2 + 1, ty);
    if (a > 0.5) for (let z = 8; z <= 9; z++) { g.set(x, y, z, 0xfff1d6); g.setE(x, y, z, 255); }
  }
  const m = vox(g, v, [cx, cy, 0], 'logo', { roughness: 0.75, metalness: 0.3, emiGain: 1.0, emiTint: 0xffe8c0 });
  return m;
}

export class Astro {
  constructor(scene) {
    this.root = new THREE.Group(); scene.add(this.root);
    const r = this.root;
    // sol
    const sunG = new THREE.SphereGeometry(0.55, 48, 32);
    this.sun = new THREE.Mesh(sunG, new THREE.MeshBasicMaterial({ color: new THREE.Color(3.2, 2.9, 2.4) }));
    r.add(this.sun);
    this.burst = new THREE.Sprite(new THREE.SpriteMaterial({ map: sunburstTexture(), blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.9 }));
    this.burst.scale.set(6, 6, 1); r.add(this.burst);
    // corona de puntas (mira siempre a camara: se orienta en update)
    this.crown = crownMesh(1.25, 1.95, 32, 0.02);
    this.crown.material.emissive = new THREE.Color(0x000000);
    r.add(this.crown);
    // aros de cobre
    const COPPER = [0x8a5634, 0xa06640, 0x744528, 0xb87a50];
    this.rings = [];
    const specs = [[2.45, 0.2, 0.05], [2.85, 0.22, 0.05], [3.3, 0.24, 0.05], [3.8, 0.26, 0.06], [4.4, 0.28, 0.06], [5.1, 0.3, 0.06], [5.9, 0.32, 0.07]];
    specs.forEach(([R, w, t], i) => {
      const piv = new THREE.Group(); r.add(piv);
      const m = ringMesh(R, w, t, 0.025, COPPER, 'copper'); piv.add(m);
      piv.userData = { R, i }; this.rings.push(piv);
    });
    // bandas anchas oscuras (version lejana, voxel grueso)
    this.bands = [];
    for (let i = 0; i < 2; i++) {
      const piv = new THREE.Group(); r.add(piv);
      const m = ringMesh(4.6 + i * 0.6, 0.5, 0.1, 0.025, BRONZE, 'bronzeR'); piv.add(m);
      this.bands.push(piv);
    }
    // bandas heroe (primer plano)
    this.hero = {};
    for (const k of ['dragons', 'lion', 'targ']) {
      const bm = reliefBitmap(k);
      const m = heroBand(bm, 960, 96, 0.003); // 2.9 x 0.29 unidades
      m.visible = false; r.add(m); this.hero[k] = m;
    }
    this.logo = logoMesh(); this.logo.visible = false; r.add(this.logo);
    // banda lisa que cruza por delante en los primeros planos
    this.cross = heroBand(bitmap(8, 8, () => {}), 480, 96, 0.003); this.cross.visible = false; r.add(this.cross);
    // luces
    this.light = new THREE.PointLight(0xffe2b8, 60, 40, 1.6); r.add(this.light);
    this.amb = new THREE.HemisphereLight(0xfff0dc, 0x3a2c22, 0.22); r.add(this.amb);
    this.front = new THREE.DirectionalLight(0xffe4c0, 0.75); this.front.position.set(0, -3, 8); r.add(this.front);
  }
  setVisible(v) { this.root.visible = v; }
  // t: tiempo de la toma ; cam: camara
  update(t, cam, state = {}) {
    this.burst.material.opacity = state.burst ?? 0.9;
    this.crown.lookAt(cam.position);
    this.crown.rotateZ(t * 0.05);
    // aros: cada uno gira sobre un eje inclinado distinto
    // aros casi de cara a la camara, como anillos concentricos que basculan
    this.rings.forEach((p, i) => {
      p.rotation.set(rad(14) * Math.sin(t * 0.35 + i * 1.3), rad(18) * Math.cos(t * 0.3 + i * 1.9), t * 0.1 * (i % 2 ? 1 : -1));
    });
    // banda oscura casi de canto cruzando el sol en diagonal
    this.bands.forEach((p, i) => {
      p.rotation.order = 'ZYX';
      p.rotation.set(rad(87 + i * 2), 0, (i ? rad(70) : rad(-16)) + t * 0.05);
    });
    for (const k in this.hero) {
      const h = this.hero[k]; h.visible = state.hero === k;
      if (h.visible) { h.position.set(...(state.heroPos || [0, 0, 2.4])); h.rotation.set(0, 0, state.heroRot || 0); }
    }
    this.cross.visible = state.cross !== undefined;
    if (this.cross.visible) { this.cross.position.set(state.cross, 0.05, 3.35); this.cross.rotation.set(0, 0, Math.PI / 2 - 0.5); }
    this.logo.visible = !!state.logo;
    if (this.logo.visible) { this.logo.position.set(0, 0, 2.2); this.logo.rotation.set(state.logoTilt || 0, 0, state.logoRot || 0); }
    if (state.bandSlope !== undefined) this.bands[0].rotation.z = state.bandSlope;

    this.bands.forEach((b, i) => (b.visible = state.bands !== false && (i === 0 || !!state.band2)));
    this.rings.forEach((b) => (b.visible = state.rings !== false));
  }
}
