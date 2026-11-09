import * as THREE from 'three';
import { T, smooth, clamp, lerp, groundMotion, shakeEnvelope } from './timeline.js';
import { terrainHeight } from './city.js';

// Keyframes: [time, pos[x,y,z], target[x,y,z], fov]
const EYE = 1.68;
const hillY = (x, z) => terrainHeight(x, z) + EYE;

const SHOTS = [
  { from: 0, to: T.introEnd, fp: false, keys: [
    [0, [430, 40, -560], [20, 18, -60], 46],
    [6, [330, 52, -440], [10, 20, -20], 46],
    [12, [220, 66, -330], [0, 22, 30], 44],
    [18, [120, 80, -240], [-10, 18, 90], 44],
  ] },
  { from: T.introEnd, to: T.beachCut, fp: true, keys: [
    [18.0, [6.1, EYE, 118], [6.4, 1.9, 98], 62],
    [24.0, [6.1, EYE, 110.5], [3.0, 3.2, 92], 62],
    [29.0, [6.1, EYE, 104.2], [-6, 6.0, 90], 62],
    [33.0, [6.1, EYE, 99.2], [5.5, 2.4, 80], 62],
    [37.5, [6.1, EYE, 93.6], [6.2, 1.8, 74], 62],
    [40.0, [6.1, EYE, 90.6], [6.6, 0.4, 82], 60],
    [43.0, [6.1, EYE, 88.2], [6.4, 0.6, 80], 60],
    [45.5, [6.1, EYE, 87.6], [2, 3.5, 70], 62],
    [48.0, [6.6, EYE, 87.2], [-8, 9, 66], 64],
    [50.5, [6.2, EYE, 86.5], [-14, 26, 70], 66],
    [53.0, [6.0, EYE, 85.5], [-10, 20, 50], 66],
    [55.5, [5.8, EYE, 84.8], [-16, 16, 49], 64],
    [57.8, [5.8, EYE, 84.2], [-14, 8, 52], 64],
    [58.7, [5.9, EYE, 83.6], [-5, 5, 74], 66],
    [59.8, [6.4, EYE, 82.6], [3, 1.6, 74], 66],
    [61.0, [4.2, EYE, 74.0], [10, 1.6, 58], 68],
    [62.5, [11.0, EYE, 61.5], [19, 1.4, 48], 68],
    [63.8, [18.4, 1.5, 53.4], [14, 1.0, 40], 66],
    [65.0, [19.0, 0.95, 51.8], [24, 0.6, 40], 64],
    [67.0, [19.0, 0.95, 51.6], [-12, 8, 26], 62],
    [69.5, [19.0, 0.95, 51.6], [-17, 9, 18], 60],
    [72.0, [19.0, 0.95, 51.6], [0, 6, 0], 62],
    [75.0, [19.0, 0.95, 51.6], [10, 2, 30], 62],
    [77.0, [19.0, 0.95, 51.6], [17, 0, 38], 62],
    [79.0, [19.0, 0.95, 51.6], [26, 0, 40], 62],
    [81.0, [19.0, 0.95, 51.6], [6, 0, 44], 60],
    [83.5, [19.0, 0.95, 51.6], [4, 0.6, 44], 58],
    [86.0, [19.0, EYE, 51.6], [-2, 6, 40], 62],
    [89.0, [18.4, EYE, 50.8], [-8, 9, 70], 62],
  ] },
  { from: T.beachCut, to: T.hillCut, fp: true, keys: [
    [89.0, [3.0, EYE + 0.2, -149.5], [0, -5, -260], 60],
    [92.0, [3.0, EYE + 0.2, -151.5], [0, -7, -270], 58],
    [94.5, [3.0, EYE + 0.2, -152.5], [-25, 0, -190], 60],
    [96.2, [3.0, EYE + 0.2, -152.8], [10, 0, -260], 56],
    [97.4, [3.0, EYE + 0.2, -152.0], [6, 2.5, -100], 66],
    [99.0, [0.3, EYE, -142.0], [0.3, 2, -80], 70],
    [101.0, [0.0, EYE, -130.0], [0, 2, -60], 70],
  ] },
  { from: T.hillCut, to: T.globeCut, fp: true, keys: [
    [101.0, [40, hillY(40, 268), 268], [10, 6, -200], 50],
    [104.0, [41, hillY(41, 267), 267], [8, 4, -240], 42],
    [108.0, [42, hillY(42, 266), 266], [5, 0, -160], 40],
    [112.0, [43, hillY(43, 265), 265], [0, 0, -60], 46],
  ] },
  { from: T.endingCut, to: 142, fp: true, keys: [
    [124.0, [58, hillY(58, 272), 272], [30, 34, 110], 52],
    [130.0, [50, hillY(50, 272), 272], [22, 32, 100], 50],
    [136.0, [42, hillY(42, 272), 272], [14, 30, 90], 48],
    [142.0, [38, hillY(38, 272), 272], [10, 30, 80], 46],
  ] },
];

