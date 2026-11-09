import * as THREE from 'three';
import { rng, T, smooth, clamp, lerp, shakeEnvelope } from './timeline.js';
import { terrainHeight } from './city.js';

const matCache = new Map();
function mat(hex, rough = 0.75, extra = {}) {
  const k = hex + ':' + rough + JSON.stringify(extra);
  if (!matCache.has(k)) matCache.set(k, new THREE.MeshStandardMaterial({ color: hex, roughness: rough, ...extra }));
  return matCache.get(k);
}

const G = {};
function geos() {
  if (G.ready) return G;
  G.head = new THREE.SphereGeometry(0.105, 24, 18);
  G.head.scale(0.92, 1.08, 1.0);
  G.hairShort = new THREE.SphereGeometry(0.112, 24, 14, 0, Math.PI * 2, 0, Math.PI * 0.52);
  G.hairLong = new THREE.CapsuleGeometry(0.11, 0.16, 6, 16);
  G.bun = new THREE.SphereGeometry(0.055, 12, 10);
  G.cap = new THREE.SphereGeometry(0.115, 20, 10, 0, Math.PI * 2, 0, Math.PI * 0.45);
  G.brim = new THREE.CylinderGeometry(0.11, 0.11, 0.015, 20, 1, false, -Math.PI / 2, Math.PI);
  G.eye = new THREE.SphereGeometry(0.014, 8, 6);
  G.nose = new THREE.ConeGeometry(0.016, 0.04, 8);
  G.neck = new THREE.CylinderGeometry(0.045, 0.05, 0.1, 12);
  G.torso = new THREE.CapsuleGeometry(0.15, 0.3, 8, 18);
  G.torso.scale(1.0, 1.0, 0.68);
  G.pelvis = new THREE.CapsuleGeometry(0.14, 0.08, 6, 16);
  G.pelvis.scale(1.0, 1.0, 0.75);
  G.upperArm = new THREE.CapsuleGeometry(0.048, 0.22, 6, 12); G.upperArm.translate(0, -0.13, 0);
  G.foreArm = new THREE.CapsuleGeometry(0.04, 0.2, 6, 12); G.foreArm.translate(0, -0.12, 0);
  G.hand = new THREE.SphereGeometry(0.04, 12, 10); G.hand.scale(0.75, 1.15, 0.55);
  G.joint = new THREE.SphereGeometry(0.062, 14, 10);
  G.thigh = new THREE.CapsuleGeometry(0.075, 0.32, 6, 14); G.thigh.translate(0, -0.21, 0);
  G.shin = new THREE.CapsuleGeometry(0.058, 0.32, 6, 14); G.shin.translate(0, -0.2, 0);
  G.shoe = new THREE.CapsuleGeometry(0.05, 0.13, 4, 10); G.shoe.rotateX(Math.PI / 2); G.shoe.scale(1.0, 0.75, 1.0); G.shoe.translate(0, -0.03, 0.05);
  G.skirt = new THREE.CylinderGeometry(0.15, 0.27, 0.42, 20, 1, true);
  G.pack = new THREE.CapsuleGeometry(0.12, 0.16, 4, 12); G.pack.scale(1.0, 1.0, 0.55);
  G.bag = new THREE.BoxGeometry(0.06, 0.24, 0.3);
  G.phone = new THREE.BoxGeometry(0.075, 0.15, 0.012);
  G.ready = true;
  return G;
}

const SKIN = [0xd9a888, 0xc8936f, 0xb07650, 0x8a5636, 0x5e3822, 0xe0b496, 0xc28a66];
const HAIR = [0x1d140f, 0x3a2416, 0x5b3a1f, 0x8a6236, 0xc9a35f, 0x2a2a2a, 0x9c9c9c];
const SHIRT = [0xc62828, 0x1565c0, 0xf5f5f5, 0x2e7d32, 0xf9a825, 0x6a1b9a, 0x37474f, 0xef6c00, 0x00838f, 0xad1457, 0x4e342e, 0x90a4ae, 0xd7ccc8, 0x283593];
const PANTS = [0x1f2a44, 0x2c3e50, 0x111111, 0x6d5a40, 0x3e4a5a, 0x4a4a4a, 0x7b6f5a];
const SHOES = [0x111111, 0x5d4037, 0xeeeeee, 0x37474f, 0x8d6e63];

