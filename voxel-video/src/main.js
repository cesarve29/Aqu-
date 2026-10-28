// BLOCKCRAFT: LA LEYENDA DE LA DRAGONA
// Cada fotograma es una funcion pura de t: renderAt(t) -> imagen. Asi se puede
// renderizar en paralelo y de forma reproducible.
import * as THREE from 'three';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';
import { clamp, lerp, smooth, ramp, sramp, pulse, V, keyed, spline, actionProgress, lerpAngle, hash2, rng } from './util.js';
import { makeAtlas } from './atlas.js';
import { TimedWorld, worldMaterials, B, BLOCK_TILE } from './voxel.js';
import { genOverworld, genEnd } from './world.js';
import { humanoid, creeper, spider, dragon, poseHumanoid, poseCreeper, poseSpider, poseDragon, makeSword, makeBow, makeArrow } from './entities.js';
import { makeSky, makeClouds, makeWater, portalMaterial, Particles, makePost } from './fx.js';
import { HUD } from './hud.js';
import * as S from './story.js';

const Q = new URLSearchParams(location.search);
const W = +(Q.get('w') || 1920), H = +(Q.get('h') || 1080);
const PI = Math.PI;

const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
document.body.appendChild(renderer.domElement);

const post = makePost(renderer, W, H);
const fxaa = new ShaderPass(FXAAShader);
fxaa.uniforms.resolution.value.set(1 / W, 1 / H);
post.composer.insertPass(fxaa, post.composer.passes.length - 1);

const camera = new THREE.PerspectiveCamera(60, W / H, 0.05, 1200);
const atlas = makeAtlas();
const mats = worldMaterials(atlas);
const hud = new HUD(W, H, atlas);
const out = document.createElement('canvas');
out.width = W; out.height = H;
const g2 = out.getContext('2d');

const col = (hex) => { const c = new THREE.Color(hex); return [c.r, c.g, c.b]; };
const tileCol = (b) => { const c = atlas.avg[BLOCK_TILE(b)]; return [c.r, c.g, c.b]; };

// =====================================================================  MUNDO NORMAL
const OV = genOverworld();
const over = { scene: new THREE.Scene() };
over.tw = new TimedWorld(OV.world, atlas, mats, OV.edits);
over.scene.add(over.tw.group);
over.sky = makeSky('over'); over.scene.add(over.sky);
over.clouds = makeClouds(); over.scene.add(over.clouds);
over.water = makeWater(600, S.SEA + 0.88); over.scene.add(over.water);
over.sun = new THREE.DirectionalLight(0xffffff, 2);
over.sun.castShadow = true;
over.sun.shadow.mapSize.set(2048, 2048);
over.sun.shadow.bias = -0.0004;
over.sun.shadow.normalBias = 0.04;
over.scene.add(over.sun, over.sun.target);
over.hemi = new THREE.HemisphereLight(0xbfd8ff, 0x6b5a40, 0.8); over.scene.add(over.hemi);
over.amb = new THREE.AmbientLight(0x4050a0, 0.1); over.scene.add(over.amb);
over.lamps = [new THREE.PointLight(0xffa040, 0, 14, 1.6), new THREE.PointLight(0xffa040, 0, 14, 1.6)];
over.lamps[0].position.set(52.5, 18.5, 56.6); over.lamps[1].position.set(54.5, 18.5, 56.6);
over.scene.add(...over.lamps);
over.scene.fog = new THREE.Fog(0xa9cdf5, 70, 260);
over.parts = new Particles(9000, false); over.add = new Particles(9000, true);
over.scene.add(over.parts.points, over.add.points);
// portal del mundo normal
over.portalMat = portalMaterial('nether');
over.portal = new THREE.Mesh(new THREE.PlaneGeometry(2, 3), over.portalMat);
over.portal.position.set(S.PORTAL.x0 + 2, S.PORTAL.y0 + 2.5, S.PORTAL.z + 0.5);
over.scene.add(over.portal);
over.portalLight = new THREE.PointLight(0xb050ff, 0, 12, 1.5);
over.portalLight.position.set(64, 19.5, 79);
over.scene.add(over.portalLight);
// espada flotante sobre la mesa
const tableSword = makeSword(1.3);
over.scene.add(tableSword);

// =====================================================================  EL FIN
const EN = genEnd();
const end = { scene: new THREE.Scene() };
end.tw = new TimedWorld(EN.world, atlas, mats, []);
end.scene.add(end.tw.group);
end.sky = makeSky('end'); end.scene.add(end.sky);
end.sun = new THREE.DirectionalLight(0xc8b6e6, 1.3);
end.sun.castShadow = true;
end.sun.shadow.mapSize.set(2048, 2048);
end.sun.shadow.bias = -0.0004;
end.sun.shadow.normalBias = 0.04;
end.scene.add(end.sun, end.sun.target);
end.scene.add(new THREE.HemisphereLight(0x8a78a8, 0x2a2238, 1.4));
end.scene.add(new THREE.AmbientLight(0x40305a, 0.6));
end.scene.fog = new THREE.Fog(0x0d0714, 50, 210);
end.parts = new Particles(9000, false); end.add = new Particles(12000, true);
end.scene.add(end.parts.points, end.add.points);
// cristales
const crystalMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(0xff6ad5).multiplyScalar(3) });
const cageMat = new THREE.LineBasicMaterial({ color: new THREE.Color(0xffd0ff).multiplyScalar(2), transparent: true, opacity: 0.9 });
const beamMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(0xff8ae0).multiplyScalar(2.5), transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false });
end.crystals = S.PILLARS.map((p) => {
  const g = new THREE.Group();
  const inner = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.9, 0.9), crystalMat);
  const c1 = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1.6, 1.6, 1.6)), cageMat);
  const c2 = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2.1, 2.1, 2.1)), cageMat);
  g.add(inner, c1, c2);
  g.position.set(p.x + 0.5, S.END_TOP + p.h + 3.2, p.z + 0.5);
  end.scene.add(g);
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 1, 6, 1, true), beamMat);
  end.scene.add(beam);
  return { g, inner, c1, c2, beam };
});
end.portalMat = portalMaterial('end');
end.portal = new THREE.Mesh(new THREE.CircleGeometry(3.05, 40), end.portalMat);
end.portal.rotation.x = -PI / 2;
end.portal.position.set(S.END_C[0] + 0.5, S.END_TOP + 0.9, S.END_C[1] + 0.5);
end.scene.add(end.portal);
// huevo de dragona
const egg = new THREE.Group();
{
  const em = new THREE.MeshLambertMaterial({ color: 0x1a0d22, emissive: 0x1a0626 });
  [[0.5, 0.15], [0.85, 0.45], [0.95, 0.75], [0.85, 1.05], [0.6, 1.3], [0.3, 1.48]].forEach(([s, y]) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(s, 0.32, s), em); m.position.y = y; m.castShadow = true; egg.add(m);
  });
  egg.position.set(S.END_C[0] + 0.5, S.END_TOP + 5, S.END_C[1] + 0.5);
  end.scene.add(egg);
}
// rayos de luz de la muerte de la dragona
const deathBeams = new THREE.Group();
{
  const r = rng(99);
  for (let i = 0; i < 30; i++) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 1), new THREE.MeshBasicMaterial({
      color: new THREE.Color().setHSL(0.85 + r() * 0.2, 0.9, 0.7).multiplyScalar(1.5), transparent: true, opacity: 0.4,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    const piv = new THREE.Group();
    piv.rotation.set(r() * PI * 2, r() * PI * 2, 0);
    m.position.z = 0.5;
    piv.add(m);
    piv.userData.seed = r();
    deathBeams.add(piv);
  }
  end.scene.add(deathBeams);
}

