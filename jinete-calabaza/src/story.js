// Guion de "El Jinete de la Calabaza Llameante": 26 escenas de 10 s.
// Todo es funcion pura del tiempo local lt (se puede renderizar por escenas y reanudar).
import * as THREE from 'three';
import { Particles, makeRing, FireTrail, Fire } from './fx.js';

export const SCENE_LEN = 10;

// ---------------------------------------------------------------------------
// utilidades
// ---------------------------------------------------------------------------
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
const easeIO = (t) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const seg = (lt, a, b) => ease((lt - a) / (b - a));
const lin = (lt, a, b) => clamp((lt - a) / (b - a));
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const yawTo = (dx, dz) => Math.atan2(dx, dz);
const pulse = (lt, c, w) => clamp(1 - Math.abs(lt - c) / w);

function catmull(p0, p1, p2, p3, t) {
  const t2 = t * t, t3 = t2 * t;
  return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
}
function path(keys, lt) {
  if (lt <= keys[0][0]) return V(...keys[0][1]);
  const n = keys.length;
  if (lt >= keys[n - 1][0]) return V(...keys[n - 1][1]);
  let i = 0;
  while (i < n - 2 && lt > keys[i + 1][0]) i++;
  const s = (lt - keys[i][0]) / (keys[i + 1][0] - keys[i][0]);
  const P = (k) => keys[clamp(k, 0, n - 1)][1];
  return V(...[0, 1, 2].map((a) => catmull(P(i - 1)[a], P(i)[a], P(i + 1)[a], P(i + 2)[a], s)));
}
function cam(c, lt, pos, look, fov = 45, opts = {}) {
  const T = opts.span ? lerp(opts.span[0], opts.span[1], easeIO((lt - opts.span[0]) / (opts.span[1] - opts.span[0]))) : lt;
  const p = path(pos, T), l = path(look, T);
  if (opts.shake) {
    const s = opts.shake;
    p.x += Math.sin(lt * 13.1) * s + Math.sin(lt * 31.7) * s * 0.5;
    p.y += Math.sin(lt * 11.3 + 2) * s;
    l.x += Math.sin(lt * 9.7 + 1) * s * 0.6;
  }
  c.position.copy(p);
  c.lookAt(l);
  if (opts.roll) c.rotateZ(opts.roll);
  c.fov = fov;
}
function noise1(t, seed = 0) {
  return Math.sin(t * 1.7 + seed) * 0.5 + Math.sin(t * 3.1 + seed * 2.3) * 0.3 + Math.sin(t * 7.3 + seed * 5.1) * 0.2;
}
function place(a, x, y, z, yaw = 0) {
  a.root.position.set(x, y, z);
  a.root.rotation.set(0, yaw, 0);
}

// ---------------------------------------------------------------------------
// personajes
// ---------------------------------------------------------------------------
function mount(ctx) {
  const R = ctx.rider;
  ctx.horse.saddle.add(R.root);
  R.root.position.set(0, -0.93, 0.08);
  R.root.rotation.set(0, 0, 0);
  R.root.visible = true;
  R.sit();
  R.mounted = true;
}
function mountKid(ctx) {
  const K = ctx.kid;
  ctx.horse.saddle.add(K.root);
  K.root.position.set(0, -0.4, -0.55);
  K.root.rotation.set(0, 0, 0);
  K.root.visible = true;
  K.sit();
  K.arms.rotation.x = -0.35;
}
function showHorse(ctx, x, y, z, yaw) {
  const H = ctx.horse;
  H.root.visible = true;
  place(H, x, y, z, yaw);
  return H;
}
function standRider(ctx, x, y, z, yaw) {
  const R = ctx.rider;
  R.root.visible = true;
  place(R, x, y, z, yaw);
  return R;
}
function standKid(ctx, x, y, z, yaw) {
  const K = ctx.kid;
  K.root.visible = true;
  place(K, x, y, z, yaw);
  return K;
}
// recorre keys (posiciones del caballo); devuelve posicion, rumbo y velocidad
function ride(ctx, keys, lt, o = {}) {
  const p = path(keys, lt), q = path(keys, lt + 0.05);
  const d = V(q.x - p.x, 0, q.z - p.z);
  const speed = d.length() / 0.05;
  const yaw = o.yaw ?? (speed > 0.05 ? yawTo(d.x, d.z) : o.yaw0 ?? 0);
  const y = o.ground ? o.ground(p.x, p.z) : p.y;
  showHorse(ctx, p.x, y, p.z, yaw);
  return { p: V(p.x, y, p.z), yaw, speed };
}
// huellas de fuego: muestras cuantizadas de la trayectoria pasada
function hoofTrail(trail, keys, lt, o = {}) {
  const step = o.step ?? 0.1, span = o.span ?? 3, t0 = o.t0 ?? 0, t1 = o.t1 ?? 99;
  const list = [];
  const last = Math.floor(Math.min(lt, t1) / step);
  for (let k = last; k >= 0 && list.length < trail.n; k--) {
    const s = k * step;
    if (s < t0 || lt - s > span) break;
    const p = path(keys, s), q = path(keys, s + 0.05);
    const d = V(q.x - p.x, 0, q.z - p.z);
    if (d.lengthSq() < 1e-6) continue;
    d.normalize();
    const side = k % 2 ? 1 : -1;
    const age = (lt - s) / span;
    const b = Math.pow(1 - age, 1.4);
    const y = o.ground ? o.ground(p.x, p.z) : p.y;
    list.push({ x: p.x - d.z * 0.22 * side, y: y + 0.02, z: p.z + d.x * 0.22 * side, w: 0.42 * (0.6 + 0.4 * b), h: 0.55 * b + 0.05, b: b * (o.b ?? 1) });
  }
  trail.update(list);
}