// Pose = joint angles. Every animation produces a full pose; poses are blended.
const KEYS = ['y', 'lean', 'twist', 'side', 'hx', 'hy', 'sLx', 'sLz', 'eL', 'sRx', 'sRz', 'eR', 'tL', 'kL', 'tR', 'kR', 'tLz', 'tRz', 'pitch'];
function P(o = {}) { const p = {}; for (const k of KEYS) p[k] = o[k] || 0; p.y = o.y ?? 0; return p; }
function mix(a, b, k) { const p = {}; for (const key of KEYS) p[key] = a[key] + (b[key] - a[key]) * k; return p; }

function poseIdle(t, ph) {
  const b = Math.sin(t * 1.3 + ph);
  return P({ y: 0.004 * b, lean: 0.02, sLz: 0.08, sRz: -0.08, eL: -0.12, eR: -0.12, hy: 0.25 * Math.sin(t * 0.4 + ph), hx: 0.03 * b, tL: -0.02, tR: 0.02, twist: 0.03 * b });
}
function poseLookAround(t, ph) {
  const p = poseIdle(t, ph);
  p.hy = 0.8 * Math.sin(t * 1.1 + ph);
  p.hx = -0.25 + 0.1 * Math.sin(t * 0.7 + ph);
  p.twist = 0.25 * Math.sin(t * 1.1 + ph);
  p.sLz = 0.25; p.sRz = -0.25; p.eL = -0.3; p.eR = -0.3;
  return p;
}
function poseWalk(ph, amp = 1) {
  const s = Math.sin(ph), c = Math.cos(ph);
  return P({
    y: 0.025 * Math.abs(c) * amp - 0.01, lean: 0.06 * amp, twist: 0.08 * s * amp,
    tL: -0.48 * s * amp, tR: 0.48 * s * amp,
    kL: (0.15 + 0.7 * Math.max(0, Math.sin(ph + 1.2))) * amp, kR: (0.15 + 0.7 * Math.max(0, Math.sin(ph + Math.PI + 1.2))) * amp,
    sLx: 0.42 * s * amp, sRx: -0.42 * s * amp, sLz: 0.07, sRz: -0.07, eL: -0.3 - 0.2 * Math.max(0, s) * amp, eR: -0.3 - 0.2 * Math.max(0, -s) * amp,
    hy: -0.05 * s, hx: 0.02,
  });
}
function poseRun(ph, amp = 1) {
  const s = Math.sin(ph), c = Math.cos(ph);
  return P({
    y: 0.06 * Math.abs(c) * amp - 0.04, lean: 0.32 * amp, twist: 0.15 * s * amp,
    tL: -0.95 * s * amp - 0.2, tR: 0.95 * s * amp - 0.2,
    kL: (0.3 + 1.5 * Math.max(0, Math.sin(ph + 1.4))) * amp, kR: (0.3 + 1.5 * Math.max(0, Math.sin(ph + Math.PI + 1.4))) * amp,
    sLx: 0.9 * s * amp, sRx: -0.9 * s * amp, sLz: 0.12, sRz: -0.12, eL: -1.5, eR: -1.5, hx: -0.15,
  });
}
function poseCrouch(t, ph, shake) {
  // "drop, cover, hold on": knees bent, torso folded, hands over the head
  const j = shake * 0.05 * Math.sin(t * 11 + ph);
  return P({
    y: -0.6 + j * 0.3, lean: 0.85 + j, tL: -1.55, kL: 2.4, tR: -1.45, kR: 2.3, tLz: 0.2, tRz: -0.2,
    sLx: -2.7, sLz: 0.45, eL: -1.9, sRx: -2.7, sRz: -0.45, eR: -1.9, hx: 0.35,
  });
}
function posePhone(t, ph) {
  const p = poseIdle(t, ph);
  p.sRx = -0.55; p.eR = -1.75; p.sRz = 0.1; p.hx = 0.35; p.hy = 0;
  return p;
}
function posePoint(t, ph) {
  const p = poseIdle(t, ph);
  p.sRx = -1.45; p.eR = -0.05; p.sRz = -0.05; p.hx = -0.05; p.hy = 0;
  p.sLx = -0.2; p.eL = -0.6;
  return p;
}
function poseFallen(t, ph) {
  return P({ y: -0.78, pitch: 1.45, lean: 0.1, tL: -0.2, kL: 0.5, tR: 0.1, kR: 0.2, sLx: -2.2, sLz: 0.6, eL: -0.6, sRx: -2.0, sRz: -0.7, eR: -0.8, hx: -0.4 });
}
function poseHug(t, ph) {
  const p = poseIdle(t, ph);
  p.sLx = -0.6; p.eL = -1.6; p.sRx = -0.6; p.eR = -1.6; p.sLz = -0.2; p.sRz = 0.2; p.hx = 0.25;
  return p;
}