// =====================================================================  PERSONAJES
const player = humanoid('hero');
const sword = makeSword(1);
sword.rotation.set(-PI / 2 + 0.25, 0, 0);
sword.position.set(0, 0, 0.12);
player.hand.add(sword);
const bow = makeBow(1);
bow.rotation.set(0, PI / 2, 0);
player.handL.add(bow);

const mobs = S.MOBS.map((m) => {
  let e;
  if (m.type === 'zombie') e = humanoid('zombie');
  else if (m.type === 'skeleton') { e = humanoid('skeleton'); const b = makeBow(0.9); b.rotation.set(0, PI / 2, 0); e.handL.add(b); }
  else if (m.type === 'creeper') e = creeper();
  else e = spider();
  over.scene.add(e.root);
  return { def: m, e };
});
const drag = dragon();
end.scene.add(drag.root);

const arrows = [];
for (let i = 0; i < 12; i++) { const a = makeArrow(); a.visible = false; arrows.push(a); }
arrows.slice(0, 4).forEach((a) => over.scene.add(a));
arrows.slice(4).forEach((a) => end.scene.add(a));

// mano en primera persona
const fp = new THREE.Group();
{
  const skin = new THREE.MeshLambertMaterial({ color: 0xd9a27a });
  const sleeve = new THREE.MeshLambertMaterial({ color: 0x2aa6a6 });
  const arm = new THREE.Group();
  const a1 = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.16, 0.56), skin); a1.position.z = -0.1; arm.add(a1);
  const a2 = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.17, 0.2), sleeve); a2.position.z = 0.26; arm.add(a2);
  fp.add(arm);
  const fsw = makeSword(0.9);
  fsw.position.set(0, 0.06, -0.36);
  fsw.rotation.set(-0.5, 0.1, 0.35);
  arm.add(fsw);
  fp.userData = { arm, sword: fsw };
  camera.add(fp);
}

// =====================================================================  JUGADOR
const yawKeyed = (keys, t) => {
  if (t <= keys[0][0]) return keys[0][3];
  for (let i = 0; i < keys.length - 1; i++) {
    if (t <= keys[i + 1][0]) return lerpAngle(keys[i][3], keys[i + 1][3], smooth((t - keys[i][0]) / (keys[i + 1][0] - keys[i][0])));
  }
  return keys[keys.length - 1][3];
};
const pKeys = (t) => (t < S.T_END || t >= S.T_CREDITS ? S.PLAYER_OVER : S.PLAYER_END);
const groundOver = (x, z) => OV.heights[clamp(Math.floor(x), 0, 127) * 128 + clamp(Math.floor(z), 0, 127)] + 1;
const groundEnd = (x, z) => EN.world.top(Math.floor(x), Math.floor(z)) + 1;
const pXZ = (t) => keyed(pKeys(t), t);
// tabla de distancia recorrida (fase de la animacion de caminar y pasos)
const DT = 0.05;
const DIST = new Float32Array(Math.ceil(S.DUR / DT) + 2);
for (let i = 1; i < DIST.length; i++) {
  const a = pXZ((i - 1) * DT), b = pXZ(i * DT);
  const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
  DIST[i] = DIST[i - 1] + (d < 2 ? d : 0);
}
const distAt = (t) => DIST[clamp(Math.floor(t / DT), 0, DIST.length - 1)];
const ACTIONS = [...S.PUNCHES, ...S.SWINGS, ...S.PLACES].sort((a, b) => a - b);

function health(t) {
  let h = 20;
  const ev = [...S.DAMAGE.map(([tt, d]) => ({ t: tt, d })), ...S.REGEN.map(([a, b]) => ({ t: a, b }))].sort((x, y) => x.t - y.t);
  for (const e of ev) {
    if (e.t > t) break;
    if (e.d) h -= e.d;
    else h = lerp(h, 20, ramp(t, e.t, e.b));
  }
  return Math.max(1, Math.round(h));
}

function playerState(t) {
  const [x, z] = pXZ(t);
  const isEnd = t >= S.T_END && t < S.T_CREDITS;
  let y = isEnd ? groundEnd(x, z) : groundOver(x, z);
  const a = pXZ(t - 0.1), b = pXZ(t + 0.1);
  const speed = Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.2;
  const walk = clamp(speed / 3);
  let yaw = yawKeyed(pKeys(t), t);
  if (speed > 0.6) yaw = lerpAngle(yaw, Math.atan2(b[0] - a[0], b[1] - a[1]), clamp((speed - 0.6) / 1.5));
  // knockback de la explosion y saltos
  y += Math.sin(PI * ramp(t, 143.5, 144.1)) * 1.0;
  y += Math.sin(PI * ramp(t, 265.4, 266.3)) * 0.9;
  y += Math.sin(PI * ramp(t, 274.2, 275.0)) * 1.3;
  if (t > 299.4 && isEnd) y -= 2.5 * sramp(t, 299.4, 300.4);
  const swing = actionProgress(ACTIONS, t, 0.45);
  let bowP = 0, bowHold = isEnd && t > 216.5 && t < 240;
  for (const r of S.RELEASE) if (t > r - 1.1 && t < r + 0.05) bowP = ramp(t, r - 1.0, r - 0.1);
  const raise = Math.max(pulse(t, 159.4, 163.8, 0.5), pulse(t, 292.2, 298.4, 0.5));
  let hurt = 0;
  for (const [dt] of S.DAMAGE) if (t >= dt && t < dt + 0.35) hurt = 1 - (t - dt) / 0.35;
  const down = sramp(t, 143.7, 144.3) * (1 - sramp(t, 146.2, 147.4));
  return { pos: V(x, y, z), yaw, walk, phase: distAt(t) * 2.4, swing, bow: bowP, bowHold, raise, hurt, down, hasSword: t > 64.8 };
}
const PS = (t) => playerState(t).pos;
const eye = (t) => PS(t).add(V(0, 1.62, 0));

// =====================================================================  MONSTRUOS
function mobState(m, t) {
  const d = m.def;
  let [x, z] = keyed(d.keys, t, (u) => u);
  let y = 0;
  if (d.leap && t >= d.leap[0]) {
    const u = ramp(t, d.leap[0], d.leap[1]);
    x = lerp(x, d.leap[2], u); z = lerp(z, d.leap[3], u);
    y += Math.sin(PI * u) * 2.6;
  }
  const p = PS(t);
  let kx = 0, kz = 0;
  for (const h of d.hits || []) {
    if (t <= h) continue;
    const dx = x - p.x, dz = z - p.z, l = Math.hypot(dx, dz) || 1;
    const k = 0.7 * sramp(t, h, h + 0.25);
    kx += (dx / l) * k; kz += (dz / l) * k;
    y += Math.sin(PI * ramp(t, h, h + 0.3)) * 0.35;
  }
  x += kx; z += kz;
  y += groundOver(x, z);
  if (d.rise) y -= 1.9 * (1 - sramp(t, d.spawn, d.spawn + 3.2));
  const a = keyed(d.keys, t - 0.1, (u) => u), b = keyed(d.keys, t + 0.1, (u) => u);
  const walk = clamp(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.2 / 1.5);
  let hurt = 0;
  for (const h of d.hits || []) if (t >= h && t < h + 0.3) hurt = 1 - (t - h) / 0.3;
  const dead = d.die ? ramp(t, d.die, d.die + 0.45) : 0;
  const visible = t >= d.spawn && (!d.die || t < d.die + 0.75) && (!d.boom || t < d.boom);
  const yaw = Math.atan2(p.x - x, p.z - z);
  return { pos: V(x, y, z), yaw, walk, phase: t * 6.5, hurt, dead, visible };
}

