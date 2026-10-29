// Guion: 26 escenas de 10 s. Todo es funcion pura del tiempo local lt (render en paralelo seguro).
import * as THREE from 'three';
import { glowMats } from './voxel.js';

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

function catmull(p0, p1, p2, p3, t) {
  const t2 = t * t, t3 = t2 * t;
  return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
}
function path(keys, lt) {
  // keys: [[t, [x,y,z]], ...]
  if (lt <= keys[0][0]) return V(...keys[0][1]);
  const n = keys.length;
  if (lt >= keys[n - 1][0]) return V(...keys[n - 1][1]);
  let i = 0;
  while (i < n - 2 && lt > keys[i + 1][0]) i++;
  const s = (lt - keys[i][0]) / (keys[i + 1][0] - keys[i][0]);
  const P = (k) => keys[clamp(k, 0, n - 1)][1];
  const out = [0, 1, 2].map((a) => catmull(P(i - 1)[a], P(i)[a], P(i + 1)[a], P(i + 2)[a], s));
  return V(...out);
}
// camara: pos/look son listas de keyframes; easeAll suaviza el tiempo global
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
  c.fov = typeof fov === 'number' ? fov : fov(lt);
}
function noise1(t, seed = 0) {
  return Math.sin(t * 1.7 + seed) * 0.5 + Math.sin(t * 3.1 + seed * 2.3) * 0.3 + Math.sin(t * 7.3 + seed * 5.1) * 0.2;
}

function place(a, x, y, z, yaw = 0) {
  a.root.position.set(x, y, z);
  a.root.rotation.set(0, yaw, 0);
}

// ---------------------------------------------------------------------------
// estados compartidos por escenario
// ---------------------------------------------------------------------------
function villageNight(S, lt, ctx) {
  const u = S.sky.userData.u;
  u.uTop.value.set(0x05061a); u.uHor.value.set(0x2a1a48); u.uBot.value.set(0x05040a);
  u.uSunDir.value.copy(S.moonDir); u.uSunCol.value.set(0xff8a30); u.uGlow.value = 0.55; u.uStars.value = 1;
  S.moon.visible = true;
  S.scene.fog.color.set(0x2a2045); S.scene.fog.density = 0.014;
  S.L.dir.color.set(0x9aaeff); S.L.dir.intensity = 1.3; S.L.dir.userData.vec = S.moonDir.clone();
  S.L.hemi.color.set(0x3a4280); S.L.hemi.groundColor.set(0x141010); S.L.hemi.intensity = 0.9;
  S.clouds.position.x = ctx.t * 0.6;
  S.clouds.material.color.set(0x3a3a55);
  S.fogEdge.userData.update(ctx.t); S.fogVillage.userData.update(ctx.t);
  S.bats.userData.update(ctx.t, [0, 0, -20]);
  S.bats.visible = true;
  S.leaves.set(ctx.t);
  S.sparks.set(ctx.t);
  S.bonfire.set(ctx.t, { flare: 1, bright: 1.1 });
  S.bonLight.intensity = 70 * (0.85 + 0.15 * noise1(ctx.t * 3));
  for (const j of S.jacks) j.mesh.userData.setOn(1);
  for (const l of S.roadLights) l.intensity = 22;
  for (const v of S.villagers) v.root.visible = false;
}

function villageDawn(S, lt, ctx) {
  villageNight(S, lt, ctx);
  const u = S.sky.userData.u;
  const sun = V(0.25, 0.1, -1).normalize();
  u.uTop.value.set(0x2a3570); u.uHor.value.set(0xff9a6a); u.uBot.value.set(0x2a1a2a);
  u.uSunDir.value.copy(sun); u.uSunCol.value.set(0xffb070); u.uGlow.value = 1.3; u.uStars.value = 0.1;
  S.moon.visible = false;
  S.scene.fog.color.set(0x8a6a7a); S.scene.fog.density = 0.012;
  S.L.dir.color.set(0xffb488); S.L.dir.intensity = 1.6; S.L.dir.userData.vec = V(0.25, 0.35, -1).normalize();
  S.L.hemi.color.set(0x8a90c0); S.L.hemi.groundColor.set(0x3a2a20); S.L.hemi.intensity = 0.9;
  S.clouds.material.color.set(0xd09a9a);
  S.bats.visible = false;
}

function lanternState(S, figZ, mode) {
  // mode: 'passing' (se apagan tras la figura), 'off', 'on', o funcion (j)=>k
  for (const j of S.jacks) {
    let k = 1;
    if (mode === 'off') k = j.door ? 1 : 0;
    else if (mode === 'passing' && !j.door) {
      const p = clamp((figZ - j.z + 0.3) / 0.9);
      k = p <= 0 ? 1 : p >= 1 ? 0 : (1 - p) * (0.5 + 0.5 * Math.sin(p * 40 + j.x));
    } else if (typeof mode === 'function') k = mode(j);
    j.mesh.userData.setOn(k);
    j.k = k;
  }
  // luces de la calle segun faroles cercanos
  for (const l of S.roadLights) {
    let s = 0, c = 0;
    for (const j of S.jacks) if (!j.door && Math.abs(j.z - l.position.z) < 9) { s += j.k; c++; }
    l.intensity = 22 * (c ? s / c : 1);
  }
}

function forestNight(S, ctx) {
  S.fireflies.set(ctx.t);
  S.fog.userData.update(ctx.t);
  for (const s of S.shafts) s.userData.u.uTime.value = ctx.t;
}

function caveBase(S, ctx, wave = -99) {
  S.fire.set(ctx.t, { wave, flare: 1 });
  S.ringFire.set(ctx.t, { wave: wave > -50 ? (wave > 0.05 ? 99 : -99) : -99, flare: 1, bright: 0.35 });
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
  S.crown.visible = true;
  S.orb.visible = true;
  S.orb.position.set(0, 6.3 + Math.sin(ctx.t * 2) * 0.15, -76);
  S.orb.rotation.set(ctx.t * 0.7, ctx.t, 0);
  S.orbLight.position.copy(S.orb.position);
  S.orbLight.intensity = 12;
  S.orbSwirl.set(ctx.t, { center: [S.orb.position.x, S.orb.position.y, S.orb.position.z] });
  S.orbSwirl.points.visible = true;
  S.kingLight.position.set(0, 14, -92);
  for (const l of S.lanterns) l.userData.glow.emissive.setRGB(0.35, 0.8, 1.0);
  if (S.fx) for (const k in S.fx) S.fx[k].visible = false;
}

// pose del rey: sentado (s=1) o de pie
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

