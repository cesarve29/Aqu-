// Poster final: abanico de espadas del Trono de Hierro, letras GOT metalicas y ojos rojos de dragon.
import { THREE, Grid, vox, bitmap, hash3, jitter, rng, sd } from './kit.js';

export class Poster {
  constructor(scene) {
    this.root = new THREE.Group(); scene.add(this.root);
    const v = 0.022, NX = 340, NY = 260, NZ = 30;
    const g = new Grid(NX, NY, NZ);
    const ox = NX / 2, oy = -40, oz = 15;
    const R = rng(21);
    const steel = (x, y, z) => jitter(hash3(x >> 2, y >> 3, z) < 0.5 ? 0x4c5056 : 0x3a3e44, 0.35, x, y, z);
    const dark = (x, y, z) => jitter(0x34363a, 0.3, x, y, z);
    for (let k = 0; k < 110; k++) {
      const a = -1.4 + (k / 109) * 2.8 + (R() - 0.5) * 0.08;
      const L = (150 + R() * 110) * (1 - Math.abs(a) * 0.2);
      const r0 = 40 + R() * 40;
      const x0 = ox + Math.sin(a) * r0, y0 = oy + Math.cos(a) * r0, z0 = oz + (R() - 0.5) * 16;
      const x1 = ox + Math.sin(a) * (r0 + L), y1 = oy + Math.cos(a) * (r0 + L);
      const w = 6 + R() * 2;
      const bb = [Math.floor(Math.min(x0, x1) - 9), Math.max(0, Math.floor(Math.min(y0, y1) - 9)), 0, Math.ceil(Math.max(x0, x1) + 9), Math.ceil(Math.max(y0, y1) + 9), NZ - 1];
      g.sdf((x, y, z) => sd.cone(x, y, z, x0, y0, z0, x1, y1, z0 - 4, w, 0.5), steel, bb);
      // guarda y pomo
      const gx = x0 + Math.sin(a) * 18, gy = y0 + Math.cos(a) * 18;
      const ca = Math.cos(a), sa = Math.sin(a);
      g.sdf((x, y, z) => sd.cone(x, y, z, gx - ca * 12, gy + sa * 12, z0 + 2, gx + ca * 12, gy - sa * 12, z0 + 2, 2.2, 2.2), dark, [Math.floor(gx - 15), Math.max(0, Math.floor(gy - 15)), 0, Math.ceil(gx + 15), Math.ceil(gy + 15), NZ - 1]);
      g.sdf((x, y, z) => sd.sphere(x, y, z, x0, y0, z0 + 2, 4.5), dark, [Math.floor(x0 - 6), Math.max(0, Math.floor(y0 - 6)), 0, Math.ceil(x0 + 6), Math.ceil(y0 + 6), NZ - 1]);
    }
    this.fan = vox(g, v, [ox, 0, oz], 'fan', { roughness: 0.35, metalness: 0.85 });
    this.fan.position.set(-1.24, -2.2, 0); this.root.add(this.fan);
    // letras GOT
    const bm = bitmap(600, 200, (x, w, h) => { x.fillStyle = '#fff'; x.font = '400 200px Cinzel'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText('GOT', w / 2, h / 2 + 10); });
    const lv = 0.012, LX = 300, LY = 100;
    const lg = new Grid(LX, LY, 6);
    for (let i = 0; i < LX; i++) for (let j = 0; j < LY; j++) {
      if (bm.at(i * 2 + 1, (LY - 1 - j) * 2 + 1) < 0.5) continue;
      const t = j / LY;
      const col = t > 0.6 ? 0xdedad6 : (t > 0.35 ? 0xd09070 : 0xa84a30);
      for (let z = 0; z < 5; z++) lg.set(i, j, z, jitter(col, 0.1, i, j, z));
    }
    this.letters = vox(lg, lv, [LX / 2, LY / 2, 0], 'gotL', { roughness: 0.25, metalness: 0.85 });
    this.letters.position.set(-1.24, 2.2, 1.2); this.letters.scale.setScalar(0.85); this.root.add(this.letters);
    // ojos de dragon
    const eg = new Grid(16, 9, 2);
    for (let i = 0; i < 16; i++) for (let j = 0; j < 9; j++) {
      const dx = (i - 7.5) / 8, dy = (j - 4) / 4.5;
      if (dx * dx + dy * dy > 1) continue;
      const pupil = Math.abs(i - 7.5) < 1.3;
      eg.set(i, j, 0, pupil ? 0x200404 : 0xb02810); if (!pupil) eg.setE(i, j, 0, 160);
    }
    this.eyes = [[-2.17, -0.55], [0.15, -0.55]].map(([x, y], i) => { const m = vox(eg, 0.025, [8, 4.5, 0], 'eye', { emiGain: 2.5, emiTint: 0xff5020 }); m.position.set(x, y, 0.75); m.rotation.z = i ? -0.2 : 0.2; this.root.add(m); return m; });
    this.key = new THREE.DirectionalLight(0xdfe6f0, 2.4); this.key.position.set(-3, 5, 6); this.root.add(this.key);
    this.rim = new THREE.DirectionalLight(0xffc8a0, 1.0); this.rim.position.set(4, 2, -3); this.root.add(this.rim);
    this.amb = new THREE.HemisphereLight(0x6a7080, 0x0a0a0a, 0.5); this.root.add(this.amb);
    this.letterLight = new THREE.PointLight(0xffd0b0, 6, 6, 1.5); this.letterLight.position.set(-1.2, 2.8, 2.5); this.root.add(this.letterLight);
    
  }
  update() {}
}