function catmull(p0, p1, p2, p3, t) {
  const t2 = t * t, t3 = t2 * t;
  return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
}
function sample(keys, t, idx) {
  let i = 0;
  while (i < keys.length - 2 && t > keys[i + 1][0]) i++;
  const k1 = keys[i], k2 = keys[Math.min(i + 1, keys.length - 1)];
  const k0 = keys[Math.max(0, i - 1)], k3 = keys[Math.min(keys.length - 1, i + 2)];
  let u = clamp((t - k1[0]) / Math.max(1e-6, k2[0] - k1[0]), 0, 1);
  u = u * u * (3 - 2 * u) * 0.35 + u * 0.65; // soft ease, keeps velocity continuous-ish
  if (idx === 3) return lerp(k1[3], k2[3], u * u * (3 - 2 * u));
  return [0, 1, 2].map(c => catmull(k0[idx][c], k1[idx][c], k2[idx][c], k3[idx][c], u));
}

export function shotAt(t) {
  for (const s of SHOTS) if (t >= s.from && t < s.to) return s;
  return null;
}

export class CameraRig {
  constructor(camera) {
    this.cam = camera;
    this.bobPh = 0;
    this.prev = null;
    this.gm = { x: 0, y: 0, z: 0 };
    this.smoothSpeed = 0;
  }

  update(t, dt) {
    const s = shotAt(t);
    if (!s) return false;
    const pos = sample(s.keys, t, 1);
    const tgt = sample(s.keys, t, 2);
    const fov = sample(s.keys, t, 3);
    const cam = this.cam;
    // head bob from speed
    if (s.fp) {
      const cur = new THREE.Vector3(...pos);
      const sp = this.prev && this.prev.s === s ? cur.distanceTo(this.prev.p) / dt : 0;
      this.prev = { p: cur, s };
      this.smoothSpeed = lerp(this.smoothSpeed, sp, 1 - Math.exp(-dt * 6));
      const v = this.smoothSpeed;
      this.bobPh += dt * (v > 3 ? 11 : 8.2) * clamp(v / 1.3, 0, 1.6);
      const amp = clamp(v / 1.3, 0, 2.2);
      pos[1] += Math.abs(Math.sin(this.bobPh)) * 0.045 * amp - 0.02 * amp;
      pos[0] += Math.sin(this.bobPh) * 0.025 * amp;
      tgt[1] += Math.abs(Math.sin(this.bobPh)) * 0.03 * amp;
      // breathing / handheld micro motion
      pos[1] += Math.sin(t * 1.7) * 0.006;
      tgt[0] += Math.sin(t * 0.63) * 0.08 + Math.sin(t * 1.37) * 0.04;
      tgt[1] += Math.sin(t * 0.81) * 0.06;
    } else {
      this.prev = null;
      tgt[0] += Math.sin(t * 0.3) * 1.5;
    }
    // earthquake shaking
    const e = shakeEnvelope(t);
    let roll = 0;
    if (e > 0 && s.fp && t < T.beachCut) {
      groundMotion(t, this.gm);
      const crouch = pos[1] < 1.2 ? 0.55 : 1;
      pos[0] += this.gm.x * 0.6 * crouch; pos[1] += this.gm.y * 0.5 * crouch; pos[2] += this.gm.z * 0.6 * crouch;
      tgt[0] += this.gm.x * 2.2 * crouch; tgt[1] += this.gm.y * 2.5 * crouch; tgt[2] += this.gm.z * 1.4;
      roll = e * 0.05 * Math.sin(t * 5.3) + e * 0.025 * Math.sin(t * 13.1);
    }
    // the hill shot: the ground still trembles from aftershocks
    if (t > T.hillCut && t < T.globeCut) {
      const a = 0.04 * smooth(T.waveHitCoast - 1, T.waveHitCoast + 1, t) * (1 - smooth(T.waveHitCoast + 3, T.globeCut, t));
      pos[1] += a * Math.sin(t * 23); tgt[0] += a * 6 * Math.sin(t * 17);
    }
    cam.position.set(...pos);
    cam.up.set(0, 1, 0);
    cam.lookAt(tgt[0], tgt[1], tgt[2]);
    cam.rotateZ(roll);
    // vertical 9:16 frame: widen the vertical FOV so the horizontal view stays usable
    const vf = cam.aspect < 1 ? 2 * Math.atan(Math.tan(fov * Math.PI / 360) * 1.5) * 180 / Math.PI : fov;
    if (cam.fov !== vf) { cam.fov = vf; cam.updateProjectionMatrix(); }
    return true;
  }
}