// =====================================================================  DRAGONA
const circ = (t, R = 30, Y = 47) => { const a = t * 0.26; return V(48 + R * Math.cos(a), Y + 3 * Math.sin(t * 0.7), 48 + R * Math.sin(a)); };
const PERCH = V(48.5, 37.6, 47.0);
const DK1 = [[240, ...circ(240).toArray()], [242.6, 70, 42, 74], [245.3, 49.5, 34.5, 63], [247.5, 47, 42, 40], [249.0, 38, 39, 46], [252.0, 37, 39, 47], [254.5, ...PERCH.toArray()]];
const DK2 = [[265.5, ...PERCH.toArray()], [267.3, 60, 44, 38], [269.2, 52, 48, 24], [271.0, 32, 44, 40], [273.0, ...PERCH.toArray()]];
function dragonPos(t) {
  if (t < 240) return circ(t);
  if (t < 254.5) return spline(DK1, t);
  if (t < 265.5) return PERCH.clone().add(V(0, Math.sin(t * 1.5) * 0.15, 0));
  if (t < 273.0) return spline(DK2, t);
  if (t < S.DRAGON_DIE[0]) return PERCH.clone().add(V(0, Math.sin(t * 1.5) * 0.15, 0));
  return PERCH.clone().add(V(0, 22 * sramp(t, S.DRAGON_DIE[0], 288), 0));
}
function dragonState(t) {
  const pos = dragonPos(t);
  const perch = (t >= 254.5 && t < 265.5) || (t >= 273 && t < S.DRAGON_DIE[0]);
  const hover = t >= 248.6 && t < 252.0;
  const dying = t >= S.DRAGON_DIE[0];
  let look;
  if (perch) look = pos.clone().add(V(0, 0, 1));
  else if (hover) look = V(52, 31, 57);
  else if (dying) look = pos.clone().add(V(Math.sin(t * 0.4), 0.1, Math.cos(t * 0.4)));
  else look = dragonPos(t + 0.15);
  const v1 = dragonPos(t + 0.2).sub(dragonPos(t)), v2 = dragonPos(t + 0.4).sub(dragonPos(t + 0.2));
  const bank = perch || hover || dying ? 0 : clamp(-v1.clone().cross(v2).y * 4, -0.6, 0.6);
  let hurt = 0;
  for (const h of [...S.DRAGON_HITS, S.DRAGON_CRIT]) if (t >= h + 0.12 && t < h + 0.45) hurt = 1 - (t - h - 0.12) / 0.33;
  let hp = 1;
  for (const h of S.DRAGON_HITS) hp -= 0.125 * sramp(t, h + 0.12, h + 0.4);
  hp -= 0.25 * sramp(t, S.DRAGON_CRIT + 0.12, S.DRAGON_CRIT + 0.5);
  const roar = Math.max(pulse(t, 205.5, 207.5), pulse(t, 209.3, 211), pulse(t, 240.3, 241.8), pulse(t, 265.4, 266.8), pulse(t, 275.6, 279), pulse(t, 248.6, 252, 0.2));
  return { pos, look, bank, perch, hover, dying, hurt, hp: clamp(hp), roar, visible: t >= S.T_END && t < S.DRAGON_DIE[1] + 0.2 };
}