// ---------------------------------------------------------------------------
// estados de escenario
// ---------------------------------------------------------------------------
function villageNight(S, lt, ctx) {
  const u = S.sky.userData.u;
  u.uTop.value.set(0x07061e); u.uHor.value.set(0x3a1e56); u.uBot.value.set(0x05040a);
  u.uSunDir.value.copy(S.moonDir); u.uSunCol.value.set(0xff7a20); u.uGlow.value = 0.8; u.uStars.value = 1;
  S.moon.visible = true;
  S.moon.scale.setScalar(100);
  S.scene.fog.color.set(0x3a2052); S.scene.fog.density = 0.013;
  S.L.dir.color.set(0xa8a0ff); S.L.dir.intensity = 1.25; S.L.dir.userData.vec = S.moonDir.clone();
  S.L.hemi.color.set(0x4a3a90); S.L.hemi.groundColor.set(0x141010); S.L.hemi.intensity = 0.9;
  S.clouds.position.x = ctx.t * 0.6;
  S.clouds.material.color.set(0x3a3055);
  S.fogEdge.userData.update(ctx.t); S.fogVillage.userData.update(ctx.t);
  S.fogEdge.userData.mat.color.set(0x8a70b8); S.fogVillage.userData.mat.color.set(0x7a60a8);
  S.bats.userData.update(ctx.t, [0, 0, -20]);
  S.bats.visible = true;
  S.leaves.set(ctx.t);
  S.sparks.set(ctx.t);
  S.bonfire.set(ctx.t, { flare: 1, bright: 1.1 });
  S.bonLight.intensity = 70 * (0.85 + 0.15 * noise1(ctx.t * 3));
  for (const j of S.jacks) j.mesh.userData.setOn(1);
  for (const l of S.roadLights) l.intensity = 22;
  for (const v of S.villagers) v.root.visible = false;
  S.smith.root.visible = false;
  for (const k of S.kids) k.root.visible = false;
  // tumba: abierta salvo que la escena diga lo contrario
  graveState(S, ctx, { lid: 0, fire: 0.25, jack: 0 });
  S.cracks.visible = false;
  S.bolt.visible = false;
  S.boltLight.intensity = 0;
  S.ghostFlame.mesh.visible = false;
  S.goldDust.points.visible = false;
  S.mtnGlow.userData.u.uTime.value = ctx.t;
}
function villageDawn(S, lt, ctx) {
  villageNight(S, lt, ctx);
  const u = S.sky.userData.u;
  const sun = V(0.25, 0.08, -1).normalize();
  u.uTop.value.set(0x3a2a78); u.uHor.value.set(0xff9a5a); u.uBot.value.set(0x2a1a2a);
  u.uSunDir.value.copy(sun); u.uSunCol.value.set(0xffb060); u.uGlow.value = 1.5; u.uStars.value = 0.1;
  S.moon.visible = false;
  S.scene.fog.color.set(0x9a6a8a); S.scene.fog.density = 0.011;
  S.fogEdge.userData.mat.color.set(0xd0a0b8); S.fogVillage.userData.mat.color.set(0xc090a8);
  S.L.dir.color.set(0xffb488); S.L.dir.intensity = 1.7; S.L.dir.userData.vec = V(0.25, 0.35, -1).normalize();
  S.L.hemi.color.set(0x9a90d0); S.L.hemi.groundColor.set(0x3a2a20); S.L.hemi.intensity = 1.0;
  S.clouds.material.color.set(0xd09ab0);
  S.bats.visible = false;
}
// lid: 1 = tumba cerrada; fire: llamas dentro de la fosa; jack: calabaza de la tumba encendida
function graveState(S, ctx, { lid = 0, fire = 0, jack = 0, blast = 0 }) {
  S.lid.visible = lid > 0 || blast > 0;
  for (const m of S.lid.children) {
    const h = m.userData.home, d = m.userData.dir;
    const b = blast;
    m.position.set(h.x + d.x * b * 3.5, h.y + Math.sin(Math.PI * Math.min(1, b)) * 3.2 * b - (b > 1 ? (b - 1) * 4 : 0), h.z + d.z * b * 3.5);
    m.rotation.set(b * 4 * d.x, b * 3, b * 4 * d.z);
    m.visible = b < 1.6;
  }
  S.graveFire.set(ctx.t, { flare: 0.3 + fire, bright: 1.0 * clamp(fire * 2), opacity: clamp(fire * 3) });
  S.graveFire.mesh.visible = fire > 0.01;
  S.graveLight.intensity = 40 * fire * (0.85 + 0.15 * noise1(ctx.t * 5));
  S.graveJack.userData.setOn(jack);
  S.graveJackFire.set(ctx.t, { bright: 1.4 * jack, flare: 0.4 + 0.6 * jack });
  S.graveJackFire.mesh.visible = jack > 0.02;
}
// faroles del camino; mode: 'on' | 'off' | (j) => k
function lanternState(S, mode) {
  for (const j of S.jacks) {
    let k = 1;
    if (mode === 'off') k = j.door ? 1 : 0;
    else if (typeof mode === 'function') k = mode(j);
    j.mesh.userData.setOn(k);
    j.k = k;
  }
  for (const l of S.roadLights) {
    let s = 0, c = 0;
    for (const j of S.jacks) if (!j.door && Math.abs(j.z - l.position.z) < 9) { s += Math.min(j.k, 1.4); c++; }
    l.intensity = 22 * (c ? s / c : 1);
  }
}
function forestNight(S, ctx) {
  S.fireflies.set(ctx.t);
  S.fog.userData.update(ctx.t);
  for (const s of S.shafts) s.userData.u.uTime.value = ctx.t;
}
function graveBase(S, ctx) {
  S.fog.userData.update(ctx.t);
  S.bats.userData.update(ctx.t, [0, 0, 0]);
  S.mtnFire.set(ctx.t, { flare: 1, bright: 1.2 });
  S.runeSparks.set(ctx.t);
  S.runeSparks.points.visible = false;
  S.runeLight.intensity = 0;
  for (const z of S.zombies) z.root.visible = false;
}
function mountainNight(S, ctx) {
  const u = S.sky.userData.u;
  u.uTop.value.set(0x05061a); u.uHor.value.set(0x2a1a48); u.uBot.value.set(0x05040a);
  u.uSunDir.value.set(-0.45, 0.4, 0.75).normalize(); u.uSunCol.value.set(0xff8a30); u.uGlow.value = 0.5; u.uStars.value = 1;
  S.moon.visible = true;
  S.fire.set(ctx.t, { wave: -99, flare: 1 });
  S.embers.set(ctx.t, { mix: 0 });
  S.drips.set(ctx.t);
  S.fog.userData.update(ctx.t);
  S.bats.userData.update(ctx.t, [0, 14, 0]);
  S.bats.visible = true;
  for (const l of S.blue) l.color.set(0x3aa8ff);
  for (const l of S.tunnelLanterns) l.userData.glow.emissive.setRGB(0.35, 0.8, 1.0);
  S.scene.fog.color.set(0x101428);
  S.L.dir.color.set(0x9aaeff); S.L.dir.intensity = 0.9;
  S.L.hemi.color.set(0x2a3060); S.L.hemi.intensity = 0.55;
}
function mountainDawn(S, ctx) {
  const u = S.sky.userData.u;
  u.uTop.value.set(0x2a1a5a); u.uHor.value.set(0xff7a5a); u.uBot.value.set(0x201020);
  u.uSunDir.value.set(0.6, 0.12, 0.8).normalize(); u.uSunCol.value.set(0xffa060); u.uGlow.value = 1.4; u.uStars.value = 0.15;
  S.moon.visible = false;
  S.fire.set(ctx.t, { wave: 99, flare: 1.1 });
  S.embers.set(ctx.t, { mix: 1 });
  for (const l of S.blue) l.color.set(0xff8a3a);
  for (const l of S.tunnelLanterns) l.userData.glow.emissive.setRGB(1.0, 0.6, 0.25);
  S.scene.fog.color.set(0x6a4070);
  S.L.dir.color.set(0xffb088); S.L.dir.intensity = 1.4; S.L.dir.userData.vec = V(0.6, 0.35, 0.8).normalize();
  S.L.hemi.color.set(0x9a80c0); S.L.hemi.intensity = 0.85;
  S.bats.visible = false;
}
function caveBase(S, ctx, wave = -99) {
  S.fire.set(ctx.t, { wave, flare: 1 });
  S.ringFire.set(ctx.t, { wave: -99, flare: 1, bright: 0.35 });
  S.crownFire.set(ctx.t, { wave: -99, flare: 1 });
  S.embers.set(ctx.t, { mix: 0 });
  S.pitEmbers.set(ctx.t, { mix: 0 });
  S.fog.userData.update(ctx.t);
  for (const s of S.shafts) s.userData.u.uTime.value = ctx.t;
  for (const l of S.lights) { l.color.set(0x3a9cff); l.intensity = l.userData.base * (0.9 + 0.1 * noise1(ctx.t * 4, l.position.z)); }
  S.hemi.color.set(0x1a3a6a);
  S.scene.fog.color.set(0x040814);
  S.army.mat.emissive.set(0x4ab8ff);
  S.army.mat.emissiveIntensity = 0;
  S.king.mat.emissiveIntensity = 0;
  S.king.root.visible = true;
  S.king.root.rotation.set(0, 0, 0);
  S.crown.visible = true;
  S.orb.visible = true;
  S.orb.scale.setScalar(1);
  S.orb.position.set(0, 6.3 + Math.sin(ctx.t * 2) * 0.15, -76);
  S.orb.rotation.set(0, ctx.t * 0.6, 0);
  S.eternal.set(ctx.t, { gold: 1, bright: 1.5 });
  S.orbLight.position.copy(S.orb.position);
  S.orbLight.intensity = 14;
  S.orbSwirl.set(ctx.t, { center: [S.orb.position.x, S.orb.position.y, S.orb.position.z] });
  S.orbSwirl.points.visible = true;
  S.kingLight.position.set(0, 14, -92);
  for (const l of S.lanterns) l.userData.glow.emissive.setRGB(0.35, 0.8, 1.0);
}
function kingPose(S, sit, lt, opts = {}) {
  const K = S.king;
  const base = opts.base || [0, 8, -95.4];
  K.root.position.set(base[0], base[1] - sit * 2.25 + (opts.dy || 0), base[2]);
  K.root.rotation.set(0, opts.yaw || 0, 0);
  K.legL.rotation.set(-sit * 1.5, 0, -sit * 0.1);
  K.legR.rotation.set(-sit * 1.5, 0, sit * 0.1);
  K.torso.rotation.set(opts.torsoX || 0, 0, 0);
  K.head.rotation.set(opts.headX || 0, opts.headY || 0, 0);
  K.armL.rotation.set(opts.armL ?? -sit * 0.6, 0, -0.15);
  K.armR.rotation.set(opts.armR ?? -sit * 0.9 - 0.3, 0, 0.12);
  K.root.scale.setScalar(3);
}
function armyIdle(S, ctx, o = {}) {
  const fig = o.fig || V(0.5, 0, 0);
  const look = o.look || 0;
  const aim = o.aim || 0;
  const t = ctx.t;
  S.army.apply((i, it) => {
    const dx = fig.x - it.x, dz = fig.z - it.z;
    let rel = Math.atan2(dx, dz) - (it.yaw || 0);
    rel = Math.atan2(Math.sin(rel), Math.cos(rel));
    const lk = clamp(look * 1.6 - (i % 7) * 0.08);
    const hy = clamp(rel, -1.3, 1.3) * lk;
    const rattle = o.rattle ? Math.sin(t * 31 + i * 1.7) * 0.06 * o.rattle : 0;
    const P = { head: [Math.sin(t * 0.7 + i) * 0.05 * (1 - lk) + rattle, hy + Math.sin(t * 9 + i) * 0.02 + rattle * 0.5] };
    if (o.rattle) { P.armR = [Math.sin(t * 27 + i) * 0.15 * o.rattle, 0.08]; P.armL = [Math.sin(t * 29 + i * 2) * 0.15 * o.rattle, -0.08]; }
    if (it.bow && aim > 0) {
      const yaw = lerp(it.yaw || 0, (it.yaw || 0) + clamp(rel, -1.2, 1.2), aim);
      P.yaw = yaw;
      P.head = [0, (hy - clamp(rel, -1.2, 1.2) * aim) * 0.3];
      P.armL = [-Math.PI / 2 * aim, -0.05];
      P.armR = [-Math.PI / 2 * aim + 0.25 * aim, 0.25 * aim];
    }
    if (o.extra) Object.assign(P, o.extra(i, it, P) || {});
    return P;
  });
}
// ejercito en batalla en la sala del trono
function battleArmy(S, ctx, o) {
  const target = o.target;
  S.army.apply((i, it) => {
    if (!(it.guard || it.row === 1)) {
      const P = { head: [0, 0] };
      if (o.waveCollapse !== undefined) P.collapse = clamp((o.waveCollapse - Math.hypot(it.x, it.z + 76) / 70) / 0.3);
      return P;
    }
    const k = i % 48;
    const ang = (k / 48) * Math.PI * 2 + 0.3;
    const rad = 6 + (k % 3) * 2.2;
    const bx = Math.cos(ang) * rad, bz = -71 + Math.sin(ang) * rad * 0.8;
    const sx = it.guard ? it.x : bx * 1.8, sz = it.guard ? it.z : -66 + Math.sin(ang) * 4;
    const ch = o.charge;
    const x = lerp(sx, lerp(bx, target.x + Math.cos(ang) * 2.8, 0.35), ch), z = lerp(sz, lerp(bz, target.z + Math.sin(ang) * 2.8, 0.35), ch);
    const yaw = yawTo(target.x - x, target.z - z);
    const P = { x, y: 3, z, yaw, walk: ch > 0.02 && ch < 0.98 ? 1 : 0, phase: ctx.t * 9 + i, head: [0, 0] };
    if (it.bow && o.aim) { P.armL = [-Math.PI / 2 * o.aim, 0]; P.armR = [-Math.PI / 2 * o.aim + 0.25, 0.25]; }
    if (o.collapse) P.collapse = o.collapse(i, { x, z });
    if (o.collapseAll) P.collapse = 1;
    return P;
  });
}
// flechas de fuego azul; deflect: radio en el que rebotan (anillo de fuego)
function arrows(fx, lt, target, t0, slow, deflect = 0) {
  const A = fx.arrowMesh;
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(1, 1, 1);
  const T = lt < t0 ? -1 : (lt - t0) * slow + 0.25;
  const hits = [];
  for (let i = 0; i < A.count; i++) {
    const a = (i / A.count) * Math.PI * 2 * 3.1;
    const rad = 8 + (i % 5) * 1.5;
    const start = V(target.x + Math.cos(a) * rad, 9 + (i % 4), target.z + Math.sin(a) * rad * 0.8 + 3);
    const end = V(target.x + Math.cos(a * 1.7) * 0.6, target.y + 1.4, target.z + Math.sin(a * 1.3) * 0.6);
    const delay = (i % 7) * 0.12;
    const fly = (k) => { const p = start.clone().lerp(end, k); p.y += Math.sin(Math.PI * k) * 2.5; return p; };
    let k = clamp((T - delay) / 1.0);
    let p = fly(k), p2 = fly(clamp(k + 0.02));
    let vis = T > delay ? 1 : 0;
    if (deflect > 0) {
      // momento en que entra en el anillo
      let kh = 1;
      for (let j = 0; j <= 40; j++) { const pp = fly(j / 40); if (Math.hypot(pp.x - target.x, pp.z - target.z) < deflect) { kh = j / 40; break; } }
      if (k > kh) {
        const hp = fly(kh);
        const out = V(hp.x - target.x, 0, hp.z - target.z).normalize();
        const tt = (k - kh) * 1.4;
        p = hp.clone().addScaledVector(out, tt * 6).add(V(0, tt * 3 - tt * tt * 4, 0));
        p2 = p.clone().addScaledVector(out, 0.1).add(V(0, 0.05, 0));
        if (tt < 0.25) hits.push(hp);
        if (tt > 1.1) vis = 0;
      }
    } else if (k >= 1) { p2 = p.clone().add(V(0, -0.1, 0)); }
    const dir = p2.sub(p).normalize();
    if (dir.lengthSq() < 0.5) dir.set(0, -1, 0);
    q.setFromUnitVectors(V(0, 0, 1), dir);
    m.compose(p, q, s.setScalar(vis));
    A.setMatrixAt(i, m);
  }
  A.instanceMatrix.needsUpdate = true;
  A.visible = lt > t0;
  return hits;
}
function dance(S, t, amt) {
  S.villagers.forEach((v, i) => {
    v.reset();
    v.root.visible = true;
    const a = t * 0.45 + (i / S.villagers.length) * Math.PI * 2;
    const r = 5 + Math.sin(t * 0.9 + i) * 0.3;
    v.root.position.set(Math.cos(a) * r, Math.abs(Math.sin(t * 5 + i * 1.3)) * 0.35 * amt, Math.sin(a) * r);
    v.root.rotation.y = -a + (i % 2 ? Math.PI : 0) + Math.sin(t * 2 + i) * 0.6;
    v.walk(t * 1.5 + i, 0.8);
    v.head.rotation.x = Math.sin(t * 5 + i) * 0.15;
  });
}
function cheer(S, t, lt) {
  S.villagers.forEach((v, i) => {
    v.reset();
    const door = S.doors[[4, 5, 6, 7, 8, 4, 5, 8][i]];
    const out = seg(lt, 1 + i * 0.25, 3 + i * 0.25);
    const dir = V(-door[0], 0, -door[1] - 8).normalize();
    const p = V(door[0], 0, door[1]).addScaledVector(dir, out * (2.2 + (i % 3)));
    v.root.visible = out > 0.02;
    v.root.position.copy(p);
    v.root.rotation.y = yawTo(0.5 - p.x, -9 - p.z);
    if (out > 0 && out < 1) v.walk(lt * 3 + i);
    if (out >= 1) v.root.position.y = Math.abs(Math.sin(t * 6 + i * 1.7)) * 0.4;
    if (out >= 1) v.arms.rotation.x = -0.8 + Math.sin(t * 6 + i) * 0.3;
  });
}
function groundG(S, z) {
  const a = S.hAt(0, Math.floor(z)) + 1, b = S.hAt(0, Math.floor(z) + 1) + 1;
  return lerp(a, b, ease((z - Math.floor(z) - 0.35) / 0.3));
}
function tunnelX(z) { return Math.sin(z / 9) * 1.5 + 0.5; }
function tunnelY(S, z) {
  const a = S.floorAt(Math.floor(z)) + 1, b = S.floorAt(Math.floor(z) + 1) + 1;
  return lerp(a, b, ease((z - Math.floor(z) - 0.35) / 0.3));
}