// pose base del ejercito en la cueva
function armyIdle(S, ctx, o = {}) {
  const fig = o.fig || V(0.5, 0, 0);
  const look = o.look || 0; // 0..1 giran la cabeza hacia la figura
  const aim = o.aim || 0;
  const t = ctx.t;
  S.army.apply((i, it) => {
    const dx = fig.x - it.x, dz = fig.z - it.z;
    const ang = Math.atan2(dx, dz);
    let rel = ang - (it.yaw || 0);
    rel = Math.atan2(Math.sin(rel), Math.cos(rel));
    const hy = clamp(rel, -1.3, 1.3) * look;
    const jitter = Math.sin(t * 9 + i) * 0.02;
    const P = { head: [Math.sin(t * 0.7 + i) * 0.05 * (1 - look) - 0.15 * look * (it.sit ? -1 : 0), hy + jitter] };
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

// ---------------------------------------------------------------------------
// ESCENAS
// ---------------------------------------------------------------------------
export const SCENES = [
  // 1: vista aerea del pueblo
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, -999, 'on');
      dance(S, ctx.t, 1);
      cam(ctx.camera, lt, [[0, [6, 44, 82]], [5, [3, 32, 52]], [10, [0, 15, 24]]], [[0, [0, 50, -120]], [5, [0, 18, -60]], [10, [0, 1, -4]]], 50, { span: [0, 10] });
      S.bats.userData.update(ctx.t, [0, 26, -60]);
      ctx.focus = V(0, 0, -10);
      ctx.grade.uFade.value = 1 - seg(lt, 0, 2.2);
    },
  },
  // 2: plaza, aldeanos bailando
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, -999, 'on');
      dance(S, ctx.t, 1);
      const a = lerp(3.6, 4.6, lt / 10);
      cam(ctx.camera, lt, [[0, [Math.cos(a) * 10, 1.3, Math.sin(a) * 10]], [10, [Math.cos(a + 0.001) * 8.5, 2.0, Math.sin(a + 0.001) * 8.5]]], [[0, [0, 1.8, 0]], [10, [0, 2.2, 0]]], 42);
      const p = V(Math.cos(a) * lerp(10, 8.5, lt / 10), lerp(1.3, 2.0, lt / 10), Math.sin(a) * lerp(10, 8.5, lt / 10));
      ctx.camera.position.copy(p);
      ctx.camera.lookAt(0, 1.9, 0);
      ctx.focus = V(0, 0, 0);
    },
  },
  // 3: la figura emerge de la niebla, contraluz de la luna
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, -999, 'on');
      const G = ctx.ghost;
      const z = lerp(-80, -69, lt / 10);
      place(G, 0.5, 0, z, 0);
      G.walk(z);
      S.scene.fog.density = 0.02;
      cam(ctx.camera, lt, [[0, [2.2, 0.9, -56]], [10, [1.4, 1.1, -61]]], [[0, [0.3, 4.2, -90]], [10, [0.4, 2.6, -80]]], 40);
      ctx.focus = V(0, 0, -70);
      ctx.grade.uVig.value = 0.6;
    },
  },
  // 4: travelling bajo, los faroles se apagan a su paso
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      const G = ctx.ghost;
      const z = lerp(-63, -49.5, lt / 10);
      place(G, 0.5, 0, z, 0);
      G.walk(z);
      lanternState(S, z, 'passing');
      cam(ctx.camera, lt, [[0, [-1.8, 0.35, z + 3.6]], [10, [-1.6, 0.4, z + 3.2]]], [[0, [0.6, 1.9, z]], [10, [0.6, 1.7, z]]], 48);
      const p = ctx.camera.position;
      p.z = z + lerp(3.6, 2.6, lt / 10) + lerp(0, -1, seg(lt, 6, 10));
      p.x = lerp(-1.9, -2.6, seg(lt, 6, 10));
      p.y = lerp(0.35, 0.9, seg(lt, 6, 10));
      ctx.camera.lookAt(lerp(0.6, 1.2, seg(lt, 6, 10)), lerp(1.9, 1.4, seg(lt, 6, 10)), z - lerp(0, 6, seg(lt, 6, 10)));
      ctx.focus = V(0, 0, z);
    },
  },
  // 5: los aldeanos huyen, la nina se esconde tras la paja
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 0, 'off');
      const G = ctx.ghost;
      const z = lerp(-19, -12.5, ease(lt / 10));
      place(G, 0.5, 0, z, 0);
      G.walk(z, lt < 9 ? 1 : 0.3);
      flee(S, ctx.t, lt);
      ctx.key.position.set(1.8, 3.2, z - 1.8);
      ctx.key.intensity = 4;
      const flare = lerp(1, 0.4, seg(lt, 1, 6));
      S.bonfire.set(ctx.t, { flare, bright: lerp(1.1, 0.8, seg(lt, 1, 6)) });
      S.bonLight.intensity = 90 * lerp(1, 0.35, seg(lt, 1, 6)) * (0.85 + 0.15 * noise1(ctx.t * 3));
      const g = ctx.girl;
      g.root.visible = true;
      const gx = lerp(4.6, 6.4, seg(lt, 1.5, 3.5)), gz = lerp(-2.5, -4.6, seg(lt, 1.5, 3.5));
      place(g, gx, 0, gz, yawTo(0.5 - gx, z - gz));
      g.walk(lt * 1.5, lt > 1.5 && lt < 3.5 ? 1 : 0);
      g.torso.rotation.x = lt > 3.5 ? 0.25 : 0;
      if (lt < 6.2) {
        cam(ctx.camera, lt, [[0, [-7.5, 2.6, 5]], [6.2, [-6.5, 2.2, 3]]], [[0, [0.5, 1.5, -12]], [6.2, [0.5, 1.6, -13]]], 46);
      } else {
        cam(ctx.camera, lt, [[6.2, [8.0, 1.25, -2.0]], [10, [7.7, 1.2, -2.7]]], [[6.2, [0.5, 1.8, -13]], [10, [0.5, 1.8, -13]]], 38);
      }
      ctx.focus = V(0, 0, -6);
    },
  },
  // 6: primer plano de la mascara que no puede gritar / la nina
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageNight(S, lt, ctx);
      lanternState(S, 0, 'off');
      S.bonfire.set(ctx.t, { flare: 0.4, bright: 0.8 });
      S.bonLight.intensity = 14;
      const G = ctx.ghost;
      place(G, 0.5, 0, -12.5, 0.25);
      const tremble = lt > 1.5 && lt < 6.4 ? 1 : 0;
      G.head.rotation.set(-0.12 * seg(lt, 1, 2.5) + Math.sin(ctx.t * 37) * 0.012 * tremble, Math.sin(ctx.t * 29) * 0.01 * tremble, Math.sin(ctx.t * 23) * 0.008 * tremble);
      G.armR.rotation.x = -0.3 * seg(lt, 1, 3);
      G.armL.rotation.x = -0.3 * seg(lt, 1, 3);
      const g = ctx.girl;
      g.root.visible = true;
      place(g, 6.4, 0, -4.6, yawTo(0.5 - 6.4, -12.5 + 4.6));
      g.torso.rotation.x = 0.15;
      if (lt > 7.6) g.setEyes(true);
      g.head.rotation.x = lt > 7.6 ? -0.08 : 0;
      // ondas de sonido palidas
      const fx = ensureFx(S, ctx);
      const mouth = V(0.5, 0, -12.5).add(V(Math.sin(0.25) * 0.55, 1.55, Math.cos(0.25) * 0.55));
      for (let k = 0; k < 3; k++) {
        const ring = fx.rings[k];
        const ph = ((lt - 1.6 - k * 0.55) % 1.65) / 1.65;
        ring.visible = lt > 1.6 + k * 0.55 && lt < 6.6 && ph >= 0;
        ring.position.copy(mouth).add(V(Math.sin(0.25), 0, Math.cos(0.25)).multiplyScalar(ph * 0.35));
        ring.lookAt(ctx.camera.position);
        ring.scale.setScalar(0.12 + ph * 0.55);
        ring.userData.u.uOpacity.value = (1 - ph) * 0.35;
        ring.userData.u.uColor.value.set(0xbfd8ff);
      }
      fx.wisp.points.visible = lt > 1.5 && lt < 6.6;
      fx.wisp.set(ctx.t, { center: [mouth.x, mouth.y, mouth.z] });
      ctx.key.position.copy(mouth).add(V(0.9, 0.5, 1.4));
      ctx.key.color.set(0xcfe0ff);
      ctx.key.intensity = 3.5;
      S.bonLight.intensity = 6;
      if (lt < 6.4) {
        cam(ctx.camera, lt, [[0, [0.5 + Math.sin(0.25) * 2.4, 1.85, -12.5 + Math.cos(0.25) * 2.4]], [6.4, [0.5 + Math.sin(0.25) * 1.5, 1.8, -12.5 + Math.cos(0.25) * 1.5]]], [[0, [0.5, 1.72, -12.5]], [6.4, [0.5, 1.72, -12.5]]], 32);
        const d = ctx.camera.position.clone();
        ctx.camera.position.set(lerp(d.x, d.x, 0), d.y, d.z);
        ctx.camera.lookAt(0.5 + Math.sin(0.25) * 0.25, 1.72, -12.5 + Math.cos(0.25) * 0.25);
      } else {
        const gp = V(6.4, 0, -4.6);
        const dir = V(0.5 - 6.4, 0, -12.5 + 4.6).normalize();
        const hp = gp.clone().add(V(0, 1.2, 0));
        const cp = hp.clone().addScaledVector(dir, lerp(1.35, 1.05, lin(lt, 6.4, 10))).add(V(0.15, 0.05, 0));
        ctx.camera.position.copy(cp);
        ctx.camera.lookAt(hp.x, hp.y + 0.05, hp.z);
        ctx.camera.fov = 34;
      }
      ctx.focus = V(2, 0, -8);
      ctx.grade.uVig.value = 0.6;
    },
  },
  // 7: el bosque muerto
  {
    set: 'forest',
    update(lt, ctx) {
      const S = ctx.set;
      forestNight(S, ctx);
      const G = ctx.ghost;
      const z = lerp(34, 23, lt / 10);
      const x = S.px(z) + 0.0;
      place(G, x, 0, z, Math.PI + Math.atan2(S.px(z - 0.5) - S.px(z + 0.5), 1) * -1);
      G.walk(z);
      S.mushLight.position.set(x + 2, 1, z - 3);
      cam(ctx.camera, lt, [[0, [x + 9, 3.0, z + 6]], [10, [x + 6, 5.5, z - 3]]], [[0, [x, 1.6, z]], [10, [x, 1.5, z]]], 44);
      const cp = V(lerp(S.px(26) + 6.5, S.px(16) + 3.5, lt / 10), lerp(2.4, 3.6, ease(lt / 10)), lerp(26, 16, lt / 10));
      ctx.camera.position.copy(cp);
      ctx.camera.lookAt(x, 1.5, z);
      ctx.key.position.set(x + 1.5, 3, z - 2.5);
      ctx.key.intensity = 2;
      ctx.focus = V(x, 0, z);
    },
  },
  // 8: la nina sigue a la figura (sobre el hombro)
  {
    set: 'forest',
    update(lt, ctx) {
      const S = ctx.set;
      forestNight(S, ctx);
      const G = ctx.ghost;
      const moving = (a, b) => lerp(a, b, 1);
      const zt = lt < 3.8 ? lerp(18, 14.2, lt / 3.8) : lt < 6.3 ? 14.2 : lerp(14.2, 10.5, (lt - 6.3) / 3.7);
      const fx = S.px(zt);
      place(G, fx, 0, zt, Math.PI);
      if (lt < 3.8 || lt > 6.3) G.walk(zt);
      else {
        G.head.rotation.y = 2.2 * seg(lt, 4.0, 4.7) * (1 - seg(lt, 5.6, 6.2));
        G.torso.rotation.y = 0.6 * seg(lt, 4.0, 4.7) * (1 - seg(lt, 5.6, 6.2));
      }
      const g = ctx.girl;
      g.root.visible = true;
      // se esconde detras de un tronco cercano
      const hide = seg(lt, 3.7, 4.2) * (1 - seg(lt, 6.4, 7.0));
      const gzBase = lt < 3.7 ? lerp(26.5, 23, lt / 3.7) : lt < 7 ? 23 : lerp(23, 20.2, (lt - 7) / 3);
      const gx0 = S.px(gzBase) + 0.6;
      const tree = nearestTrunk(S, S.px(22.5) + 2.5, 22.5);
      const hx = tree[0] + 0.15, hz = tree[1] + 0.95;
      const gx = lerp(gx0, hx, hide), gz = lerp(gzBase, hz, hide);
      place(g, gx, groundF(S, gx, gz), gz, Math.PI + (hide > 0.5 ? 0.6 : 0));
      if (hide < 0.05 || (hide > 0.95 && false)) g.walk(lt * 1.6, lt < 3.7 || lt > 7 ? 1 : 0);
      else g.walk(lt * 3, hide > 0.02 && hide < 0.98 ? 1 : 0);
      g.torso.rotation.x = hide * 0.2;
      // camara sobre el hombro de la nina
      const cp = V(gx + 0.9 + hide * 0.5, groundF(S, gx, gz) + 1.15, gz + 2.0);
      ctx.camera.position.copy(cp);
      ctx.camera.lookAt(lerp(fx, gx, 0.15), 1.2, lerp(zt, gz, 0.1) - 1);
      ctx.camera.fov = 42;
      ctx.focus = V(fx, 0, zt + 4);
    },
  },
  // 9: el pantano y la bruja
  {
    set: 'swamp',
    update(lt, ctx) {
      const S = ctx.set;
      S.fog.userData.update(ctx.t);
      S.bats.userData.update(ctx.t, [10, -2, 0]);
      S.bubbles.set(ctx.t);
      S.fireflies.set(ctx.t);
      S.caulLight.intensity = 25 * (0.8 + 0.2 * noise1(ctx.t * 5));
      const G = ctx.ghost;
      const z = lerp(8, -5, lt / 10);
      place(G, 0.0, 0, z, Math.PI);
      G.walk(z);
      const W = S.witch;
      W.reset();
      W.root.position.set(S.hut.hx0 + 1.4, 4, -6);
      W.root.rotation.y = -Math.PI / 2;
      W.head.rotation.y = clamp(Math.atan2(z + 6, 4) * -1, -0.9, 0.9) * (1 - seg(lt, 6.8, 7.6));
      W.root.position.x = S.hut.hx0 + 1.4 + seg(lt, 7.0, 8.0) * 1.2;
      S.curtain.position.z = lerp(-7.9, -6, seg(lt, 6.8, 8.0));
      S.curtain.scale.x = lerp(0.15, 1, seg(lt, 6.8, 8.0));
      S.winLight.intensity = lerp(8, 1, seg(lt, 7, 8.2));
      cam(ctx.camera, lt, [[0, [-7, 2.4, 13]], [10, [-5.5, 3.2, 3]]], [[0, [2, 2.5, 0]], [10, [3, 3.8, -6]]], 44);
      ctx.focus = V(4, 0, -2);
    },
  },
  // 10: cementerio, los zombis se levantan y se apartan
  {
    set: 'graveyard',
    update(lt, ctx) {
      const S = ctx.set;
      graveBase(S, ctx);
      const G = ctx.ghost;
      const z = lerp(26, 4, lt / 10);
      const gy = groundG(S, z);
      place(G, 0.5, gy, z, Math.PI);
      G.walk(z);
      S.zombies.forEach((zb, i) => {
        const [hx, hy, hz] = zb.home;
        const rise = seg(lt, i * 0.9, i * 0.9 + 1.6);
        const bow = seg(lt, i * 0.9 + 2.4, i * 0.9 + 3.3);
        const side = hx < 0 ? -1 : 1;
        zb.root.visible = rise > 0.01;
        zb.root.position.set(hx + side * bow * 1.3, hy - 2.1 * (1 - rise), hz);
        zb.root.rotation.set(0, side < 0 ? Math.PI / 2 - 0.3 : -Math.PI / 2 + 0.3, 0);
        zb.armR.rotation.set(-Math.PI / 2 * (1 - bow) - 0.3 * rise, 0, 0);
        zb.armL.rotation.set(-Math.PI / 2 * (1 - bow) - 0.3 * rise, 0, 0);
        zb.torso.rotation.x = 0.55 * bow;
        zb.head.rotation.x = 0.35 * bow;
        zb.legL.rotation.x = Math.sin(lt * 6 + i) * 0.4 * (bow > 0 && bow < 1 ? 1 : 0);
        zb.legR.rotation.x = -zb.legL.rotation.x;
      });
      cam(ctx.camera, lt, [[0, [3.5, 3.2, 31]], [10, [-4.5, 5.0, 11]]], [[0, [0.5, 1.6, 22]], [10, [0.5, 2.5, 2]]], 46);
      ctx.focus = V(0, 0, z);
    },
  },
  // 11: la lapida gigante revela el camino
  {
    set: 'graveyard',
    update(lt, ctx) {
      const S = ctx.set;
      graveBase(S, ctx);
      S.zombies.forEach((zb) => { zb.root.visible = false; });
      const G = ctx.ghost;
      const z = lerp(-14.5, -18.6, seg(lt, 0, 2));
      place(G, 0.5, groundG(S, z), z, Math.PI);
      if (lt < 2) G.walk(z);
      const kneel = seg(lt, 1.8, 2.8);
      G.body.position.y = 0.75 - 0.42 * kneel;
      G.skirt.rotation.x = -0.5 * kneel;
      G.torso.rotation.x = 0.35 * kneel;
      G.armR.rotation.x = -1.35 * seg(lt, 2.4, 3.2);
      G.head.rotation.x = -0.25 * seg(lt, 4, 6);
      for (let i = 0; i < 4; i++) {
        const m = glowMats['rune' + (i + 1)];
        if (m) m.emissiveIntensity = 1.1 * seg(lt, 2.8 + i * 0.6, 3.4 + i * 0.6) * (0.85 + 0.15 * Math.sin(ctx.t * 6 + i));
      }
      S.runeLight.intensity = 25 * seg(lt, 2.8, 5);
      S.runeSparks.points.visible = lt > 3;
      const up = seg(lt, 6, 9.6);
      const pos = path([[0, [3.6, S.gh + 1.2, S.gz + 5.5]], [6, [2.4, S.gh + 1.6, S.gz + 4.2]], [10, [0.5, S.gh + 7.5, S.gz + 9]]], lt);
      ctx.camera.position.copy(pos);
      const look = V(0.5, S.gh + 2.5, S.gz).lerp(V(0, 22, -240), easeIO(up));
      ctx.camera.lookAt(look);
      ctx.camera.fov = lerp(40, 34, up);
      ctx.focus = V(0, S.gh, S.gz + 3);
      S.mtnFire.set(ctx.t, { flare: 1 + up * 0.4, bright: 1.2 + up * 0.8 });
      S.mtnGlow.userData.u.uOpacity.value = 0.25 + up * 0.25;
    },
  },
  // 12: la montana con la calavera
  {
    set: 'mountain',
    update(lt, ctx) {
      const S = ctx.set;
      mountainNight(S, ctx);
      const G = ctx.ghost;
      const z = lerp(24, 9, lt / 10);
      place(G, 0.5, 0, z, Math.PI);
      G.walk(z);
      cam(ctx.camera, lt, [[0, [3, 6, 44]], [10, [1, 3.5, 20]]], [[0, [0, 15, -12]], [10, [0, 13, -12]]], 50, { span: [0, 10] });
      ctx.focus = V(0, 0, 4);
    },
  },
  // 13: dentro del tunel; la nina se queda en la entrada
  {
    set: 'mountain',
    update(lt, ctx) {
      const S = ctx.set;
      mountainNight(S, ctx);
      const G = ctx.ghost;
      const z = lerp(-8, -27, lt / 10);
      const fy = tunnelY(S, z);
      place(G, tunnelX(z), fy, z, Math.PI);
      G.walk(z);
      const g = ctx.girl;
      g.root.visible = true;
      const gz = lerp(-4, -8.5, seg(lt, 0, 2.5));
      place(g, 1.2, 0, gz, Math.PI);
      g.walk(lt * 1.5, lt < 2.5 ? 1 : 0);
      g.torso.rotation.x = lt > 3 ? -0.1 : 0;
      g.arms.position.y = 0.6;
      const cz = -17.5;
      const cp = V(tunnelX(cz) + 2.3, tunnelY(S, cz) + 2.6, cz);
      ctx.key.position.set(G.root.position.x + 0.6, G.root.position.y + 2.6, z + 1.6);
      ctx.key.color.set(0x9ad0ff);
      ctx.key.intensity = 9;
      ctx.camera.position.copy(cp);
      const head = V(G.root.position.x, G.root.position.y + 1.5, z);
      const early = head.clone().lerp(V(0.6, 1.4, -8), 0.35);
      const ahead = V(tunnelX(z - 7), tunnelY(S, z - 7) + 1.2, z - 7);
      ctx.camera.lookAt(early.lerp(ahead, seg(lt, 3.6, 6.4)));
      ctx.camera.fov = 48;
      ctx.focus = V(0, 0, -12);
    },
  },
  // 14: revelacion de la caverna
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 1, lt);
      const G = ctx.ghost;
      const z = lerp(5, 0.5, seg(lt, 0, 7));
      place(G, 0.0, 0, z, Math.PI);
      if (lt < 7) G.walk(z);
      armyIdle(S, ctx, { fig: V(0, 0, z) });
      S.army.mat.emissiveIntensity = 0.2;
      cam(ctx.camera, lt, [[0, [0.6, 1.7, 9.5]], [4, [0.3, 5, 6]], [10, [0, 19, -3]]], [[0, [0, 1.6, -8]], [4, [0, 3, -25]], [10, [0, 1, -42]]], 52, { span: [0, 10] });
    },
  },
  // 15: giro alrededor; los craneos voltean
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 1, lt);
      const G = ctx.ghost;
      place(G, 0.0, 0, 0.5, Math.PI);
      const look = seg(lt, 1.8, 3.6);
      armyIdle(S, ctx, { fig: V(0, 0, 0.5), look });
      S.army.mat.emissiveIntensity = 0.2 + 2.2 * seg(lt, 3.8, 4.8);
      const flare = 1 + 0.8 * seg(lt, 4.4, 5.0) - 0.4 * seg(lt, 5.4, 7);
      S.fire.set(ctx.t, { wave: -99, flare });
      for (const l of S.lights) l.intensity *= flare;
      const a = lerp(-0.4, Math.PI * 0.95, easeIO(lt / 10));
      ctx.camera.position.set(Math.sin(a) * 6.5, 2.3 + Math.sin(lt / 10 * Math.PI) * 1.2, 0.5 + Math.cos(a) * 6.5);
      ctx.camera.lookAt(0, 1.4, 0.5);
      ctx.camera.fov = 46;
    },
  },
  // 16: pasillo de arqueros que tensan los arcos
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 1, lt);
      const G = ctx.ghost;
      const z = lerp(-2, -15, lt / 10);
      place(G, 0.0, 0, z, Math.PI);
      G.walk(z);
      armyIdle(S, ctx, { fig: V(0, 0, z), look: 1, aim: seg(lt, 1.2, 3.0) });
      S.army.mat.emissiveIntensity = 2.2;
      cam(ctx.camera, lt, [[0, [0.4, 1.3, z - 4.6]], [10, [1.2, 1.6, z - 4.2]]], [[0, [0, 1.6, z]], [10, [0, 1.5, z]]], 50);
      ctx.camera.position.set(lerp(0.4, 1.5, lt / 10), lerp(1.2, 1.7, lt / 10), z - lerp(4.8, 3.8, lt / 10));
      ctx.camera.lookAt(0, 1.5, z);
    },
  },
  // 17: puente de huesos sobre la fosa de fuego
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 1, lt);
      const G = ctx.ghost;
      const z = lerp(-46, -60, lt / 10);
      place(G, 0.0, 0, z, Math.PI);
      G.walk(z, 0.7);
      armyIdle(S, ctx, { fig: V(0, 0, z), look: 1, aim: 1 });
      S.army.mat.emissiveIntensity = 2.2;
      cam(ctx.camera, lt, [[0, [8.5, 2.6, -50]], [10, [6.5, 3.0, -57.5]]], [[0, [0, 0.3, -47.5]], [10, [0, 0.8, -59.5]]], 50);
    },
  },
  // 18: sala del trono; el rey se levanta
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      const stand = seg(lt, 4.2, 6.8);
      kingPose(S, 1 - stand, lt, { headX: -0.1 * stand });
      S.king.mat.emissiveIntensity = 2.5 * seg(lt, 6.2, 7.0);
      S.kingLight.intensity = 10 + 30 * seg(lt, 6.2, 7.0);
      const G = ctx.ghost;
      const z = lerp(-61, -68.5, seg(lt, 0, 4));
      const st = (c) => clamp(c >= -62 ? 0 : -62 - c, 0, 3);
      const zc = Math.floor(z), zf = z - zc;
      const y = lerp(st(zc), st(zc + 1), ease((zf - 0.35) / 0.3));
      place(G, 0.0, y, z, Math.PI);
      if (lt < 4) G.walk(z);
      armyIdle(S, ctx, { fig: V(0, 3, z), look: 1, aim: 1, extra: (i, it) => (it.guard ? null : { y: -50 }) });
      S.army.mat.emissiveIntensity = 2.2;
      if (lt < 4.2) {
        cam(ctx.camera, lt, [[0, [1.6, 3, -57]], [4.2, [1.2, 4.4, -63]]], [[0, [0, 9, -92]], [4.2, [0, 10, -94]]], 44);
      } else {
        cam(ctx.camera, lt, [[4.2, [3.6, 6.4, -86.5]], [10, [2.8, 6.8, -88]]], [[4.2, [0, 11, -95.5]], [10, [0, 13.6, -95]]], 40);
      }
    },
  },
  // 19: el rey alza el baculo; carga y lluvia de flechas; la figura se vuelve humo
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      const raise = seg(lt, 0.3, 1.4);
      kingPose(S, 0, lt, { armR: -0.3 - 2.6 * raise, headX: -0.15 });
      S.king.mat.emissiveIntensity = 2.5;
      S.kingLight.intensity = 40;
      const G = ctx.ghost;
      const smoke = seg(lt, 4.6, 5.4) * (1 - seg(lt, 6.6, 7.2));
      const p0 = V(0, 3, -69.5), p1 = V(-5, 3, -73);
      const gp = lt < 6.6 ? p0 : p1;
      place(G, gp.x, gp.y, gp.z, Math.PI * 0.9);
      G.mat.opacity = 1 - smoke;
      G.root.visible = smoke < 0.98;
      const fx = ensureFx(S, ctx);
      fx.smokeA.points.visible = lt > 4.5 && lt < 8;
      fx.smokeA.set(lt - 4.6, { center: [p0.x, p0.y + 1, p0.z] });
      fx.smokeB.points.visible = lt > 6.3 && lt < 9.5;
      fx.smokeB.set(lt - 6.4, { center: [p1.x, p1.y + 1, p1.z] });
      // carga de los esqueletos hacia la figura
      const charge = seg(lt, 1.4, 5.0);
      battleArmy(S, ctx, lt, { charge, target: p0, aim: seg(lt, 1.6, 2.4) });
      // flechas en camara lenta
      const slow = lt > 2.6 ? 0.35 : 1;
      arrows(fx, lt, p0, 2.6, slow);
      ctx.grade.uTint.value.setRGB(0.95, 1, 1.08);
      if (lt < 2.6) cam(ctx.camera, lt, [[0, [6, 6, -66]], [2.6, [5, 7, -64]]], [[0, [0, 12, -90]], [2.6, [0, 6, -80]]], 46);
      else cam(ctx.camera, lt, [[2.6, [-6, 3.6, -62]], [10, [-7.5, 4.6, -66]]], [[2.6, [0, 4.5, -70]], [10, [-3, 3.8, -72]]], 42);
    },
  },
  // 20: la figura se desliza entre esqueletos que se desarman
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      caveBase(S, ctx);
      kingPose(S, 0, lt, { armR: -2.9, headX: -0.1 });
      S.king.mat.emissiveIntensity = 2.5;
      S.kingLight.intensity = 40;
      const G = ctx.ghost;
      const gpath = [[0, [-5, 3, -73]], [2.5, [-8, 3.3, -68]], [5, [-2, 3.3, -66]], [7.5, [6, 3.3, -70]], [10, [3, 3, -73]]];
      const gp = path(gpath, lt);
      const ahead = path(gpath, lt + 0.1);
      place(G, gp.x, gp.y, gp.z, yawTo(ahead.x - gp.x, ahead.z - gp.z));
      G.skirt.rotation.x = -0.45;
      G.armR.rotation.set(0.6, 0, -0.5);
      G.armL.rotation.set(0.6, 0, 0.5);
      G.torso.rotation.x = 0.25;
      const fx = ensureFx(S, ctx);
      fx.trail.points.visible = true;
      fx.trail.set(ctx.t, { center: [gp.x, gp.y + 0.8, gp.z] });
      // colapsos al paso
      const passT = {};
      battleArmy(S, ctx, 10, {
        charge: 1, target: V(-5, 3, -73), aim: 0.2,
        collapse: (i, pos) => {
          let best = 99;
          for (let s = 0; s <= lt; s += 0.1) {
            const q = path(gpath, s);
            if (Math.hypot(q.x - pos.x, q.z - pos.z) < 2.3) { best = s; break; }
          }
          return best > 50 ? 0 : clamp((lt - best) / 1.1);
        },
      });
      const a = lerp(0.5, 2.4, easeIO(lt / 10));
      ctx.camera.position.set(Math.sin(a) * 6.5, lerp(10.5, 11.5, Math.sin(lt / 10 * Math.PI)), -71 + Math.cos(a) * 6.5);
      ctx.camera.lookAt(gp.x * 0.7, 3.4, gp.z * 0.7 - 71 * 0.3);
      ctx.camera.fov = 48;
    },
  },
  // 21: golpe del baculo, onda de fuego azul; la mascara se agrieta
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
      S.kingLight.intensity = 40 + 120 * clamp(1 - Math.abs(lt - 2.1) * 2);
      battleArmy(S, ctx, 10, { charge: 1, target: V(-5, 3, -73), aim: 0.2, collapseAll: true });
      const fx = ensureFx(S, ctx);
      const wr = clamp((lt - 2.05) / 1.4);
      const ring = fx.ground;
      ring.visible = lt > 2.05 && lt < 3.6;
      ring.position.set(0, 3.15, -84);
      ring.rotation.set(-Math.PI / 2, 0, 0);
      ring.scale.setScalar(1 + wr * 40);
      ring.userData.u.uColor.value.set(0x3ab0ff);
      ring.userData.u.uOpacity.value = 1 - wr;
      fx.burst.points.visible = lt > 2 && lt < 6;
      fx.burst.set(lt - 2.05, { center: [0, 3.5, -84], colA: 0x5ac8ff });
      // la figura sale despedida contra el pilar
      const hit = clamp((lt - 2.35) / 0.5);
      const start = V(2.5, 3, -75), end = V(-6.45, 3, -69.0);
      const gp = start.clone().lerp(end, 1 - Math.pow(1 - hit, 3));
      gp.y += Math.sin(Math.PI * hit) * 1.4;
      const G = ctx.ghost;
      place(G, gp.x, gp.y, gp.z, lt < 2.35 ? yawTo(-1, 0.5) : yawTo(3.2, 2.4));
      if (lt > 2.7) G.setFace('cracked');
      const down = seg(lt, 2.8, 3.2) * (1 - seg(lt, 5.2, 7.2));
      G.body.position.y = 0.75 - 0.45 * down;
      G.torso.rotation.x = -0.35 * hit * (1 - seg(lt, 5.2, 7.2)) + 0.4 * down;
      G.head.rotation.x = 0.3 * down;
      G.armR.rotation.z = -0.5 * down; G.armL.rotation.z = 0.5 * down;
      fx.hoodSmoke.points.visible = lt > 3;
      fx.hoodSmoke.set(ctx.t, { center: [gp.x, gp.y + 1.9 - 0.4 * down, gp.z] });
      if (lt < 4) cam(ctx.camera, lt, [[0, [12, 6, -72]], [4, [10, 5.5, -70]]], [[0, [-1, 4.5, -80]], [4, [-3, 4, -76]]], 50, { shake: lt > 2 && lt < 3 ? 0.18 : 0 });
      else cam(ctx.camera, lt, [[4, [-3.2, 4.3, -66.6]], [10, [-3.6, 4.7, -66.4]]], [[4, [-6.4, 4.0, -69.0]], [10, [-6.4, 4.5, -69.0]]], 40);
      ctx.grade.uFlash.value = 0.5 * clamp(1 - Math.abs(lt - 2.1) * 4);
      ctx.grade.uFlashCol.value.set(0x9adfff);
    },
  },
  // 22: salta el anillo de fuego y toma el orbe
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
      battleArmy(S, ctx, 10, { charge: 1, target: V(-5, 3, -73), aim: 0.2, collapseAll: true });
      const G = ctx.ghost;
      const jump = clamp((lt - 0.8) / 1.3);
      const a = V(-6.5, 3, -72), b = V(0, 3, -73.6);
      const gp = a.clone().lerp(b, easeIO(jump));
      gp.y += Math.sin(Math.PI * jump) * 2.6;
      place(G, gp.x, gp.y, gp.z, yawTo(b.x - a.x, b.z - a.z) * (1 - seg(lt, 2.1, 2.8)) + Math.PI * seg(lt, 2.1, 2.8));
      G.setFace(lt < 6.1 ? 'cracked' : 'normal');
      G.skirt.rotation.x = -0.5 * Math.sin(Math.PI * jump);
      // tomar el orbe
      const grab = seg(lt, 2.8, 3.6);
      G.armR.rotation.set(-2.2 * grab * (1 - seg(lt, 4.2, 5.2)) - 0.9 * seg(lt, 4.2, 5.2), 0, 0);
      const into = seg(lt, 4.4, 6.0);
      const orbStart = V(0, 6.3, -76), hand = V(0.3, 5.4, -74.6), mouth = V(0, 4.5, -73.95);
      const op = lt < 3.6 ? orbStart.clone().lerp(hand, seg(lt, 2.8, 3.6)) : hand.clone().lerp(mouth, into);
      S.orb.position.copy(op);
      S.orb.scale.setScalar(1 - into * 0.95);
      S.orb.visible = into < 0.99;
      S.orbLight.position.copy(op);
      S.orbLight.intensity = 12 * (1 - into);
      S.orbSwirl.set(ctx.t, { center: [op.x, op.y, op.z] });
      G.mat.emissiveIntensity = 1.3 * seg(lt, 6.0, 6.8);
      ctx.grade.uFlash.value = 0.6 * clamp(1 - Math.abs(lt - 6.05) * 3);
      if (lt < 4.2) cam(ctx.camera, lt, [[0, [-3, 5.5, -62]], [4.2, [2.6, 5.4, -66]]], [[0, [-3, 4, -73]], [4.2, [0, 5, -74.5]]], 44);
      else cam(ctx.camera, lt, [[4.2, [0.55, 5.0, -74.9]], [10, [0.3, 4.75, -74.9]]], [[4.2, [0, 4.8, -73.8]], [10, [0, 4.55, -73.8]]], 50);
      if (lt > 4.2) { ctx.key.position.set(0.9, 5.4, -74.9); ctx.key.intensity = 1.2; }
      S.ringFire.set(ctx.t, { wave: -99, bright: lt > 4.2 ? 0.22 : 0.32 });
    },
  },
  // 23: EL GRITO: fuego azul -> naranja, todo se derrumba
  {
    set: 'cavern',
    shadow: false,
    update(lt, ctx) {
      const S = ctx.set;
      const wave = (lt - 1.5) * 0.42;
      caveBase(S, ctx, wave);
      const G = ctx.ghost;
      place(G, 0, 3, -73.6, Math.PI);
      const scream = seg(lt, 0.6, 1.5);
      G.head.rotation.x = -0.45 * scream;
      G.torso.rotation.x = -0.15 * scream;
      G.armR.rotation.set(-0.3 * scream, 0, -1.2 * scream);
      G.armL.rotation.set(-0.3 * scream, 0, 1.2 * scream);
      G.mat.emissiveIntensity = 1.3;
      G.head.rotation.y = Math.sin(ctx.t * 40) * 0.015 * scream * (lt < 5 ? 1 : 0);
      S.orb.visible = false;
      S.orbSwirl.points.visible = false;
      S.orbLight.intensity = 0;
      S.ringFire.set(ctx.t, { wave: lt > 1.5 ? 99 : -99, flare: 1 + 0.6 * clamp(1 - Math.abs(lt - 1.7)), bright: lt < 3.4 ? 0.22 : 0.4 });
      // luces que cambian con la ola
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
      // derrumbe general
      S.army.mat.emissiveIntensity = 2.2 * (1 - clamp(wave * 2));
      battleArmy(S, ctx, 10, { charge: 1, target: V(-5, 3, -73), aim: 0.2, collapseAll: true, waveCollapse: wave });
      // el rey cae al final
      const kc = seg(lt, 4.2, 6.2);
      kingPose(S, 0, lt, { base: [0, 3, -86], armR: lerp(-0.8, 0.4, kc), torsoX: 1.2 * kc, headX: 0.6 * kc, dy: -2.2 * kc * kc });
      S.king.root.rotation.z = 0.4 * kc;
      S.king.mat.emissiveIntensity = 2.5 * (1 - kc);
      S.kingLight.position.set(0, 9, -84);
      S.kingLight.intensity = 40 * (1 - kc);
      S.crown.visible = lt < 4.0;
      const fx = ensureFx(S, ctx);
      fx.crownBurst.points.visible = lt > 3.9 && lt < 8;
      fx.crownBurst.set(lt - 4.0, { center: [0, 12.5, -86] });
      // onda blanca
      const wr = clamp((lt - 1.5) / 2.2);
      const ring = fx.shock;
      ring.visible = lt > 1.5 && lt < 3.8;
      ring.position.set(0, 4.5, -73.6);
      ring.rotation.set(-Math.PI / 2, 0, 0);
      ring.scale.setScalar(1 + wr * 70);
      ring.userData.u.uColor.value.set(0xffffff);
      ring.userData.u.uOpacity.value = 1 - wr;
      const ring2 = fx.shock2;
      ring2.visible = lt > 1.5 && lt < 3.2;
      ring2.position.set(0, 4.55, -73.2);
      ring2.lookAt(ctx.camera.position);
      ring2.scale.setScalar(0.5 + clamp((lt - 1.5) / 1.7) * 14);
      ring2.userData.u.uOpacity.value = 1 - clamp((lt - 1.5) / 1.7);
      fx.burst.points.visible = lt > 1.5 && lt < 7;
      fx.burst.set(lt - 1.5, { center: [0, 4.5, -73.6], colA: 0xffa040 });
      fx.bigBurst.points.visible = lt > 1.6;
      fx.bigBurst.set(lt - 1.6, { center: [0, 3, -70] });
      ctx.grade.uFlash.value = 0.75 * clamp(1 - Math.abs(lt - 1.55) * 2.2);
      ctx.grade.uFlashCol.value.set(0xffffff);
      ctx.bloom.strength = 0.6 + 0.4 * clamp(1 - Math.abs(lt - 1.8));
      if (lt < 3.4) cam(ctx.camera, lt, [[0, [0.35, 4.05, -74.9]], [3.4, [0.5, 3.95, -74.9]]], [[0, [0, 4.6, -73.7]], [3.4, [0, 4.9, -73.7]]], 58, { shake: lt > 1.4 && lt < 3 ? 0.06 : 0 });
      if (lt < 3.4) { ctx.key.position.set(0.9, 4.9, -74.9); ctx.key.intensity = 1.2; }
      else cam(ctx.camera, lt, [[3.4, [10, 9, -58]], [10, [14, 14, -48]]], [[3.4, [0, 5, -78]], [10, [0, 3, -70]]], 52);
    },
  },
  // 24: amanecer; sale de la cueva y la nina corre hacia el
  {
    set: 'mountain',
    update(lt, ctx) {
      const S = ctx.set;
      mountainNight(S, ctx);
      mountainDawn(S, ctx);
      const G = ctx.ghost;
      const z = lerp(-11, -1.5, seg(lt, 0, 8));
      place(G, 0.5, 0, z, 0);
      if (lt < 8) G.walk(z);
      const g = ctx.girl;
      g.root.visible = true;
      const gz = lerp(14, 1.0, seg(lt, 3, 8.3));
      place(g, 0.9, 0, gz, Math.PI);
      g.walk(lt * 2.6, lt > 3 && lt < 8.3 ? 1 : 0);
      g.body.position.y += lt > 8.3 ? Math.abs(Math.sin(lt * 8)) * 0.12 * (1 - seg(lt, 9.4, 10)) : 0;
      if (lt > 8.3) G.head.rotation.x = 0.35;
      cam(ctx.camera, lt, [[0, [6, 2.2, 20]], [10, [3.2, 1.6, 6]]], [[0, [0, 6, -12]], [10, [0.6, 1.6, -0.5]]], 46, { span: [0, 10] });
      ctx.focus = V(0, 0, 0);
    },
  },
  // 25: regreso al pueblo; los faroles se reencienden en ola
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageDawn(S, lt, ctx);
      const G = ctx.ghost;
      const z = lerp(-26, -12.5, seg(lt, 0, 6));
      place(G, 0.5, 0, z, 0);
      if (lt < 6) G.walk(z);
      const g = ctx.girl;
      g.root.visible = true;
      const gz = z + 0.4;
      place(g, 1.6, 0, gz, lt < 6 ? 0 : -Math.PI / 2 + 0.3);
      if (lt < 6) g.walk(lt * 2.4);
      const wave = (lt - 0.5) * 14;
      lanternState(S, 0, (j) => (j.door ? 1 : clamp((wave - (j.z + 64)) / 2)));
      S.bonfire.set(ctx.t, { flare: 0.4 + 0.9 * seg(lt, 2, 4), bright: 1.2 });
      S.bonLight.intensity = 90 * (0.4 + 0.8 * seg(lt, 2, 4));
      cheer(S, ctx.t, lt);
      // la nina le regala una calabacita
      const fx = ensureFx(S, ctx);
      const gift = fx.gift;
      gift.visible = true;
      const hp = V(1.6, 0.85, gz + 0.3), fp = V(1.0, 1.0, z + 0.45);
      const k = seg(lt, 7.0, 8.4);
      gift.position.copy(hp.lerp(fp, k));
      gift.rotation.y = -Math.PI / 2;
      g.arms.rotation.x = -0.5 * seg(lt, 6.6, 7.2) * (1 - seg(lt, 8.4, 9));
      G.armR.rotation.x = -0.9 * seg(lt, 7.4, 8.4);
      if (lt > 7) G.head.rotation.y = 0.5;
      if (lt < 6) cam(ctx.camera, lt, [[0, [-6, 5, 6]], [6, [-5, 3.5, 2]]], [[0, [0, 2, -30]], [6, [0, 1.5, -14]]], 46);
      else cam(ctx.camera, lt, [[6, [4.8, 1.6, -9.5]], [10, [4.2, 1.5, -10.4]]], [[6, [1.0, 1.2, -12.2]], [10, [1.0, 1.2, -12.2]]], 40);
      ctx.focus = V(0, 0, -10);
    },
  },
  // 26: final: sonrie y se aleja hacia el amanecer
  {
    set: 'village',
    update(lt, ctx) {
      const S = ctx.set;
      villageDawn(S, lt, ctx);
      lanternState(S, 0, 'on');
      S.bonfire.set(ctx.t, { flare: 1.3, bright: 1.2 });
      cheer(S, ctx.t, 10 + lt);
      const G = ctx.ghost;
      const turn = seg(lt, 5.0, 6.2);
      const walkZ = lt > 6 ? lerp(-12.5, -18, (lt - 6) / 4) : -12.5;
      place(G, 0.5, 0, walkZ, Math.PI * turn);
      if (lt > 6) G.walk(walkZ);
      G.head.rotation.z = 0.28 * seg(lt, 1.6, 2.6) * (1 - seg(lt, 4.6, 5.2));
      if (lt > 3.3) G.setFace('grin');
      G.armR.rotation.x = -0.9 * (1 - seg(lt, 6.2, 7));
      const fx = ensureFx(S, ctx);
      fx.gift.visible = true;
      const hand = V(0.5 + Math.sin(Math.PI * turn) * 0.45 + (1 - turn) * 0.5, 1.0, walkZ + Math.cos(Math.PI * turn) * 0.45);
      fx.gift.position.copy(hand);
      fx.gift.rotation.y = Math.PI * turn;
      const g = ctx.girl;
      g.root.visible = true;
      place(g, 1.6, 0, -12.1, -Math.PI / 2 + 0.3 + Math.PI * 0.6 * seg(lt, 6, 7));
      g.arms.rotation.x = lt > 7 ? -0.6 + Math.sin(lt * 7) * 0.2 : 0;
      if (lt < 5) {
        const c = V(0.55, 1.62, -11.0);
        ctx.camera.position.copy(c.add(V(0.1 * lt / 5, 0, -0.25 * lt / 5)));
        ctx.camera.lookAt(0.5, 1.6, -12.5);
        ctx.camera.fov = 34;
        ctx.key.position.set(1.0, 2.0, -11.2);
        ctx.key.color.set(0xfff2e6);
        ctx.key.intensity = 1.6;
      } else cam(ctx.camera, lt, [[5, [1.2, 1.4, -8]], [10, [0.8, 2.4, -6]]], [[5, [0.5, 1.6, -13]], [10, [0.5, 1.8, -24]]], 44);
      ctx.grade.uFade.value = seg(lt, 8.3, 9.8);
      ctx.focus = V(0, 0, -12);
    },
  },
];