// =====================================================================  PARTICULAS
const smokeC = [col(0x9a9a9a), col(0xbcbcbc), col(0x7a7a7a), col(0xdddddd)];
const fireC = [col(0xffd040), col(0xff7a10), col(0xffaa30)];
const purpleC = [col(0xb04aff), col(0xe08aff), col(0x7a20d0)];
const pinkC = [col(0xff6ad5), col(0xffd0ff), col(0xff9ae8)];
{
  const P = over.parts, A = over.add;
  const tr = S.TREE;
  for (const t of S.PUNCHES) P.add({ t0: t + 0.15, n: 4, pos: [tr.x + 0.5, 17.6 + Math.min(4, S.LOG_BREAK.filter((b) => b < t).length) * 1, tr.z + 0.2], spread: [0.3, 0.3, 0.1], vel: [-0.5, 1.5, 0], vs: [1, 1, 1], life: 0.6, size: 0.09, colors: [tileCol(B.LOG)], grav: -12 });
  S.LOG_BREAK.forEach((t, i) => P.add({ t0: t, n: 26, pos: [tr.x + 0.5, tr.y0 + i + 0.5, tr.z + 0.5], spread: [0.4, 0.4, 0.4], vel: [0, 1.6, 0], vs: [1.6, 1.4, 1.6], life: 0.9, size: 0.12, colors: [tileCol(B.LOG), col(0x8a6a40)], grav: -14 }));
  A.add({ t0: 61.8, t1: 64.6, rate: 40, pos: [S.TABLE.x + 0.5, 18.6, S.TABLE.z + 0.5], spread: [0.5, 0.6, 0.5], vel: [0, 0.4, 0], vs: [0.3, 0.3, 0.3], life: 1.2, size: 0.08, colors: [col(0x9ffff4), col(0xffffff)], grav: 0 });
  for (const m of S.MOBS) {
    if (m.rise) P.add({ t0: m.spawn, t1: m.spawn + 3.2, rate: 25, pos: [m.keys[0][1], 17.1, m.keys[0][2]], spread: [0.5, 0.05, 0.5], vel: [0, 1.6, 0], vs: [1.0, 0.8, 1.0], life: 0.8, size: 0.1, colors: [tileCol(B.DIRT), tileCol(B.GRASS)], grav: -10 });
    if (m.die) {
      const fin = m.leap ? [m.leap[2], m.leap[3]] : m.keys[m.keys.length - 1].slice(1);
      P.add({ t0: m.die + 0.65, n: 40, pos: [fin[0], 17.6, fin[1]], spread: [0.5, 0.5, 0.5], vel: [0, 1.3, 0], vs: [0.8, 0.6, 0.8], life: 1.2, size: 0.22, colors: smokeC, grav: 0.4, drag: 1.5, grow: 1 });
    }
    for (const h of m.hits || []) {
      A.add({ t0: h, n: 14, pos: [0, 1.3, 0], spread: [0.3, 0.3, 0.3], vel: [0, 1.5, 0], vs: [2, 1.5, 2], life: 0.45, size: 0.09, colors: [col(0xffffff), col(0xfff3a0)], grav: -6, posFn: (tt) => mobState(mobs.find((q) => q.def === m), h).pos });
    }
  }
  // explosion
  const K = S.CRATER;
  P.add({ t0: K.t, n: 220, pos: [K.x + 0.5, K.y + 1, K.z + 0.5], spread: [1, 0.6, 1], vel: [0, 2.6, 0], vs: [4.5, 3.5, 4.5], life: 3.2, size: 0.8, colors: smokeC, grav: 0.3, drag: 1.2, grow: 2 });
  A.add({ t0: K.t, n: 160, pos: [K.x + 0.5, K.y + 1, K.z + 0.5], spread: [0.6, 0.4, 0.6], vel: [0, 3, 0], vs: [7, 6, 7], life: 0.9, size: 0.45, colors: fireC, grav: -3, drag: 2.5 });
  P.add({ t0: K.t, n: 140, pos: [K.x + 0.5, K.y + 0.5, K.z + 0.5], spread: [1.2, 0.5, 1.2], vel: [0, 7, 0], vs: [6, 4, 6], life: 1.8, size: 0.16, colors: [tileCol(B.GRASS), tileCol(B.DIRT), tileCol(B.STONE)], grav: -18 });
  P.add({ t0: K.t + 0.5, t1: K.t + 9, rate: 10, pos: [K.x + 0.5, K.y + 0.6, K.z + 0.5], spread: [2, 0.3, 2], vel: [0.3, 1.2, 0], vs: [0.3, 0.3, 0.3], life: 3, size: 0.6, colors: smokeC, grav: 0, drag: 0.6, grow: 1.5 });
  // flechas que se clavan
  for (const [, ta, x, y, z] of S.SK_ARROWS) P.add({ t0: ta, n: 10, pos: [x, y, z], spread: [0.1, 0.1, 0.1], vel: [0, 1.4, 0], vs: [1, 1, 1], life: 0.5, size: 0.08, colors: [tileCol(B.DIRT)], grav: -12 });
  // construccion del portal
  for (const t of S.PORTAL_PLACE) P.add({ t0: t, n: 10, pos: [64, 18.5, 80.5], spread: [2, 2, 0.5], vel: [0, 0.6, 0], vs: [0.5, 0.5, 0.5], life: 0.6, size: 0.08, colors: [col(0x2a1a44), col(0x6a3aa0)], grav: -6 });
  A.add({ t0: 188.6, n: 40, pos: [64, 18.2, 80.4], spread: [0.4, 0.1, 0.2], vel: [0, 2, 0], vs: [2, 2, 2], life: 0.5, size: 0.06, colors: fireC, grav: -8 });
  A.add({ t0: S.PORTAL_LIT, t1: 200, rate: 45, pos: [64, 19.5, 80.5], spread: [1.2, 1.6, 0.6], vel: [0, 0.5, 0], vs: [0.6, 0.6, 0.6], life: 2.0, size: 0.09, colors: purpleC, grav: 0 });
  A.add({ t0: 159.6, n: 80, pos: [64.8, 19.5, 64.6], spread: [0.5, 0.5, 0.5], vel: [0, 2.5, 0], vs: [2.5, 2.5, 2.5], life: 1.5, size: 0.1, colors: [col(0x8aff40), col(0xd0ff60)], grav: -2 });
  // luciernagas nocturnas
  A.add({ t0: 84, t1: 168, rate: 5, pos: [64, 18, 66], spread: [22, 2.5, 22], vel: [0, 0.2, 0], vs: [0.3, 0.2, 0.3], life: 6, size: 0.07, colors: [col(0xd8ff60), col(0xfff080)], grav: 0 });
}
{
  const P = end.parts, A = end.add;
  A.add({ t0: 199, t1: 335, rate: 22, pos: [48, 36, 48], spread: [60, 18, 60], vel: [0, 0.25, 0], vs: [0.2, 0.2, 0.2], life: 8, size: 0.14, colors: purpleC, grav: 0, fade: 1 });
  S.CRYSTAL_BOOM.forEach((t, k) => {
    const p = S.PILLARS[k], y = S.END_TOP + p.h + 3.2;
    A.add({ t0: t, n: 200, pos: [p.x + 0.5, y, p.z + 0.5], spread: [0.5, 0.5, 0.5], vel: [0, 1, 0], vs: [8, 7, 8], life: 1.0, size: 0.5, colors: [...fireC, ...pinkC], grav: -2, drag: 2 });
    P.add({ t0: t, n: 120, pos: [p.x + 0.5, y, p.z + 0.5], spread: [1, 1, 1], vel: [0, 1.5, 0], vs: [4, 3, 4], life: 3, size: 1.0, colors: smokeC, grav: 0.2, drag: 1.2, grow: 2 });
  });
  // aliento de la dragona
  A.add({ t0: 248.6, t1: 252.5, rate: 120, pos: [51.2, 31.6, 57.2], spread: [2.6, 0.5, 2.6], vel: [0, 0.4, 0], vs: [0.6, 0.4, 0.6], life: 2.6, size: 0.55, colors: purpleC, grav: 0, grow: 1 });
  A.add({ t0: 248.6, t1: 251.2, rate: 90, pos: [0, 0, 0], spread: [0.4, 0.4, 0.4], vel: [0, -2.5, 0], vs: [1.5, 1, 1.5], life: 1.0, size: 0.35, colors: purpleC, grav: -4, posFn: (tt) => dragHead.clone() });
  for (const h of [...S.DRAGON_HITS, S.DRAGON_CRIT]) A.add({ t0: h + 0.12, n: h === S.DRAGON_CRIT ? 90 : 22, pos: [48.5, 33.0, 58.6], spread: [0.6, 0.6, 0.4], vel: [0, 2, 1], vs: [3, 2.5, 3], life: 0.6, size: 0.12, colors: [col(0xffffff), col(0xfff3a0), col(0xb0f0ff)], grav: -6 });
  // muerte
  A.add({ t0: 276, t1: 290, rate: 150, pos: [0, 0, 0], spread: [3, 2, 4], vel: [0, 0, 0], vs: [6, 6, 6], life: 1.4, size: 0.3, colors: [...pinkC, col(0xffffff), col(0xffe080)], grav: 0, drag: 1, posFn: (tt) => dragonPos(tt) });
  A.add({ t0: 286, t1: 292.5, rate: 30, pos: [48.5, 40, 47], spread: [6, 6, 6], vel: [0, -1.5, 0], vs: [2, 1, 2], life: 2.5, size: 0.22, colors: [col(0x8aff40), col(0xd8ff60)], grav: -2 });
  A.add({ t0: S.EXIT_PORTAL, t1: 335, rate: 20, pos: [48.5, 31.2, 48.5], spread: [2.5, 0.2, 2.5], vel: [0, 0.8, 0], vs: [0.2, 0.3, 0.2], life: 2.5, size: 0.08, colors: [col(0x80ffee), col(0xffffff)], grav: 0 });
}
let dragHead = V();

// =====================================================================  ENTORNO
const SUN_EL = [[0, -4], [12, 13], [40, 40], [66, 46], [75, 28], [84, 3], [90, -10], [94, -30], [100, -45], [160, -45], [166, -16], [172, 1], [180, 13], [200, 22], [303, -3], [318, 7], [335, 13]];
const C3 = (h) => new THREE.Color(h);
const PAL = {
  dTop: C3(0x3f7ae8), dHor: C3(0xa6cbf3), sTop: C3(0x34407e), sHor: C3(0xff8448), nTop: C3(0x02030a), nHor: C3(0x0a1230),
};
function envOver(t, focus, shadowSize) {
  const el = keyed(SUN_EL, t)[0] * PI / 180;
  const az = 0.55 + t * 0.0008;
  const sd = V(Math.cos(el) * Math.cos(az), Math.sin(el), Math.cos(el) * Math.sin(az));
  const se = Math.sin(el);
  const day = smooth((se + 0.1) / 0.32);
  const ss = Math.exp(-Math.pow((se - 0.02) / 0.14, 2));
  const top = PAL.nTop.clone().lerp(PAL.dTop, day).lerp(PAL.sTop, ss * 0.45);
  const hor = PAL.nHor.clone().lerp(PAL.dHor, day).lerp(PAL.sHor, ss * 0.85);
  const glow = C3(0xffd090).lerp(C3(0xff5a18), ss);
  const night = 1 - day;
  const u = over.sky.material.uniforms;
  u.sunDir.value.copy(sd); u.top.value.copy(top); u.hor.value.copy(hor); u.glow.value.copy(glow); u.night.value = night; u.uTime.value = t;
  const moon = sd.clone().negate();
  const useSun = se > -0.06;
  const ld = useSun ? sd : moon;
  over.sun.position.copy(focus).addScaledVector(ld, 90);
  over.sun.target.position.copy(focus);
  over.sun.intensity = useSun ? 2.7 * smooth((se + 0.06) / 0.25) : 1.1 * smooth((-se - 0.06) / 0.2);
  over.sun.color.copy(useSun ? C3(0xfff1dc).lerp(C3(0xff9050), ss) : C3(0x9db4ff));
  const sc = over.sun.shadow.camera;
  sc.left = sc.bottom = -shadowSize; sc.right = sc.top = shadowSize; sc.near = 1; sc.far = 220;
  sc.updateProjectionMatrix();
  over.hemi.color.copy(top.clone().lerp(C3(0xffffff), 0.35));
  over.hemi.groundColor.copy(C3(0x6b5a40).lerp(C3(0x101020), night));
  over.hemi.intensity = lerp(0.75, 0.95, day);
  over.hemi.color.lerp(C3(0x6a86d0), night);
  over.amb.intensity = lerp(0.6, 0.08, day);
  over.scene.fog.color.copy(hor);
  const lampOn = smooth(night * 1.4 - 0.2);
  over.lamps.forEach((l) => { l.intensity = 9 * lampOn; });
  const wu = over.water.material.uniforms;
  wu.uTime.value = t; wu.sunDir.value.copy(useSun ? sd : moon); wu.top.value.copy(top); wu.hor.value.copy(hor);
  wu.sunCol.value.copy(useSun ? glow : C3(0x6070a0)); wu.night.value = night;
  const cu = over.clouds.material.uniforms;
  cu.uTime.value = t;
  cu.light.value.copy(C3(0xffffff).lerp(C3(0xffb080), ss * 0.7).multiplyScalar(lerp(0.12, 1.15, day)));
  return { day, night };
}
function envEnd(t, focus) {
  end.sky.material.uniforms.uTime.value = t;
  end.sun.position.copy(focus).add(V(30, 80, 20));
  end.sun.target.position.copy(focus);
  const sc = end.sun.shadow.camera;
  sc.left = sc.bottom = -55; sc.right = sc.top = 55; sc.near = 1; sc.far = 220;
  sc.updateProjectionMatrix();
}

