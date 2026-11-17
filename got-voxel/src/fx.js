// Efectos: ceniza/nieve, fuego de dragon, llamas en el suelo, brasas, humo, lava.
import * as THREE from 'three';
import { hash3, clamp, lerp, fbm, vnoise, smooth } from './voxel.js';

const box = new THREE.BoxGeometry(1, 1, 1);
const M4 = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3(), E = new THREE.Euler(), C = new THREE.Color();

// --- nieve/ceniza que cae: copos suaves (sprites redondos con bordes difusos)
function flakeTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(32, 32, 0, 32, 32, 30);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.35, 'rgba(255,255,255,0.85)');
  g.addColorStop(0.7, 'rgba(255,255,255,0.25)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.beginPath(); x.arc(32, 32, 30, 0, Math.PI * 2); x.fill();
  // pequenas irregularidades del copo
  x.globalCompositeOperation = 'destination-out';
  for (let i = 0; i < 6; i++) { const a = i * 1.047 + 0.3; x.fillStyle = 'rgba(0,0,0,0.35)'; x.beginPath(); x.arc(32 + Math.cos(a) * 24, 32 + Math.sin(a) * 24, 7, 0, Math.PI * 2); x.fill(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
export class Ash {
  constructor(scene, n = 3000) {
    this.n = n;
    this.geo = new THREE.BufferGeometry();
    this.pos = new Float32Array(n * 3);
    this.geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    this.mat = new THREE.PointsMaterial({ color: 0xf2f4f6, size: 0.03, map: flakeTexture(), transparent: true, depthWrite: false, sizeAttenuation: true, opacity: 0.95 });
    this.mesh = new THREE.Points(this.geo, this.mat);
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }
  update(t, center, size, opts = {}) {
    const [cx, cy, cz] = center, [sx, sy, sz] = size;
    const speed = opts.speed ?? 0.35;
    this.mat.size = 0.05 * (opts.scale ?? 1);
    const cnt = Math.min(this.n, opts.count ?? this.n);
    for (let i = 0; i < this.n; i++) {
      const j = i * 3;
      if (i >= cnt) { this.pos[j] = 0; this.pos[j + 1] = -999; this.pos[j + 2] = 0; continue; }
      const r1 = hash3(i, 1, 7), r2 = hash3(i, 2, 7), r3 = hash3(i, 3, 7), r4 = hash3(i, 4, 7);
      const fall = (r2 * sy + t * speed * (0.6 + r4 * 0.8)) % sy;
      // revoloteo suave de copo
      const x = (r1 * sx + t * (opts.wind ?? 0.12) + Math.sin(t * (0.5 + r3) + i) * 0.18) % sx;
      this.pos[j] = cx - sx / 2 + x;
      this.pos[j + 1] = cy + sy / 2 - fall;
      this.pos[j + 2] = cz + (r3 - 0.5) * sz + Math.cos(t * (0.4 + r1 * 0.5) + i * 1.3) * 0.18;
    }
    this.geo.attributes.position.needsUpdate = true;
  }
  set visible(v) { this.mesh.visible = v; }
}

// gradiente de color del fuego segun edad (0..1)
function fireColor(f, out, hot = 1) {
  if (f < 0.08) out.setRGB(9 * hot, 7.5 * hot, 4.5 * hot);
  else if (f < 0.35) { const k = (f - 0.08) / 0.27; out.setRGB(lerp(9, 7, k) * hot, lerp(7.5, 2.6, k) * hot, lerp(4.5, 0.5, k) * hot); }
  else if (f < 0.7) { const k = (f - 0.35) / 0.35; out.setRGB(lerp(7, 2.2, k) * hot, lerp(2.6, 0.45, k) * hot, lerp(0.5, 0.08, k) * hot); }
  else { const k = (f - 0.7) / 0.3; out.setRGB(lerp(2.2, 0.04, k), lerp(0.45, 0.035, k), lerp(0.08, 0.03, k)); }
  return out;
}

// --- chorro de fuego: particulas cubicas emisivas
export class FireStream {
  constructor(scene, n = 2600) {
    this.n = n;
    const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: true });
    this.mesh = new THREE.InstancedMesh(box, mat, n);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3);
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }
  // origin, dir: Vector3 ; on(tBirth) -> bool
  update(t, origin, dir, opts = {}) {
    const life = opts.life ?? 1.1, speed = opts.speed ?? 22, spread = opts.spread ?? 0.16;
    const on = opts.on || (() => true);
    const side = new THREE.Vector3(0, 1, 0).cross(dir).normalize();
    const up = new THREE.Vector3().crossVectors(dir, side).normalize();
    const reach = opts.reach ?? 999;
    for (let i = 0; i < this.n; i++) {
      const phase = hash3(i, 9, 1) * life;
      const age = ((t + phase) % life);
      const birth = t - age;
      const f = age / life;
      if (!on(birth)) { M4.makeScale(0, 0, 0); this.mesh.setMatrixAt(i, M4); continue; }
      const r1 = hash3(i, 1, 2) - 0.5, r2 = hash3(i, 2, 2) - 0.5, r3 = hash3(i, 3, 2);
      let dist = speed * age * (0.85 + r3 * 0.3);
      // al llegar al obstaculo se expande
      let splash = 0;
      if (dist > reach) { splash = dist - reach; dist = reach; }
      const sp = spread * dist + splash * 0.9;
      const turb = vnoise(i * 0.1, t * 3, 0) - 0.5;
      P.copy(origin).addScaledVector(dir, dist)
        .addScaledVector(side, r1 * sp * 2 + turb * 0.4 * f)
        .addScaledVector(up, r2 * sp * 1.6 + f * f * 2.2 + splash * 0.35);
      const s = (0.18 + f * 1.1 + splash * 0.25) * (0.6 + r3 * 0.8) * (opts.scale ?? 1);
      E.set(r1 * 6 + t * 2, r2 * 6 + t, r3 * 6); Q.setFromEuler(E);
      S.set(s, s, s); M4.compose(P, Q, S); this.mesh.setMatrixAt(i, M4);
      fireColor(f, C, opts.hot ?? 1); this.mesh.setColorAt(i, C);
    }
    this.mesh.instanceMatrix.needsUpdate = true; this.mesh.instanceColor.needsUpdate = true;
  }
  set visible(v) { this.mesh.visible = v; }
}