export class Person {
  constructor(scene, r, opts) {
    const g = geos();
    this.r = r;
    this.opts = opts;
    const female = r() < 0.5;
    const child = opts.child || false;
    const sc = child ? 0.62 + r() * 0.1 : (female ? 0.93 : 1.0) * (0.94 + r() * 0.1);
    const skin = mat(SKIN[Math.floor(r() * SKIN.length)], 0.55);
    const hair = mat(HAIR[Math.floor(r() * HAIR.length)], 0.6);
    const shirt = mat(SHIRT[Math.floor(r() * SHIRT.length)], 0.8);
    const pants = mat(PANTS[Math.floor(r() * PANTS.length)], 0.85);
    const shoes = mat(SHOES[Math.floor(r() * SHOES.length)], 0.5);
    const eyeM = mat(0x161210, 0.2);
    const jacket = r() < 0.35 ? mat(SHIRT[Math.floor(r() * SHIRT.length)], 0.7) : shirt;

    const root = this.root = new THREE.Group();
    root.scale.setScalar(sc);
    const hips = this.hips = new THREE.Group(); hips.position.y = 0.92; root.add(hips);
    const pelvis = new THREE.Mesh(g.pelvis, pants); pelvis.position.y = 0.0; hips.add(pelvis);
    const torso = this.torso = new THREE.Group(); torso.position.y = 0.06; hips.add(torso);
    const chest = new THREE.Mesh(g.torso, jacket); chest.position.y = 0.26; chest.scale.x = female ? 0.95 : 1.1; torso.add(chest);
    const neck = new THREE.Mesh(g.neck, skin); neck.position.y = 0.55; torso.add(neck);
    const head = this.head = new THREE.Group(); head.position.y = 0.6; torso.add(head);
    const hm = new THREE.Mesh(g.head, skin); hm.position.y = 0.1; head.add(hm);
    for (const ex of [-0.037, 0.037]) { const e = new THREE.Mesh(g.eye, eyeM); e.position.set(ex, 0.115, 0.093); head.add(e); }
    const nose = new THREE.Mesh(g.nose, skin); nose.rotation.x = Math.PI / 2; nose.position.set(0, 0.085, 0.105); head.add(nose);
    const hs = r();
    if (opts.cap || hs < 0.12) {
      const c = new THREE.Mesh(g.cap, mat(SHIRT[Math.floor(r() * SHIRT.length)], 0.8)); c.position.y = 0.12; head.add(c);
      const b = new THREE.Mesh(g.brim, c.material); b.position.set(0, 0.14, 0.09); head.add(b);
    } else if (female && hs < 0.75) {
      const h1 = new THREE.Mesh(g.hairShort, hair); h1.position.y = 0.105; h1.rotation.x = -0.25; head.add(h1);
      const h2 = new THREE.Mesh(g.hairLong, hair); h2.position.set(0, 0.04, -0.035); h2.scale.set(1.0, 1.0, 0.75); head.add(h2);
    } else if (female) {
      const h1 = new THREE.Mesh(g.hairShort, hair); h1.position.y = 0.105; h1.rotation.x = -0.25; head.add(h1);
      const bn = new THREE.Mesh(g.bun, hair); bn.position.set(0, 0.2, -0.08); head.add(bn);
    } else if (hs > 0.94) {
      // bald
    } else {
      const h1 = new THREE.Mesh(g.hairShort, hair); h1.position.y = 0.1; h1.rotation.x = -0.3; h1.scale.set(1, 0.85, 1); head.add(h1);
    }
    const mkArm = (sx) => {
      const sh = new THREE.Group(); sh.position.set(sx * 0.165 * (female ? 0.92 : 1.05), 0.46, 0); torso.add(sh);
      const ua = new THREE.Mesh(g.upperArm, jacket); sh.add(ua);
      const sj = new THREE.Mesh(g.joint, jacket); sh.add(sj);
      const el = new THREE.Group(); el.position.y = -0.27; sh.add(el);
      const fa = new THREE.Mesh(g.foreArm, r() < 0.5 && jacket === shirt ? skin : jacket); el.add(fa);
      const hd = new THREE.Mesh(g.hand, skin); hd.position.y = -0.27; el.add(hd);
      return [sh, el, hd];
    };
    [this.shL, this.elL, this.handL] = mkArm(1);
    [this.shR, this.elR, this.handR] = mkArm(-1);
    const skirt = female && r() < 0.35 && !child;
    const mkLeg = (sx) => {
      const th = new THREE.Group(); th.position.set(sx * 0.085, -0.02, 0); hips.add(th);
      const tm = new THREE.Mesh(g.thigh, skirt ? skin : pants); th.add(tm);
      const kn = new THREE.Group(); kn.position.y = -0.43; th.add(kn);
      const sm = new THREE.Mesh(g.shin, skirt ? skin : pants); kn.add(sm);
      const ft = new THREE.Mesh(g.shoe, shoes); ft.position.y = -0.43; kn.add(ft);
      return [th, kn];
    };
    [this.thL, this.knL] = mkLeg(1);
    [this.thR, this.knR] = mkLeg(-1);
    if (skirt) { const s = new THREE.Mesh(g.skirt, pants); s.position.y = -0.12; hips.add(s); s.material = mat(SHIRT[Math.floor(r() * SHIRT.length)], 0.85, { side: THREE.DoubleSide }); }
    if (r() < 0.3 || opts.pack) { const p = new THREE.Mesh(g.pack, mat([0x263238, 0x8d2b2b, 0x1b4f72, 0x4d5e2a][Math.floor(r() * 4)], 0.8)); p.position.set(0, 0.28, -0.15); torso.add(p); }
    else if (r() < 0.3) { const b = new THREE.Mesh(g.bag, mat(0x6d4c41, 0.6)); b.position.set(0.24, -0.3, 0); this.shL.add(b); }
    if (opts.phone) { const ph = new THREE.Mesh(g.phone, mat(0x111111, 0.3)); ph.position.set(0, -0.05, 0.03); this.handR.add(ph); }
    root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    scene.add(root);

    this.x = opts.x; this.z = opts.z; this.heading = opts.heading || 0;
    this.phase = r() * 6.28; this.walkPh = r() * 6.28;
    this.speed = 0; this.pose = poseIdle(0, 0); this.sc = sc;
    this.react = r();
    this.choice = r();
  }

