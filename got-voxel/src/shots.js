// Lista de planos (tiempos medidos sobre el video original, 4:22 a 30 fps).
import * as THREE from 'three';
import { smooth, smoother, lerp, clamp, range, hash3 } from './voxel.js';
import { blendPose } from './characters.js';
import { THRONE_POS } from './world.js';

// interpolacion por keyframes: keys = [[t, valor(es)], ...]
export function kf(t, keys, ease = smooth) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [ta, va] = keys[i], [tb, vb] = keys[i + 1];
    if (t <= tb) {
      const k = ease((t - ta) / (tb - ta));
      if (typeof va === 'number') return lerp(va, vb, k);
      return va.map((v, j) => lerp(v, vb[j], k));
    }
  }
  return keys[keys.length - 1][1];
}
export function kpose(t, keys) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [ta, a] = keys[i], [tb, b] = keys[i + 1];
    if (t <= tb) return blendPose(a, b, smooth((t - ta) / (tb - ta)));
  }
  return keys[keys.length - 1][1];
}
const sin = Math.sin, cos = Math.cos, PI = Math.PI;
const V = (x, y, z) => new THREE.Vector3(x, y, z);

// ---------------------------------------------------------------------------
// Poses de personajes
// ---------------------------------------------------------------------------
const EXP = {
  cry: { eyes: 'squint', mouth: 'closed', brow: 'sad', tears: true },
  sob: { eyes: 'squint', mouth: 'open', brow: 'sad', tears: true },
  sad: { eyes: 'open', mouth: 'closed', brow: 'sad', tears: true },
  up: { eyes: 'up', mouth: 'part', brow: 'fear', tears: true },
  fear: { eyes: 'wide', mouth: 'part', brow: 'fear', tears: false },
  shout: { eyes: 'squint', mouth: 'grit', brow: 'fear', tears: false },
  dead: { eyes: 'closed', mouth: 'part', brow: 'neutral' },
};
export const POSE = {
  jonCradle: {
    hpL: [-1.45, 0.25, 0], knL: [2.7, 0, 0], hpR: [-1.45, -0.25, 0], knR: [2.7, 0, 0],
    spine: [0.38, -0.15, 0], neck: [0.15, -0.2, 0], head: [0.3, -0.45, 0],
    shR: [-0.55, 0.5, -0.05], elR: [-0.25, 0, 0], shL: [-0.75, 0, 0.35], elL: [-1.0, 0, 0],
    expr: EXP.cry,
  },
  jonKneelFloor: {
    hpL: [-1.5, 0.2, 0], knL: [2.8, 0, 0], hpR: [-0.2, -0.1, 0], knR: [1.5, 0, 0],
    spine: [0.75, 0, 0], neck: [0.2, 0, 0], head: [0.3, 0, 0],
    shR: [-0.9, 0, -0.1], elR: [-0.4, 0, 0], shL: [-0.9, 0, 0.1], elL: [-0.5, 0, 0], expr: EXP.cry,
  },
  jonStand: { shL: [0.02, 0, 0.06], shR: [0.02, 0, -0.06], elL: [-0.1, 0, 0], elR: [-0.1, 0, 0], expr: EXP.sad },
  jonLookUp: { neck: [-0.25, 0, 0], head: [-0.35, 0, 0], shL: [0.05, 0, 0.1], shR: [0.05, 0, -0.1], elL: [-0.2, 0, 0], elR: [-0.2, 0, 0], expr: EXP.up },
  jonCrouch: {
    hpL: [-1.6, 0.2, 0], knL: [2.4, 0, 0], hpR: [-1.2, -0.2, 0], knR: [2.0, 0, 0],
    spine: [0.95, 0.2, 0], neck: [0.4, 0, 0], head: [0.3, 0.3, 0],
    shL: [-2.4, 0, 0.6], elL: [-1.6, 0, 0], shR: [-2.3, 0, -0.5], elR: [-1.5, 0, 0], expr: EXP.shout,
  },
  danyCradled: {
    spine: [0.1, 0, 0], neck: [-0.3, -0.3, 0], head: [-0.25, -0.5, 0],
    shL: [0.1, 0, 0.25], elL: [-0.3, 0, 0], shR: [0.3, 0, -0.6], elR: [-0.2, 0, 0],
    hpL: [0.5, 0, 0.05], hpR: [0.5, 0, -0.05], hair: 0.6, expr: EXP.dead, dagger: false,
  },
  danyFloor: {
    neck: [-0.1, 0, 0], head: [-0.1, -0.55, 0], shL: [0, 0, 0.12], shR: [0, 0, -0.12], elL: [-0.15, 0, 0], elR: [-0.15, 0, 0],
    hpL: [0, 0, 0.05], hpR: [0, 0, -0.05], hair: 1.35, expr: EXP.dead, dagger: true,
  },
};

const DANY_FLOOR = [0.55, 0.13, 0.4];
function danyLying(D, pos, yaw = 0) {
  D.dany.root.position.set(...pos);
  D.dany.root.rotation.set(-PI / 2, PI / 2 + yaw, 0, 'YXZ');
}
function danyCradledAt(D, pos, up = 0.9, yaw = 0) {
  D.dany.root.position.set(...pos);
  D.dany.root.rotation.set(-up, yaw, PI / 2, 'XYZ');
}
function danyOnFloor(D, over = {}) {
  danyLying(D, DANY_FLOOR, 0.05);
  D.dany.pose({ ...POSE.danyFloor, ...over });
}
function jonAt(D, pos, yaw, pose, extra = {}) {
  D.jon.root.position.set(...pos); D.jon.root.rotation.set(0, yaw, 0);
  D.jon.pose({ ...pose, ...extra });
}
function breathe(lt, a = 0.02) { return sin(lt * 1.7) * a; }

const JON_STAND = [1.8, 0.75, -1.4];
const JON_CROUCH = [1.3, 0.42, -5.9];

// ---------------------------------------------------------------------------
// Poses de Drogon
// ---------------------------------------------------------------------------
const WING_FOLD = { raise: -0.35, sweep: 1.25, elbow: 2.5, spread: 0.1, wrist: 2.6, elbowRaise: -0.15, fingerDroop: -0.15 };
const WING_HALF = { raise: 0.25, sweep: 0.55, elbow: 1.2, spread: 0.55, wrist: -0.2 };
const WING_OPEN = { raise: 0.45, sweep: 0.15, elbow: 0.35, spread: 1.0, wrist: 0 };
function wingMix(a, b, k) { const o = {}; for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) o[key] = lerp(a[key] ?? 0, b[key] ?? 0, k); return o; }

