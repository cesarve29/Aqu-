// Drogon: dragon voxel articulado (cuello, cabeza, mandibula, alas, patas, cola).
import * as THREE from 'three';
import { Grid, meshGrid, voxMaterial, sd, jitter, shade, mix, hash3, clamp, lerp, fbm } from './voxel.js';

export const DV = 0.08; // voxel del dragon (m)
const MAT = voxMaterial({ roughness: 0.62, metalness: 0.05, key: 'dragon', emiGain: 3.0 });

const SCALE_A = 0x1b1716, SCALE_B = 0x2a201d, SCALE_R = 0x3d1d17, BELLY = 0x4a3a33, SPIKE = 0x120f0f, HORN = 0x2a2420;
function scaleCol(x, y, z, belly = 0) {
  const pat = ((x + (y >> 1)) % 3 === 0) ? 0.82 : 1;
  const base = hash3(x >> 1, y >> 1, z >> 1) < 0.18 ? SCALE_R : (hash3(x, y, z) < 0.5 ? SCALE_A : SCALE_B);
  return jitter(shade(mix(base, BELLY, belly), pat), 0.18, x, y, z);
}

// construye una parte a partir de una SDF en metros (coordenadas locales de la parte)
function part(min, max, fn, colFn, emiFn) {
  const nx = Math.ceil((max[0] - min[0]) / DV) + 1, ny = Math.ceil((max[1] - min[1]) / DV) + 1, nz = Math.ceil((max[2] - min[2]) / DV) + 1;
  const g = new Grid(nx, ny, nz);
  for (let z = 0; z < nz; z++) for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
    const px = min[0] + (x + 0.5) * DV, py = min[1] + (y + 0.5) * DV, pz = min[2] + (z + 0.5) * DV;
    const d = fn(px, py, pz);
    if (d < 0) {
      g.set(x, y, z, colFn(x, y, z, px, py, pz, d));
      if (emiFn) { const e = emiFn(px, py, pz); if (e > 0) g.setE(x, y, z, e); }
    }
  }
  const m = new THREE.Mesh(meshGrid(g, { scale: DV, origin: [-min[0] / DV, -min[1] / DV, -min[2] / DV] }), MAT);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

const U = (a, b) => Math.min(a, b);

function headMesh() {
  const fn = (x, y, z) => {
    let d = sd.ellip(x, y, z, 0, 0.12, 0.45, 0.62, 0.52, 0.75);
    d = sd.smin(d, sd.ellip(x, y * 1.35, z, 0, 0.0, 1.45, 0.42, 0.36, 1.05), 0.25);           // hocico
    d = sd.smin(d, sd.ellip(x, y, z, 0, 0.06, 2.25, 0.27, 0.22, 0.32), 0.15);                 // punta
    for (const s of [-1, 1]) {
      d = U(d, sd.ellip(x, y, z, s * 0.33, 0.42, 0.95, 0.2, 0.13, 0.42));                     // cejas
      d = U(d, sd.cone(x, y, z, s * 0.32, 0.42, 0.35, s * 0.62, 0.85, -1.15, 0.16, 0.03));      // cuernos
      d = U(d, sd.cone(x, y, z, s * 0.48, 0.15, 0.25, s * 0.95, 0.25, -0.75, 0.12, 0.02));      // gola lateral
      d = U(d, sd.cone(x, y, z, s * 0.5, -0.12, 0.35, s * 1.0, -0.15, -0.5, 0.1, 0.02));
      d = U(d, sd.cone(x, y, z, s * 0.3, 0.3, 1.6, s * 0.35, 0.42, 1.25, 0.06, 0.02));         // cuernitos del hocico
      // dientes superiores
      for (let k = 0; k < 7; k++) {
        const tz = 0.75 + k * 0.22;
        const tx = s * lerp(0.32, 0.2, k / 6);
        d = U(d, sd.cone(x, y, z, tx, -0.18, tz, tx, -0.38, tz + 0.03, 0.05, 0.01));
      }
    }
    // espinas de la cresta central
    for (let k = 0; k < 4; k++) d = U(d, sd.cone(x, y, z, 0, 0.5, 0.6 - k * 0.3, 0, 0.85 - k * 0.05, 0.25 - k * 0.35, 0.09, 0.02));
    // cuenca del ojo
    for (const s of [-1, 1]) d = Math.max(d, -sd.sphere(x, y, z, s * 0.47, 0.25, 1.0, 0.07));
    return d;
  };
  const col = (gx, gy, gz, x, y, z) => {
    for (const s of [-1, 1]) if (Math.hypot(x - s * 0.43, y - 0.25, z - 1.0) < 0.12) {
      const r = Math.hypot(y - 0.25, z - 1.0);
      return r < 0.04 ? 0x100808 : 0xd07018;
    }
    if (y < -0.2 && Math.abs(x) < 0.33 && z > 0.6) return jitter(0xd8ccb0, 0.12, gx, gy, gz); // dientes
    if (Math.abs(x) > 0.25 && y > 0.3 && z < 0.3) return jitter(HORN, 0.2, gx, gy, gz);
    return scaleCol(gx, gy, gz, y < -0.15 ? 0.2 : 0);
  };
  const emi = (x, y, z) => { for (const s of [-1, 1]) if (Math.hypot(x - s * 0.43, y - 0.25, z - 1.0) < 0.12 && Math.hypot(y - 0.25, z - 1.0) >= 0.04) return 120; return 0; };
  return part([-1.1, -0.45, -1.3], [1.1, 1.0, 2.6], fn, col, emi);
}