  apply(p) {
    const root = this.root;
    root.position.set(this.x, this.groundY() , this.z);
    root.rotation.set(0, this.heading, 0);
    this.hips.position.y = 0.92 + p.y;
    this.hips.rotation.set(p.pitch, 0, p.side);
    this.torso.rotation.set(p.lean, p.twist, 0);
    this.head.rotation.set(p.hx, p.hy, 0);
    this.shL.rotation.set(p.sLx, 0, p.sLz); this.elL.rotation.set(p.eL, 0, 0);
    this.shR.rotation.set(p.sRx, 0, p.sRz); this.elR.rotation.set(p.eR, 0, 0);
    this.thL.rotation.set(p.tL, 0, p.tLz); this.knL.rotation.set(p.kL, 0, 0);
    this.thR.rotation.set(p.tR, 0, p.tRz); this.knR.rotation.set(p.kR, 0, 0);
  }

  groundY() {
    const x = this.x, z = this.z;
    if (z > -150 && z < 145 && Math.abs(x) > 5 && Math.abs(x) < 9) return 0.15;
    if (x > 9 && x < 45 && z > 9 && z < 63) return 0.16;
    if (z <= -149 && z >= -163) return 0.2;
    return terrainHeight(x, z);
  }

  // steer toward a heading smoothly
  turnTo(target, dt, rate = 4) {
    let d = target - this.heading;
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    this.heading += clamp(d, -rate * dt, rate * dt);
  }

  move(vx, vz, dt) {
    this.x += vx * dt; this.z += vz * dt;
    const sp = Math.hypot(vx, vz);
    if (sp > 0.05) this.turnTo(Math.atan2(vx, vz), dt, 6);
    this.walkPh += sp * dt * (sp > 2.5 ? 3.3 : 4.6);
    this.speed = sp;
  }

  setPose(target, dt, rate = 6) {
    this.pose = mix(this.pose, target, 1 - Math.exp(-rate * dt));
  }
}