function drogon(D, p) { D.drogon.root.visible = true; D.drogon.pose(p); D.drogon.root.updateMatrixWorld(true); }
function dragonSniff(lt, extra = {}) {
  return {
    pos: [-5.6, 0, -2.6], yaw: 1.08, bodyY: 2.5, pitch: 0.12, roll: sin(lt * 0.5) * 0.02,
    neckPitch0: 0.05, neckPitch1: 0.32 + sin(lt * 0.6) * 0.03, neckYaw0: 0.05, neckYaw1: -0.02,
    headPitch: 0.28 + sin(lt * 0.9) * 0.04, headYaw: sin(lt * 0.4) * 0.08, jaw: 0.02,
    wing: WING_FOLD, hip: 0.35, knee: -0.4, tailYaw: 0.25, tailWave: lt * 0.8, tailAmp: 0.06, ...extra,
  };
}
const DRAGON_FIRE_POS = [-4.6, 0, -1.4];
const DRAGON_FIRE_YAW = 2.72;
function dragonFire(lt, extra = {}) {
  return {
    pos: DRAGON_FIRE_POS, yaw: DRAGON_FIRE_YAW, bodyY: 3.0, pitch: -0.12, roll: 0,
    neckPitch0: -0.22, neckPitch1: 0.12, neckYaw0: 0.02 + sin(lt * 0.7) * 0.03, neckYaw1: 0.04,
    headPitch: 0.05, headYaw: sin(lt * 1.1) * 0.05, jaw: 0.75 + sin(lt * 7) * 0.05,
    wing: WING_HALF, hip: 0.3, knee: -0.35, tailYaw: 0.3, tailWave: lt, tailAmp: 0.08, ...extra,
  };
}
function dragonFly(t, extra = {}) {
  const f = sin(t * 2 * PI * 0.55);
  return {
    bodyY: 0, pitch: -0.08 + f * 0.04, roll: sin(t * 0.4) * 0.06,
    neckPitch0: 0.0, neckPitch1: 0.05, headPitch: 0.1, jaw: 0,
    wing: { raise: 0.15 + f * 0.75, sweep: 0.2, elbow: 0.3 - f * 0.15, spread: 1.0, wrist: -f * 0.25, elbowRaise: -f * 0.25 },
    hip: 1.2, knee: -0.6, tailPitch: 0.02, tailYaw: 0.0, tailWave: t * 1.5, tailAmp: 0.05, ...extra,
  };
}

const _o = new THREE.Vector3(), _d = new THREE.Vector3();
function breathFire(D, t, opts = {}) {
  D.drogon.mouth.getWorldPosition(_o);
  D.drogon.head.getWorldDirection(_d);
  _d.y -= opts.dip ?? 0.12; _d.normalize();
  D.fx.fire.visible = true;
  D.fx.fire.update(t, _o, _d, { on: opts.on || (() => true), speed: 20, life: opts.life ?? 0.75, spread: 0.1, reach: opts.reach ?? 10, scale: opts.scale ?? 0.65, hot: 0.6 });
  const fl = 0.85 + 0.15 * sin(t * 23) * sin(t * 7.3);
  D.fireLight.position.copy(_o).addScaledVector(_d, 3); D.fireLight.intensity = 30 * fl * (opts.k ?? 1); D.fireLight.distance = 30;
  D.fireLight2.position.copy(_o).addScaledVector(_d, opts.reach ?? 10); D.fireLight2.intensity = 45 * fl * (opts.k ?? 1); D.fireLight2.distance = 25;
}
function fireMood(D, k = 1) {
  const G = D.ctx.grade.uniforms;
  G.uTint.value.set(lerp(0.95, 1.12, k), lerp(1.0, 0.98, k), lerp(1.06, 0.82, k));
  G.uSat.value = lerp(0.85, 1.05, k);
  D.ctx.bloom.strength = lerp(0.45, 0.6, k); D.ctx.bloom.threshold = lerp(0.85, 0.8, k);
  D.ctx.scene.fog.color.set(k > 0.5 ? 0x8a6a58 : 0xa3b0bc);
  D.hemi.intensity = lerp(1.25, 0.8, k);
  D.sky.material.uniforms.uWarm.value.setRGB(0.25 * k, 0.12 * k, 0.03 * k);
}
function throneFire(D, t, k = 1) {
  const tp = THRONE_POS;
  const src = [];
  for (let i = 0; i < 9; i++) {
    const a = i / 9 * PI * 2;
    src.push({ p: [tp.x + cos(a) * 2.2, tp.y, tp.z + sin(a) * 1.6], r: 1.0, h: 2.2, s: 0.22, k, hot: 0.5 });
  }
  src.push({ p: [tp.x, tp.y + 1, tp.z], r: 1.4, h: 3.5, s: 0.3, k, hot: 0.5 });
  for (let i = 0; i < 6; i++) src.push({ p: [tp.x - 5 + i * 2, 0.6 + (i % 2) * 0.5, tp.z + 4.5], r: 0.8, h: 1.4, s: 0.2, k: k * 0.8, hot: 0.5 });
  D.fx.flames.visible = true; D.fx.flames.update(t, src);
}
function lava(D, t, cover, heat = 1) {
  const tp = THRONE_POS;
  D.fx.lava.visible = true;
  D.fx.lava.update(t, [tp.x, tp.y + 0.06, tp.z + 0.8], {
    heat,
    mask: (x, z) => {
      const dx = (x - tp.x) / 4.2, dz = (z - tp.z - 0.8) / 3.0;
      const r = Math.hypot(dx, dz) + (hash3(Math.floor(x * 8), 0, Math.floor(z * 8)) - 0.5) * 0.25;
      return clamp((cover - r) * 4);
    },
    height: (x, z, tt) => 0.02 * sin(x * 3 + tt) * sin(z * 2.5 - tt),
  });
}

function camKF(D, lt, pk, lk, fov = 30, focus = null, ap = 0.003, mb = 0.015, shake = 0) {
  const p = kf(lt, pk), l = kf(lt, lk);
  const sx = shake ? (hash3(Math.floor(lt * 30), 1, 1) - 0.5) * shake : 0, sy = shake ? (hash3(Math.floor(lt * 30), 2, 1) - 0.5) * shake : 0;
  D.camera([p[0] + sx, p[1] + sy, p[2]], l, fov);
  D.focus(focus ?? Math.hypot(p[0] - l[0], p[1] - l[1], p[2] - l[2]), ap, mb);
}
function snow(D, lt, c, s = [8, 6, 8], o = {}) { D.fx.ash.visible = true; D.fx.ash.update(lt, c, s, { speed: 0.3, ...o }); }
// posicion del centro de la cabeza de un personaje
function headOf(ch) { ch.root.updateMatrixWorld(true); return ch.head.localToWorld(new THREE.Vector3(0, 0.25, 0.05)); }
function dragonHead(D) { return D.drogon.head.localToWorld(new THREE.Vector3(0, 0.1, 1.0)); }
// camara frente a un personaje: ang = giro respecto a su frente, dy = altura relativa, ly = ajuste del objetivo
function frontCam(D, ch, lt, { dist = 1.6, ang = 0.35, dy = 0, ly = -0.05, fov = 30, ap = 0.005, drift = 0.02 } = {}) {
  const h = headOf(ch);
  const yaw = ch.root.rotation.y + ang;
  const p = [h.x + Math.sin(yaw) * dist + Math.sin(lt * 0.3) * drift, h.y + dy, h.z + Math.cos(yaw) * dist];
  D.camera(p, [h.x, h.y + ly, h.z], fov);
  D.focus(Math.hypot(p[0] - h.x, p[1] - h.y, p[2] - h.z), ap, 0.02);
}
// camara que mira a un punto desde una posicion
function look(D, p, l, fov = 36, ap = 0.002) { D.camera(p, [l.x ?? l[0], l.y ?? l[1], l.z ?? l[2]], fov); const L = l.x !== undefined ? [l.x, l.y, l.z] : l; D.focus(Math.hypot(p[0] - L[0], p[1] - L[1], p[2] - L[2]), ap, 0.012); }
function danyInClaw(D, wingIdx = 1) {
  const wr = D.drogon.wings[wingIdx].wr; const wp = new THREE.Vector3(); wr.getWorldPosition(wp);
  return wp;
}