// ---------------------------------------------------------------------------
// ayudantes de las escenas
// ---------------------------------------------------------------------------
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

function flee(S, t, lt) {
  S.villagers.forEach((v, i) => {
    v.reset();
    const a = (40 + 0) * 0.45 + (i / S.villagers.length) * Math.PI * 2;
    const start = V(Math.cos(a) * 5, 0, Math.sin(a) * 5);
    const door = S.doors[[4, 5, 6, 7, 8, 4, 5, 8][i]];
    const target = V(door[0], 0, door[1]);
    const k = clamp((lt - 1.2 - i * 0.18) / 3.6);
    const p = start.clone().lerp(target, k);
    v.root.visible = k < 0.98;
    v.root.position.copy(p);
    const lookFig = lt < 1.2 + i * 0.18;
    v.root.rotation.y = lookFig ? yawTo(0.5 - p.x, -15 - p.z) : yawTo(target.x - start.x, target.z - start.z);
    v.walk(lt * 3 + i, k > 0 && k < 1 ? 1.3 : 0);
    if (lookFig) v.body.position.y = 0.75 + Math.abs(Math.sin(lt * 12 + i)) * 0.05;
  });
}

function cheer(S, t, lt) {
  S.villagers.forEach((v, i) => {
    v.reset();
    const door = S.doors[[4, 5, 6, 7, 8, 4, 5, 8][i]];
    const out = seg(lt, 2 + i * 0.25, 4 + i * 0.25);
    const dir = V(-door[0], 0, -door[1]).normalize();
    const p = V(door[0], 0, door[1]).addScaledVector(dir, out * (2.2 + (i % 3)));
    v.root.visible = out > 0.02;
    v.root.position.copy(p);
    v.root.rotation.y = yawTo(0.5 - p.x, -12 - p.z);
    if (out > 0 && out < 1) v.walk(lt * 3 + i);
    if (out >= 1) v.root.position.y = Math.abs(Math.sin(t * 6 + i * 1.7)) * 0.45;
  });
}