// -------------------------------------------------------------- crowd logic
export class Crowd {
  constructor(scene) {
    this.scene = scene;
    const r = this.r = rng(777);
    this.people = [];
    // sidewalk walkers near the camera route
    for (let i = 0; i < 46; i++) {
      const side = r() < 0.5 ? -1 : 1;
      const lane = side * (r() < 0.5 ? 6.5 : 8.4);
      const z = -20 + r() * 150;
      if (side > 0 && z > 8 && z < 62 && r() < 0.6) continue;
      const dir = r() < 0.5 ? -1 : 1;
      const p = new Person(scene, r, { x: lane, z, heading: dir > 0 ? 0 : Math.PI, phone: r() < 0.3 });
      p.type = 'walker'; p.dir = dir; p.lane = lane; p.v = 1.1 + r() * 0.45;
      this.people.push(p);
    }
    // plaza people
    for (let i = 0; i < 22; i++) {
      const x = 14 + r() * 28, z = 16 + r() * 42;
      if (Math.hypot(x - 32, z - 42) < 5) continue;
      const child = r() < 0.15;
      const p = new Person(scene, r, { x, z, heading: r() * 6.28, child, phone: r() < 0.3 });
      p.type = 'plaza'; p.home = [x, z]; p.v = 0.6 + r() * 0.5;
      p.wander = r() < 0.5;
      this.people.push(p);
    }
    // beach / promenade
    for (let i = 0; i < 30; i++) {
      const x = -32 + r() * 64, z = -153 - r() * 22;
      const p = new Person(scene, r, { x, z, heading: Math.PI + (r() - 0.5), child: r() < 0.15, cap: r() < 0.3 });
      p.type = 'beach'; p.home = [x, z]; p.v = 0.8 + r() * 0.5;
      this.people.push(p);
    }
    // hill viewpoint
    for (let i = 0; i < 26; i++) {
      const x = 14 + r() * 52, z = 248 + r() * 12;
      const p = new Person(scene, r, { x, z, heading: Math.PI + (r() - 0.5) * 0.6, child: r() < 0.2, pack: r() < 0.4 });
      p.type = 'hill'; p.home = [x, z];
      this.people.push(p);
    }
  }

  update(t, dt) {
    const shake = shakeEnvelope(t);
    for (const p of this.people) {
      switch (p.type) {
        case 'walker': this.walker(p, t, dt, shake); break;
        case 'plaza': this.plazaP(p, t, dt, shake); break;
        case 'beach': this.beachP(p, t, dt, shake); break;
        case 'hill': this.hillP(p, t, dt, shake); break;
      }
      p.apply(p.pose);
    }
  }

  // tsunami: run inland
  fleeInland(p, t, dt) {
    const v = 4.2 + p.react * 1.2;
    p.move((p.choice - 0.5) * 0.6, v, dt);
    p.setPose(poseRun(p.walkPh), dt, 8);
  }

  walker(p, t, dt, shake) {
    const tStop = T.pStart + 0.8 + p.react * 1.6;
    const tReact = T.sStart + 0.2 + p.react * 1.0;
    if (t > T.runInland + p.react * 2) return this.fleeInland(p, t, dt);
    if (t < tStop) {
      p.move(0, p.dir * p.v, dt);
      if (p.z > 140) p.z -= 160; if (p.z < -20) p.z += 160;
      p.setPose(poseWalk(p.walkPh), dt, 10);
      return;
    }
    if (t < tReact) {
      p.speed = 0;
      p.setPose(p.choice < 0.35 ? posePhone(t, p.phase) : poseLookAround(t, p.phase), dt, 3);
      return;
    }
    if (t < T.shakeEnd + p.react * 2.5) {
      if (!p.target) {
        const danger = p.lane < 0 && p.z > 8 && p.z < 66;
        if (p.choice < 0.6 || danger) p.target = [0.5 + p.react * 3, p.z + (p.choice - 0.5) * 6];
        else p.target = [p.x, p.z];
        p.fallT = p.choice > 0.85 ? tReact + 0.6 : null;
      }
      if (p.fallT && t > p.fallT && t < p.fallT + 2.2) { p.speed = 0; p.setPose(poseFallen(t, p.phase), dt, 7); return; }
      const dx = p.target[0] - p.x, dz = p.target[1] - p.z, d = Math.hypot(dx, dz);
      if (d > 0.4) {
        const v = Math.min(3.6, d * 2) * (1 - shake * 0.35);
        p.move(dx / d * v, dz / d * v, dt);
        p.setPose(mix(poseRun(p.walkPh, 0.8), poseLookAround(t, p.phase), shake * 0.15), dt, 8);
      } else {
        p.speed = 0;
        p.setPose(poseCrouch(t, p.phase, shake), dt, 5);
      }
      return;
    }
    // aftermath
    p.speed = 0;
    p.setPose(p.choice < 0.25 ? posePhone(t, p.phase) : p.choice < 0.35 ? poseHug(t, p.phase) : poseLookAround(t * 0.6, p.phase), dt, 2.5);
  }