function jawMesh() {
  // pivote en la bisagra; se extiende hacia +z
  const fn = (x, y, z) => {
    let d = sd.ellip(x, y * 1.6, z, 0, -0.05, 0.95, 0.38, 0.28, 1.15);
    d = Math.max(d, y - 0.02); // plano superior
    for (const s of [-1, 1]) for (let k = 0; k < 7; k++) {
      const tz = 0.6 + k * 0.2, tx = s * lerp(0.28, 0.16, k / 6);
      d = U(d, sd.cone(x, y, z, tx, -0.02, tz, tx, 0.17, tz - 0.02, 0.045, 0.01));
    }
    for (const s of [-1, 1]) d = U(d, sd.cone(x, y, z, s * 0.3, -0.15, 0.2, s * 0.55, -0.3, -0.35, 0.08, 0.02));
    return d;
  };
  const col = (gx, gy, gz, x, y, z) => {
    if (y > 0.0) return jitter(0xd8ccb0, 0.12, gx, gy, gz);
    if (y > -0.08 && Math.abs(x) < 0.22) return jitter(0x5a1414, 0.2, gx, gy, gz); // lengua/boca
    return scaleCol(gx, gy, gz, y < -0.2 ? 0.25 : 0);
  };
  return part([-0.6, -0.45, -0.4], [0.6, 0.22, 2.2], fn, col);
}

function segMesh(L, r0, r1, spike, bellyDir = 1) {
  const fn = (x, y, z) => {
    let d = sd.cone(x, y, z, 0, 0, -0.05, 0, 0, L + 0.08, r0, r1);
    if (spike > 0) d = U(d, sd.cone(x, y, z, 0, r0 * 0.8, L * 0.35, 0, r0 + spike, L * 0.05 - spike * 0.3, Math.max(0.08, r0 * 0.22), 0.02));
    return d;
  };
  const col = (gx, gy, gz, x, y, z) => (y > r0 * 0.85 && Math.abs(x) < 0.2) ? jitter(SPIKE, 0.2, gx, gy, gz) : scaleCol(gx, gy, gz, y < -r0 * 0.5 * bellyDir ? 0.35 : 0);
  const R = Math.max(r0, r1) + 0.1;
  return part([-R, -R, -0.15], [R, R + spike + 0.1, L + 0.15], fn, col);
}