// =====================================================================  CAMARA
const orbit = (c, R, Y, a) => V(c.x + R * Math.cos(a), c.y + Y, c.z + R * Math.sin(a));
const MZ = V(64.5, 17, 66.5);
const behind = (t, back, up, side = 0) => {
  const p = playerState(t);
  const f = V(Math.sin(p.yaw), 0, Math.cos(p.yaw)), r = V(Math.cos(p.yaw), 0, -Math.sin(p.yaw));
  return p.pos.clone().addScaledVector(f, -back).add(V(0, up, 0)).addScaledVector(r, side);
};
const mobPos = (id, t) => mobState(mobs.find((m) => m.def.id === id), t).pos;
const crystalPos = (k) => end.crystals[k].g.position.clone();

const SHOTS = [];
const shot = (t0, t1, fn) => SHOTS.push({ t0, t1, fn });
// --- titulo y vuelos
shot(0, 12, (t) => ({ pos: orbit(MZ, 78, 46, -0.9 + t * 0.03), target: MZ.clone().add(V(0, 4, 0)), fov: 55 }));
shot(12, 21, (t) => { const u = ramp(t, 12, 21); return { pos: V(lerp(8, 44, u), lerp(52, 40, u), lerp(120, 100, u)), target: V(lerp(60, 80, u), 18, lerp(40, 30, u)), fov: 62 }; });
shot(21, 30, (t) => { const u = ramp(t, 21, 30); return { pos: V(lerp(72, 66, u), lerp(20, 38, u), lerp(142, 110, u)), target: V(64, lerp(20, 16, u), lerp(96, 66, u)), fov: 60, shadow: 60 }; });
shot(30, 40, (t) => { const u = sramp(t, 30, 40); return { pos: V(lerp(36, 48.5, u), lerp(34, 20.2, u), lerp(88, 68, u)), target: V(lerp(54, 53.5, u), lerp(17, 18.2, u), lerp(60, 57, u)), fov: 50 }; });
// --- dia
shot(40, 48, (t) => { const p = PS(t); return { pos: p.clone().add(V(-1.5, 1.9, 5.8)), target: p.clone().add(V(0.8, 1.1, 0)), fov: 52 }; });
shot(48, 52.2, () => ({ pos: V(65.2, 18.4, 63.6), target: V(69.6, 18.4, 58.4), fov: 55 }));
shot(52.2, 55.0, (t) => ({ pos: eye(t), target: V(70.5, 17.5 + S.LOG_BREAK.slice(0, 2).reduce((a, b) => a + sramp(t, b - 0.1, b + 0.5), 0), 58.5), fov: 70, fp: true }));
shot(55.0, 57.6, (t) => ({ pos: V(lerp(63.2, 62.6, ramp(t, 55, 57.6)), 19.4, 63.4), target: V(69.5, 19.6, 58.5), fov: 55 }));
shot(57.6, 61, (t) => { const p = PS(t); return { pos: V(63.8, 19.8, 64.8), target: p.clone().add(V(0, 1, 0)), fov: 50 }; });
shot(61, 66, (t) => ({ pos: V(lerp(62.8, 61.9, ramp(t, 61, 66)), 19.2, 60.2), target: V(60.4, 18.4, 56.8), fov: 45 }));
shot(66, 70.5, (t) => { const p = playerState(t); const e = eye(t); return { pos: e, target: e.clone().add(V(Math.sin(p.yaw) * 4, -0.6, Math.cos(p.yaw) * 4)), fov: 70, fp: true }; });
shot(70.5, 75, (t) => ({ pos: orbit(PS(t), 5.5, 2.2, 1.9 + (t - 70.5) * 0.12), target: PS(t).add(V(0, 1.3, 0)), fov: 50 }));
// --- noche
shot(75, 86, (t) => ({ pos: V(lerp(34, 38, ramp(t, 75, 86)), 31, 94), target: V(63, 16, 66), fov: 55, shadow: 70 }));
shot(86, 92, (t) => ({ pos: V(66.7, 17.9, 73.4), target: V(64.5, lerp(16.4, 18.0, ramp(t, 86, 90)), 77.2), fov: 55 }));
shot(92, 100, (t) => ({ pos: behind(t, 2.6, 2.0, -1.0), target: mobPos('z1', t).add(V(0, 1.3, 0)), fov: 55 }));
shot(100, 104.6, (t) => ({ pos: orbit(MZ, 5.2, 2.2, 0.4 + (t - 100) * 0.25), target: PS(t).add(V(0, 1.1, 0.8)), fov: 55 }));
shot(104.6, 109.4, (t) => ({ pos: eye(t), target: mobPos('z2', t).add(V(0, 1.3, 0)), fov: 72, fp: true }));
shot(109.4, 114.6, () => ({ pos: V(59.8, 19.4, 71.2), target: V(63.7, 17.8, 67.0), fov: 50 }));
shot(114.6, 119.2, (t) => ({ pos: behind(t, 3, 1.75, -1.5), target: V(80.5, lerp(18.2, 19.4, ramp(t, 114.6, 119)), 57.5), fov: lerp(40, 28, ramp(t, 114.6, 119.2)) }));
shot(119.2, 125.6, () => ({ pos: V(78.2, 20.4, 73.0), target: V(72.5, 18.0, 62.0), fov: 64 }));
shot(125.6, 129.8, (t) => ({ pos: behind(t, 3.5, 2.0, 0.8), target: V(80.5, 19, 57.5), fov: 60 }));
shot(129.8, 133.2, (t) => ({ pos: eye(t), target: mobPos('sk', t).add(V(0, 1.2, 0)), fov: 72, fp: true }));
shot(133.2, 138.4, (t) => { const p = PS(t); return { pos: p.clone().add(V(-4.2, 1.8, 0.6)), target: p.clone().add(V(0, 1.2, 0)), fov: 55 }; });
shot(138.4, 141.2, () => ({ pos: V(76.4, 18.6, 73.4), target: V(71.4, 17.9, 66.6), fov: 50 }));
shot(141.2, 143.5, (t) => ({ pos: V(74.8, 18.5, 63.6), target: mobPos('cr', t).add(V(0, 1.0, 0)), fov: lerp(55, 38, ramp(t, 141.2, 143.5)) }));
shot(143.5, 147.2, () => ({ pos: V(60.5, 22.5, 75.5), target: V(71, 17.2, 67), fov: 55 }));
shot(147.2, 152, (t) => ({ pos: V(lerp(77.5, 75, ramp(t, 147.2, 152)), 23, 61.5), target: V(71.5, 16, 67.5), fov: 52 }));
shot(152, 158.4, () => ({ pos: V(68.6, 18.7, 69.6), target: V(63.4, 17.9, 66.0), fov: 58 }));
shot(158.4, 163.6, (t) => ({ pos: orbit(PS(t), 4.4, 1.4, 0.2 + (t - 158.4) * 0.22), target: PS(t).add(V(0, 1.5, 0)), fov: 52 }));
shot(163.6, 168, (t) => { const u = sramp(t, 163.6, 168); return { pos: V(64.8 + 3, lerp(19, 34, u), 64.6 - lerp(4, 18, u)), target: V(64.8, 17.5, 66), fov: 55, shadow: 50 }; });
// --- amanecer y portal
shot(168, 176, (t) => ({ pos: V(92, 30, lerp(44, 48, ramp(t, 168, 176))), target: V(64, 17, 72), fov: 50, shadow: 70 }));
shot(176, 188.2, (t) => ({ pos: orbit(V(64, 18.2, 79.5), 8.5, 2.6, 2.3 + (t - 176) * 0.07), target: V(64, 18.8, 79.8), fov: 52 }));
shot(188.2, 192, (t) => ({ pos: V(67.2, 18.6, 75.6), target: V(64, 19.2, 80.4), fov: 48 }));
shot(192, 196, (t) => ({ pos: V(65.6, 19.0, 73.2), target: V(64.2, 19.0, 80.5), fov: 52 }));
shot(196, 200, (t) => ({ pos: V(64.5, 18.7, lerp(77.0, 80.8, sramp(t, 196, 199.4))), target: V(64.5, 18.9, 85), fov: lerp(70, 100, ramp(t, 197, 200)) }));
// --- el Fin
const EC = V(48, 32, 48);
shot(200, 208, (t) => ({ pos: orbit(EC, 66, 26, 1.2 + (t - 200) * 0.05), target: EC.clone().add(V(0, 6, 0)), fov: 55 }));
shot(208, 213.5, (t) => { const d = dragonPos(t); return { pos: V(53, 32.6, 67), target: d, fov: 50 }; });
shot(213.5, 217, (t) => ({ pos: behind(t, 4, 2.2, 1), target: PS(t).add(V(0, 3, -12)), fov: 58 }));
S.RELEASE.forEach((r, k) => {
  const nxt = k < 5 ? S.RELEASE[k + 1] - 1.3 : 240;
  shot(r - 1.3, r + 0.25, (t) => { const c = crystalPos(k); const e = eye(t); const d = c.clone().sub(e).setY(0).normalize(); const side = V(d.z, 0, -d.x); const pos = e.clone().addScaledVector(d, -4.5).addScaledVector(side, -1.3).add(V(0, -0.9, 0)); return { pos, target: pos.clone().addScaledVector(d, 10).add(V(0, 4.0, 0)), fov: 62 }; });
  shot(r + 0.25, nxt, (t) => {
    const c = crystalPos(k);
    const p = PS(t);
    const away = V(c.x - p.x, 0, c.z - p.z).normalize();
    const side = V(away.z, 0, -away.x);
    return { pos: c.clone().addScaledVector(away, -11).addScaledVector(side, 6).add(V(0, -3, 0)), target: c.clone().add(V(0, -1, 0)), fov: 55 };
  });
});
shot(240, 247.4, (t) => ({ pos: V(46.2, 32.4, 62.5), target: dragonPos(t).add(V(0, 0.5, 0)), fov: 60 }));
shot(247.4, 252.6, () => ({ pos: V(64, 36, 66), target: V(47, 33, 53), fov: 55 }));
shot(252.6, 257.6, (t) => ({ pos: V(lerp(64, 60, ramp(t, 252.6, 257.6)), 36, 68), target: V(48.5, 34, 50), fov: 50 }));
shot(257.6, 261.1, (t) => ({ pos: eye(t), target: dragHead.clone(), fov: 75, fp: true }));
shot(261.1, 265.4, (t) => ({ pos: orbit(V(48.5, 31, 58.5), 9.5, 3.5, 0.1 + (t - 261.1) * 0.18), target: V(48.5, 33.8, 56.5), fov: 55 }));
shot(265.4, 272.4, (t) => ({ pos: V(54, 32.4, 70.5), target: dragonPos(t), fov: 62 }));
shot(272.4, 275.8, (t) => ({ pos: V(57.5, 33.2, 64.0), target: V(48.5, 33.6, 59.5), fov: 52 }));
shot(275.8, 289.6, (t) => ({ pos: orbit(V(48.5, 34, 47), 34, 14 + 0.5 * (t - 275.8), 0.92 + (t - 275.8) * 0.019), target: dragonPos(t), fov: 52 }));
shot(289.6, 292.2, (t) => ({ pos: V(56, 37, 59), target: V(48.5, 32, 48.5), fov: 50 }));
shot(292.2, 298.8, (t) => ({ pos: orbit(PS(t), 5, 1.8, 1.2 + (t - 292.2) * 0.2), target: PS(t).add(V(0, 1.5, 0)), fov: 50 }));
shot(298.8, 303, (t) => ({ pos: V(52.5, 37.5, 55.5), target: V(48.5, 30.5, 50), fov: 55 }));
// --- creditos
shot(303, 336, (t) => ({ pos: orbit(MZ, 70, 40, 2.0 + (t - 303) * 0.02), target: MZ.clone().add(V(0, 6, 0)), fov: 52, shadow: 80 }));