// --- llamas en el suelo: emisores fijos
export class Flames {
  constructor(scene, n = 1800) {
    this.n = n;
    this.mesh = new THREE.InstancedMesh(box, new THREE.MeshBasicMaterial({ color: 0xffffff }), n);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3);
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
    this.sources = [];
  }
  // sources: [{p:[x,y,z], r, h, k (intensidad 0..1)}]
  update(t, sources, opts = {}) {
    const per = Math.floor(this.n / Math.max(1, sources.length));
    for (let i = 0; i < this.n; i++) {
      const si = Math.floor(i / per);
      const src = sources[si];
      if (!src || (src.k ?? 1) <= 0.01 || hash3(i, 5, 5) > (src.k ?? 1)) { M4.makeScale(0, 0, 0); this.mesh.setMatrixAt(i, M4); continue; }
      const life = 0.55 + hash3(i, 1, 5) * 0.7;
      const age = (t + hash3(i, 2, 5) * life) % life, f = age / life;
      const a = hash3(i, 3, 5) * Math.PI * 2, rr = Math.sqrt(hash3(i, 4, 5)) * src.r;
      const sway = Math.sin(t * 4 + i) * 0.15 * f;
      P.set(src.p[0] + Math.cos(a) * rr * (1 - f * 0.5) + sway, src.p[1] + f * src.h * (0.6 + hash3(i, 6, 5) * 0.8), src.p[2] + Math.sin(a) * rr * (1 - f * 0.5));
      const s = (src.s ?? 0.25) * (1 - f * 0.6) * (0.6 + hash3(i, 7, 5) * 0.8);
      E.set(i, t + i, 0); Q.setFromEuler(E); S.set(s, s * 1.4, s); M4.compose(P, Q, S); this.mesh.setMatrixAt(i, M4);
      fireColor(0.08 + f * 0.75, C, src.hot ?? 0.9); this.mesh.setColorAt(i, C);
    }
    this.mesh.instanceMatrix.needsUpdate = true; this.mesh.instanceColor.needsUpdate = true;
  }
  set visible(v) { this.mesh.visible = v; }
}