function bodyMesh() {
  const fn = (x, y, z) => {
    let d = sd.ellip(x, y, z, 0, 0, 0, 1.45, 1.3, 3.1);
    d = sd.smin(d, sd.ellip(x, y, z, 0, 0.25, 1.9, 1.2, 1.1, 1.4), 0.4); // pecho
    d = sd.smin(d, sd.ellip(x, y, z, 0, 0.1, -2.4, 1.0, 0.95, 1.2), 0.4); // cadera
    for (let k = 0; k < 9; k++) {
      const zz = 2.6 - k * 0.65;
      const top = 1.15 - Math.abs(zz) * 0.08;
      d = U(d, sd.cone(x, y, z, 0, top, zz, 0, top + 0.55, zz - 0.3, 0.14, 0.02));
    }
    return d;
  };
  const col = (gx, gy, gz, x, y, z) => (y > 1.1 && Math.abs(x) < 0.2) ? jitter(SPIKE, 0.2, gx, gy, gz) : scaleCol(gx, gy, gz, y < -0.6 ? 0.45 : 0);
  return part([-1.6, -1.4, -3.4], [1.6, 2.0, 3.4], fn, col);
}

// ala izquierda (side=1) o derecha (side=-1); huesos a lo largo de +x*side
function boneMesh(L, r0, r1, side, claw = false) {
  const fn = (x, y, z) => {
    let d = sd.cone(x, y, z, 0, 0, 0, side * L, 0, 0, r0, r1);
    if (claw) d = U(d, sd.cone(x, y, z, side * L * 0.98, 0, 0, side * (L + 0.1), -0.45, 0.25, 0.1, 0.01));
    return d;
  };
  const R = Math.max(r0, r1) + 0.1;
  return part([side > 0 ? -R : -L - 0.4, -R - 0.5, -R], [side > 0 ? L + 0.4 : R, R, R + 0.4], fn, (gx, gy, gz) => scaleCol(gx, gy, gz, 0));
}

// panel de membrana: triangulo (0,0,0)-A-B en el plano local, grosor 1 voxel
function membraneMesh(A, B, side, rimC = null) {
  const pts = [[0, 0, 0], A, B];
  const min = [0, 1, 2].map((i) => Math.min(...pts.map((p) => p[i])) - 0.12);
  const max = [0, 1, 2].map((i) => Math.max(...pts.map((p) => p[i])) + 0.12);
  // plano del triangulo
  const ax = A[0], ay = A[1], az = A[2], bx = B[0], by = B[1], bz = B[2];
  const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
  const nl = Math.hypot(nx, ny, nz);
  const fn = (x, y, z) => {
    const dp = Math.abs((x * nx + y * ny + z * nz) / nl);
    if (dp > DV * 0.7) return 1;
    // coordenadas baricentricas
    const v0 = A, v1 = B;
    const d00 = v0[0] * v0[0] + v0[1] * v0[1] + v0[2] * v0[2], d01 = v0[0] * v1[0] + v0[1] * v1[1] + v0[2] * v1[2], d11 = v1[0] * v1[0] + v1[1] * v1[1] + v1[2] * v1[2];
    const d20 = x * v0[0] + y * v0[1] + z * v0[2], d21 = x * v1[0] + y * v1[1] + z * v1[2];
    const den = d00 * d11 - d01 * d01;
    const v = (d11 * d20 - d01 * d21) / den, w = (d00 * d21 - d01 * d20) / den;
    // borde de fuga festoneado
    const scallop = 0.06 * Math.sin((v - w) * 18);
    return (v >= -0.02 && w >= -0.02 && v + w <= 0.96 + scallop) ? -1 : 1;
  };
  const col = (gx, gy, gz) => {
    const vein = (gx + gz) % 9 === 0 || (gx - gz + 999) % 13 === 0;
    return jitter(vein ? 0x1a1010 : (hash3(gx >> 2, gy, gz >> 2) < 0.5 ? 0x2c1a17 : 0x36201b), 0.15, gx, gy, gz);
  };
  return part(min, max, fn, col);
}