function nearestTrunk(S, x, z) {
  let best = null, bd = 1e9;
  for (const tr of S.trunks) {
    const d = Math.hypot(tr[0] - x, tr[1] - z);
    if (d < bd) { bd = d; best = tr; }
  }
  return best;
}

function groundF(S, x, z) {
  return S.hAt(Math.floor(x), Math.floor(z)) + 1;
}

function groundG(S, z) {
  const a = S.hAt(0, Math.floor(z)) + 1, b = S.hAt(0, Math.floor(z) + 1) + 1;
  const f = z - Math.floor(z);
  return lerp(a, b, ease((f - 0.35) / 0.3));
}

function graveBase(S, ctx) {
  S.fog.userData.update(ctx.t);
  S.bats.userData.update(ctx.t, [0, 0, 0]);
  S.mtnFire.set(ctx.t, { flare: 1, bright: 1.2 });
  S.runeSparks.set(ctx.t);
  S.runeSparks.points.visible = false;
  for (let i = 0; i < 4; i++) if (glowMats['rune' + (i + 1)]) glowMats['rune' + (i + 1)].emissiveIntensity = 0;
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
  S.scene.fog.color.set(0x101428);
  S.L.dir.color.set(0x9aaeff); S.L.dir.intensity = 0.9;
  S.L.hemi.color.set(0x2a3060); S.L.hemi.intensity = 0.55;
}