// --- brasas que flotan
export class Embers {
  constructor(scene, n = 1500) {
    this.n = n;
    this.mesh = new THREE.InstancedMesh(box, new THREE.MeshBasicMaterial({ color: 0xffffff }), n);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3);
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }
  update(t, center, size, opts = {}) {
    const [cx, cy, cz] = center, [sx, sy, sz] = size;
    const cnt = opts.count ?? this.n;
    for (let i = 0; i < this.n; i++) {
      if (i >= cnt) { M4.makeScale(0, 0, 0); this.mesh.setMatrixAt(i, M4); continue; }
      const rise = ((hash3(i, 1, 3) * sy + t * (opts.speed ?? 0.8) * (0.5 + hash3(i, 2, 3))) % sy);
      P.set(cx + (hash3(i, 3, 3) - 0.5) * sx + Math.sin(t * 1.3 + i) * 0.4, cy - sy / 2 + rise, cz + (hash3(i, 4, 3) - 0.5) * sz + Math.cos(t * 1.1 + i * 2) * 0.4);
      const s = (opts.size ?? 0.05) * (0.5 + hash3(i, 5, 3));
      const flick = 0.5 + 0.5 * Math.sin(t * 9 + i * 3.1);
      C.setRGB(6 * (0.5 + flick), 1.6 * (0.4 + flick * 0.6), 0.3);
      E.set(t + i, i, 0); Q.setFromEuler(E); S.set(s, s, s); M4.compose(P, Q, S);
      this.mesh.setMatrixAt(i, M4); this.mesh.setColorAt(i, C);
    }
    this.mesh.instanceMatrix.needsUpdate = true; this.mesh.instanceColor.needsUpdate = true;
  }
  set visible(v) { this.mesh.visible = v; }
}

// --- humo (cubos grandes semitransparentes)
export class Smoke {
  constructor(scene, n = 400, color = 0x2a2828, opacity = 0.35) {
    this.n = n;
    this.mesh = new THREE.InstancedMesh(box, new THREE.MeshLambertMaterial({ color, transparent: true, opacity, depthWrite: false }), n);
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }
  update(t, center, size, opts = {}) {
    const [cx, cy, cz] = center, [sx, sy, sz] = size;
    const cnt = opts.count ?? this.n;
    for (let i = 0; i < this.n; i++) {
      if (i >= cnt) { M4.makeScale(0, 0, 0); this.mesh.setMatrixAt(i, M4); continue; }
      const life = 6 + hash3(i, 1, 4) * 6;
      const age = (t + hash3(i, 2, 4) * life) % life, f = age / life;
      P.set(cx + (hash3(i, 3, 4) - 0.5) * sx + f * (opts.drift ?? 2), cy + f * sy, cz + (hash3(i, 4, 4) - 0.5) * sz);
      const s = (opts.size ?? 2.2) * (0.4 + f) * (0.6 + hash3(i, 5, 4) * 0.8) * Math.sin(Math.PI * Math.min(1, f * 1.3));
      E.set(i, i * 2 + t * 0.1, 0); Q.setFromEuler(E); S.set(s, s, s); M4.compose(P, Q, S); this.mesh.setMatrixAt(i, M4);
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
  set visible(v) { this.mesh.visible = v; }
}

// --- campo de lava/metal fundido: rejilla de cubos con color animado
export class Lava {
  constructor(scene, nx = 70, nz = 50, v = 0.12) {
    this.nx = nx; this.nz = nz; this.v = v;
    const n = nx * nz;
    this.mesh = new THREE.InstancedMesh(box, new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.5, emissive: 0xffffff, emissiveIntensity: 0 }), n);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3);
    // usamos MeshBasic para que el brillo sea controlable
    this.mesh.material = new THREE.MeshBasicMaterial({ color: 0xffffff });
    this.mesh.frustumCulled = false;
    scene.add(this.mesh);
  }
  // heightFn(x,z) altura local; maskFn(x,z) 0..1 cobertura; flow velocidad
  update(t, origin, opts = {}) {
    const { nx, nz, v } = this;
    let i = 0;
    for (let z = 0; z < nz; z++) for (let x = 0; x < nx; x++, i++) {
      const wx = origin[0] + (x - nx / 2) * v, wz = origin[2] + (z - nz / 2) * v;
      const m = opts.mask ? opts.mask(wx, wz, t) : 1;
      if (m <= 0.02) { M4.makeScale(0, 0, 0); this.mesh.setMatrixAt(i, M4); continue; }
      const h = opts.height ? opts.height(wx, wz, t) : 0;
      const n = fbm(wx * 1.3 + t * 0.35, t * 0.25, wz * 1.3 - t * 0.2, 3);
      const crust = clamp((n - 0.45) * 4);
      const heat = (opts.heat ?? 1) * m;
      C.setRGB(lerp(7.5, 0.25, crust) * heat + 0.04, lerp(1.8, 0.05, crust) * heat + 0.02, lerp(0.15, 0.02, crust) * heat + 0.02);
      P.set(wx, origin[1] + h, wz); S.set(v, v * (1 + h * 2), v);
      M4.compose(P, Q.identity(), S); this.mesh.setMatrixAt(i, M4); this.mesh.setColorAt(i, C);
    }
    this.mesh.instanceMatrix.needsUpdate = true; this.mesh.instanceColor.needsUpdate = true;
  }
  set visible(v) { this.mesh.visible = v; }
}