// objetos de efectos creados a demanda por escenario
function ensureFx(S) {
  if (S.fxApi) return S.fxApi;
  const api = {};
  S.fx = {};
  let n = 0;
  const reg = (o) => { S.scene.add(o); S.fx['o' + n++] = o; o.visible = false; return o; };
  const P = (cnt, o) => { const p = new Particles(cnt, o); reg(p.points); return p; };
  api.shock = reg(makeRing(0xffffff, 1.6));
  api.shock2 = reg(makeRing(0xffffff, 1.2));
  api.ground = reg(makeRing(0x3ab0ff, 1.6));
  api.spinRing = reg(makeRing(0xff8a30, 2.2));
  api.burst = P(500, { burst: true, center: [0, 0, 0], box: [1, 0.5, 1], vel: [0, 0.5, 0], speed: 14, life: 2.2, size: 0.06, colA: 0x5ac8ff, bright: 1.8, drag: 1.4, grav: 2 });
  api.bigBurst = P(900, { burst: true, center: [0, 0, 0], box: [20, 2, 20], vel: [0, 1.5, 0], speed: 9, life: 4, size: 0.07, colA: 0xffa030, bright: 1.8, drag: 0.8, grav: 0.6, seed: 9 });
  api.crownBurst = P(260, { burst: true, center: [0, 0, 0], box: [0.6, 0.4, 0.6], vel: [0, 0, 0], speed: 7, life: 2, size: 0.06, colA: 0x7ad0ff, bright: 2, drag: 1.2, grav: 6, seed: 5 });
  api.goldBurst = P(600, { burst: true, center: [0, 0, 0], box: [0.6, 0.6, 0.6], vel: [0, 0.4, 0], speed: 11, life: 2.6, size: 0.05, colA: 0xffd060, bright: 1.4, drag: 1.3, grav: 0.5, seed: 13 });
  api.clashA = P(200, { burst: true, center: [0, 0, 0], box: [0.3, 0.3, 0.3], vel: [0, 0.5, 0], speed: 6, life: 0.9, size: 0.05, colA: 0xffa040, bright: 2.6, drag: 2, grav: 5, seed: 17 });
  api.clashB = P(200, { burst: true, center: [0, 0, 0], box: [0.3, 0.3, 0.3], vel: [0, 0.5, 0], speed: 6, life: 0.9, size: 0.05, colA: 0x5ac8ff, bright: 2.6, drag: 2, grav: 5, seed: 19 });
  api.dust = P(260, { burst: true, center: [0, 0, 0], box: [2.5, 0.3, 3.5], vel: [0, 0.6, 0], speed: 4, life: 2.5, size: 0.12, colA: 0x4a3a2a, bright: 1, normal: true, drag: 2, grav: 0.8, seed: 23 });
  api.dissolve = P(900, { center: [0, 0, 0], box: [1.6, 3.2, 2.2], vel: [0.6, 2.2, -1.2], spread: [0.5, 0.6, 0.5], life: 3.5, size: 0.07, colA: 0xffd060, colB: 0xff8a30, bright: 2.2, swirl: 0.5, seed: 29 });
  api.flameTrail = P(240, { center: [0, 0, 0], box: [0.25, 0.25, 0.25], vel: [0, 0.6, 0], spread: [0.3, 0.3, 0.3], life: 0.8, size: 0.04, colA: 0xffd870, bright: 1.3, seed: 31 });
  api.ringFire = new FireTrail(28, { orange: true, bright: 1.3, seed: 37, speed: 5 });
  reg(api.ringFire.mesh);
  api.flameBall = new Fire([{ x: 0, y: -0.3, z: 0, w: 0.7, h: 1.0 }, { x: 0.05, y: -0.3, z: 0.05, w: 0.45, h: 0.75 }], { orange: true, gold: 1, bright: 0.9, seed: 41, speed: 4 });
  reg(api.flameBall.mesh);
  api.flameLight = reg(new THREE.PointLight(0xffc860, 0, 14, 1.8));
  // lagrima de brasa
  api.tear = reg(new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.09, 0.06), new THREE.MeshBasicMaterial({ color: new THREE.Color(3, 1.6, 0.5) })));
  api.tearTrail = P(40, { center: [0, 0, 0], box: [0.02, 0.02, 0.02], vel: [0, 0.2, 0], spread: [0.05, 0.05, 0.05], life: 0.5, size: 0.02, colA: 0xffa040, bright: 2 });
  const arrowGeo = new THREE.BoxGeometry(0.06, 0.06, 0.9);
  const arrowMat = new THREE.MeshStandardMaterial({ color: 0x9adfff, emissive: 0x3ab0ff, emissiveIntensity: 1.2 });
  api.arrowMesh = new THREE.InstancedMesh(arrowGeo, arrowMat, 70);
  api.arrowMesh.frustumCulled = false;
  reg(api.arrowMesh);
  S.fxApi = api;
  return api;
}

// ---------------------------------------------------------------------------
// ESCENAS
// ---------------------------------------------------------------------------
const ROAD_IN = [[0, [-8, 0, -80.3]], [1.5, [-5, 0, -79.6]], [3, [-0.8, 0, -77]], [5, [0, 0, -64]], [10, [0, 0, -26]]];