function mountainDawn(S, ctx) {
  const u = S.sky.userData.u;
  u.uTop.value.set(0x2a2a66); u.uHor.value.set(0xff8a6a); u.uBot.value.set(0x201020);
  u.uSunDir.value.set(0.6, 0.12, 0.8).normalize(); u.uSunCol.value.set(0xffa070); u.uGlow.value = 1.2; u.uStars.value = 0.15;
  S.moon.visible = false;
  S.fire.set(ctx.t, { wave: 99, flare: 1.1 });
  S.embers.set(ctx.t, { mix: 1 });
  for (const l of S.blue) l.color.set(0xff8a3a);
  S.scene.fog.color.set(0x6a4a6a);
  S.L.dir.color.set(0xffb088); S.L.dir.intensity = 1.4; S.L.dir.userData.vec = V(0.6, 0.35, 0.8).normalize();
  S.L.hemi.color.set(0x8a80b0); S.L.hemi.intensity = 0.85;
  S.bats.visible = false;
}

function tunnelX(z) {
  return Math.sin(z / 9) * 1.5 + 0.5;
}
function tunnelY(S, z) {
  const a = S.floorAt(Math.floor(z)) + 1, b = S.floorAt(Math.floor(z) + 1) + 1;
  const f = z - Math.floor(z);
  return lerp(a, b, ease((f - 0.35) / 0.3));
}