function camAt(t) {
  if (window.DEBUGCAM) return { pos: V(...window.DEBUGCAM.slice(0, 3)), target: V(...window.DEBUGCAM.slice(3, 6)), fov: 55 };
  for (const s of SHOTS) if (t >= s.t0 && t < s.t1) return s.fn(t);
  return SHOTS[SHOTS.length - 1].fn(t);
}
function shake(t) {
  let a = 0;
  const hit = (t0, A, k) => { if (t >= t0) a += A * Math.exp(-(t - t0) * k); };
  hit(S.CRATER.t, 0.6, 2.2);
  for (const b of S.CRYSTAL_BOOM) hit(b, 0.25, 3);
  for (const r of [205.5, 209.3, 240.3, 265.4, 275.6]) hit(r, 0.12, 1.5);
  for (const d of S.DAMAGE) hit(d[0], 0.18, 6);
  for (const h of [...S.DRAGON_HITS, S.DRAGON_CRIT]) hit(h + 0.12, 0.08, 6);
  hit(245.0, 0.3, 2);
  hit(254.5, 0.25, 3);
  hit(273.0, 0.2, 3);
  hit(290, 0.4, 1.5);
  if (t > 276 && t < 290) a += 0.05 + 0.1 * ramp(t, 276, 290);
  return V(Math.sin(t * 53.1) + Math.sin(t * 31.7), Math.sin(t * 47.3 + 1) + Math.sin(t * 27.9), Math.sin(t * 61.7 + 2)).multiplyScalar(a * 0.25);
}

// =====================================================================  RENDER
function posePlayer(t, scene, fpShot) {
  const p = playerState(t);
  scene.add(player.root);
  player.root.position.copy(p.pos);
  player.root.rotation.set(0, p.yaw, 0);
  poseHumanoid(player, { t, walk: p.walk, phase: p.phase, swing: p.swing, raise: p.raise, bow: p.bow, bowHold: p.bowHold });
  if (p.down > 0) { player.root.rotation.x = -p.down * 1.2; }
  const inPortal = (t > 196.6 && t < S.T_END) || (t > 300.4 && t < S.T_CREDITS);
  player.root.visible = !fpShot && !inPortal && t < S.T_CREDITS;
  sword.visible = p.hasSword && !p.bowHold;
  bow.visible = p.bowHold;
  player.M.tint(1, 0, 0, p.hurt * 0.6);
  return p;
}