// ---------------------------------------------------------------------------
// Planos
// ---------------------------------------------------------------------------
export const SHOTS = [
  // A 0:00 - 0:45.8  Jon llora sosteniendo a Daenerys; Drogon aparece al fondo
  { t0: 0, t1: 45.8, run(D, lt) {
    const p = { ...POSE.jonCradle };
    const sob = sin(lt * 2.1) * 0.5 + 0.5;
    p.spine = [0.3 + sob * 0.04 + sin(lt * 0.4) * 0.03, -0.1 + sin(lt * 0.3) * 0.04, 0];
    p.neck = [0.12 + sin(lt * 0.7) * 0.04, -0.1, 0];
    p.head = [0.25 + kf(lt, [[0, 0], [8, 0.08], [16, -0.05], [26, 0.1], [34, 0], [40, -0.12], [45.8, -0.05]]), -0.25 + kf(lt, [[0, -0.05], [12, 0.05], [24, -0.1], [36, 0.0], [45.8, -0.05]]), 0];
    const crying = (lt > 9 && lt < 12) || (lt > 19 && lt < 22.5) || (lt > 27 && lt < 29);
    p.expr = lt > 40 ? EXP.sad : crying ? EXP.sob : EXP.cry;
    jonAt(D, [0, 0.42, 0], 0, p);
    danyCradledAt(D, [0.6, 0.5, 0.42], 0.9, 0); D.dany.pose(POSE.danyCradled);
    if (lt > 28) {
      const k = smooth(range(lt, 28, 45));
      drogon(D, { ...dragonSniff(lt), pos: [lerp(-15, -7.5, k), 0, lerp(-17, -10, k)], yaw: lerp(0.9, 0.75, k), neckPitch1: 0.2, headPitch: 0.2 });
    }
    camKF(D, lt, [[0, [0.15, 0.6, 2.75]], [20, [0.2, 0.62, 2.7]], [30, [0.1, 0.58, 2.8]], [45.8, [0.15, 0.6, 2.72]]],
      [[0, [-0.15, 0.98, 0.15]], [20, [-0.12, 0.99, 0.12]], [30, [-0.17, 0.98, 0.12]], [45.8, [-0.15, 0.98, 0.12]]], 30, 2.65, 0.004, 0.02);
    D.setSun([-7, 14, -12], [0, 1, 0], 3);
    snow(D, lt, [0, 1.6, 0], [5, 4, 5], { speed: 0.25 });
  } },
  // B 0:45.8 - 0:52.3  Rostro de Daenerys; la mano de Jon en su mejilla
  { t0: 45.8, t1: 52.27, run(D, lt) {
    const p = { ...POSE.jonCradle, expr: EXP.cry };
    p.shR = [-0.75 - smooth(range(lt, 1, 4)) * 0.25, 0.55, -0.1]; p.elR = [-0.9, 0, 0];
    p.spine = [0.42, -0.12, 0]; p.head = [0.45, -0.35, 0];
    jonAt(D, [0, 0.42, 0], 0, p);
    danyCradledAt(D, [0.6, 0.5, 0.42], 0.9, 0); D.dany.pose(POSE.danyCradled);
    { const h = headOf(D.dany); const f = new THREE.Vector3(); D.dany.head.getWorldDirection(f); const p = [h.x + f.x * 1.1 + 0.25, h.y + f.y * 1.1 + 0.15, h.z + f.z * 1.1 + 0.2 + lt * 0.01]; look(D, p, [h.x, h.y, h.z], 34, 0.005); }
    D.setSun([-7, 14, -12], [0, 1, 0], 3);
    snow(D, lt, [-0.4, 1.2, 0.6], [3, 2.5, 3], { speed: 0.2 });
  } },
  // C 0:52.3 - 1:02.6  La deja en el suelo y se levanta (contrapicado)
  { t0: 52.27, t1: 62.6, run(D, lt) {
    danyOnFloor(D, { head: [-0.1, -0.7, 0] });
    const k = smooth(range(lt, 3, 8.5));
    const pose = blendPose(POSE.jonKneelFloor, { ...POSE.jonStand, neck: [0.25, 0, 0], head: [0.3, 0, 0] }, k);
    jonAt(D, [lerp(0.4, 0.55, k), lerp(0.42, 0.75, k), lerp(1.15, 1.3, k)], PI, pose, { expr: EXP.cry });
    { const h = headOf(D.jon); look(D, [-1.5 + lt * 0.01, 0.22, -0.1], [h.x, h.y - 0.1, h.z], 34, 0.004); }
    D.setSun([-7, 14, -12], [0, 1, 0], 4);
    snow(D, lt, [0, 1.5, 0.8], [5, 4, 5]);
  } },
  // D 1:02.6 - 1:08.2  Drogon se acerca por la sala oscura; Jon de espaldas
  { t0: 62.6, t1: 68.17, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, [lerp(1.4, 1.7, smooth(lt / 5)), 0.75, lerp(-0.6, -1.2, smooth(lt / 5))], -1.9, POSE.jonStand, { neck: [0.1, 0, 0] });
    const k = smooth(lt / 5.5);
    drogon(D, { ...dragonSniff(lt), pos: [lerp(-8, -6.4, k), 0, lerp(-6, -3.6, k)], yaw: 1.0, neckPitch1: 0.18 + k * 0.1 });
    { const h = dragonHead(D); look(D, [4.6 - lt * 0.05, 1.3, 2.6], [h.x, h.y + 0.6, h.z], 40, 0.0015); }
    D.hemi.intensity = 0.7; D.sun.intensity = 0.8;
    D.setSun([-7, 14, -12], [-2, 1, -2], 10);
    snow(D, lt, [1, 2, -1], [8, 5, 8]);
  } },
  // E 1:08.2 - 1:11.4  Picado general
  { t0: 68.17, t1: 71.37, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonStand);
    drogon(D, { ...dragonSniff(lt), pos: [-6.2, 0, -3.0], neckPitch1: 0.25 });
    camKF(D, lt, [[0, [6.5, 11, 6.5]], [3.2, [6.3, 10.8, 6.2]]], [[0, [-0.5, 0, -2.5]], [3.2, [-0.6, 0, -2.6]]], 40, 13, 0.0015);
    D.setSun([-7, 14, -12], [0, 0, -2], 12);
    snow(D, lt, [2, 4, 0], [14, 8, 14], { scale: 2 });
  } },
  // F 1:11.4 - 1:21.3  Drogon empuja con el hocico el cuerpo de Daenerys
  { t0: 71.37, t1: 81.33, run(D, lt) {
    danyOnFloor(D, { shR: [0, 0, -0.12 - sin(lt * 1.2) * 0.04] });
    jonAt(D, [2.6, 0.75, 1.9], -2.4, POSE.jonStand);
    const nudge = Math.max(0, sin(lt * 1.3)) * 0.06;
    drogon(D, dragonSniff(lt, { neckPitch1: 0.34 + nudge, headPitch: 0.32 + nudge }));
    look(D, [1.2 - lt * 0.02, 0.65, 4.4], [-0.7, 0.85, -0.2], 38, 0.0025);
    D.setSun([-7, 14, -12], [-1, 0, -1], 8);
    snow(D, lt, [1, 2, 1], [8, 5, 8]);
  } },
  // G 1:21.3 - 1:23.0  Jon de pie al fondo; cabeza de Drogon en primer termino
  { t0: 81.33, t1: 83, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.9, POSE.jonStand, { expr: EXP.sad });
    drogon(D, dragonSniff(lt + 10));
    { const h = headOf(D.jon); look(D, [-1.6, 1.5, 3.4], [h.x - 0.6, h.y - 0.4, h.z], 32, 0.003); }
    D.setSun([-7, 14, -12], [0, 0, -1], 8);
    snow(D, lt, [0, 2, 0], [8, 5, 8]);
  } },
  // H 1:23.0 - 1:25.8  Rostro de Daenerys con el hocico de Drogon
  { t0: 83, t1: 85.8, run(D, lt) {
    danyOnFloor(D, { head: [-0.1, -0.85, 0] });
    drogon(D, dragonSniff(lt + 12, { neckPitch1: 0.36, headPitch: 0.36 }));
    camKF(D, lt, [[0, [-0.6, 0.25, 1.4]], [2.8, [-0.62, 0.25, 1.35]]], [[0, [-0.05, 0.25, 0.3]], [2.8, [-0.05, 0.25, 0.3]]], 34, 1.2, 0.005);
    D.setSun([-7, 14, -12], [0, 0, 0], 4);
    snow(D, lt, [-0.3, 1, 0.6], [3, 2, 3]);
  } },
  // I 1:25.8 - 1:32.9  Drogon sobre el cuerpo, la empuja suavemente
  { t0: 85.8, t1: 92.87, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.9, POSE.jonStand);
    const nudge = Math.max(0, sin(lt * 1.1 + 1)) * 0.07;
    drogon(D, dragonSniff(lt + 20, { neckPitch1: 0.3 + nudge, headPitch: 0.3 + nudge }));
    camKF(D, lt, [[0, [2.8, 0.45, 3.2]], [7, [2.6, 0.5, 3.1]]], [[0, [-1.2, 1.6, -0.8]], [7, [-1.2, 1.7, -0.9]]], 36, 3.9, 0.003);
    D.setSun([-7, 14, -12], [-1, 0, -1], 8);
    snow(D, lt, [0, 2, 1], [8, 5, 8]);
  } },
  // J 1:32.9 - 1:35.7  Jon de pie, plano medio
  { t0: 92.87, t1: 95.67, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonStand, { spine: [breathe(lt), 0, 0], head: [0.05, 0.1, 0] });
    drogon(D, dragonSniff(lt + 27));
    frontCam(D, D.jon, lt, { dist: 2.6, ang: 0.45, dy: -0.15, ly: -0.45, fov: 30, ap: 0.004 });
    D.hemi.intensity = 0.8;
    D.setSun([-7, 14, -12], [1.8, 1, -1.4], 5);
    snow(D, lt, [0, 2, -1], [6, 4, 6]);
  } },
  // K 1:35.7 - 1:42.5  Drogon levanta la cabeza y ruge
  { t0: 95.67, t1: 102.47, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonLookUp);
    const k = smooth(range(lt, 0, 3.2)), roar = smooth(range(lt, 1.5, 2.5)) * (1 - smooth(range(lt, 5.5, 6.8)));
    drogon(D, {
      ...dragonSniff(lt), pos: [-5.8, 0, -3.0], yaw: lerp(1.08, 1.3, k), bodyY: lerp(2.5, 3.3, k), pitch: lerp(0.12, -0.35, k),
      neckPitch0: lerp(0.05, -0.35, k), neckPitch1: lerp(0.32, 0.1, k), headPitch: lerp(0.28, -0.1, k) + roar * -0.15, jaw: roar * 0.85,
      wing: wingMix(WING_FOLD, WING_HALF, k * 0.6),
    });
    { const h = dragonHead(D); look(D, [8.5 - lt * 0.05, 1.4, 0.8], [h.x + 1.5, h.y - 2.0, h.z], 58, 0.001); }
    D.setSun([-7, 14, -12], [-2, 2, -2], 10);
    snow(D, lt, [1, 3, -1], [8, 6, 8]);
  } },
  // L 1:42.5 - 1:48.8  Drogon se alza con las alas abiertas, Jon pequeno
  { t0: 102.47, t1: 108.8, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonLookUp);
    const k = smooth(range(lt, 0, 3.5));
    drogon(D, {
      ...dragonSniff(lt), pos: [-5.8, 0, -3.2], yaw: 1.3, bodyY: lerp(3.3, 4.0, k), pitch: lerp(-0.35, -0.6, k),
      neckPitch0: -0.3, neckPitch1: lerp(0.1, 0.25, k), headPitch: 0.15, jaw: 0.2 * sin(lt),
      wing: wingMix(WING_HALF, WING_OPEN, k), hip: 0.9, knee: -0.9,
    });
    look(D, [9.5 - lt * 0.05, 0.7, 7.5], [-3, 4.6 + lt * 0.05, -3], 50, 0.001);
    D.setSun([-7, 14, -12], [-2, 2, -2], 14);
    snow(D, lt, [2, 4, 0], [16, 9, 14], { scale: 2 });
  } },
  // M 1:48.8 - 1:51.0  Jon mira hacia arriba, con miedo
  { t0: 108.8, t1: 111.03, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonLookUp, { spine: [breathe(lt, 0.03), 0, 0] });
    drogon(D, { ...dragonSniff(lt), pos: [-5.8, 0, -3.2], yaw: 1.3, bodyY: 4.0, pitch: -0.6, neckPitch0: -0.3, neckPitch1: 0.3, headPitch: 0.4, wing: WING_OPEN });
    frontCam(D, D.jon, lt, { dist: 1.9, ang: 0.3, dy: -0.15, ly: -0.12 });
    D.setSun([-7, 14, -12], [1.8, 1.5, -1.4], 4);
    snow(D, lt, [1, 2, -1], [4, 3, 4]);
  } },
  // N 1:51.0 - 1:53.8  Drogon mira hacia abajo (punto de vista de Jon)
  { t0: 111.03, t1: 113.83, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonLookUp);
    drogon(D, { ...dragonSniff(lt), pos: [-5.8, 0, -3.2], yaw: 1.3, bodyY: 4.0, pitch: -0.6, neckPitch0: -0.25, neckPitch1: 0.42, headPitch: 0.55, headYaw: sin(lt) * 0.05, jaw: 0.08, wing: WING_OPEN });
    { const h = dragonHead(D); look(D, [1.2, 1.7, -1.0], [h.x, h.y, h.z], 38, 0.0015); }
    D.setSun([-7, 14, -12], [-2, 4, -2], 10);
    snow(D, lt, [0, 3, -1], [6, 5, 6]);
  } },
  // O 1:53.8 - 1:59.5  Jon mira hacia arriba (respira)
  { t0: 113.83, t1: 119.53, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonLookUp, { spine: [breathe(lt, 0.03), 0, 0], head: [-0.4 + sin(lt * 0.8) * 0.04, 0.08, 0] });
    frontCam(D, D.jon, lt, { dist: 1.85, ang: -0.25, dy: -0.15, ly: -0.12 });
    D.setSun([-7, 14, -12], [1.8, 1.5, -1.4], 4);
    snow(D, lt, [1, 2, -1], [4, 3, 4]);
  } },
  // P 1:59.5 - 2:00.5  Silueta de Jon; la boca de Drogon empieza a brillar
  { t0: 119.53, t1: 120.53, run(D, lt) {
    danyOnFloor(D);
    jonAt(D, JON_STAND, -1.6, POSE.jonLookUp);
    drogon(D, { ...dragonFire(lt), pos: [-5.8, 0, -3.2], yaw: 1.5, jaw: 0.35 });
    D.drogon.mouth.getWorldPosition(_o);
    D.fireLight.position.copy(_o); D.fireLight.intensity = 60 * lt; D.fireLight.distance = 10;
    { const h = dragonHead(D); look(D, [4.8, 2.0, -0.9], [h.x, h.y - 0.3, h.z], 36, 0.002); }
    D.hemi.intensity = 0.7;
    D.setSun([-7, 14, -12], [-2, 2, -2], 10);
    snow(D, lt, [1, 2, -1], [6, 4, 6]);
  } },
  // Q 2:00.5 - 2:01.6  Primer chorro de fuego
  { t0: 120.53, t1: 121.63, run(D, lt, t) {
    danyOnFloor(D);
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch);
    drogon(D, dragonFire(t));
    breathFire(D, t, { on: (b) => b > 120.45 });
    fireMood(D, 0.8);
    { const h = dragonHead(D); look(D, [h.x + 3.2, h.y - 0.6, h.z + 2.2], [h.x - 1.5, h.y - 0.4, h.z - 2.0], 44, 0.002); }
    D.setSun([-7, 14, -12], [-2, 2, -6], 10);
  } },
  // R 2:01.6 - 2:03.2  Jon agachado, el fuego pasa sobre el; trono al fondo
  { t0: 121.63, t1: 123.23, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch);
    drogon(D, dragonFire(t));
    breathFire(D, t, { on: (b) => b > 120.45 });
    fireMood(D, 1);
    camKF(D, lt, [[0, [3.6, 0.9, -3.4]], [1.6, [3.5, 0.9, -3.5]]], [[0, [0.6, 0.9, -7.5]], [1.6, [0.6, 0.9, -7.6]]], 36, 3.0, 0.004, 0.015, 0.015);
    D.setSun([-7, 14, -12], [0, 1, -6], 8);
  } },
  // S 2:03.2 - 2:06.7  El chorro cruza la sala hacia el trono
  { t0: 123.23, t1: 126.73, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch);
    drogon(D, dragonFire(t));
    breathFire(D, t);
    throneFire(D, t, smooth(range(t, 123, 128)) * 0.6);
    fireMood(D, 1);
    camKF(D, lt, [[0, [9.5, 2.0, -6.5]], [3.5, [9.4, 2.1, -6.8]]], [[0, [-2, 3, -8.5]], [3.5, [-2.2, 3, -8.6]]], 40, 11, 0.0015, 0.012, 0.01);
    D.setSun([-7, 14, -12], [-1, 1, -7], 12);
  } },
  // T 2:06.7 - 2:09.8  Jon agachado en la escalinata; el fuego pasa a su lado
  { t0: 126.73, t1: 129.77, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch);
    drogon(D, dragonFire(t));
    breathFire(D, t);
    throneFire(D, t, 0.7);
    fireMood(D, 1);
    camKF(D, lt, [[0, [5.2, 1.2, -1.2]], [3, [5.0, 1.2, -1.4]]], [[0, [0.3, 1.6, -8]], [3, [0.3, 1.6, -8]]], 40, 6, 0.002, 0.012, 0.01);
    D.setSun([-7, 14, -12], [0, 1, -6], 10);
  } },
  // U 2:09.8 - 2:10.8  Cabeza de Drogon de frente, la boca ardiendo
  { t0: 129.77, t1: 130.77, run(D, lt, t) {
    drogon(D, dragonFire(t));
    breathFire(D, t, { k: 1.2 });
    fireMood(D, 1);
    const hp = new THREE.Vector3(); D.drogon.mouth.getWorldPosition(hp);
    const dir = new THREE.Vector3(); D.drogon.head.getWorldDirection(dir);
    const side = new THREE.Vector3(0, 1, 0).cross(dir).normalize();
    const cp = hp.clone().addScaledVector(dir, 2.2).addScaledVector(side, 1.6).add(V(0, 0.4, 0));
    D.camera([cp.x, cp.y, cp.z], [hp.x - dir.x * 1.2, hp.y + 0.2, hp.z - dir.z * 1.2], 40);
    D.focus(2.6, 0.003, 0.015);
    D.setSun([-7, 14, -12], [hp.x, hp.y, hp.z], 6);
  } },
  // V 2:10.8 - 2:14.2  Jon cubriendose la cara, el trono detras entre llamas
  { t0: 130.77, t1: 134.2, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch, { spine: [0.95 + sin(lt * 3) * 0.03, 0.2, 0] });
    drogon(D, dragonFire(t));
    breathFire(D, t);
    throneFire(D, t, 0.8);
    fireMood(D, 1);
    camKF(D, lt, [[0, [2.6, 1.0, -3.6]], [3.4, [2.5, 1.0, -3.8]]], [[0, [0.6, 1.0, -7.6]], [3.4, [0.5, 1.0, -7.7]]], 32, 2.4, 0.005, 0.02, 0.01);
    D.setSun([-7, 14, -12], [0, 1, -6], 6);
  } },
  // W 2:14.2 - 2:16.8  Perfil de Drogon escupiendo fuego, hombro de Jon delante
  { t0: 134.2, t1: 136.8, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch);
    drogon(D, dragonFire(t));
    breathFire(D, t);
    throneFire(D, t, 0.85);
    fireMood(D, 1);
    camKF(D, lt, [[0, [3.0, 1.4, -5.0]], [2.6, [3.0, 1.45, -5.2]]], [[0, [-2.6, 3.6, -5.4]], [2.6, [-2.6, 3.6, -5.6]]], 36, 5.5, 0.003, 0.015, 0.01);
    D.setSun([-7, 14, -12], [-1, 2, -5], 10);
  } },
  // X 2:16.8 - 2:19.1  Jon encogido, humo y fuego; mira por encima del hombro
  { t0: 136.8, t1: 139.13, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch, { head: [0.1, -0.6 * smooth(range(lt, 1, 2)), 0] });
    drogon(D, dragonFire(t));
    breathFire(D, t);
    throneFire(D, t, 0.9);
    fireMood(D, 1);
    D.fx.smoke.visible = true; D.fx.smoke.update(t, [0, 2, -9], [8, 6, 6], { size: 1.6 });
    camKF(D, lt, [[0, [2.3, 1.1, -4.2]], [2.3, [2.25, 1.1, -4.3]]], [[0, [1.2, 0.9, -6.2]], [2.3, [1.2, 0.9, -6.2]]], 32, 2.3, 0.005, 0.02, 0.01);
    D.setSun([-7, 14, -12], [0, 1, -6], 6);
  } },
  // Y 2:19.1 - 2:19.9  General: Drogon arriba, Jon abajo
  { t0: 139.13, t1: 139.93, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch);
    drogon(D, dragonFire(t));
    breathFire(D, t);
    throneFire(D, t, 0.9);
    fireMood(D, 1);
    camKF(D, lt, [[0, [4.0, 0.6, -2.2]], [0.8, [4.0, 0.6, -2.25]]], [[0, [-2, 3.5, -4]], [0.8, [-2, 3.5, -4]]], 44, 6, 0.0015);
    D.setSun([-7, 14, -12], [-1, 2, -4], 10);
  } },
  // Z 2:19.9 - 2:20.7  Drogon de cerca escupiendo fuego
  { t0: 139.93, t1: 140.73, run(D, lt, t) {
    jonAt(D, JON_CROUCH, -0.4, POSE.jonCrouch);
    drogon(D, dragonFire(t));
    breathFire(D, t);
    fireMood(D, 1);
    camKF(D, lt, [[0, [0.4, 2.4, -4.0]], [0.8, [0.4, 2.45, -4.05]]], [[0, [-2.6, 3.8, -6.6]], [0.8, [-2.6, 3.8, -6.6]]], 40, 4, 0.002);
    D.setSun([-7, 14, -12], [-2, 3, -6], 8);
  } },
  // AA 2:20.7 - 2:25.0  El Trono de Hierro envuelto en fuego
  { t0: 140.73, t1: 145.03, run(D, lt, t) {
    drogon(D, dragonFire(t));
    breathFire(D, t, { k: 1.2 });
    throneFire(D, t, 1);
    fireMood(D, 1);
    const tp = THRONE_POS;
    camKF(D, lt, [[0, [tp.x + 0.6, tp.y + 1.2, tp.z - 6.5]], [4.3, [tp.x + 0.5, tp.y + 1.1, tp.z - 5.6]]], [[0, [tp.x, tp.y + 2.3, tp.z]], [4.3, [tp.x, tp.y + 2.4, tp.z]]], 40, 6, 0.002);
    D.setSun([-7, 14, -12], [tp.x, tp.y, tp.z], 6);
  } },
  // AB 2:25.0 - 2:28.1  Las espadas del respaldo se funden
  { t0: 145.03, t1: 148.07, run(D, lt, t) {
    drogon(D, dragonFire(t));
    breathFire(D, t, { k: 1.3 });
    throneFire(D, t, 1);
    fireMood(D, 1);
    const tp = THRONE_POS;
    camKF(D, lt, [[0, [tp.x + 0.2, tp.y + 3.0, tp.z - 3.2]], [3, [tp.x + 0.1, tp.y + 3.2, tp.z - 3.0]]], [[0, [tp.x, tp.y + 3.4, tp.z]], [3, [tp.x, tp.y + 3.3, tp.z]]], 40, 3.1, 0.003);
    D.setSun([-7, 14, -12], [tp.x, tp.y, tp.z], 6);
  } },
  // AC 2:28.1 - 2:30.2  La boca de Drogon escupiendo fuego
  { t0: 148.07, t1: 150.2, run(D, lt, t) {
    drogon(D, dragonFire(t, { jaw: 0.95 }));
    breathFire(D, t, { k: 1.2 });
    fireMood(D, 1);
    const hp = new THREE.Vector3(); D.drogon.mouth.getWorldPosition(hp);
    const dir = new THREE.Vector3(); D.drogon.head.getWorldDirection(dir);
    const side = new THREE.Vector3(0, 1, 0).cross(dir).normalize();
    const cp = hp.clone().addScaledVector(dir, -1.2).addScaledVector(side, -3.0).add(V(0, -0.4, 0));
    D.camera([cp.x, cp.y, cp.z], [hp.x - dir.x * 1.0, hp.y, hp.z - dir.z * 1.0], 40);
    D.focus(3.2, 0.003, 0.015);
    D.setSun([-7, 14, -12], [hp.x, hp.y, hp.z], 6);
  } },
  // AD-AF 2:30.2 - 2:42.4  Todo es fuego; el trono se derrite
  { t0: 150.2, t1: 162.4, run(D, lt, t) {
    drogon(D, dragonFire(t));
    breathFire(D, t, { k: 1.3 });
    throneFire(D, t, 1);
    fireMood(D, 1);
    lava(D, t, smooth(range(t, 152, 162)) * 1.0, 1);
    const tp = THRONE_POS;
    const cuts = [[150.2, [tp.x + 2.5, tp.y + 1.5, tp.z + 3.5], [tp.x, tp.y + 1.2, tp.z]], [152.4, [tp.x - 1.6, tp.y + 1.4, tp.z + 4.2], [tp.x, tp.y + 2.4, tp.z]],
      [154.83, [tp.x + 3.0, tp.y + 2.5, tp.z + 2.5], [tp.x, tp.y + 0.4, tp.z]], [156.13, [tp.x - 2.2, tp.y + 1.0, tp.z + 2.6], [tp.x, tp.y + 0.6, tp.z]],
      [158.03, [tp.x + 0.5, tp.y + 1.5, tp.z + 4.4], [tp.x, tp.y + 0.6, tp.z]], [159.77, [tp.x + 1.2, tp.y + 0.8, tp.z + 3.0], [tp.x, tp.y + 0.3, tp.z]]];
    let c = cuts[0];
    for (const cc of cuts) if (t >= cc[0]) c = cc;
    const ll = t - c[0];
    D.camera([c[1][0] + ll * 0.06, c[1][1], c[1][2] - ll * 0.08], c[2], 40);
    D.focus(Math.hypot(c[1][0] - c[2][0], c[1][1] - c[2][1], c[1][2] - c[2][2]), 0.003, 0.015);
    D.fx.smoke.visible = true; D.fx.smoke.update(t, [tp.x, tp.y + 1, tp.z], [8, 6, 6], { size: 1.8 });
    D.setSun([-7, 14, -12], [tp.x, tp.y, tp.z], 6);
  } },
  // AG 2:42.4 - 2:46.1  El metal fundido corre por los escalones
  { t0: 162.4, t1: 166.1, run(D, lt, t) {
    drogon(D, dragonFire(t));
    breathFire(D, t, { k: 0.8 });
    throneFire(D, t, 0.7);
    fireMood(D, 1);
    lava(D, t, 1.15, 1.1);
    const tp = THRONE_POS;
    camKF(D, lt, [[0, [tp.x + 2.0, tp.y + 3.0, tp.z + 2.6]], [3.7, [tp.x + 1.6, tp.y + 2.8, tp.z + 2.2]]], [[0, [tp.x - 0.5, tp.y, tp.z + 0.6]], [3.7, [tp.x - 0.6, tp.y, tp.z + 0.4]]], 40, 3.6, 0.003);
    D.setSun([-7, 14, -12], [tp.x, tp.y, tp.z], 6);
  } },
  // AH 2:46.1 - 2:49.5  Ola de fuego sobre la tarima, lava
  { t0: 166.1, t1: 169.47, run(D, lt, t) {
    drogon(D, dragonFire(t, { jaw: lerp(0.75, 0.2, smooth(range(t, 168.5, 169.4))) }));
    breathFire(D, t, { on: (b) => b < 168.9, k: 0.9 });
    throneFire(D, t, 0.8);
    fireMood(D, 1);
    lava(D, t, 1.15, 1.0);
    const tp = THRONE_POS;
    camKF(D, lt, [[0, [tp.x + 1.5, tp.y + 0.6, tp.z + 6.0]], [3.4, [tp.x + 1.4, tp.y + 0.6, tp.z + 5.6]]], [[0, [tp.x, tp.y + 0.8, tp.z]], [3.4, [tp.x, tp.y + 0.8, tp.z]]], 40, 6, 0.002);
    D.setSun([-7, 14, -12], [tp.x, tp.y, tp.z], 8);
  } },
  // AI 2:49.5 - 3:00.6  Drogon deja de escupir fuego y mira a Jon; Jon se vuelve
  { t0: 169.47, t1: 180.6, run(D, lt, t) {
    const k = smooth(range(lt, 2, 6));
    jonAt(D, [lerp(JON_CROUCH[0], 1.0, k), lerp(0.42, 0.75, k), lerp(JON_CROUCH[2], -5.2, k)], lerp(-0.4, 2.6, smooth(range(lt, 4, 8))),
      blendPose(POSE.jonCrouch, POSE.jonLookUp, k), { expr: lt > 7 ? EXP.fear : EXP.shout });
    drogon(D, { ...dragonFire(t), jaw: 0.1, neckYaw0: lerp(0.02, 0.35, k), neckYaw1: lerp(0.04, 0.3, k), headPitch: lerp(0.05, 0.35, k), neckPitch1: lerp(0.12, 0.3, k), headYaw: 0.2 * k });
    throneFire(D, t, 0.6);
    lava(D, t, 1.15, 0.8);
    fireMood(D, 0.55);
    if (lt < 5.5) { const h = dragonHead(D); look(D, [h.x + 3.5, h.y - 0.3, h.z + 2.0], [h.x, h.y, h.z], 38, 0.002); }
    else frontCam(D, D.jon, lt, { dist: 2.0, ang: 0.6, dy: -0.1, ly: 0.1, fov: 34 });
    D.setSun([-7, 14, -12], [0, 2, -5], 8);
    snow(D, lt, [0, 3, -5], [8, 5, 8], { count: 1200 });
  } },
  // AJ 3:00.6 - 3:09.8  Desde detras de Jon: la ciudad en llamas
  { t0: 180.6, t1: 189.83, run(D, lt, t) {
    jonAt(D, [14.6, 1.75, -3.5], PI / 2, POSE.jonStand, { neck: [0.1, 0, 0], expr: EXP.sad });
    const G = D.ctx.grade.uniforms; G.uTint.value.set(0.97, 0.99, 1.04); G.uSat.value = 0.9;
    D.ctx.scene.fog.color.set(0x7e8a94); D.ctx.scene.fog.density = 0.008;
    D.sky.material.uniforms.uTop.value.set(0x46525e); D.sky.material.uniforms.uHor.value.set(0x8a929a); D.sky.material.uniforms.uWarm.value.setRGB(0.12, 0.05, 0.01);
    const src = [];
    for (let i = 0; i < 26; i++) { const a = -0.9 + i * 0.07; const r = 40 + hash3(i, 1, 1) * 50; src.push({ p: [9 + cos(a) * r, 0.5 + hash3(i, 2, 1) * 4, -3.5 + sin(a) * r], r: 2 + hash3(i, 3, 1) * 3, h: 3 + hash3(i, 4, 1) * 5, s: 0.9, k: 1, hot: 0.45 }); }
    src.push({ p: [16.5, 2, 0.5], r: 0.8, h: 5, s: 0.35, k: 1, hot: 0.5 });
    D.fx.flames.visible = true; D.fx.flames.update(t, src);
    D.fx.smoke.visible = true; D.fx.smoke.update(t, [60, 8, -3], [80, 25, 80], { size: 9, drift: 6 });
    D.ctx.bloom.strength = 0.8;
    look(D, [12.2 + lt * 0.02, 3.2, -2.6], [40, 1.0, -7.5], 40, 0.002);
    D.setSun([-7, 14, -12], [9, 1, -3.5], 6);
    snow(D, lt, [14, 3, -3.5], [6, 4, 6], { count: 900 });
  } },
  // AK 3:09.8 - 3:21.0  Cenital: brasas sobre la tarima; llega Drogon
  { t0: 189.83, t1: 201.03, run(D, lt, t) {
    danyOnFloor(D);
    jonAt(D, [1.4, 0.75, 1.6], -2.4, POSE.jonStand, { neck: [0.3, 0, 0] });
    const k = smooth(range(lt, 6.5, 11));
    drogon(D, { ...dragonSniff(t), pos: [lerp(-10, -6.2, k), 0, lerp(-5, -2.8, k)], yaw: 1.05, wing: WING_FOLD });
    lava(D, t, 1.1, 0.55);
    D.fx.embers.visible = true; D.fx.embers.update(t, [0, 3, -10], [10, 8, 10], { speed: 0.6, size: 0.06 });
    const tp = THRONE_POS;
    camKF(D, lt, [[0, [tp.x - 1, 16, tp.z + 1.5]], [4, [-0.5, 16, -6.0]], [11.2, [0.5, 15, 1.0]]], [[0, [tp.x, 0, tp.z + 0.3]], [4, [-0.2, 0, -6.5]], [11.2, [0.2, 0, 0.2]]], 40, 15, 0.0012);
    D.setSun([-7, 14, -12], [0, 0, -5], 14);
    snow(D, lt, [0, 6, -4], [16, 10, 16], { scale: 2.5, count: 2000 });
  } },
  // AL 3:21.0 - 3:25.2  Primer plano de Jon con la ciudad ardiendo detras
  { t0: 201.03, t1: 205.17, run(D, lt, t) {
    danyOnFloor(D);
    jonAt(D, [1.4, 0.75, 1.6], -2.2, POSE.jonStand, { neck: [0.2, 0, 0], head: [0.15, 0.25, 0], expr: EXP.sad });
    drogon(D, dragonSniff(t));
    const src = [];
    for (let i = 0; i < 12; i++) src.push({ p: [-30 - i * 4, 1 + hash3(i, 5, 5) * 3, 20 + i * 3], r: 3, h: 6, s: 1.3, k: 1, hot: 0.7 });
    D.fx.flames.visible = true; D.fx.flames.update(t, src);
    frontCam(D, D.jon, lt, { dist: 1.6, ang: 0.5, dy: 0, ly: -0.1 });
    D.setSun([-7, 14, -12], [1.4, 1.5, 1.6], 4);
    snow(D, lt, [1.5, 2, 1.5], [4, 3, 4], { count: 1200 });
  } },
  // AM 3:25.2 - 3:36.9  Daenerys con la daga; Drogon la toma con su garra y la levanta
  { t0: 205.17, t1: 216.9, run(D, lt, t) {
    const lift = smooth(range(lt, 7.0, 11.7));
    jonAt(D, [1.4, 0.75, 1.6], -2.2, POSE.jonStand);
    const wk = smooth(range(lt, 3, 7));
    const p = dragonSniff(t, { neckPitch1: lerp(0.3, 0.1, lift), headPitch: 0.3, wing: { raise: lerp(-0.4, 0.05, wk), sweep: lerp(1.0, 0.25, wk), elbow: lerp(2.0, 1.1, wk), spread: 0.25, wrist: -0.6 }, bodyY: lerp(2.5, 3.2, lift), pitch: lerp(0.12, -0.2, lift) });
    drogon(D, p);
    if (lt < 7.0) {
      danyOnFloor(D);
    } else {
      const wp = danyInClaw(D, 1);
      const fl = new THREE.Vector3(...DANY_FLOOR);
      const k = smooth(range(lt, 7.0, 8.2));
      const pos = fl.clone().lerp(wp.add(V(0.4, -0.6, 0.3)), k);
      danyLying(D, [pos.x, pos.y, pos.z], 0.05 + k * 0.3);
      D.dany.pose({ ...POSE.danyFloor, shL: [0, 0, 0.12 + k * 0.6], shR: [0, 0, -0.12 - k * 0.6], neck: [-0.1 - k * 0.6, 0, 0], hpL: [k * 0.5, 0, 0.05], hpR: [k * 0.5, 0, -0.05], hair: 1.35 + k * 0.4 });
    }
    camKF(D, lt, [[0, [-0.3, 0.45, 2.7]], [7, [-0.2, 0.5, 2.6]], [11.7, [0.0, 1.0, 3.6]]], [[0, [0.3, 0.2, 0.4]], [7, [0.3, 0.3, 0.4]], [11.7, [0.0, 1.5, 0.0]]], 36, null, 0.003);
    D.setSun([-7, 14, -12], [0, 0, 0], 6);
    snow(D, lt, [0, 2, 1], [6, 4, 6]);
  } },
  // AN 3:36.9 - 3:47.1  Jon en penumbra, mira
  { t0: 216.9, t1: 227.13, run(D, lt) {
    jonAt(D, [1.4, 0.75, 1.6], -2.2, POSE.jonLookUp, { head: [-0.2 + lt * 0.015, 0.25 - lt * 0.02, 0], spine: [breathe(lt), 0, 0], expr: lt < 6 ? EXP.fear : EXP.up });
    D.hemi.intensity = 0.55; D.sun.intensity = 0.7;
    frontCam(D, D.jon, lt, { dist: 1.7, ang: 0.35, dy: -0.15, ly: 0 });
    D.setSun([-7, 14, -12], [1.4, 1.5, 1.6], 4);
    snow(D, lt, [1, 2, 1], [4, 3, 4], { count: 1000 });
  } },
  // AO 3:47.1 - 4:08.0  Drogon despega con Daenerys y se aleja entre el humo; Jon lo mira
  { t0: 227.13, t1: 248.03, run(D, lt, t) {
    const k = smooth(range(lt, 0, 20));
    const pos = kf(lt, [[0, [-2, 4, -2]], [6, [5, 18, -3]], [20.9, [105, 30, -14]]]);
    drogon(D, { ...dragonFly(t), pos, yaw: PI / 2 - 0.1 });
    const wp = danyInClaw(D, 1);
    danyLying(D, [wp.x + 0.3, wp.y - 0.8, wp.z], 0.35);
    D.dany.pose({ ...POSE.danyFloor, shL: [0, 0, 0.8], shR: [0, 0, -0.8], neck: [-0.7, 0, 0], hpL: [0.5, 0, 0.05], hpR: [0.5, 0, -0.05] });
    jonAt(D, [3.2, 0.75, -1.4], PI / 2, POSE.jonStand, { neck: [-0.15 - (1 - k) * 0.15, 0, 0], head: [-0.2, 0, 0] });
    const tp = THRONE_POS;
    const src = [{ p: [tp.x - 4, 1.3, tp.z + 5], r: 1, h: 2, s: 0.35, k: 0.8 }, { p: [tp.x + 4, 1.4, tp.z + 5], r: 1, h: 2, s: 0.35, k: 0.8 }, { p: [-11, 2, -21], r: 1.5, h: 6, s: 0.6, k: 1 }, { p: [10, 2, -21], r: 1.2, h: 5, s: 0.5, k: 1 }];
    D.fx.flames.visible = true; D.fx.flames.update(t, src);
    lava(D, t, 1.1, 0.45);
    D.ctx.scene.fog.density = 0.011; D.ctx.scene.fog.color.set(0x8c98a2);
    D.fx.fog.visible = true; D.fx.fog.update(t, [0, 6, -40], [60, 20, 60], { size: 10, drift: 3 });
    { const dp = D.drogon.root.position; if (lt < 4.5) look(D, [dp.x + 6, dp.y - 2.5, dp.z + 9], [dp.x, dp.y, dp.z], 44, 0.0015);
    else look(D, [-1.6, 1.2, 0.6], [lerp(3.2, dp.x, 0.85), lerp(1.6, dp.y, 0.85), lerp(-1.4, dp.z, 0.85)], 46, 0.001); }
    D.setSun([-7, 14, -12], [0, 2, -6], 14);
    snow(D, lt, [-1, 4, -4], [12, 8, 12], { count: 1600, scale: 1.6 });
  } },
  // AP 4:08.0 - 4:22.1  Drogon vuela sobre el mar entre la niebla y desaparece
  { t0: 248.03, t1: 262.2, run(D, lt, t) {
    D.world.group.visible = false; D.throne.visible = false; D.jon.root.visible = false;
    const k = lt / 14;
    const pos = [lerp(-4, 18, k), lerp(14, 22, k), lerp(-10, -140, k)];
    drogon(D, { ...dragonFly(t), pos, yaw: PI + 0.25 });
    const wp = danyInClaw(D, 1);
    danyLying(D, [wp.x + 0.3, wp.y - 0.8, wp.z], 0.35);
    D.dany.pose({ ...POSE.danyFloor, shL: [0, 0, 0.8], shR: [0, 0, -0.8], neck: [-0.7, 0, 0] });
    D.sea.visible = true;
    D.ctx.scene.fog.color.set(0x6e7a84); D.ctx.scene.fog.density = 0.013 + k * 0.006;
    D.sky.material.uniforms.uTop.value.set(0x4a5560); D.sky.material.uniforms.uHor.value.set(0x76828c);
    D.fx.fog.visible = true; D.fx.fog.update(t, [0, 12, -80], [120, 20, 120], { size: 14, drift: 4 });
    { const dp = D.drogon.root.position; look(D, [lerp(-6, 4, k), 8, lerp(12, -60, k)], [dp.x, dp.y, dp.z], 38, 0.0008); }
    D.ctx.grade.uniforms.uFade.value = 1 - smooth(range(lt, 11.5, 14));
    D.hemi.intensity = 1.0;
    D.setSun([-7, 14, -12], [0, 10, -40], 30);
  } },
];