// ejercito en batalla dentro de la sala del trono
function battleArmy(S, ctx, lt, o) {
  const target = o.target;
  S.army.apply((i, it) => {
    if (!(it.guard || it.row === 1)) {
      const P = { head: [0, 0] };
      if (o.waveCollapse !== undefined) P.collapse = clamp((o.waveCollapse - Math.hypot(it.x, it.z + 76) / 70) / 0.3);
      return P;
    }
    // posicion de batalla en semicirculo alrededor del objetivo
    const k = i % 48;
    const ang = (k / 48) * Math.PI * 2 + 0.3;
    const rad = 6 + (k % 3) * 2.2;
    const bx = Math.cos(ang) * rad, bz = -71 + Math.sin(ang) * rad * 0.8;
    const sx = it.guard ? it.x : bx * 1.8, sz = it.guard ? it.z : -66 + Math.sin(ang) * 4;
    const ch = o.charge;
    const x = lerp(sx, lerp(bx, target.x + Math.cos(ang) * 2.6, 0.35), ch), z = lerp(sz, lerp(bz, target.z + Math.sin(ang) * 2.6, 0.35), ch);
    const yaw = yawTo(target.x - x, target.z - z);
    const P = { x, y: 3, z, yaw, walk: ch > 0.02 && ch < 0.98 ? 1 : 0, phase: ctx.t * 9 + i, head: [0, 0] };
    if (it.bow && o.aim) { P.armL = [-Math.PI / 2 * o.aim, 0]; P.armR = [-Math.PI / 2 * o.aim + 0.25, 0.25]; }
    if (o.collapse) P.collapse = o.collapse(i, { x, z });
    if (o.collapseAll) P.collapse = 1;
    if (o.collapseAll && o.waveCollapse !== undefined) P.collapse = 1;
    return P;
  });
}