function renderAt(t) {
  const isEnd = t >= S.T_END && t < S.T_CREDITS;
  const W_ = isEnd ? end : over;
  const cam = camAt(t);
  const fpShot = !!cam.fp;
  const p = posePlayer(t, W_.scene, fpShot);
  W_.scene.add(camera);

  if (!isEnd) {
    over.tw.update(t);
    const env = envOver(t, cam.shadow ? cam.target.clone() : p.pos.clone(), cam.shadow || 28);
    renderer.toneMappingExposure = lerp(1.0, 1.45, env.night);
    for (const m of mobs) {
      const st = mobState(m, t);
      const e = m.e;
      e.root.visible = st.visible && t < S.T_END;
      if (!e.root.visible) continue;
      e.root.position.copy(st.pos);
      e.root.rotation.set(0, st.yaw, 0);
      const d = m.def;
      if (d.type === 'zombie') {
        const att = actionProgress(d.attack || [], t, 0.5);
        poseHumanoid(e, { t, walk: st.walk, phase: st.phase, armsForward: true, swing: att, dead: st.dead });
      } else if (d.type === 'skeleton') {
        let bp = 0;
        for (const s of d.shots) if (t > s - 0.9 && t < s + 0.1) bp = ramp(t, s - 0.8, s);
        poseHumanoid(e, { t, walk: st.walk, phase: st.phase, bowHold: true, bow: bp, dead: st.dead });
      } else if (d.type === 'creeper') {
        const fuse = ramp(t, d.fuse, d.boom);
        poseCreeper(e, { walk: st.walk, phase: st.phase, fuse });
        const blink = fuse > 0 && Math.sin(t * (10 + fuse * 30)) > 0 ? 0.9 * fuse + 0.1 : 0;
        e.M.tint(1, 1, 1, blink);
      } else {
        poseSpider(e, { walk: t >= d.leap[0] && t < d.leap[1] ? 0 : st.walk, phase: st.phase, dead: st.dead });
      }
      if (d.type !== 'creeper') e.M.tint(1, 0, 0, Math.max(st.hurt * 0.7, st.dead * 0.6));
    }
    // flechas del esqueleto
    S.SK_ARROWS.forEach(([t0, t1, x, y, z], i) => {
      const a = arrows[i];
      const from = V(80.5, 19.1, 57.5), to = V(x, y, z);
      a.visible = t >= t0 && t < (i === 2 ? t1 : t1 + 6) && t < S.T_END;
      if (!a.visible) return;
      const u = ramp(t, t0, t1);
      const pos = from.clone().lerp(to, u).add(V(0, Math.sin(PI * u) * 1.2, 0));
      const nx = from.clone().lerp(to, Math.min(1, u + 0.02)).add(V(0, Math.sin(PI * Math.min(1, u + 0.02)) * 1.2, 0));
      a.position.copy(pos);
      if (u < 1) a.lookAt(nx);
    });
    // espada de la mesa
    tableSword.visible = t > 61.8 && t < 64.8;
    if (tableSword.visible) {
      const u = sramp(t, 64.2, 64.8);
      const base = V(S.TABLE.x + 0.5, 18.3 + Math.sin(t * 2.5) * 0.08 + sramp(t, 61.8, 62.6) * 0.3, S.TABLE.z + 0.5);
      tableSword.position.copy(base.lerp(p.pos.clone().add(V(0, 1.0, 0)), u));
      tableSword.rotation.set(0, t * 2.2, 0.35);
      tableSword.scale.setScalar(lerp(1, 0.6, u));
    }
    over.portal.visible = t >= S.PORTAL_LIT;
    over.portalMat.uniforms.open.value = sramp(t, S.PORTAL_LIT, S.PORTAL_LIT + 1.2);
    over.portalMat.uniforms.uTime.value = t;
    over.portalLight.intensity = 14 * sramp(t, S.PORTAL_LIT, S.PORTAL_LIT + 1);
    over.parts.update(t); over.add.update(t);
  } else {
    renderer.toneMappingExposure = 1.1;
    end.tw.update(t);
    envEnd(t, cam.target.clone().lerp(p.pos, 0.5));
    const ds = dragonState(t);
    drag.root.visible = ds.visible;
    drag.root.position.copy(ds.pos);
    drag.root.lookAt(ds.look);
    drag.root.rotateZ(ds.bank);
    const breath = pulse(t, 248.6, 251.4, 0.3);
    poseDragon(drag, {
      t, flap: ds.perch ? 0.15 : ds.dying ? 0.5 : 1, flapSpeed: ds.perch ? 1.2 : 3.0, fold: ds.perch ? 0.6 : 0,
      neckPitch: ds.perch ? 0.72 : ds.hover ? 0.7 : 0.15, headPitch: ds.perch ? 0.38 : breath * 0.5, jaw: Math.max(ds.roar, breath), perch: ds.perch,
    });
    drag.root.updateMatrixWorld(true);
    dragHead = drag.headP.localToWorld(V(0, 0, 2.6));
    const dieU = ramp(t, S.DRAGON_DIE[0] + 0.5, S.DRAGON_DIE[1]);
    drag.M.tint(1, ds.dying ? 0.6 : 0, ds.dying ? 0.9 : 0, Math.max(ds.hurt * 0.8, dieU * 1.5));
    drag.parts.forEach((m, i) => { m.visible = hash2(i, 7, 3) > Math.pow(ramp(t, 283, 290), 1.4); });
    deathBeams.visible = ds.dying && t < S.DRAGON_DIE[1];
    if (deathBeams.visible) {
      deathBeams.position.copy(ds.pos);
      deathBeams.rotation.y = t * 0.35;
      const L = 60 * sramp(t, 275.8, 288.5);
      deathBeams.children.forEach((pv, i) => {
        const on = ramp(t, 275.8 + pv.userData.seed * 10, 276.8 + pv.userData.seed * 10);
        pv.children[0].scale.set(0.4 + on, 0.4 + on, L * on + 0.01);
        pv.children[0].position.z = (L * on) / 2;
      });
    }
    end.crystals.forEach((c, k) => {
      const alive = t < S.CRYSTAL_BOOM[k];
      c.g.visible = alive;
      c.inner.rotation.set(t * 1.3, t * 1.7, 0);
      c.c1.rotation.set(-t * 0.9, t * 1.1, t * 0.5);
      c.c2.rotation.set(t * 0.6, -t * 0.8, t * 0.3);
      c.g.position.y = S.END_TOP + S.PILLARS[k].h + 3.2 + Math.sin(t * 2 + k) * 0.25;
      const dist = ds.pos.distanceTo(c.g.position);
      c.beam.visible = alive && ds.visible && dist < 42 && !ds.dying;
      if (c.beam.visible) {
        const a = c.g.position, b = ds.pos;
        c.beam.position.copy(a).lerp(b, 0.5);
        c.beam.scale.set(1, dist, 1);
        c.beam.quaternion.setFromUnitVectors(V(0, 1, 0), b.clone().sub(a).normalize());
      }
    });
    // flechas del jugador
    S.RELEASE.forEach((r, k) => {
      const a = arrows[4 + k];
      a.visible = t >= r && t < r + S.ARROW_FLIGHT;
      if (!a.visible) return;
      const u = ramp(t, r, r + S.ARROW_FLIGHT);
      const from = eye(r).add(V(0, -0.2, 0)), to = crystalPos(k);
      const arc = (q) => from.clone().lerp(to, q).add(V(0, Math.sin(PI * q) * 1.5, 0));
      a.position.copy(arc(u));
      a.lookAt(arc(Math.min(1, u + 0.02)));
    });
    egg.visible = t > S.EXIT_PORTAL + 0.5;
    egg.position.y = S.END_TOP + 5 + 3 * (1 - sramp(t, S.EXIT_PORTAL + 0.5, S.EXIT_PORTAL + 2));
    end.portal.visible = t > S.EXIT_PORTAL;
    end.portalMat.uniforms.open.value = sramp(t, S.EXIT_PORTAL, S.EXIT_PORTAL + 1.5);
    end.portalMat.uniforms.uTime.value = t;
    end.parts.update(t); end.add.update(t);
  }

  // camara
  camera.position.copy(cam.pos).add(shake(t));
  camera.fov = cam.fov || 60;
  camera.updateProjectionMatrix();
  camera.lookAt(cam.target);
  W_.sky.position.copy(camera.position);
  if (W_.clouds) W_.clouds.material.uniforms.camPos.value.copy(camera.position);
  const scale = H / (2 * Math.tan((camera.fov * PI) / 360));
  for (const P of [W_.parts, W_.add]) P.points.material.uniforms.scale.value = scale;
  fp.visible = fpShot;
  if (fpShot) {
    const s = p.swing;
    const arm = fp.userData.arm;
    const bobA = Math.sin(p.phase) * 0.025 * p.walk;
    arm.position.set(0.36 + bobA, -0.36 - Math.abs(bobA), -0.55);
    arm.rotation.set(0.15, 0.25, 0);
    fp.userData.sword.visible = p.hasSword;
    if (s >= 0) {
      const k = Math.sin(s * PI);
      arm.rotation.x = 0.15 - k * 0.9;
      arm.rotation.y = 0.25 + k * 0.6;
      arm.position.x -= k * 0.22;
      arm.position.z -= k * 0.18;
    }
  }

  // post
  const g = post.grade.uniforms;
  g.uTime.value = t;
  g.fade.value = Math.max(1 - ramp(t, 0, 1.8), ramp(t, 300.6, 302.6) * (t < S.T_CREDITS ? 1 : 0), t >= S.T_CREDITS ? 1 - ramp(t, S.T_CREDITS, S.T_CREDITS + 2) : 0, ramp(t, 332.5, 334.8));
  g.warp.value = t < S.T_END ? sramp(t, 196.5, 199.8) : 0;
  const fl = Math.max(pulse(t, 199.3, 201.6, 0.6), pulse(t, 289.7, 291.0, 0.35), pulse(t, S.CRATER.t, S.CRATER.t + 0.35, 0.05) * 0.8);
  g.flash.value = fl;
  g.flashCol.value.set(t > 289 && t < 292 ? 0xffe8ff : 0xffffff);
  g.hurt.value = p.hurt;
  g.vig.value = isEnd ? 0.45 : 0.35;
  g.sat.value = isEnd ? 1.15 : 1.12;
  post.bloom.strength = isEnd ? 0.85 : 0.55;
  post.bloom.threshold = 0.85;
  post.rp.scene = W_.scene;
  post.rp.camera = camera;
  post.composer.render();

  // HUD
  g2.clearRect(0, 0, W, H);
  g2.drawImage(renderer.domElement, 0, 0);
  drawHud(t, p, fpShot);
  return out;
}