// ---------------------------------------------------------------------- phone in hand
export class Phone {
  constructor(camera) {
    const g = this.group = new THREE.Group();
    camera.add(g);
    const skin = new THREE.MeshStandardMaterial({ color: 0xd9a582, roughness: 0.55 });
    const sleeve = new THREE.MeshStandardMaterial({ color: 0x2b3a55, roughness: 0.85 });
    const body = new THREE.MeshPhysicalMaterial({ color: 0x1a1c1f, roughness: 0.25, metalness: 0.7, clearcoat: 1 });
    this.canvas = document.createElement('canvas');
    this.canvas.width = 360; this.canvas.height = 720;
    this.ctx = this.canvas.getContext('2d');
    this.tex = new THREE.CanvasTexture(this.canvas);
    this.tex.colorSpace = THREE.SRGBColorSpace;
    this.tex.anisotropy = 8;
    const screenMat = new THREE.MeshBasicMaterial({ map: this.tex, toneMapped: false });
    const phone = new THREE.Group();
    const shape = new THREE.Shape();
    const w = 0.072, h = 0.15, r = 0.01;
    shape.moveTo(-w / 2 + r, -h / 2); shape.lineTo(w / 2 - r, -h / 2); shape.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
    shape.lineTo(w / 2, h / 2 - r); shape.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2); shape.lineTo(-w / 2 + r, h / 2);
    shape.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r); shape.lineTo(-w / 2, -h / 2 + r); shape.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
    const bodyM = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.008, bevelEnabled: true, bevelThickness: 0.001, bevelSize: 0.001, bevelSegments: 2 }), body);
    bodyM.position.z = -0.008; phone.add(bodyM);
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.006, h - 0.008), screenMat);
    scr.position.z = 0.0012; phone.add(scr);
    // hand: palm + thumb + fingers wrapping the phone
    const palm = new THREE.Mesh(new THREE.CapsuleGeometry(0.032, 0.05, 6, 12), skin);
    palm.scale.set(1.25, 1, 0.6); palm.position.set(0.012, -0.055, -0.03); phone.add(palm);
    const thumb = new THREE.Mesh(new THREE.CapsuleGeometry(0.011, 0.045, 4, 8), skin);
    thumb.position.set(0.04, -0.035, 0.004); thumb.rotation.z = 0.5; phone.add(thumb);
    for (let i = 0; i < 4; i++) {
      const f = new THREE.Mesh(new THREE.CapsuleGeometry(0.0095, 0.03, 4, 8), skin);
      f.position.set(-0.04, -0.03 + i * 0.022, -0.004); f.rotation.z = -0.2; phone.add(f);
    }
    const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.045, 0.4, 14), sleeve);
    arm.position.set(0.06, -0.24, -0.06); arm.rotation.set(0.6, 0, 0.35); phone.add(arm);
    const wrist = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.033, 0.06, 12), skin);
    wrist.position.set(0.025, -0.1, -0.035); wrist.rotation.set(0.6, 0, 0.35); phone.add(wrist);
    phone.traverse(o => { if (o.isMesh) o.renderOrder = 10; });
    this.phone = phone;
    g.add(phone);
    this.lastKey = '';
    const light = new THREE.PointLight(0xffffff, 0.0, 0.6);
    light.position.set(0, 0, 0.1); phone.add(light);
    this.light = light;
  }

  draw(t) {
    const alert = t >= T.alert;
    const sec = Math.floor(t * 2);
    const key = alert ? 'a' + sec : 'n' + Math.floor(t);
    if (key === this.lastKey) return;
    this.lastKey = key;
    const c = this.ctx, W = 360, H = 720;
    if (!alert) {
      const g = c.createLinearGradient(0, 0, W, H);
      g.addColorStop(0, '#22476b'); g.addColorStop(1, '#0e1a2b');
      c.fillStyle = g; c.fillRect(0, 0, W, H);
      c.fillStyle = 'rgba(255,255,255,0.9)'; c.font = '600 96px Inter, sans-serif'; c.textAlign = 'center';
      c.fillText('08:41', W / 2, 200);
      c.font = '500 26px Inter, sans-serif'; c.fillText('martes, 14 de abril', W / 2, 245);
      c.fillStyle = 'rgba(255,255,255,0.15)'; roundRect(c, 24, 300, W - 48, 90, 22); c.fill();
      c.fillStyle = '#fff'; c.textAlign = 'left'; c.font = '600 22px Inter'; c.fillText('Mamá', 50, 338);
      c.font = '400 20px Inter'; c.fillStyle = 'rgba(255,255,255,0.8)'; c.fillText('¿Llegas a comer hoy?', 50, 368);
      this.tex.needsUpdate = true;
      return;
    }
    const blink = Math.floor(t * 4) % 2 === 0;
    c.fillStyle = blink ? '#c4161c' : '#9c0f14'; c.fillRect(0, 0, W, H);
    c.fillStyle = '#fff'; c.textAlign = 'center';
    // warning triangle
    c.beginPath(); c.moveTo(W / 2, 90); c.lineTo(W / 2 + 70, 210); c.lineTo(W / 2 - 70, 210); c.closePath();
    c.lineWidth = 10; c.strokeStyle = '#fff'; c.lineJoin = 'round'; c.stroke();
    c.font = '800 70px Inter'; c.fillText('!', W / 2, 198);
    c.font = '800 40px Inter'; c.fillText('ALERTA', W / 2, 280); c.fillText('SÍSMICA', W / 2, 326);
    c.font = '500 22px Inter';
    c.fillText('Sismo extremadamente', W / 2, 380); c.fillText('fuerte detectado.', W / 2, 408);
    c.fillText('Aléjate de edificios.', W / 2, 446); c.fillText('Agáchate, cúbrete, sujétate.', W / 2, 474);
    const rem = Math.max(0, Math.ceil(T.sStart - t));
    c.fillStyle = 'rgba(0,0,0,0.25)'; roundRect(c, 40, 520, W - 80, 140, 24); c.fill();
    c.fillStyle = '#fff'; c.font = '600 22px Inter'; c.fillText('Ondas S llegan en', W / 2, 562);
    c.font = '800 64px Inter'; c.fillText(rem > 0 ? rem + ' s' : 'AHORA', W / 2, 634);
    this.tex.needsUpdate = true;
  }

  update(t) {
    // raised between alert-0.4 and ~47.5
    const up = smooth(T.alert - 0.6, T.alert + 0.1, t) * (1 - smooth(46.6, 47.6, t));
    this.group.visible = up > 0.001;
    if (!this.group.visible) return;
    this.draw(t);
    const vib = t > T.alert && t < T.alert + 1.6 ? 0.004 * Math.sin(t * 160) : 0;
    const e = shakeEnvelope(t);
    this.phone.position.set(0.07 + vib + e * 0.01 * Math.sin(t * 9), lerp(-0.5, -0.115, up) + e * 0.008 * Math.sin(t * 11), -0.33);
    this.phone.rotation.set(0.32 + (1 - up) * 0.6, -0.12, 0.06 + vib * 4);
    this.light.intensity = 0.15 * up;
  }
}

function roundRect(c, x, y, w, h, r) {
  c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