function arrows(fx, lt, target, t0, slow) {
  const A = fx.arrowMesh;
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(1, 1, 1);
  const T = lt < t0 ? -1 : (lt - t0) * slow + 0.25;
  for (let i = 0; i < A.count; i++) {
    const a = (i / A.count) * Math.PI * 2 * 3.1;
    const rad = 7 + (i % 5) * 1.5;
    const start = V(target.x + Math.cos(a) * rad, 9 + (i % 4), target.z + Math.sin(a) * rad * 0.8 + 4);
    const end = V(target.x + Math.cos(a * 1.7) * 0.9, target.y + 0.05, target.z + Math.sin(a * 1.3) * 0.9);
    const delay = (i % 7) * 0.06;
    const k = clamp((T - delay) / 1.0);
    const p = start.clone().lerp(end, k);
    p.y += Math.sin(Math.PI * k) * 2.5;
    const nk = clamp(k + 0.02);
    const p2 = start.clone().lerp(end, nk);
    p2.y += Math.sin(Math.PI * nk) * 2.5;
    const dir = p2.sub(p).normalize();
    if (dir.lengthSq() < 0.5) dir.set(0, -1, 0);
    q.setFromUnitVectors(V(0, 0, 1), dir);
    const vis = T > delay && k < 1 ? 1 : k >= 1 ? 1 : 0;
    m.compose(p, q, s.setScalar(vis));
    A.setMatrixAt(i, m);
  }
  A.instanceMatrix.needsUpdate = true;
  A.visible = lt > t0;
}