function drawHud(t, p, fpShot) {
  const game = (t > 40 && t < 196) || (t > 212.5 && t < 300);
  if (game) {
    let sel = 0;
    if (t < 64.8) sel = 8;
    if (t > 175 && t < 188.3) sel = 3;
    if (t > 188.3 && t < 192) sel = 4;
    if (t > 216.5 && t < 240) sel = 1;
    const xp = 0.2 + 0.06 * S.MOBS.filter((m) => m.die && t > m.die).length + 0.4 * sramp(t, 286, 292) + (t > 292 ? 27 : 0);
    hud.hotbar(g2, sel, p.hasSword, health(t), xp);
    if (fpShot) hud.crosshair(g2);
  }
  for (const [t0, title, text, icon] of S.TOASTS) {
    const a = sramp(t, t0, t0 + 0.4) * (1 - sramp(t, t0 + 4.2, t0 + 4.6));
    hud.toast(g2, a, title, text, icon);
  }
  if (t > 207.5 && t < 290.5) {
    const ds = dragonState(t);
    hud.boss(g2, sramp(t, 207.5, 208.5) * (1 - sramp(t, 289.4, 290.4)), ds.hp, 'DRAGONA DEL FIN');
  }
  if (t < 12.5) {
    const a = sramp(t, 1.5, 3) * (1 - sramp(t, 10.8, 12.2));
    g2.globalAlpha = a;
    hud.title(g2, t);
    g2.globalAlpha = 1;
  }
  for (const [t0, l1, l2] of S.CHAPTERS) hud.chapter(g2, sramp(t, t0, t0 + 0.6) * (1 - sramp(t, t0 + 4.2, t0 + 5)), l1, l2);
  hud.big(g2, sramp(t, 292.4, 293.2) * (1 - sramp(t, 298, 299)), '¡VICTORIA!', '#ffe060', 17);
  if (t >= S.T_CREDITS) hud.credits(g2, ramp(t, S.T_CREDITS + 1, 330), S.CREDITS);
}

// eventos para la banda sonora
function buildEvents() {
  const ev = [];
  const e = (t, type, x) => ev.push({ t: +t.toFixed(3), type, ...(x || {}) });
  for (const t of S.PUNCHES) e(t + 0.15, 'punch');
  S.LOG_BREAK.forEach((t) => e(t, 'break'));
  e(61.8, 'sparkle');
  for (const [t] of S.TOASTS) e(t, 'toast');
  for (const m of S.MOBS) {
    if (m.rise) e(m.spawn + 0.5, 'groan');
    for (const h of m.hits || []) { e(h, 'hit'); e(h + 0.05, m.type + '_hurt'); }
    if (m.die) e(m.die + 0.6, 'poof');
    for (const a of m.attack || []) e(a, 'whoosh');
  }
  for (const t of [95.5, 98.2, 104.8, 109.9]) e(t, 'groan');
  for (const s of S.SWINGS) e(s, 'whoosh');
  for (const [t0, t1, , , , ] of S.SK_ARROWS) { e(t0, 'bow'); e(t1, 'arrow_hit'); }
  e(141, 'hiss'); e(S.CRATER.t, 'explode');
  e(153.3, 'spider_hiss');
  for (const [t] of S.DAMAGE) e(t, 'hurt');
  for (const t of S.PORTAL_PLACE) e(t, 'place');
  e(188.6, 'ignite'); e(S.PORTAL_LIT, 'portal_open'); e(196.5, 'warp');
  for (const r of [205.5, 209.3, 240.3, 265.4, 275.6]) e(r, 'roar');
  S.RELEASE.forEach((r, k) => { e(r - 1.0, 'bow_draw'); e(r, 'bow'); e(S.CRYSTAL_BOOM[k], 'crystal'); });
  e(248.6, 'breath');
  for (const h of S.DRAGON_HITS) { e(h, 'whoosh'); e(h + 0.12, 'dragon_hit'); }
  e(S.DRAGON_CRIT + 0.12, 'crit');
  e(254.5, 'land'); e(273.0, 'land');
  e(276, 'dragon_death'); e(290, 'boom_big'); e(S.EXIT_PORTAL, 'portal_open'); e(292.4, 'victory');
  for (let t = 286; t < 292.5; t += 0.27) e(t, 'xp');
  // pasos
  let last = 0;
  for (let i = 1; i < DIST.length; i++) {
    const t = i * DT;
    if (DIST[i] - last > 1.35) {
      last = DIST[i];
      const inside = (t > 196.6 && t < S.T_END) || t >= S.T_CREDITS;
      if (!inside) e(t, t >= S.T_END ? 'step_end' : 'step');
    }
  }
  // aleteos de la dragona en vuelo
  for (let t = 200; t < 275; t += 2 * PI / 3.0) {
    const ds = dragonState(t);
    if (!ds.perch) e(t, 'flap', { d: +ds.pos.distanceTo(PS(t)).toFixed(1) });
  }
  return ev.sort((a, b) => a.t - b.t);
}

window.renderAt = (t) => { renderAt(t); return true; };
window.grab = (t, q = 0.93) => renderAt(t).toDataURL('image/jpeg', q);
window.EVENTS = buildEvents();
window.DUR = S.DUR;
window.ready = true;