export class Dragon {
  constructor() {
    this.root = new THREE.Group();
    this.body = new THREE.Group(); this.root.add(this.body);
    this.body.add(bodyMesh());
    // cuello: 7 segmentos
    this.neck = [];
    let parent = this.body;
    const NL = 0.62;
    const neckBase = new THREE.Group(); neckBase.position.set(0, 0.55, 2.7); this.body.add(neckBase); parent = neckBase;
    for (let i = 0; i < 8; i++) {
      const r0 = lerp(0.95, 0.5, i / 7), r1 = lerp(0.95, 0.5, (i + 1) / 7);
      const seg = new THREE.Group();
      if (i > 0) seg.position.set(0, 0, NL);
      seg.add(segMesh(NL, r0, r1, lerp(0.55, 0.28, i / 7)));
      parent.add(seg); this.neck.push(seg); parent = seg;
    }
    this.headJoint = new THREE.Group(); this.headJoint.position.set(0, 0, NL); parent.add(this.headJoint);
    this.head = new THREE.Group(); this.headJoint.add(this.head);
    this.head.add(headMesh());
    this.jaw = new THREE.Group(); this.jaw.position.set(0, -0.18, 0.35); this.head.add(this.jaw);
    this.jaw.add(jawMesh());
    // boca: punto para el fuego
    this.mouth = new THREE.Object3D(); this.mouth.position.set(0, -0.15, 2.45); this.head.add(this.mouth);
    // cola: 12 segmentos hacia -z
    this.tail = [];
    const tailBase = new THREE.Group(); tailBase.position.set(0, 0.15, -3.1); tailBase.rotation.y = Math.PI; this.body.add(tailBase);
    parent = tailBase;
    for (let i = 0; i < 12; i++) {
      const L = 0.8;
      const seg = new THREE.Group(); if (i > 0) seg.position.set(0, 0, L);
      seg.add(segMesh(L, lerp(0.85, 0.12, i / 12), lerp(0.85, 0.12, (i + 1) / 12), lerp(0.4, 0.12, i / 11)));
      parent.add(seg); this.tail.push(seg); parent = seg;
    }
    // alas
    this.wings = [1, -1].map((side) => this.buildWing(side));
    // patas traseras
    this.legs = [1, -1].map((side) => {
      const hp = new THREE.Group(); hp.position.set(side * 1.05, -0.4, -2.0); this.body.add(hp);
      hp.add(part([-0.7, -2.1, -0.7], [0.7, 0.5, 0.8], (x, y, z) => sd.cone(x, y, z, 0, 0.1, 0, 0, -1.9, 0.25, 0.6, 0.34), (gx, gy, gz) => scaleCol(gx, gy, gz, 0.1)));
      const kn = new THREE.Group(); kn.position.set(0, -1.9, 0.25); hp.add(kn);
      kn.add(part([-0.5, -1.8, -0.7], [0.5, 0.35, 1.1], (x, y, z) => {
        let d = sd.cone(x, y, z, 0, 0, 0, 0, -1.55, -0.35, 0.36, 0.24);
        for (const tx of [-0.25, 0, 0.25]) d = U(d, sd.cone(x, y, z, 0, -1.55, -0.35, tx, -1.68, 0.75, 0.15, 0.03));
        return d;
      }, (gx, gy, gz) => scaleCol(gx, gy, gz, 0)));
      return { hp, kn };
    });
    this.root.traverse((o) => { if (o.isMesh) o.frustumCulled = true; });
  }