const SC = [
  // 1: vista aerea del pueblo en Halloween
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      graveState(S, ctx, { lid: 1, fire: 0, jack: 0 });
      lanternState(S, 'on');
      dance(S, ctx.t, 1);
      cam(ctx.camera, lt, [[0, [10, 52, 96]], [5, [5, 34, 58]], [10, [1, 14, 26]]], [[0, [0, 40, -120]], [5, [0, 14, -60]], [10, [0, 1.5, -4]]], 50, { span: [0, 10] });
      S.bats.userData.update(ctx.t, [0, 24, -40]);
      ctx.focus = V(0, 0, -10);
      ctx.grade.uFade.value = 1 - seg(lt, 0, 2.2);
      ctx.flame.k = 0;
    },
  },
  // 2: fiesta en la plaza; el nino espantapajaros rie con sus amigos
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      graveState(S, ctx, { lid: 1 });
      lanternState(S, 'on');
      dance(S, ctx.t, 1);
      // ninos jugando
      const kidsPos = [[6.8, 3.6], [8.2, 2.2], [7.6, 4.8]];
      S.kids.forEach((k, i) => {
        k.reset(); k.root.scale.setScalar(0.6); k.root.visible = true;
        const [x, z] = kidsPos[i];
        k.root.position.set(x, Math.abs(Math.sin(ctx.t * 7 + i * 2)) * 0.25, z);
        k.root.rotation.y = yawTo(7.2 - x, 3.2 - z) + Math.sin(ctx.t * 3 + i) * 0.3;
        k.head.rotation.x = -0.2 + Math.sin(ctx.t * 9 + i) * 0.1;
        k.arms.rotation.x = -0.5 + Math.sin(ctx.t * 8 + i) * 0.4;
      });
      const K = standKid(ctx, 7.0, Math.abs(Math.sin(ctx.t * 6.5)) * 0.3, 3.3, yawTo(-1, 0.5));
      K.head.rotation.x = -0.25 + Math.sin(ctx.t * 10) * 0.12;
      K.torso.rotation.z = Math.sin(ctx.t * 5) * 0.1;
      if (lt < 5.5) {
        const a = lerp(3.6, 4.4, lt / 5.5);
        ctx.camera.position.set(Math.cos(a) * 10, 1.6, Math.sin(a) * 10);
        ctx.camera.lookAt(0, 1.8, 0);
        ctx.camera.fov = 42;
      } else {
        cam(ctx.camera, lt, [[5.5, [9.9, 1.25, 5.3]], [10, [9.5, 1.1, 4.8]]], [[5.5, [7.3, 0.85, 3.5]], [10, [7.3, 0.85, 3.5]]], 40);
        ctx.key.position.set(9.5, 2, 4.5); ctx.key.color.set(0xffc090); ctx.key.intensity = 3;
      }
      ctx.focus = V(2, 0, 2);
      ctx.flame.k = 0;
    },
  },
  // 3: el herrero cuenta la leyenda; flashback en sepia; los ninos se asustan
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 'on');
      const flash = lt > 4.2 && lt < 8.6;
      S.bonfire.set(ctx.t, { flare: 0.7, bright: 1.0 });
      S.bonLight.intensity = 55;
      // herrero junto al fuego
      const sm = S.smith;
      sm.reset(); sm.root.visible = true;
      place(sm, -3.4, 0, 1.2, yawTo(3.4, -1.2) + 0.5);
      sm.arms.rotation.x = -0.4 + Math.sin(ctx.t * 2.2) * 0.25;
      sm.head.rotation.x = Math.sin(ctx.t * 1.7) * 0.08;
      // ninos sentados escuchando
      const seats = [[-1.2, 3.4], [0.4, 3.7], [1.8, 3.0]];
      S.kids.forEach((k, i) => {
        k.reset(); k.root.scale.setScalar(0.6); k.root.visible = true;
        const [x, z] = seats[i];
        place(k, x, -0.27, z, yawTo(-3.4 - x, 1.2 - z));
        k.legL.rotation.set(-1.45, 0, 0.1); k.legR.rotation.set(-1.45, 0, -0.1);
        if (lt > 8.6) { k.setEyes(true); k.torso.rotation.x = -0.25; k.arms.rotation.x = -1.1; k.root.position.z += 0.1 * Math.sin(ctx.t * 30); }
      });
      const K = standKid(ctx, -0.5, -0.27, 2.2, yawTo(-2.9, -1.0));
      K.legL.rotation.set(-1.45, 0, 0.1); K.legR.rotation.set(-1.45, 0, -0.1);
      if (lt > 8.6) { K.setEyes(true); K.torso.rotation.x = -0.3; K.root.position.x += 0.04 * Math.sin(ctx.t * 37); }
      if (!flash) {
        graveState(S, ctx, { lid: 1 });
        if (lt < 4.2) cam(ctx.camera, lt, [[0, [-0.6, 1.4, 4.6]], [4.2, [-1.2, 1.5, 3.7]]], [[0, [-3.4, 1.4, 1.2]], [4.2, [-3.4, 1.5, 1.2]]], 40);
        else cam(ctx.camera, lt, [[8.6, [-4.8, 1.0, 1.0]], [10, [-4.6, 0.95, 1.4]]], [[8.6, [0, 0.7, 2.9]], [10, [0, 0.7, 2.9]]], 36);
        ctx.key.position.set(-1.5, 2.2, 2.6); ctx.key.color.set(0xffa060); ctx.key.intensity = 2.5;
      } else {
        // flashback: el caballero oscuro junto al roble y la tumba vacia
        const f = lt - 4.2;
        graveState(S, ctx, { lid: 0, fire: 0 });
        mount(ctx);
        const H = showHorse(ctx, -3.2, 0, -76.2, yawTo(1, 0.35));
        S.L.hemi.intensity = 2.6;
        H.walk(ctx.t * 2, 0.3);
        ctx.rider.pumpkin.visible = false;
        ctx.rider.headLight.intensity = 0;
        ctx.flame.k = 0;
        ctx.flame.noHoof = true;
        S.scene.fog.density = 0.02;
        cam(ctx.camera, f, [[0, [2.6, 1.0, -70.6]], [4.4, [1.6, 1.3, -71.6]]], [[0, [-6, 4.2, -80]], [4.4, [-5, 3.0, -78.5]]], 46);
        ctx.key.position.set(0.5, 4, -73); ctx.key.color.set(0xfff0d0); ctx.key.intensity = 60; ctx.key.distance = 16;
        const g = ctx.grade;
        g.uSat.value = 0.12; g.uTint.value.setRGB(1.25, 1.0, 0.72); g.uGrain.value = 0.09; g.uVig.value = 0.85; g.uContrast.value = 1.12;
        ctx.focus = V(-8, 0, -80);
      }
      ctx.grade.uFlash.value = 0.8 * Math.max(pulse(lt, 4.2, 0.25), pulse(lt, 8.6, 0.25));
      ctx.grade.uFlashCol.value.set(0xfff0d0);
      if (!flash) ctx.flame.k = 0;
      if (!flash) ctx.focus = V(-1, 0, 2);
    },
  },
  // 4: el rayo cae sobre el roble; la tierra se agrieta; se enciende la calabaza
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 'on');
      const strike = lt > 2.0 && lt < 2.5;
      S.bolt.visible = strike && Math.sin(lt * 90) > -0.3;
      S.boltLight.intensity = strike ? 220 * (0.6 + 0.4 * Math.sin(lt * 70)) : 0;
      const crack = seg(lt, 3.0, 6.0);
      S.cracks.visible = crack > 0;
      for (const piv of S.cracks.children) for (const m of piv.children) m.scale.x = clamp(crack * 4 - m.userData.k);
      S.cracks.children[0].children[0].material.opacity = 0.6 + 0.4 * noise1(ctx.t * 6);
      const blast = clamp((lt - 6.0) / 1.4) * 1.7;
      const fire = lt > 6 ? 0.5 + 0.7 * pulse(lt, 6.4, 1.2) : 0.15 * crack;
      graveState(S, ctx, { lid: lt < 6 ? 1 : 0, blast: lt >= 6 ? blast : 0, fire, jack: seg(lt, 7.6, 8.6) * (0.7 + 0.3 * noise1(ctx.t * 9)) });
      if (lt < 6) for (const m of S.lid.children) m.position.y = m.userData.home.y + Math.abs(Math.sin(ctx.t * 40 + m.position.x * 7)) * 0.08 * crack;
      const fx = ensureFx(S);
      fx.dust.points.visible = lt > 6;
      fx.dust.set(lt - 6, { center: [-8, 0.3, -80.5] });
      if (lt < 7.2) cam(ctx.camera, lt, [[0, [6, 3.2, -60]], [7.2, [2, 2.4, -66]]], [[0, [-12, 9, -84]], [7.2, [-8, 2.5, -81]]], 48, { shake: lt > 2 && lt < 3 ? 0.12 : lt > 6 && lt < 7 ? 0.08 : 0 });
      else cam(ctx.camera, lt, [[7.2, [-6.6, 1.1, -80.2]], [10, [-6.9, 0.95, -81.4]]], [[7.2, [-8, 0.5, -83.2]], [10, [-8, 0.5, -83.2]]], 40);
      ctx.grade.uFlash.value = 0.45 * pulse(lt, 2.1, 0.25) + 0.2 * pulse(lt, 2.35, 0.1);
      ctx.grade.uFlashCol.value.set(0xd8e8ff);
      ctx.focus = V(-8, 0, -80);
      ctx.flame.k = 0;
    },
  },
  // 5: el Jinete surge de la tumba; el caballo se encabrita (contrapicado)
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 'on');
      graveState(S, ctx, { lid: 0, fire: 0.9 - 0.4 * seg(lt, 3, 6), jack: 1 });
      const rise = seg(lt, 0.4, 3.6);
      const fwd = seg(lt, 3.2, 4.6);
      mount(ctx);
      const H = showHorse(ctx, -8, lerp(-3.4, 0, rise), lerp(-81.2, -78.6, fwd), 0);
      if (rise < 1) H.walk(ctx.t * 3, 0.8);
      const rear = seg(lt, 4.6, 5.6) * (1 - seg(lt, 7.6, 8.6));
      H.rear(rear, ctx.t);
      const R = ctx.rider;
      R.armL.rotation.x = -0.7 - 1.6 * rear;
      R.armL.rotation.z = 0.3 * rear;
      R.torso.rotation.x = -0.2 * rear;
      R.wind(ctx.t, 0.3 + 0.4 * rear);
      ctx.flame.k = 0.6 + 0.5 * seg(lt, 1, 4) + 0.3 * rear;
      ctx.flame.red = 0.7;
      ctx.flame.flare = 1 + 0.5 * rear;
      const fx = ensureFx(S);
      fx.dust.points.visible = lt < 5;
      fx.dust.set(lt + 0.5, { center: [-8, 0.3, -80.5] });
      if (lt < 4.4) cam(ctx.camera, lt, [[0, [-5.6, 0.35, -75.0]], [4.4, [-5.9, 0.3, -75.4]]], [[0, [-8, 1.2, -80.5]], [4.4, [-8, 2.8, -79.5]]], 46);
      else cam(ctx.camera, lt, [[4.4, [-6.0, 0.25, -74.6]], [10, [-5.6, 0.3, -74.2]]], [[4.4, [-8, 3.4, -78.5]], [10, [-8, 3.0, -78.6]]], 52, { shake: rear > 0.5 ? 0.03 : 0 });
      S.boltLight.intensity = 160 * pulse(lt, 5.2, 0.15);
      S.bolt.visible = lt > 5.1 && lt < 5.3;
      ctx.grade.uFlash.value = 0.3 * pulse(lt, 5.2, 0.2);
      ctx.grade.uFlashCol.value.set(0xd8e8ff);
      ctx.key.position.set(-5.4, 3.0, -75.4); ctx.key.color.set(0xb0c0ff); ctx.key.intensity = 45; ctx.key.distance = 14;
      ctx.focus = V(-8, 0, -79);
    },
  },
  // 6: galope en camara lenta; las calabazas se avivan y se apagan; puertas cerradas
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      mount(ctx);
      const keys = [[0, [-3.5, 0, -78.4]], [1.2, [-1.2, 0, -76.6]], [2.4, [0, 0, -72]], [10, [0, 0, -30]]];
      const { p } = ride(ctx, keys, lt);
      ctx.horse.gallop(ctx.t * 5.5, 1);
      ctx.rider.wind(ctx.t * 0.5, 0.9);
      ctx.rider.torso.rotation.x = 0.15;
      lanternState(S, (j) => {
        if (j.door) return 1;
        const d = p.z - j.z;
        if (d < -7) return 1;
        if (d < 0) return 1 + 0.6 * ((d + 7) / 7);
        return Math.max(0, 1.6 * (1 - d / 1.6)) * (0.7 + 0.3 * Math.sin(ctx.t * 30 + j.x));
      });
      hoofTrail(S.trail, keys, lt, { span: 4 });
      // aldeanos que huyen a sus casas
      S.villagers.forEach((v, i) => {
        if (i > 5) return;
        v.reset();
        const door = S.doors[i];
        const zz = door[1];
        const k = clamp((p.z - zz + 16 - (i % 2) * 2) / 4);
        const start = V(door[0] * 0.35, 0, zz + (i % 2 ? 2.5 : -2));
        const pos = start.clone().lerp(V(door[0], 0, door[1]), k);
        v.root.visible = k < 0.97;
        v.root.position.copy(pos);
        v.root.rotation.y = k <= 0 ? yawTo(p.x - pos.x, p.z - pos.z) : yawTo(door[0] - start.x, door[1] - start.z);
        v.walk(ctx.t * 3 + i, k > 0 && k < 1 ? 1.4 : 0);
        if (k <= 0) v.setEyes(true);
        v.arms.rotation.x = k > 0 ? -1.3 : 0;
      });
      const side = V(-4.2, 0.8, 3.4);
      ctx.camera.position.set(p.x + side.x + Math.sin(lt * 0.4) * 0.3, side.y + lt * 0.05, p.z + side.z + lerp(0, 2.5, lt / 10));
      ctx.camera.lookAt(p.x + 0.3, 2.5, p.z - 0.8);
      ctx.camera.fov = 44;
      ctx.flame.k = 1.2; ctx.flame.red = 0.8;
      ctx.key.position.set(p.x - 2.5, 3.5, p.z + 2); ctx.key.color.set(0xb8c0ff); ctx.key.intensity = 12; ctx.key.distance = 12;
      ctx.focus = V(0, 0, p.z);
      ctx.grade.uVig.value = 0.55;
    },
  },
  // 7: plaza vacia, hoguera moribunda; el nino tiembla escondido tras la paja
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 'off');
      S.bonfire.set(ctx.t, { flare: 0.35, bright: 0.8 });
      S.bonLight.intensity = 14 * (0.8 + 0.2 * noise1(ctx.t * 4));
      mount(ctx);
      const keys = [[0, [0, 0, -24]], [3, [0, 0, -12]], [5.2, [0, 0, -6.5]], [10, [0, 0, -6.5]]];
      const { p, speed } = ride(ctx, keys, lt, { yaw0: 0 });
      ctx.horse.yaw = 0;
      ctx.horse.root.rotation.y = 0;
      if (speed > 0.3) ctx.horse.walk(ctx.t * 4, Math.min(1, speed / 3)); else ctx.horse.walk(0, 0);
      ctx.horse.neck.rotation.x = 0.55 + 0.1 * Math.sin(ctx.t * 1.3);
      hoofTrail(S.trail, keys, lt, { span: 5, step: 0.35, b: 0.7 });
      ctx.rider.wind(ctx.t, 0.15);
      const K = standKid(ctx, 6.5, 0, -6.2, yawTo(-6.5, -0.3));
      K.body.position.y = 0.75 - 0.15;
      K.torso.rotation.x = 0.35;
      K.legL.rotation.x = -0.6; K.legR.rotation.x = -0.6;
      K.root.position.x += Math.sin(ctx.t * 41) * 0.012;
      K.head.rotation.z = Math.sin(ctx.t * 37) * 0.03;
      K.arms.rotation.x = -0.6;
      if (lt > 7.5) K.setEyes(true);
      if (lt < 5.2) cam(ctx.camera, lt, [[0, [4.5, 2.2, 9]], [5.2, [3.2, 1.8, 6.5]]], [[0, [0, 2.3, -14]], [5.2, [0, 2.6, -6]]], 44);
      else {
        cam(ctx.camera, lt, [[5.2, [9.9, 2.1, -3.2]], [10, [9.5, 1.9, -3.7]]], [[5.2, [2.0, 1.6, -6.5]], [10, [3.0, 1.3, -6.5]]], 42);
        ctx.key.position.set(7.4, 1.6, -4.8); ctx.key.color.set(0xffb070); ctx.key.intensity = 2;
      }
      ctx.flame.k = 1.0; ctx.flame.red = 0.7;
      ctx.focus = V(2, 0, -5);
    },
  },
  // 8: primer plano: la calabaza gira hacia el nino; el fuego pasa a un naranja triste; lagrima de brasa
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 'off');
      S.bonfire.set(ctx.t, { flare: 0.35, bright: 0.8 });
      S.bonLight.intensity = 12;
      mount(ctx);
      const H = showHorse(ctx, 0, 0, -6.5, 0);
      H.walk(0, 0);
      H.neck.rotation.x = 0.6 + 0.05 * Math.sin(ctx.t);
      const R = ctx.rider;
      const turn = seg(lt, 0.8, 2.6);
      R.head.rotation.y = 1.25 * turn;
      R.head.rotation.x = 0.18 * turn;
      R.torso.rotation.y = 0.25 * turn;
      R.wind(ctx.t, 0.1);
      const soft = seg(lt, 3.0, 6.0);
      ctx.flame.k = lerp(0.55, 0.38, soft);
      ctx.grade.uExposure.value = 0.95; ctx.flame.red = 0.8 * (1 - soft); ctx.flame.soft = soft; ctx.flame.flare = lerp(1.1, 0.7, soft);
      const K = standKid(ctx, 6.5, 0, -6.2, yawTo(-6.5, -0.3));
      K.body.position.y = 0.6 + 0.15 * seg(lt, 5, 7);
      K.torso.rotation.x = 0.35 * (1 - seg(lt, 5, 7));
      K.legL.rotation.x = -0.6 * (1 - seg(lt, 5, 7)); K.legR.rotation.x = -0.6 * (1 - seg(lt, 5, 7));
      K.setEyes(lt < 6.5);
      K.head.rotation.x = -0.25;
      // lagrima de brasa
      const fx = ensureFx(S);
      ctx.camera.updateMatrixWorld();
      R.root.updateMatrixWorld(true);
      const eye = V(-0.12, -0.02, 0.33);
      R.head.localToWorld(eye);
      const tt = lt - 6.6;
      fx.tear.visible = tt > 0 && tt < 2.2;
      fx.tear.position.set(eye.x + tt * 0.08, eye.y - 4.9 * tt * tt * 0.35 - tt * 0.1, eye.z + tt * 0.05);
      fx.tearTrail.points.visible = fx.tear.visible;
      fx.tearTrail.set(ctx.t, { center: [fx.tear.position.x, fx.tear.position.y, fx.tear.position.z] });
      const head = V(); R.head.getWorldPosition(head);
      if (lt < 6.3) {
        cam(ctx.camera, lt, [[0, [head.x + 2.8, head.y + 0.1, head.z + 2.2]], [6.3, [head.x + 2.2, head.y + 0.05, head.z + 1.7]]], [[0, [head.x, head.y, head.z]], [6.3, [head.x, head.y - 0.05, head.z]]], 30);
      } else {
        cam(ctx.camera, lt, [[6.3, [head.x + 1.8, head.y - 0.25, head.z + 1.0]], [10, [head.x + 1.6, head.y - 0.45, head.z + 0.9]]], [[6.3, [head.x, head.y - 0.1, head.z]], [10, [head.x, head.y - 0.8, head.z]]], 34);
      }
      ctx.key.position.set(head.x + 1.4, head.y + 0.6, head.z + 0.4); ctx.key.color.set(0xb8c8ff); ctx.key.intensity = 1.6;
      ctx.focus = V(2, 0, -5);
      ctx.grade.uVig.value = 0.6;
    },
  },
  // 9: el Jinete senala la montana con el brillo azul; aparicion de la llama dorada en la niebla
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 'off');
      S.bonfire.set(ctx.t, { flare: 0.35, bright: 0.8 });
      S.bonLight.intensity = 12;
      S.scene.fog.density = 0.0032;
      S.moon.visible = false;
      const u = S.sky.userData.u;
      u.uSunDir.value.copy(S.MTN.clone().add(V(0, 120, -60)).normalize());
      u.uSunCol.value.set(0x3a90ff); u.uGlow.value = 1.6 + 0.3 * noise1(ctx.t);
      mount(ctx);
      const dir = Math.atan2(S.MTN.x, S.MTN.z - 60 + 6.5);
      const H = showHorse(ctx, 0, 0, -6.5, lerp(0, dir, seg(lt, 0, 1.5)));
      H.walk(ctx.t * 3, lt < 1.5 ? 0.6 : 0);
      const R = ctx.rider;
      const point = seg(lt, 1.6, 2.8);
      R.armR.rotation.set(-0.7 - 1.0 * point, 0, -0.1);
      R.head.rotation.x = -0.08 * point;
      R.wind(ctx.t, 0.2);
      ctx.flame.k = 0.9; ctx.flame.soft = 0.7;
      const K = standKid(ctx, 1.6, 0, -4.8, dir);
      K.head.rotation.x = -0.35;
      K.arms.rotation.x = -0.4;
      const ap = seg(lt, 3.5, 6.5);
      S.ghostFlame.mesh.visible = ap > 0.01;
      S.ghostFlame.mesh.position.set(5, 12, -95);
      S.ghostFlame.mesh.scale.setScalar(1.3);
      S.ghostFlame.set(ctx.t, { gold: 1, opacity: 0.45 * ap * (0.85 + 0.15 * noise1(ctx.t * 2)), bright: 0.45 });
      S.goldDust.points.visible = ap > 0.01;
      S.goldDust.set(ctx.t, { center: [5, 18, -95], opacity: ap });
      S.mtnGlow.userData.u.uOpacity.value = 0.35 + 0.1 * Math.sin(ctx.t * 2);
      cam(ctx.camera, lt, [[0, [3.2, 2.6, 2.5]], [10, [2.0, 3.6, 0.2]]], [[0, [0, 3.2, -14]], [5, [3, 12, -90]], [10, [8, 30, -200]]], 46, { span: [0, 10] });
      ctx.key.position.set(1.5, 4, -3); ctx.key.intensity = 3;
      ctx.focus = V(0, 0, -6);
    },
  },
  // 10: el nino sube al caballo; galopan fuera del pueblo
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 'off');
      S.bonfire.set(ctx.t, { flare: 0.35, bright: 0.8 });
      S.bonLight.intensity = 12;
      mount(ctx);
      const keys = [[0, [0, 0, -6.5]], [4.2, [0, 0, -6.5]], [5.4, [0, 0, -9]], [10, [0, 0, -62]]];
      const { p } = ride(ctx, keys, lt, { yaw0: Math.PI });
      ctx.horse.root.rotation.y = Math.PI;
      const H = ctx.horse;
      if (lt > 4.2) H.gallop(ctx.t * 9, seg(lt, 4.2, 5.2)); else H.walk(0, 0);
      const R = ctx.rider;
      // le tiende la mano
      const reach = seg(lt, 0.4, 1.4) * (1 - seg(lt, 3.0, 3.8));
      R.armL.rotation.set(-0.7 - 0.5 * reach, 0, 0.6 * reach);
      R.head.rotation.y = 0.9 * reach;
      R.head.rotation.x = 0.25 * reach;
      R.wind(ctx.t, lt > 4.2 ? 0.9 : 0.15);
      ctx.flame.k = 1.0; ctx.flame.soft = 0.3;
      const K = ctx.kid;
      if (lt < 3.4) {
        const lift = seg(lt, 1.4, 3.4);
        H.root.updateMatrixWorld(true);
        const seat = V(0, -0.4, -0.55); H.saddle.localToWorld(seat);
        const ground = V(1.6, 0, -5.6);
        const kp = ground.clone().lerp(seat, lift);
        kp.y += Math.sin(Math.PI * lift) * 0.6;
        standKid(ctx, kp.x, kp.y, kp.z, lerp(yawTo(-1, -0.6), Math.PI, lift));
        K.arms.rotation.x = -1.6 * (1 - lift) - 0.4;
        if (lift > 0.5) K.sit();
      } else mountKid(ctx);
      hoofTrail(S.trail, keys, lt, { t0: 4.2, span: 3 });
      if (lt < 4.6) cam(ctx.camera, lt, [[0, [4.8, 2.0, -2.0]], [4.6, [4.2, 2.3, -3.2]]], [[0, [0.8, 2.2, -6]], [4.6, [0.3, 2.4, -6.5]]], 42);
      else cam(ctx.camera, lt, [[4.6, [3.2, 2.0, -2]], [10, [2.4, 4.6, -18]]], [[4.6, [0, 2.2, -10]], [10, [0, 2.4, -55]]], 46);
      ctx.key.position.set(p.x + 2, 4, p.z + 2); ctx.key.intensity = 5;
      ctx.focus = V(0, 0, p.z);
    },
  },
  // 11: travelling rapido por el bosque muerto
  {
    set: 'forest',
    update(lt, ctx) {
      const S = ctx.set;
      forestNight(S, ctx);
      mount(ctx); mountKid(ctx);
      const z0 = 62, z1 = -58;
      const keys = [];
      for (let k = 0; k <= 10; k++) { const z = lerp(z0, z1, k / 10); keys.push([k, [S.px(z), 0, z]]); }
      const gr = (x, z) => S.hAt(Math.floor(x), Math.floor(z)) + 1;
      const { p, yaw } = ride(ctx, keys, lt, { ground: gr });
      ctx.horse.gallop(ctx.t * 11, 1);
      ctx.rider.wind(ctx.t, 1);
      ctx.rider.torso.rotation.x = 0.2;
      ctx.kid.torso.rotation.x = 0.3;
      hoofTrail(S.trail, keys, lt, { span: 2.2, step: 0.06, ground: gr });
      S.mushLight.position.set(p.x + 2, 1, p.z - 3);
      const fwd = V(Math.sin(yaw), 0, Math.cos(yaw));
      const sideV = V(fwd.z, 0, -fwd.x);
      const a = lt < 5 ? 1 : -1;
      const off = sideV.clone().multiplyScalar(2.6 * a).addScaledVector(fwd, lerp(6.0, 3.2, (lt % 5) / 5));
      ctx.camera.position.set(p.x + off.x, p.y + 2.2 + 0.3 * Math.sin(lt * 1.3), p.z + off.z);
      ctx.camera.lookAt(p.x, p.y + 2.3, p.z);
      ctx.camera.fov = 52;
      ctx.flame.k = 1.0; ctx.flame.soft = 0.2;
      ctx.key.position.set(p.x + sideV.x * 2.5 * a, p.y + 3.5, p.z + sideV.z * 2.5 * a); ctx.key.color.set(0xb0c0ff); ctx.key.intensity = 10; ctx.key.distance = 10;
      ctx.focus = V(p.x, 0, p.z);
    },
  },
  // 12: cementerio con niebla; los zombis se acercan; los ojos del Jinete se avivan y retroceden
  {
    set: 'graveyard',
    update(lt, ctx) {
      const S = ctx.set;
      graveBase(S, ctx);
      mount(ctx); mountKid(ctx);
      const keys = [[0, [0.5, 0, 28]], [5, [0.5, 0, 14.5]], [6.5, [0.5, 0, 13]], [10, [0.5, 0, 6]]];
      const gr = (x, z) => groundG(S, z);
      const { p, speed } = ride(ctx, keys, lt, { ground: gr, yaw0: Math.PI });
      ctx.horse.walk(ctx.t * 4.5, Math.min(1, speed / 2.5));
      hoofTrail(S.trail, keys, lt, { span: 5, step: 0.3, ground: gr, b: 0.8 });
      const flare = seg(lt, 5.2, 5.9) * (1 - 0.5 * seg(lt, 8, 10));
      ctx.flame.k = 0.9 + 0.9 * flare; ctx.flame.red = 0.6 * flare; ctx.flame.flare = 1 + 0.8 * flare;
      const R = ctx.rider;
      R.head.rotation.y = 0.5 * Math.sin(lt * 0.8) * (1 - flare);
      R.torso.rotation.x = -0.1 * flare;
      ctx.kid.torso.rotation.x = 0.4 * seg(lt, 2, 4);
      ctx.kid.setEyes(lt > 2);
      S.zombies.forEach((zb, i) => {
        const [hx, hy, hz] = zb.home;
        const rise = seg(lt, i * 0.35, i * 0.35 + 1.4);
        const side = hx < 0 ? -1 : 1;
        const approach = seg(lt, 1.5, 5.3);
        const retreat = seg(lt, 5.6, 8.0);
        zb.root.visible = rise > 0.01;
        const dz = p.z - hz;
        const toward = clamp(approach * 1.2 - Math.abs(dz) * 0.04);
        const x = hx + side * (-1.3 * toward + 2.6 * retreat);
        zb.root.position.set(x, hy - 2.1 * (1 - rise), hz + dz * 0.25 * toward - side * 0);
        zb.root.rotation.set(0, yawTo(p.x - x, p.z - hz), 0);
        zb.armR.rotation.set(-Math.PI / 2 * (1 - retreat) - 0.2 + retreat * 0.6, 0, 0);
        zb.armL.rotation.set(-Math.PI / 2 * (1 - retreat) - 0.2 + retreat * 0.6, 0, 0);
        zb.torso.rotation.x = -0.3 * retreat;
        zb.head.rotation.x = 0.4 * retreat;
        const wk = (approach > 0 && approach < 1) || (retreat > 0 && retreat < 1) ? 1 : 0;
        zb.legL.rotation.x = Math.sin(ctx.t * 6 + i) * 0.5 * wk;
        zb.legR.rotation.x = -zb.legL.rotation.x;
      });
      if (lt < 5.2) cam(ctx.camera, lt, [[0, [4.5, 3.0, 33]], [5.2, [4.2, 2.4, 22]]], [[0, [0.5, 2.0, 22]], [5.2, [0.5, 2.6, 13]]], 46);
      else { ctx.camera.position.set(p.x + 2.8, p.y + 2.1, p.z - 5.6); ctx.camera.lookAt(p.x, p.y + 2.5, p.z); ctx.camera.fov = 46; }
      ctx.key.position.set(p.x + 2.5, p.y + 3.5, p.z - 1); ctx.key.color.set(0xb8c8ff); ctx.key.intensity = 5;
      ctx.focus = V(0, 0, p.z);
    },
  },
  // 13: la cueva-calavera; el caballo se niega a entrar
  {
    set: 'mountain',
    update(lt, ctx) {
      const S = ctx.set;
      mountainNight(S, ctx);
      if (lt < 7.8) {
        mount(ctx); mountKid(ctx);
        const keys = [[0, [0.5, 0, 26]], [5, [0.5, 0, 9]], [7.8, [0.5, 0, 10.5]]];
        const { speed } = ride(ctx, keys, lt, { yaw: Math.PI });
        const H = ctx.horse;
        if (lt < 5) H.gallop(ctx.t * 7, clamp(speed / 4));
        const rear = seg(lt, 5.0, 5.8) * (1 - seg(lt, 6.8, 7.6));
        H.rear(rear, ctx.t);
        H.eyeM.emissiveIntensity = 4 + 3 * rear;
        ctx.rider.wind(ctx.t, 0.6);
        ctx.kid.torso.rotation.x = 0.3;
        ctx.flame.k = 1.1; ctx.flame.soft = 0.2;
        cam(ctx.camera, lt, [[0, [4, 6, 44]], [7.8, [2.5, 3.6, 24]]], [[0, [0, 14, -12]], [7.8, [0, 8, -10]]], 50);
        ctx.key.position.set(2, 5, 14); ctx.key.intensity = 8;
      } else {
        const f = lt - 7.8;
        const H = showHorse(ctx, 0.5, 0, 11.5, Math.PI);
        H.walk(0, 0);
        H.neck.rotation.x = 0.9;
        H.root.rotation.y = Math.PI + 0.4;
        const z = lerp(8.5, 5.5, f / 2.2);
        const R = standRider(ctx, 0.2, 0, z, Math.PI);
        R.walk(z * 1.3, 1);
        R.wind(ctx.t, 0.15);
        const K = standKid(ctx, 1.25, 0, z + 0.6, Math.PI);
        K.walk(z * 2, 1);
        ctx.flame.k = 1.0;
        cam(ctx.camera, f, [[0, [3.2, 2.4, 16.5]], [2.2, [2.8, 2.6, 15.5]]], [[0, [0, 4, 0]], [2.2, [0, 6, -6]]], 46);
        ctx.key.position.set(2, 4, 12); ctx.key.intensity = 6;
      }
      ctx.focus = V(0, 0, 6);
    },
  },
  // 14: bajan por el tunel de piedra con faroles de almas
  {
    set: 'mountain',
    update(lt, ctx) {
      const S = ctx.set;
      mountainNight(S, ctx);
      const z = lerp(-10, -30, lt / 10);
      const R = standRider(ctx, tunnelX(z), tunnelY(S, z), z, Math.PI);
      R.walk(z * 1.2, 1);
      R.wind(ctx.t, 0.1);
      const kz = z + 1.1;
      const K = standKid(ctx, tunnelX(kz) + 0.45, tunnelY(S, kz), kz, Math.PI);
      K.walk(kz * 2.2, 1);
      K.arms.rotation.x = -0.7;
      ctx.flame.k = 1.25;
      const head = V(R.root.position.x, R.root.position.y + 2.2, z);
      if (lt < 5) {
        const cz = z - lerp(3.6, 3.2, lt / 5);
        ctx.camera.position.set(tunnelX(cz) - 0.9, tunnelY(S, cz) + 1.7, cz);
        ctx.camera.lookAt(head.x, head.y - 0.2, head.z);
        ctx.camera.fov = 46;
      } else {
        const cz = z + 3.6;
        ctx.camera.position.set(tunnelX(cz) - 1.2, tunnelY(S, cz) + 3.4, cz);
        ctx.camera.lookAt(tunnelX(z - 8), tunnelY(S, z - 8) + 1.4, z - 8);
        ctx.camera.fov = 50;
      }
      ctx.fill.position.set(head.x, head.y + 0.2, head.z + 0.8); ctx.fill.intensity = 3;
      ctx.focus = V(0, 0, -20);
    },
  },
  // 15: revelacion de la caverna enorme
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 1, lt);
      const z = lerp(5, 0.8, seg(lt, 0, 7));
      const R = standRider(ctx, 0, 0, z, Math.PI);
      if (lt < 7) R.walk(z * 1.3, 1);
      R.wind(ctx.t, 0.1);
      const K = standKid(ctx, 0.6, 0, z + 1.0, Math.PI);
      if (lt < 7) K.walk(z * 2.2, 1);
      K.head.rotation.x = -0.3;
      armyIdle(S, ctx, { fig: V(0, 0, z) });
      S.army.mat.emissiveIntensity = 0.3;
      ctx.flame.k = 1.1;
      cam(ctx.camera, lt, [[0, [0.8, 1.9, 9.5]], [4, [0.4, 5.5, 6]], [10, [0, 20, -2]]], [[0, [0, 1.8, -8]], [4, [0, 3, -25]], [10, [0, 1, -42]]], 54, { span: [0, 10] });
      ctx.fill.position.set(0, 3, z + 1.2); ctx.fill.intensity = 3;
    },
  },
  // 16: cientos de craneos giran a la vez; sus cuencas se encienden; el nino se esconde tras la capa
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 1, lt);
      const R = standRider(ctx, 0, 0, 0.8, Math.PI);
      R.wind(ctx.t, 0.08);
      const hide = seg(lt, 3.6, 4.6);
      const K = standKid(ctx, lerp(0.7, 0.15, hide), 0, lerp(1.6, 1.25, hide), Math.PI);
      K.torso.rotation.x = 0.3 * hide;
      K.setEyes(lt > 3);
      K.walk(lt * 3, hide > 0 && hide < 1 ? 1 : 0);
      R.capeA.rotation.x = 0.15 + 0.25 * hide;
      R.capeA.rotation.z = 0.15 * hide;
      const look = seg(lt, 1.8, 3.4);
      armyIdle(S, ctx, { fig: V(0, 0, 0.8), look, rattle: seg(lt, 3.4, 4) * (1 - 0.6 * seg(lt, 7, 9)) });
      S.army.mat.emissiveIntensity = 0.3 + 2.4 * seg(lt, 3.6, 4.4);
      const flare = 1 + 0.8 * seg(lt, 4.2, 4.8) - 0.4 * seg(lt, 5.4, 7);
      S.fire.set(ctx.t, { wave: -99, flare });
      for (const l of S.lights) l.intensity *= flare;
      ctx.flame.k = 1.1 + 0.4 * seg(lt, 4.4, 5);
      const a = lerp(-0.4, Math.PI * 0.95, easeIO(lt / 10));
      ctx.camera.position.set(Math.sin(a) * 6.5, 2.4 + Math.sin(lt / 10 * Math.PI) * 1.2, 0.8 + Math.cos(a) * 6.5);
      ctx.camera.lookAt(0, 1.6, 0.8);
      ctx.camera.fov = 46;
      ctx.fill.position.set(0, 3, 2.2); ctx.fill.intensity = 2.5;
    },
  },
  // 17: pasillo de arqueros; al fondo el altar con la Llama Eterna
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 1, lt);
      const z = lerp(-2, -16, lt / 10);
      const R = standRider(ctx, 0, 0, z, Math.PI);
      R.walk(z * 1.2, 1);
      R.wind(ctx.t, 0.1);
      const K = standKid(ctx, 0.25, 0, z + 0.9, Math.PI);
      K.walk(z * 2.2, 1);
      K.arms.rotation.x = -0.7;
      armyIdle(S, ctx, { fig: V(0, 0, z), look: 1, aim: seg(lt, 0.8, 2.6) });
      S.army.mat.emissiveIntensity = 2.4;
      ctx.flame.k = 1.3; ctx.flame.red = 0.3;
      if (lt < 5.8) {
        ctx.camera.position.set(lerp(0.9, 1.4, lt / 5.8), lerp(1.4, 1.8, lt / 5.8), z + lerp(3.4, 3.0, lt / 5.8));
        ctx.camera.lookAt(0, 2.0, z - 10);
        ctx.camera.fov = 48;
      } else {
        cam(ctx.camera, lt, [[5.8, [2.6, 5.2, -69.5]], [10, [1.6, 5.8, -71.6]]], [[5.8, [0, 5.4, -76]], [10, [0, 6.2, -76]]], 40);
      }
      ctx.fill.position.set(0, 3, z + 1.2); ctx.fill.intensity = 2.5;
    },
  },
  // 18: el Rey Esqueleto se levanta del trono y alza el baculo
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      const stand = seg(lt, 3.6, 6.2);
      const raise = seg(lt, 6.6, 8.0);
      kingPose(S, 1 - stand, lt, { headX: -0.1 * stand, armR: lerp(-1.2, -2.8, raise) });
      S.king.mat.emissiveIntensity = 2.5 * seg(lt, 5.8, 6.6);
      S.kingLight.intensity = 10 + 40 * seg(lt, 5.8, 6.6) + 40 * raise * (0.8 + 0.2 * noise1(ctx.t * 8));
      S.gem.material.emissiveIntensity = 1.5 + 3 * raise;
      S.crownFire.set(ctx.t, { wave: -99, flare: 1 + 0.6 * stand, bright: 1.1 + 0.8 * stand });
      const z = lerp(-61, -68.5, seg(lt, 0, 3.6));
      const st = (c) => clamp(c >= -62 ? 0 : -62 - c, 0, 3);
      const zc = Math.floor(z), zf = z - zc;
      const y = lerp(st(zc), st(zc + 1), ease((zf - 0.35) / 0.3));
      const R = standRider(ctx, 0, y, z, Math.PI);
      if (lt < 3.6) R.walk(z * 1.2, 1);
      R.wind(ctx.t, 0.1);
      const kz = z + 1.0;
      const zc2 = Math.floor(kz), zf2 = kz - zc2;
      const K = standKid(ctx, 0.5, lerp(st(zc2), st(zc2 + 1), ease((zf2 - 0.35) / 0.3)), kz, Math.PI);
      if (lt < 3.6) K.walk(kz * 2.2, 1);
      K.setEyes(lt > 5);
      armyIdle(S, ctx, { fig: V(0, 3, z), look: 1, aim: 1, extra: (i, it) => (it.guard ? null : { y: -50 }) });
      S.army.mat.emissiveIntensity = 2.2;
      ctx.flame.k = 1.3; ctx.flame.red = 0.4;
      if (lt < 3.8) cam(ctx.camera, lt, [[0, [1.6, 3, -56.5]], [3.8, [1.2, 4.4, -62.5]]], [[0, [0, 9, -92]], [3.8, [0, 10, -94]]], 44);
      else cam(ctx.camera, lt, [[3.8, [4.2, 6.0, -85.5]], [10, [3.2, 6.6, -87.5]]], [[3.8, [0, 11, -95.5]], [10, [0, 14.2, -95]]], 42, { shake: raise > 0.9 ? 0.02 : 0 });
      ctx.fill.position.set(0, y + 3, z + 1.3); ctx.fill.intensity = 2.5;
    },
  },
  // 19: "Ninguno saldra de aqui": carga; flechas en camara lenta; la espada se enciende y gira
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 0, lt, { armR: -2.8 + 0.4 * Math.sin(lt * 2), headX: -0.15 - 0.15 * pulse(lt, 0.9, 0.9) });
      S.king.mat.emissiveIntensity = 2.5;
      S.kingLight.intensity = 50;
      S.gem.material.emissiveIntensity = 4;
      const p0 = V(0, 3, -69.5);
      const R = standRider(ctx, p0.x, p0.y, p0.z, Math.PI);
      const draw = seg(lt, 2.6, 3.4);
      const ignite = seg(lt, 3.3, 3.9);
      const spin = seg(lt, 4.4, 4.8) * (1 - seg(lt, 8.6, 9.2));
      R.sword.visible = draw > 0.3;
      R.sheath.children[2].visible = draw <= 0.3;
      R.swordFire.mesh.visible = ignite > 0.01;
      R.swordFire.set(ctx.t, { flare: ignite, bright: 1.3 * ignite });
      R.blade.material.emissiveIntensity = 1.6 * ignite;
      R.armR.rotation.set(-1.4 - 1.2 * draw * (1 - spin) + 0.0 * spin, 0, -0.3 * draw + 1.2 * spin);
      R.sword.rotation.set(Math.PI / 2 - 0.8 * draw * (1 - spin), 0, 0);
      const spinA = spin > 0 ? (lt - 4.4) * 9 * spin : 0;
      R.root.rotation.y = Math.PI + spinA;
      R.legL.rotation.x = 0.3 * spin; R.legR.rotation.x = -0.3 * spin;
      R.wind(ctx.t, 0.3 + 0.6 * spin);
      ctx.flame.k = 1.5 + 0.3 * ignite; ctx.flame.red = 0.6;
      const K = standKid(ctx, -1.1, 3, -67.4, yawTo(1.1, -2));
      K.torso.rotation.x = 0.5; K.body.position.y = 0.55; K.setEyes(true);
      K.arms.rotation.x = -1.2;
      const fx = ensureFx(S);
      const charge = seg(lt, 1.6, 5.2);
      battleArmy(S, ctx, { charge, target: p0, aim: seg(lt, 1.8, 2.6) });
      const slow = lt > 3.0 ? 0.32 : 1;
      const hits = arrows(fx, lt, p0, 2.4, slow, spin > 0.5 ? 1.9 : 0);
      // anillo de fuego giratorio
      const rl = [];
      if (spin > 0.05) for (let i = 0; i < 28; i++) {
        const a = (i / 28) * Math.PI * 2 + spinA;
        rl.push({ x: p0.x + Math.cos(a) * 1.7, y: p0.y + 1.05 + Math.sin(a * 3 + ctx.t * 4) * 0.08, z: p0.z + Math.sin(a) * 1.7, w: 0.55, h: 0.75 * spin, b: spin * (0.6 + 0.4 * ((i % 3) / 2)) });
      }
      fx.ringFire.update(rl);
      fx.ringFire.set(ctx.t, {});
      fx.ringFire.mesh.visible = spin > 0.05;
      fx.spinRing.visible = spin > 0.1;
      fx.spinRing.position.set(p0.x, p0.y + 1.3, p0.z);
      fx.spinRing.rotation.set(-Math.PI / 2, 0, spinA);
      fx.spinRing.scale.setScalar(3.6);
      fx.spinRing.userData.u.uOpacity.value = 0.5 * spin;
      fx.clashB.points.visible = hits.length > 0;
      if (hits.length) fx.clashB.set(((lt * 4) % 1) * 0.8 + 0.01, { center: [hits[0].x, hits[0].y, hits[0].z] });
      R.updateSparks(ctx.t, ignite > 0.5);
      ctx.grade.uTint.value.setRGB(0.95, 1, 1.08);
      if (lt < 2.4) cam(ctx.camera, lt, [[0, [5, 9.5, -82]], [2.4, [4.2, 10.5, -84]]], [[0, [0, 14.5, -95]], [2.4, [0, 15, -95]]], 44, { shake: lt < 1.6 ? 0.04 : 0 });
      else if (lt < 4.4) cam(ctx.camera, lt, [[2.4, [1.6, 4.4, -66.6]], [4.4, [1.3, 4.6, -67.0]]], [[2.4, [0, 4.6, -69.5]], [4.4, [0, 4.8, -69.5]]], 40);
      else cam(ctx.camera, lt, [[4.4, [-6.5, 4.6, -63.5]], [10, [-8.0, 5.6, -66]]], [[4.4, [0, 4.2, -69.5]], [10, [0, 3.9, -69.5]]], 44);
      ctx.fill.position.set(p0.x + 1, p0.y + 3, p0.z + 1.5); ctx.fill.intensity = 3;
    },
  },
  // 20: la espada llameante parte esqueletos; chispas naranjas y azules; camara envolvente
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 0, lt, { armR: -2.8, headX: -0.1 });
      S.king.mat.emissiveIntensity = 2.5;
      S.kingLight.intensity = 45;
      const gpath = [[0, [0, 3, -69.5]], [2.5, [-6, 3.3, -67]], [5, [-2, 3.3, -64.5]], [7.5, [5.5, 3.3, -68]], [10, [3, 3, -72.5]]];
      const gp = path(gpath, lt), ahead = path(gpath, lt + 0.1);
      const R = standRider(ctx, gp.x, gp.y, gp.z, yawTo(ahead.x - gp.x, ahead.z - gp.z));
      R.walk(lt * 4.5, 1.2);
      R.sword.visible = true;
      R.sheath.children[2].visible = false;
      R.swordFire.mesh.visible = true;
      R.swordFire.set(ctx.t, { flare: 1.1, bright: 1.4 });
      R.blade.material.emissiveIntensity = 1.6;
      const sw = Math.sin(lt * 6.5);
      R.armR.rotation.set(-1.6 + sw * 0.9, 0, -0.2 + Math.cos(lt * 6.5) * 0.8);
      R.torso.rotation.y = sw * 0.45;
      R.wind(ctx.t, 0.7);
      R.updateSparks(ctx.t, true);
      ctx.flame.k = 1.6; ctx.flame.red = 0.5;
      const fx = ensureFx(S);
      const hitsAt = [];
      battleArmy(S, ctx, {
        charge: 1, target: V(0, 3, -69.5), aim: 0.2,
        collapse: (i, pos) => {
          let best = 99;
          for (let s = 0; s <= lt; s += 0.1) {
            const q = path(gpath, s);
            if (Math.hypot(q.x - pos.x, q.z - pos.z) < 2.4) { best = s; break; }
          }
          if (best < 50 && lt - best < 0.5) hitsAt.push(pos);
          return best > 50 ? 0 : clamp((lt - best) / 1.0);
        },
      });
      fx.clashA.points.visible = hitsAt.length > 0;
      fx.clashB.points.visible = hitsAt.length > 0;
      if (hitsAt.length) {
        const h = hitsAt[0];
        const ph = ((lt * 2.2) % 1) * 0.9 + 0.02;
        fx.clashA.set(ph, { center: [h.x, 4.2, h.z] });
        fx.clashB.set(ph * 0.9, { center: [h.x + 0.3, 4.0, h.z - 0.2] });
      }
      const a = lerp(0.5, 2.6, easeIO(lt / 10));
      ctx.camera.position.set(gp.x + Math.sin(a) * 6.2, lerp(6.5, 7.8, Math.sin(lt / 10 * Math.PI)), gp.z + Math.cos(a) * 6.2);
      ctx.camera.lookAt(gp.x, 4.0, gp.z);
      ctx.camera.fov = 50;
      ctx.fill.position.set(gp.x + 1, gp.y + 3, gp.z + 1.5); ctx.fill.intensity = 3;
    },
  },
  // 21: golpe del baculo; la onda azul derriba al Jinete; la calabaza se agrieta; el nino corre al altar
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      const slam = seg(lt, 1.6, 2.1);
      const kb = [0, 3, -86];
      kingPose(S, 0, lt, { base: kb, armR: lerp(-2.9, -0.6, slam), torsoX: 0.3 * slam, headX: 0.2 * slam });
      S.king.mat.emissiveIntensity = 2.5;
      S.kingLight.position.set(0, 9, -84);
      S.kingLight.intensity = 40 + 120 * pulse(lt, 2.1, 0.5);
      S.gem.material.emissiveIntensity = 4;
      battleArmy(S, ctx, { charge: 1, target: V(0, 3, -69.5), aim: 0.2, collapseAll: true });
      const fx = ensureFx(S);
      const wr = clamp((lt - 2.05) / 1.4);
      fx.ground.visible = lt > 2.05 && lt < 3.6;
      fx.ground.position.set(0, 3.15, -84);
      fx.ground.rotation.set(-Math.PI / 2, 0, 0);
      fx.ground.scale.setScalar(1 + wr * 40);
      fx.ground.userData.u.uColor.value.set(0x3ab0ff);
      fx.ground.userData.u.uOpacity.value = 1 - wr;
      fx.burst.points.visible = lt > 2 && lt < 6;
      fx.burst.set(lt - 2.05, { center: [0, 3.5, -84], colA: 0x5ac8ff });
      const hit = clamp((lt - 2.35) / 0.5);
      const start = V(1.5, 3, -74), end = V(-6.45, 3, -69.0);
      const gp = start.clone().lerp(end, 1 - Math.pow(1 - hit, 3));
      gp.y += Math.sin(Math.PI * hit) * 1.4;
      const R = standRider(ctx, gp.x, gp.y, gp.z, lt < 2.35 ? yawTo(-1.5, -12) : yawTo(6.4, -5));
      R.sword.visible = lt < 2.5;
      R.sheath.children[2].visible = false;
      R.swordFire.mesh.visible = lt < 2.5;
      R.swordFire.set(ctx.t, { flare: 1, bright: 1.2 });
      R.blade.material.emissiveIntensity = lt < 2.5 ? 1.5 : 0;
      R.armR.rotation.set(-1.8, 0, 0.2);
      if (lt > 2.7) R.setFace('cracked');
      const down = seg(lt, 2.8, 3.2);
      R.hips.position.y = 0.95 - 0.55 * down;
      R.legL.rotation.x = -1.4 * down; R.legR.rotation.x = -1.2 * down;
      R.torso.rotation.x = -0.35 * hit * (1 - down) + 0.45 * down;
      R.head.rotation.x = 0.35 * down;
      R.armR.rotation.z = -0.4 * down; R.armL.rotation.z = 0.4 * down;
      R.armL.rotation.x = -0.6 * down;
      R.wind(ctx.t, 0.2);
      ctx.flame.k = lt < 2.6 ? 1.5 : lerp(1.5, 0.3, seg(lt, 2.6, 3.4)) * (0.8 + 0.2 * noise1(ctx.t * 12));
      ctx.flame.red = 0.3;
      // el nino corre hacia el altar
      const run = seg(lt, 5.6, 9.2);
      const kp = V(-5.2, 3, -67.6).lerp(V(-0.8, 3, -71.6), run);
      const K = standKid(ctx, kp.x, kp.y, kp.z, run > 0 ? yawTo(4.4, -4) : yawTo(-1.3, -1.4));
      K.walk(lt * 3.2, run > 0 && run < 1 ? 1.5 : 0);
      K.setEyes(true);
      if (lt < 4) cam(ctx.camera, lt, [[0, [12, 6, -72]], [4, [10, 5.5, -70]]], [[0, [-1, 4.5, -80]], [4, [-3, 4, -76]]], 50, { shake: lt > 2 && lt < 3 ? 0.18 : 0 });
      else if (lt < 6.2) cam(ctx.camera, lt, [[4, [-7.4, 5.0, -64.2]], [6.2, [-7.6, 5.3, -64.6]]], [[4, [-6.2, 3.8, -69.2]], [6.2, [-6.2, 3.9, -69.2]]], 44);
      else cam(ctx.camera, lt, [[6.2, [-6.5, 4.4, -64]], [10, [-4.5, 4.6, -64.5]]], [[6.2, [-3, 3.6, -70]], [10, [0, 4.2, -74]]], 46);
      ctx.grade.uFlash.value = 0.5 * pulse(lt, 2.1, 0.25);
      ctx.grade.uFlashCol.value.set(0x9adfff);
      ctx.fill.position.set(-6.4, 5.5, -67.5); ctx.fill.intensity = 2;
    },
  },
  // 22: el nino salta el anillo de fuego, toma el cristal y se lo lanza; la llama dorada vuela en camara lenta
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 0, lt, { base: [0, 3, -86], armR: -0.8, torsoX: 0.1 });
      S.king.mat.emissiveIntensity = 2.5;
      S.kingLight.position.set(0, 9, -84);
      S.kingLight.intensity = 40;
      battleArmy(S, ctx, { charge: 1, target: V(0, 3, -69.5), aim: 0.2, collapseAll: true });
      // el Jinete, caido
      const R = standRider(ctx, -6.45, 3, -69.0, yawTo(6.4, -5));
      R.setFace('cracked');
      R.hips.position.y = 0.4;
      R.legL.rotation.x = -1.4; R.legR.rotation.x = -1.2;
      R.torso.rotation.x = 0.45 - 0.35 * seg(lt, 6.5, 8.5);
      R.head.rotation.x = 0.35 - 0.5 * seg(lt, 6, 8);
      const reach = seg(lt, 7.2, 8.6);
      R.armR.rotation.set(-0.3 - 1.3 * reach, 0, -0.4);
      R.armL.rotation.set(-0.6 - 1.1 * reach, 0, 0.4);
      R.sheath.children[2].visible = false;
      ctx.flame.k = 0.3 * (0.8 + 0.2 * noise1(ctx.t * 12)) + 0.25 * seg(lt, 7, 9.5);
      // nino: salto, cristal, lanzamiento
      const jump = clamp((lt - 0.3) / 1.2);
      const a = V(-0.8, 3, -71.6), b = V(0, 3, -75.2);
      const kp = a.clone().lerp(b, easeIO(jump));
      kp.y += Math.sin(Math.PI * jump) * 1.6;
      const K = standKid(ctx, kp.x, kp.y, kp.z, jump < 1 ? yawTo(b.x - a.x, b.z - a.z) : lerp(Math.PI, yawTo(-6.45, 6.2), seg(lt, 3.4, 4.2)));
      K.lantern.visible = false;
      K.light.intensity = 0;
      if (jump < 1) { K.legL.rotation.x = -0.8 * Math.sin(Math.PI * jump); K.legR.rotation.x = 0.5 * Math.sin(Math.PI * jump); }
      const grab = seg(lt, 2.0, 2.8);
      const throwK = seg(lt, 4.3, 4.7);
      K.arms.rotation.x = -1.8 * grab * (1 - throwK) - 2.4 * throwK * (1 - seg(lt, 5.2, 6));
      K.torso.rotation.x = -0.3 * grab * (1 - throwK) + 0.4 * throwK * (1 - seg(lt, 5.2, 6));
      const fx = ensureFx(S);
      const hand = V(0, 4.0, -75.0);
      const orbStart = V(0, 6.3, -76);
      const target = V(-6.2, 5.0, -68.9);
      let op;
      if (lt < 4.5) op = orbStart.clone().lerp(hand, seg(lt, 1.8, 2.8));
      else {
        const f = clamp((lt - 4.5) / 5.2);
        op = hand.clone().lerp(target, f);
        op.y += Math.sin(Math.PI * f) * 2.6;
      }
      S.orb.position.copy(op);
      S.orb.rotation.set(lt, lt * 1.6, 0);
      S.orbLight.position.copy(op);
      S.orbLight.intensity = 4;
      S.orbSwirl.set(ctx.t, { center: [op.x, op.y, op.z] });
      // el cristal se rompe al lanzarlo; vuela solo la llama
      const free = lt > 4.6;
      S.orb.children[1].visible = !free; S.orb.children[2].visible = !free; S.orb.children[0].visible = !free;
      S.eternal.mesh.visible = !free;
      fx.flameBall.mesh.visible = free;
      fx.flameBall.mesh.position.copy(op).add(V(0, 0.2, 0));
      fx.flameBall.set(ctx.t, { gold: 1, bright: 0.6, flare: 1 });
      fx.flameTrail.points.visible = free;
      fx.flameTrail.set(ctx.t, { center: [op.x, op.y, op.z] });
      fx.goldBurst.points.visible = lt > 4.5 && lt < 7;
      fx.goldBurst.set((lt - 4.55) * 0.5, { center: [hand.x, hand.y + 0.3, hand.z], speed: 4 });
      S.ringFire.set(ctx.t, { wave: -99, bright: 0.4, flare: 1 + 0.4 * pulse(lt, 0.9, 0.5) });
      if (lt < 4.3) cam(ctx.camera, lt, [[0, [-3.2, 4.6, -66.5]], [4.3, [2.8, 5.0, -70.5]]], [[0, [-0.5, 3.8, -73]], [4.3, [0, 4.6, -75.2]]], 44);
      else cam(ctx.camera, lt, [[4.3, [1.8, 4.6, -70.5]], [7, [-1.5, 6.6, -69.0]], [10, [-4.2, 6.2, -66.6]]], [[4.3, [0, 4.4, -75]], [7, [-3.2, 6.0, -71.5]], [10, [-6.2, 4.8, -68.9]]], 46);
      ctx.fill.position.set(op.x, op.y, op.z); ctx.fill.color.set(0xffc860); ctx.fill.intensity = 0;
      ctx.key.position.set(-5.5, 5.5, -67); ctx.key.intensity = 1.5; ctx.key.color.set(0xffd090);
    },
  },
  // 23: CLIMAX: la llama se funde con la calabaza; fuego dorado; la ola convierte el fuego azul en naranja
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      const wave = (lt - 2.2) * 0.42;
      caveBase(S, ctx, wave);
      S.orb.visible = false;
      S.orbSwirl.points.visible = false;
      S.orbLight.intensity = 0;
      const fx = ensureFx(S);
      // atrapa la llama
      const catchK = seg(lt, 0, 0.8);
      const merge = seg(lt, 0.8, 2.0);
      const rise = seg(lt, 1.4, 3.0);
      const p = V(-6.45, 3, -69.0);
      const R = standRider(ctx, p.x, p.y, p.z, yawTo(6.4, -5));
      R.setFace(lt < 1.7 ? 'cracked' : 'angry');
      R.hips.position.y = lerp(0.4, 0.95, rise);
      R.legL.rotation.x = -1.4 * (1 - rise); R.legR.rotation.x = -1.2 * (1 - rise);
      R.torso.rotation.x = 0.1 * (1 - rise) - 0.25 * pulse(lt, 2.3, 0.8);
      R.head.rotation.x = -0.15 - 0.3 * pulse(lt, 2.3, 0.8);
      R.armR.rotation.set(-1.6 * (1 - merge) - 0.3, 0, -0.4 - 1.0 * pulse(lt, 2.3, 1));
      R.armL.rotation.set(-1.7 * (1 - merge) - 0.3, 0, 0.4 + 1.0 * pulse(lt, 2.3, 1));
      R.wind(ctx.t, 0.3 + 0.7 * pulse(lt, 2.3, 1.2));
      R.sheath.children[2].visible = false;
      R.root.updateMatrixWorld(true);
      const head = V(); R.head.getWorldPosition(head);
      const hand = V(-6.2, 5.0, -68.9);
      fx.flameBall.mesh.visible = merge < 1;
      fx.flameBall.mesh.position.copy(hand.clone().lerp(head, merge)).add(V(0, 0.2, 0));
      fx.flameBall.mesh.scale.setScalar(1 - 0.7 * merge);
      fx.flameBall.set(ctx.t, { gold: 1, bright: 0.9 });
      const gold = seg(lt, 1.6, 2.2);
      ctx.flame.k = lerp(0.45, 1.1, gold) - 0.2 * seg(lt, 4, 8); ctx.flame.gold = gold; ctx.flame.flare = 1 + 0.8 * gold;
      fx.goldBurst.points.visible = lt > 2.0;
      fx.goldBurst.set(lt - 2.1, { center: [head.x, head.y, head.z], speed: 11 });
      // onda dorada
      const wr = clamp((lt - 2.2) / 2.4);
      fx.shock.visible = lt > 2.2 && lt < 4.6;
      fx.shock.position.set(p.x, 3.6, p.z);
      fx.shock.rotation.set(-Math.PI / 2, 0, 0);
      fx.shock.scale.setScalar(1 + wr * 80);
      fx.shock.userData.u.uColor.value.set(0xffc850);
      fx.shock.userData.u.uOpacity.value = 1 - wr;
      fx.shock2.visible = lt > 2.2 && lt < 3.8;
      fx.shock2.position.copy(head);
      fx.shock2.lookAt(ctx.camera.position);
      fx.shock2.scale.setScalar(0.5 + clamp((lt - 2.2) / 1.6) * 14);
      fx.shock2.userData.u.uColor.value.set(0xffe090);
      fx.shock2.userData.u.uOpacity.value = 0.45 * (1 - clamp((lt - 2.2) / 1.6));
      // luces y fuego cambian con la ola
      S.ringFire.set(ctx.t, { wave: wave > 0.05 ? 99 : -99, flare: 1, bright: 0.4 });
      const orange = new THREE.Color(0xff7a2a), blue = new THREE.Color(0x3a9cff);
      for (const l of S.lights) {
        const d = Math.hypot(l.position.x, l.position.z + 76) / 70;
        const m = clamp((wave - d) / 0.35);
        l.color.copy(blue).lerp(orange, m);
        l.intensity *= 1 + 0.4 * m;
      }
      S.hemi.color.set(0x1a3a6a).lerp(new THREE.Color(0x6a3a1a), clamp(wave));
      S.embers.set(ctx.t, { mix: clamp(wave) });
      S.pitEmbers.set(ctx.t, { mix: clamp(wave * 0.9) });
      for (const l of S.lanterns) {
        const d = Math.hypot(l.position.x, l.position.z + 76) / 70;
        const m = clamp((wave - d) / 0.35);
        l.userData.glow.emissive.setRGB(lerp(0.35, 1.0, m), lerp(0.8, 0.55, m), lerp(1.0, 0.2, m));
      }
      S.scene.fog.color.set(0x040814).lerp(new THREE.Color(0x1a0a04), clamp(wave));
      S.army.mat.emissiveIntensity = 2.2 * (1 - clamp(wave * 2));
      battleArmy(S, ctx, { charge: 1, target: V(0, 3, -69.5), aim: 0.2, collapseAll: true, waveCollapse: wave });
      const kc = seg(lt, 4.2, 6.4);
      kingPose(S, 0, lt, { base: [0, 3, -86], armR: lerp(-0.8, 0.4, kc), torsoX: 1.2 * kc, headX: 0.6 * kc, dy: -2.2 * kc * kc });
      S.king.root.rotation.z = 0.4 * kc;
      S.king.mat.emissiveIntensity = 2.5 * (1 - kc);
      S.kingLight.position.set(0, 9, -84);
      S.kingLight.intensity = 40 * (1 - kc);
      S.crown.visible = lt < 4.2;
      fx.crownBurst.points.visible = lt > 4.1 && lt < 8;
      fx.crownBurst.set(lt - 4.2, { center: [0, 12.5, -86] });
      fx.bigBurst.points.visible = lt > 2.3;
      fx.bigBurst.set(lt - 2.3, { center: [-3, 3, -72], colA: 0xffb040 });
      // el nino junto al altar, protegiendose
      const K = standKid(ctx, 0, 3, -75.2, yawTo(-6.45, 6.2));
      K.lantern.visible = false; K.light.intensity = 0;
      K.arms.rotation.x = -1.3 * pulse(lt, 2.6, 1.4);
      ctx.grade.uFlash.value = 0.35 * pulse(lt, 2.25, 0.4);
      ctx.grade.uFlashCol.value.set(0xffe2a0);
      ctx.bloom.strength = 0.6 + 0.2 * pulse(lt, 2.4, 1);
      if (lt < 3.6) {
        cam(ctx.camera, lt, [[0, [head.x + 3.0, head.y - 0.3, head.z - 1.0]], [3.6, [head.x + 2.5, head.y - 0.1, head.z - 1.0]]], [[0, [head.x, head.y + 0.1, head.z]], [3.6, [head.x, head.y + 0.1, head.z]]], 40, { shake: lt > 2.1 && lt < 3.2 ? 0.05 : 0 });
        ctx.key.position.set(head.x + 1.5, head.y + 0.6, head.z - 0.6); ctx.key.intensity = 1.5; ctx.key.color.set(0xffe0c0);
      } else cam(ctx.camera, lt, [[3.6, [10, 9, -58]], [10, [14, 14, -48]]], [[3.6, [0, 5, -78]], [10, [0, 3, -70]]], 52);
      ctx.fill.position.set(head.x, head.y + 1, head.z + 1); ctx.fill.color.set(0xffc060); ctx.fill.intensity = 0.8 * gold;
    },
  },
  // 24: salen de la cueva al amanecer; el caballo los espera con ojos calmados
  {
    set: 'mountain',
    update(lt, ctx) {
      const S = ctx.set;
      mountainNight(S, ctx);
      mountainDawn(S, ctx);
      const z = lerp(-11, 1.5, seg(lt, 0, 7.5));
      const R = standRider(ctx, 0.3, 0, z, 0);
      if (lt < 7.5) R.walk(z * 1.2, 1);
      R.wind(ctx.t, 0.15);
      ctx.flame.k = 1.0; ctx.flame.gold = 0.6;
      const K = standKid(ctx, 1.3, 0, z + 0.3, 0);
      if (lt < 7.5) K.walk(z * 2.2, 1);
      K.head.rotation.x = -0.2;
      const H = showHorse(ctx, 1.0, 0, 5.2, Math.PI);
      H.walk(ctx.t * 2, lt > 6 ? 0.4 : 0);
      H.neck.rotation.x = 0.7 - 0.25 * seg(lt, 5, 7);
      H.eyeM.emissive.setRGB(1, 0.55, 0.2);
      H.eyeM.emissiveIntensity = 1.6;
      H.hoofFire(ctx.t, 0.35);
      ctx.flame.noHoof = true;
      cam(ctx.camera, lt, [[0, [7, 2.4, 20]], [10, [4.2, 1.8, 9.5]]], [[0, [0, 6, -12]], [10, [0.8, 2.0, 1.5]]], 46, { span: [0, 10] });
      ctx.focus = V(0, 0, 0);
    },
  },
  // 25: amanecer en el pueblo; las calabazas se reencienden en ola; el Jinete baja al nino
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageDawn(S, lt, ctx);
      mount(ctx);
      const keys = [[0, [0, 0, -62]], [5.5, [0, 0, -12]], [6.5, [0, 0, -9.5]], [10, [0, 0, -9.5]]];
      const { p, speed } = ride(ctx, keys, lt, { yaw0: 0 });
      ctx.horse.root.rotation.y = 0;
      if (speed > 0.5) ctx.horse.gallop(ctx.t * 8, Math.min(1, speed / 6)); else ctx.horse.walk(0, 0);
      ctx.horse.eyeM.emissive.setRGB(1, 0.55, 0.2); ctx.horse.eyeM.emissiveIntensity = 1.6;
      hoofTrail(S.trail, keys, lt, { span: 2.5, b: 0.7 });
      const R = ctx.rider;
      R.wind(ctx.t, Math.min(1, speed / 6));
      ctx.flame.k = 1.0; ctx.flame.gold = 0.5;
      // la ola de calabazas que se reencienden a su paso
      lanternState(S, (j) => (j.door ? 1 : clamp((p.z - j.z + 4) / 3)));
      S.bonfire.set(ctx.t, { flare: 0.4 + 0.9 * seg(lt, 4, 6), bright: 1.2 });
      S.bonLight.intensity = 90 * (0.4 + 0.8 * seg(lt, 4, 6));
      cheer(S, ctx.t, lt - 3);
      // lo baja con cuidado
      const down = seg(lt, 6.6, 9.0);
      const K = ctx.kid;
      if (down <= 0) mountKid(ctx);
      else {
        ctx.horse.root.updateMatrixWorld(true);
        const seat = V(0, -0.4, -0.55); ctx.horse.saddle.localToWorld(seat);
        const ground = V(1.9, 0, -9.2);
        const kp = seat.clone().lerp(ground, down);
        kp.y += Math.sin(Math.PI * down) * 0.4;
        standKid(ctx, kp.x, kp.y, kp.z, lerp(0, -Math.PI / 2 + 0.4, down));
        if (down < 0.8) K.sit();
        K.arms.rotation.x = -0.5;
        R.armL.rotation.set(-0.7 - 0.6 * Math.sin(Math.PI * down), 0, 0.8 * Math.sin(Math.PI * down));
        R.head.rotation.y = 0.8 * down;
        R.head.rotation.x = 0.3 * down;
      }
      if (lt < 6) cam(ctx.camera, lt, [[0, [-5, 4.5, -40]], [6, [-4.5, 3, -2]]], [[0, [0, 2.2, -60]], [6, [0, 2.2, -12]]], 46);
      else cam(ctx.camera, lt, [[6, [3.3, 2.4, -4.4]], [10, [3.0, 2.1, -5.0]]], [[6, [0.6, 2.2, -9.6]], [10, [1.4, 1.3, -9.2]]], 44);
      ctx.focus = V(0, 0, -10);
    },
  },
  // 26: bajo el viejo roble; la calabaza sonrie; se deshacen en brasas doradas; queda una calabaza
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageDawn(S, lt, ctx);
      lanternState(S, 'on');
      graveState(S, ctx, { lid: 1, fire: 0, jack: seg(lt, 6.4, 7.6) });
      mount(ctx);
      const H = showHorse(ctx, -8, 0, -77.6, yawTo(1.5, 2.5));
      H.walk(0, 0);
      H.eyeM.emissive.setRGB(1, 0.55, 0.2); H.eyeM.emissiveIntensity = 1.6;
      const R = ctx.rider;
      const look = seg(lt, 0.4, 1.6);
      R.head.rotation.y = 0.75 * look;
      R.head.rotation.x = 0.28 * look;
      if (lt > 2.4) R.setFace('smile');
      R.wind(ctx.t, 0.15);
      const dis = seg(lt, 4.2, 7.0);
      ctx.flame.k = 0.65 * (1 - dis); ctx.flame.gold = 0.5;
      ctx.flame.hoof = 0.4 * (1 - dis);
      // se deshacen: fundido de materiales + brasas doradas
      const fade = (m) => { m.transparent = dis > 0; m.opacity = 1 - dis; };
      for (const m of Object.values(R.mats)) fade(m);
      for (const m of H.mats) fade(m);
      R.root.visible = dis < 0.99;
      H.root.visible = dis < 0.99;
      const fx = ensureFx(S);
      fx.dissolve.points.visible = lt > 4.0 && lt < 9.8;
      fx.dissolve.set(ctx.t, { center: [-8, 2.0 + (lt - 4) * 0.6, -77.6], opacity: clamp((lt - 4) * 1.5) * (1 - seg(lt, 7.5, 9.6)) });
      const K = standKid(ctx, -6.3, 0, -75.0, yawTo(-1.7, -2.6));
      K.head.rotation.x = -0.35 - 0.3 * seg(lt, 4.5, 7);
      K.arms.rotation.x = lt > 7.4 ? -0.6 + Math.sin(lt * 7) * 0.25 : -0.3;
      if (lt < 4.2) {
        const head = V(); R.root.updateMatrixWorld(true); R.head.getWorldPosition(head);
        cam(ctx.camera, lt, [[0, [-5.0, 2.4, -73.4]], [4.2, [-5.6, 2.6, -74.4]]], [[0, [head.x, head.y - 0.2, head.z]], [4.2, [head.x, head.y, head.z]]], 38);
        ctx.key.position.set(-5.2, 3.2, -73.8); ctx.key.color.set(0xffe8d8); ctx.key.intensity = 10; ctx.key.distance = 10;
      } else cam(ctx.camera, lt, [[4.2, [-1.5, 2.2, -68]], [10, [-2.5, 4.5, -66]]], [[4.2, [-8, 3, -79]], [7, [-9, 7, -86]], [10, [-8.5, 1.2, -83]]], 44);
      ctx.grade.uFade.value = seg(lt, 8.0, 9.6);
      ctx.focus = V(-8, 0, -78);
    },
  },
];

// envoltura comun: fuego de la cara, cascos y brasas tras cada escena
export const SCENES = SC.map((sc) => ({
  set: sc.set,
  shadow: sc.shadow,
  update(lt, ctx) {
    ctx.flame = { k: 1, red: 0.4, soft: 0, gold: 0, flare: 1 };
    sc.update(lt, ctx);
    const R = ctx.rider, H = ctx.horse, f = ctx.flame;
    R.flame(ctx.t, f);
    R.updateFx(ctx.t, R.root.visible && R.pumpkin.visible ? f.k : 0, f.gold);
    if (!f.noHoof) H.hoofFire(ctx.t, f.hoof ?? 1);
  },
}));