// objetos de efectos creados a demanda por escenario
import { Particles, makeRing } from './fx.js';
import { makeJack } from './models.js';
function ensureFx(S) {
  if (S.fxApi) return S.fxApi;
  const api = {};
  S.fx = {};
  let n = 0;
  const reg = (o) => { S.scene.add(o); S.fx['o' + n++] = o; o.visible = false; return o; };
  const P = (cnt, o) => { const p = new Particles(cnt, o); reg(p.points); return p; };
  api.rings = [0, 1, 2].map(() => reg(makeRing(0xbfd8ff, 0.5)));
  api.wisp = P(40, { center: [0, 0, 0], box: [0.15, 0.1, 0.1], vel: [0, 0.25, 0.4], spread: [0.25, 0.2, 0.2], life: 1.6, size: 0.012, colA: 0xcfe0ff, bright: 0.7, swirl: 0.15 });
  api.shock = reg(makeRing(0xffffff, 1.6));
  api.shock2 = reg(makeRing(0xffffff, 1.2));
  api.ground = reg(makeRing(0x3ab0ff, 1.6));
  api.smokeA = P(220, { burst: true, center: [0, 0, 0], box: [0.8, 1.8, 0.8], vel: [0, 0.6, 0], speed: 2.5, life: 1.6, size: 0.22, colA: 0x0a0a10, bright: 1, normal: true, drag: 2 });
  api.smokeB = P(220, { burst: true, center: [0, 0, 0], box: [0.8, 1.8, 0.8], vel: [0, 0.4, 0], speed: 2.0, life: 1.4, size: 0.22, colA: 0x0a0a10, bright: 1, normal: true, drag: 2, seed: 4 });
  api.trail = P(160, { center: [0, 0, 0], box: [0.6, 1.2, 0.6], vel: [0, 0.5, 0], spread: [0.3, 0.2, 0.3], life: 0.9, size: 0.16, colA: 0x0c0c12, bright: 1, normal: true });
  api.hoodSmoke = P(90, { center: [0, 0, 0], box: [0.4, 0.2, 0.4], vel: [0, 0.9, 0], spread: [0.15, 0.2, 0.15], life: 2.2, size: 0.14, colA: 0x2a2a30, bright: 1, normal: true, swirl: 0.25 });
  api.burst = P(500, { burst: true, center: [0, 0, 0], box: [1, 0.5, 1], vel: [0, 0.5, 0], speed: 14, life: 2.2, size: 0.06, colA: 0x5ac8ff, bright: 1.8, drag: 1.4, grav: 2 });
  api.bigBurst = P(900, { burst: true, center: [0, 0, 0], box: [20, 2, 20], vel: [0, 1.5, 0], speed: 9, life: 4, size: 0.07, colA: 0xffa030, bright: 1.8, drag: 0.8, grav: 0.6, seed: 9 });
  api.crownBurst = P(260, { burst: true, center: [0, 0, 0], box: [0.6, 0.4, 0.6], vel: [0, 0, 0], speed: 7, life: 2, size: 0.06, colA: 0x7ad0ff, bright: 2, drag: 1.2, grav: 6, seed: 5 });
  const arrowGeo = new THREE.BoxGeometry(0.05, 0.05, 0.9);
  const arrowMat = new THREE.MeshStandardMaterial({ color: 0x9adfff, emissive: 0x3ab0ff, emissiveIntensity: 1.6 });
  api.arrowMesh = new THREE.InstancedMesh(arrowGeo, arrowMat, 70);
  api.arrowMesh.frustumCulled = false;
  reg(api.arrowMesh);
  const gift = makeJack(0.32);
  gift.userData.setOn(1.2);
  api.gift = reg(gift);
  S.fxApi = api;
  return api;
}