  plazaP(p, t, dt, shake) {
    const tReact = T.sStart + 0.3 + p.react * 1.3;
    if (t > T.runInland + p.react * 2) return this.fleeInland(p, t, dt);
    if (t < T.pStart + 1 + p.react * 2) {
      if (p.wander) {
        const a = t * 0.08 * p.v + p.phase;
        const tx = p.home[0] + Math.cos(a) * 3, tz = p.home[1] + Math.sin(a) * 3;
        const dx = tx - p.x, dz = tz - p.z, d = Math.hypot(dx, dz);
        if (d > 0.2) { p.move(dx / d * Math.min(1.2, d), dz / d * Math.min(1.2, d), dt); p.setPose(poseWalk(p.walkPh, Math.min(1, d)), dt, 8); }
        else p.setPose(poseIdle(t, p.phase), dt, 4);
      } else p.setPose(poseIdle(t, p.phase), dt, 4);
      return;
    }
    if (t < tReact) { p.speed = 0; p.setPose(p.choice < 0.4 ? posePhone(t, p.phase) : poseLookAround(t, p.phase), dt, 3); return; }
    if (t < T.shakeEnd + p.react * 2) {
      // move away from trees / kiosk toward open space, then crouch
      if (!p.target) p.target = [lerp(p.x, 27, 0.3), lerp(p.z, 33, 0.25)];
      const dx = p.target[0] - p.x, dz = p.target[1] - p.z, d = Math.hypot(dx, dz);
      if (d > 0.4 && t < tReact + 3) { const v = Math.min(3, d * 2); p.move(dx / d * v, dz / d * v, dt); p.setPose(poseRun(p.walkPh, 0.7), dt, 8); }
      else { p.speed = 0; p.setPose(poseCrouch(t, p.phase, shake), dt, 5); }
      return;
    }
    p.speed = 0;
    p.setPose(p.choice < 0.3 ? poseHug(t, p.phase) : p.choice < 0.55 ? posePhone(t, p.phase) : poseLookAround(t * 0.7, p.phase), dt, 2.5);
  }

  beachP(p, t, dt, shake) {
    if (t > T.runInland - 0.5 + p.react * 1.5) {
      const v = 4.5 + p.react;
      p.move((-p.x) * 0.02, v, dt);
      p.setPose(poseRun(p.walkPh), dt, 8);
      return;
    }
    if (t > T.recedeStart + 1 + p.react * 2) {
      // curiosity: walk toward the receding water and point
      if (p.choice < 0.45 && t < T.tsunamiAlarm + 1) { p.move(0, -0.9, dt); p.setPose(poseWalk(p.walkPh, 0.8), dt, 8); return; }
      p.speed = 0;
      p.turnTo(Math.PI, dt, 2);
      p.setPose(p.choice > 0.7 ? posePoint(t, p.phase) : p.choice > 0.5 ? posePhone(t, p.phase) : poseLookAround(t * 0.5, p.phase), dt, 3);
      return;
    }
    const a = t * 0.05 * p.v + p.phase;
    const tx = p.home[0] + Math.cos(a) * 6, tz = p.home[1] + Math.sin(a) * 3;
    const dx = tx - p.x, dz = tz - p.z, d = Math.hypot(dx, dz);
    if (d > 0.3) { p.move(dx / d * Math.min(1.1, d), dz / d * Math.min(1.1, d), dt); p.setPose(poseWalk(p.walkPh, Math.min(1, d)), dt, 8); }
    else p.setPose(poseIdle(t, p.phase), dt, 4);
  }

  hillP(p, t, dt) {
    p.speed = 0;
    p.turnTo(Math.PI + (p.home[0] - 40) * -0.004, dt, 2);
    if (t > T.waveHitCoast - 4 && t < T.globeCut + 2 && p.choice > 0.6) p.setPose(posePoint(t, p.phase), dt, 3);
    else if (p.choice < 0.25) p.setPose(poseHug(t, p.phase), dt, 3);
    else if (p.choice < 0.4) p.setPose(posePhone(t, p.phase), dt, 3);
    else p.setPose(poseIdle(t, p.phase), dt, 3);
  }
}