  buildWing(side) {
    const sh = new THREE.Group(); sh.position.set(side * 1.0, 0.85, 1.7); this.body.add(sh);
    const L1 = 2.3, L2 = 3.0;
    sh.add(boneMesh(L1, 0.42, 0.28, side));
    const el = new THREE.Group(); el.position.set(side * L1, 0, 0); sh.add(el);
    el.add(boneMesh(L2, 0.27, 0.2, side));
    const wr = new THREE.Group(); wr.position.set(side * L2, 0, 0); el.add(wr);
    // garra/pulgar en la muneca
    wr.add(part([-0.4, -0.6, -0.3], [0.4, 0.3, 0.8], (x, y, z) => U(sd.sphere(x, y, z, 0, 0, 0, 0.26), sd.cone(x, y, z, 0, 0, 0.1, side * 0.1, -0.45, 0.6, 0.12, 0.01)), (gx, gy, gz) => jitter(HORN, 0.2, gx, gy, gz)));
    const fingers = [];
    const FL = [4.6, 5.4, 4.8, 3.7];
    const FA = [0.35, 0.95, 1.55, 2.15]; // angulo de abanico (desde +x hacia -z)
    for (let i = 0; i < 4; i++) {
      const fg = new THREE.Group(); wr.add(fg);
      fg.add(boneMesh(FL[i], 0.15, 0.05, side));
      fingers.push({ g: fg, L: FL[i], a: FA[i] });
    }
    // membranas entre dedos (adjuntas al dedo i, alcanzan al dedo i+1 en abanico nominal)
    for (let i = 0; i < 4; i++) {
      const f = fingers[i];
      const A = [side * f.L, 0, 0];
      let B;
      if (i < 3) {
        const da = FA[i + 1] - FA[i], Ln = FL[i + 1];
        B = [side * Math.cos(da) * Ln, 0, -Math.sin(da) * Ln];
      } else {
        // ultimo panel: hacia el costado del cuerpo (aprox.)
        B = [side * Math.cos(1.0) * 2.0, 0, -Math.sin(1.0) * 3.4];
      }
      f.g.add(membraneMesh(A, B, side));
    }
    // membrana interior: entre antebrazo y el flanco
    el.add(membraneMesh([side * L2, 0, 0], [side * 0.2, -0.2, -3.6], side));
    sh.add(membraneMesh([side * L1, 0, 0], [side * -0.2, -0.4, -3.4], side));
    return { side, sh, el, wr, fingers };
  }

  // pose del dragon
  pose(p) {
    const r = (o, v) => o.rotation.set(v?.[0] || 0, v?.[1] || 0, v?.[2] || 0, 'YXZ');
    this.root.position.set(...(p.pos || [0, 0, 0]));
    this.root.rotation.set(0, p.yaw || 0, 0);
    r(this.body, [p.pitch || 0, 0, p.roll || 0]);
    this.body.position.y = p.bodyY ?? 2.6;
    // cuello: curva repartida
    const n = this.neck.length;
    for (let i = 0; i < n; i++) {
      const k = i / (n - 1);
      const pitch = lerp(p.neckPitch0 ?? -0.25, p.neckPitch1 ?? 0.15, k);
      const yaw = lerp(p.neckYaw0 ?? 0, p.neckYaw1 ?? 0, k);
      this.neck[i].rotation.set(pitch, yaw, 0, 'YXZ');
    }
    r(this.head, [p.headPitch || 0, p.headYaw || 0, p.headRoll || 0]);
    this.jaw.rotation.set(p.jaw || 0, 0, 0);
    // cola
    const tn = this.tail.length;
    for (let i = 0; i < tn; i++) {
      const k = i / (tn - 1);
      this.tail[i].rotation.set((p.tailPitch ?? 0.08) * (1 - k * 0.3), (p.tailYaw ?? 0.1) + Math.sin((p.tailWave ?? 0) + i * 0.5) * (p.tailAmp ?? 0.05), 0, 'YXZ');
    }
    // alas: p.wing = {raise, sweep, twist, elbow, spread, fold}
    for (const w of this.wings) {
      const P = p.wing || {};
      const s = w.side;
      w.sh.rotation.set(P.twist || 0, s * (P.sweep ?? 0.3), s * (P.raise ?? 0), 'YXZ');
      w.el.rotation.set(0, -s * (P.elbow ?? 0.6), s * (P.elbowRaise ?? 0), 'YXZ');
      w.wr.rotation.set(0, s * (P.wrist ?? 0), s * (P.wristRaise ?? 0), 'YXZ');
      const spread = P.spread ?? 1;
      for (const f of w.fingers) f.g.rotation.set(0, s * (f.a * spread), s * (P.fingerDroop ?? 0), 'YXZ');
    }
    for (const L of this.legs) {
      const s = L === this.legs[0] ? 1 : -1;
      r(L.hp, [p.hip ?? 0.2, 0, s * 0.05]);
      r(L.kn, [p.knee ?? 0, 0, 0]);
    }
  }
}
