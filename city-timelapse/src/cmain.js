// TIMELAPSE: NUEVA SANTANDER — un jugador en modo creativo construye una ciudad bloque a bloque.
// Cada fotograma es funcion pura de t (60 fps).
import * as THREE from 'three';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { clamp, lerp, smooth, ramp, sramp, V, keyed, spline, lerpAngle, rng, hash2 } from '../../voxel-video/src/util.js';
import { humanoid, poseHumanoid } from '../../voxel-video/src/entities.js';
import { makeSky, Particles, makePost } from '../../voxel-video/src/fx.js';
import { drawText } from '../../voxel-video/src/hud.js';
import { makeCityAtlas, T } from './catlas.js';
import { B, BDEF, buildTimedMeshes, cityMaterials } from './cmesh.js';
import { genCity, SX, SZ, G, WATER_Y, MAIN } from './cworld.js';

export const DUR = 180;
const Q = new URLSearchParams(location.search);
const W = +(Q.get('w') || 1920), H = +(Q.get('h') || 1080);
const PI = Math.PI;

const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.shadowMap.autoUpdate = false;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
document.body.appendChild(renderer.domElement);
const post = makePost(renderer, W, H);
const fxaa = new ShaderPass(FXAAShader);
fxaa.uniforms.resolution.value.set(1 / W, 1 / H);
post.composer.insertPass(fxaa, post.composer.passes.length - 1);

const camera = new THREE.PerspectiveCamera(60, W / H, 0.1, 2000);
const scene = new THREE.Scene();
const atlas = makeCityAtlas();
const U = { uTime: { value: 0 }, uNight: { value: 0 } };
const mats = cityMaterials(atlas, U);
const city = genCity();
const cityMesh = buildTimedMeshes(city.grid, atlas, mats.mat, mats.depth);
scene.add(cityMesh);
const C3 = (h) => new THREE.Color(h);

// suelo exterior (para que no se vea el borde del mundo)
{
  const cv = document.createElement('canvas'); cv.width = cv.height = 16;
  const g = cv.getContext('2d');
  g.drawImage(atlas.canvas, (T.GRASS % 8) * 16, Math.floor(T.GRASS / 8) * 16, 16, 16, 0, 0, 16, 16);
  const tex = new THREE.CanvasTexture(cv);
  tex.magFilter = tex.minFilter = THREE.NearestFilter; tex.generateMipmaps = false;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.colorSpace = THREE.SRGBColorSpace;
  const mk = (x0, x1, z0, z1) => {
    const t = tex.clone(); t.needsUpdate = true; t.repeat.set(x1 - x0, z1 - z0);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(x1 - x0, z1 - z0), new THREE.MeshLambertMaterial({ map: t, color: 0xdddddd }));
    m.rotation.x = -PI / 2; m.position.set((x0 + x1) / 2, G + 1 - 0.002, (z0 + z1) / 2); m.receiveShadow = true;
    scene.add(m);
  };
  mk(-1200, 1368, SZ, 1400); mk(-1200, 1368, -1200, 11); mk(-1200, 0, 36, SZ); mk(SX, 1368, 36, SZ);
}
// agua con reflejo real (Reflector) y ondas
const WaterShader = {
  uniforms: {
    color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null },
    uTime: { value: 0 }, deep: { value: C3(0x0a2a3a) }, fogColor: { value: new THREE.Color() }, fogNear: { value: 100 }, fogFar: { value: 500 },
    sunDir: { value: V(0, 1, 0) }, sunCol: { value: new THREE.Color() },
  },
  vertexShader: `uniform mat4 textureMatrix; varying vec4 vUv; varying vec3 vW;
    void main(){ vUv = textureMatrix * vec4(position, 1.0); vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uTime, fogNear, fogFar; uniform vec3 deep, fogColor, sunDir, sunCol;
    varying vec4 vUv; varying vec3 vW;
    float h21(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
    float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y); }
    float wav(vec2 p){ return vn(p*0.5 + vec2(uTime*0.35, uTime*0.2)) + 0.5*vn(p*1.4 - uTime*0.5) + 0.25*vn(p*3.1 + vec2(-uTime*0.4, uTime*0.6)); }
    void main(){
      vec2 p = vW.xz; float e = 0.12;
      float w0 = wav(p), wx = wav(p + vec2(e, 0.0)), wz = wav(p + vec2(0.0, e));
      vec3 n = normalize(vec3((w0 - wx) * 0.9, 1.0, (w0 - wz) * 0.9));
      vec3 v = normalize(cameraPosition - vW);
      float fres = 0.3 + 0.7 * pow(1.0 - max(dot(n, v), 0.0), 3.0);
      vec4 uv = vUv; uv.xy += n.xz * 2.2 * uv.w * 0.02;
      vec3 refl = texture2DProj(tDiffuse, uv).rgb;
      vec3 c = mix(deep, refl, clamp(fres + 0.25, 0.0, 0.95));
      c += sunCol * pow(max(dot(reflect(-v, n), sunDir), 0.0), 220.0) * 2.5;
      float d = length(cameraPosition - vW);
      c = mix(c, fogColor, smoothstep(fogNear, fogFar, d));
      gl_FragColor = vec4(c, 1.0);
    }`,
};
const water = new Reflector(new THREE.PlaneGeometry(2600, 30), { textureWidth: Math.round(W * 0.45), textureHeight: Math.round(H * 0.45), clipBias: 0.002, shader: WaterShader });
water.rotation.x = -PI / 2;
water.position.set(84, WATER_Y, 23);
scene.add(water);
const water2 = new THREE.Mesh(new THREE.PlaneGeometry(2600, 30), new THREE.ShaderMaterial({
  uniforms: THREE.UniformsUtils.clone(WaterShader.uniforms),
  vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
  fragmentShader: WaterShader.fragmentShader.replace('uniform sampler2D tDiffuse;', 'uniform vec3 skyTop, skyHor;').replace('varying vec4 vUv;', '').replace('vec4 uv = vUv; uv.xy += n.xz * 2.2 * uv.w * 0.02;', '').replace('vec3 refl = texture2DProj(tDiffuse, uv).rgb;', 'vec3 rr = reflect(-v, n); vec3 refl = mix(skyHor, skyTop, clamp(rr.y * 1.5, 0.0, 1.0));'),
}));
water2.material.uniforms.skyTop = { value: new THREE.Color() };
water2.material.uniforms.skyHor = { value: new THREE.Color() };
water2.rotation.x = -PI / 2;
water2.position.copy(water.position);
scene.add(water2);

// cielo, sol y luces
const sky = makeSky('over'); scene.add(sky);
const sun = new THREE.DirectionalLight(0xffffff, 2.5);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0003; sun.shadow.normalBias = 0.05;
scene.add(sun, sun.target);
const hemi = new THREE.HemisphereLight(0xbfd8ff, 0x6b5a40, 0.9); scene.add(hemi);
const amb = new THREE.AmbientLight(0x4050a0, 0.1); scene.add(amb);
scene.fog = new THREE.Fog(0xa9cdf5, 140, 560);

// nubes de bloques en 3D
const clouds = new THREE.Group();
const cloudMat = new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0x303030, transparent: true, opacity: 0.94 });
{
  const r = rng(77);
  for (let i = 0; i < 46; i++) {
    const c = new THREE.Group();
    const n = 4 + Math.floor(r() * 6);
    for (let k = 0; k < n; k++) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(6 + r() * 10, 2.5 + r() * 2, 6 + r() * 10), cloudMat);
      m.position.set((r() - 0.5) * 16, (r() - 0.5) * 2, (r() - 0.5) * 12);
      c.add(m);
    }
    c.userData = { x0: r() * 700 - 260, z0: r() * 640 - 240, y: 104 + r() * 14 };
    clouds.add(c);
  }
  scene.add(clouds);
}
// haz del faro en la torre central
const beamMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { a: { value: 0 } },
  vertexShader: `varying float vY; void main(){ vY = position.y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform float a; varying float vY; void main(){ float f = (1.0 - smoothstep(0.0, 300.0, vY + 150.0)) ; gl_FragColor = vec4(vec3(0.75, 0.9, 1.0) * 2.2 * a * f, 1.0); }`,
});
const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 300, 10, 1, true), beamMat);
beam.position.set(city.beacon.beacon[0], city.beacon.beacon[1] + 150, city.beacon.beacon[2]);
scene.add(beam);

// particulas al colocar bloques
const parts = new Particles(6000, false);
scene.add(parts.points);
{
  const colOf = (b) => { const c = atlas.avg[BDEF[b].tiles[1]]; return [c.r, c.g, c.b]; };
  city.placements.forEach(([t, x, y, z, b], i) => {
    if (i % 4) return;
    parts.add({ t0: t, n: 3, pos: [x, y, z], spread: [0.45, 0.45, 0.45], vel: [0, 1.2, 0], vs: [1.4, 1, 1.4], life: 0.55, size: 0.12, colors: [colOf(b), [1, 1, 1]], grav: -7, seed: i });
  });
}

// ===================================================================== jugador
const player = humanoid('hero');
scene.add(player.root);
const held = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.22, 0.22), new THREE.MeshLambertMaterial({ color: 0xffffff }));
held.position.set(0, -0.05, 0.12);
player.hand.add(held);
const P = city.placements;
const PT = Float64Array.from(P.map((p) => p[0]));
const pre = [[0, 0, 0]];
for (const p of P) { const l = pre[pre.length - 1]; pre.push([l[0] + p[1], l[1] + p[2], l[2] + p[3]]); }
const lowerBound = (t) => { let a = 0, b = PT.length; while (a < b) { const m = (a + b) >> 1; if (PT[m] < t) a = m + 1; else b = m; } return a; };
const taskAt = (t) => { let cur = city.tasks[0]; for (const tk of city.tasks) if (tk.t0 !== undefined && tk.t0 <= t) { if (!cur || tk.t0 >= (cur.t0 ?? -1)) cur = tk; } return cur; };
const ROOF = V(23.5, G + 44 + 2, 51.5);
function rawTarget(t) {
  const a = lowerBound(t - 0.6), b = Math.max(a + 1, lowerBound(t + 0.6));
  const i0 = Math.min(a, P.length - 1), i1 = Math.min(b, P.length);
  const n = i1 - i0;
  const avg = n > 0 ? V((pre[i1][0] - pre[i0][0]) / n, (pre[i1][1] - pre[i0][1]) / n, (pre[i1][2] - pre[i0][2]) / n) : V(P[P.length - 1][1], P[P.length - 1][2], P[P.length - 1][3]);
  const tk = taskAt(t);
  const f = V(tk.focus[0], 0, tk.focus[2]);
  let dir = V(avg.x - f.x, 0, avg.z - f.z);
  if (dir.length() < 0.5) dir.set(1, 0, 0.4);
  dir.normalize();
  const pos = avg.clone().addScaledVector(dir, 3.2).add(V(0, 2.0, 0));
  pos.y = Math.max(pos.y, G + 3);
  return { pos, look: avg };
}
const TAB = [];
const TDT = 0.1;
for (let t = 0; t <= DUR + 1; t += TDT) TAB.push(rawTarget(t));
function playerState(t) {
  // suavizado: media de muestras en +-0.7 s
  const i = t / TDT;
  let acc = V(), lk = V(), wsum = 0;
  for (let k = -7; k <= 7; k++) {
    const j = clamp(Math.round(i) + k, 0, TAB.length - 1);
    const w = 1 - Math.abs(k) / 8;
    acc.addScaledVector(TAB[j].pos, w); lk.addScaledVector(TAB[j].look, w); wsum += w;
  }
  acc.multiplyScalar(1 / wsum); lk.multiplyScalar(1 / wsum);
  let pos = acc, look = lk;
  const t0 = 8, start = V(-30, 40, 10);
  if (t < t0 + 1.5) { const u = sramp(t, 0, t0 + 1.5); pos = start.clone().lerp(acc, u); }
  if (t > 157) { const u = sramp(t, 157, 163); pos = pos.clone().lerp(ROOF.clone().add(V(0, 0.0, 0)), u); look = look.clone().lerp(V(84, 30, 120), u); }
  const yaw = Math.atan2(look.x - pos.x, look.z - pos.z);
  const building = t > 8 && t < 156.5;
  return { pos, look, yaw, building, standing: t > 162 };
}
const PS = (t) => playerState(t).pos;

// ===================================================================== tiempo del dia
const TOD = [[0, 5.6], [20, 8], [45, 13], [60, 17.5], [66, 19.2], [72, 25], [78, 29.5], [82, 30.6], [100, 36], [118, 40], [124, 42.3], [128, 46], [132, 54.2], [140, 56.5], [150, 61], [158, 64.6], [164, 65.9], [170, 66.4], [180, 66.8]];
const hourAt = (t) => keyed(TOD, t, (u) => u)[0];
const PAL = { dTop: C3(0x3f7ae8), dHor: C3(0xb8d4ef), sTop: C3(0x3a3f8a), sHor: C3(0xff8a50), nTop: C3(0x03040e), nHor: C3(0x101a3a) };
function env(t, focus, sh) {
  const h = hourAt(t) % 24;
  const a = PI * (h - 6) / 12;
  const sd = V(Math.cos(a), Math.sin(a) * 0.82, Math.sin(a) * 0.57).normalize();
  const se = sd.y;
  const day = smooth((se + 0.1) / 0.32);
  const ss = Math.exp(-Math.pow((se - 0.03) / 0.15, 2));
  const top = PAL.nTop.clone().lerp(PAL.dTop, day).lerp(PAL.sTop, ss * 0.5);
  const hor = PAL.nHor.clone().lerp(PAL.dHor, day).lerp(PAL.sHor, ss * 0.8);
  const glow = C3(0xffd090).lerp(C3(0xff6a20), ss);
  const night = 1 - day;
  const u = sky.material.uniforms;
  u.sunDir.value.copy(sd); u.top.value.copy(top); u.hor.value.copy(hor); u.glow.value.copy(glow); u.night.value = night; u.uTime.value = t;
  const useSun = se > -0.06;
  const ld = useSun ? sd : sd.clone().negate();
  sun.position.copy(focus).addScaledVector(ld, 220);
  sun.target.position.copy(focus);
  sun.intensity = useSun ? 2.8 * smooth((se + 0.06) / 0.25) : 0.7 * smooth((-se - 0.06) / 0.2);
  sun.color.copy(useSun ? C3(0xfff0d8).lerp(C3(0xff9a58), ss) : C3(0x9db4ff));
  const c = sun.shadow.camera;
  c.left = c.bottom = -sh; c.right = c.top = sh; c.near = 1; c.far = 500; c.updateProjectionMatrix();
  hemi.color.copy(top.clone().lerp(C3(0xffffff), 0.4)).lerp(C3(0x6a86d0), night);
  hemi.groundColor.copy(C3(0x6b5a40).lerp(C3(0x101020), night));
  hemi.intensity = lerp(0.7, 1.0, day);
  amb.intensity = lerp(0.55, 0.1, day);
  scene.fog.color.copy(hor);
  U.uNight.value = smooth((0.12 - se) / 0.25);
  for (const wu of [water.material.uniforms, water2.material.uniforms]) {
    wu.uTime.value = t; wu.fogColor.value.copy(hor); wu.sunDir.value.copy(ld); wu.sunCol.value.copy(useSun ? glow : C3(0x6070a0));
    wu.deep.value.copy(C3(0x0b2c3c).lerp(C3(0x02060c), night));
  }
  water2.material.uniforms.skyTop.value.copy(top); water2.material.uniforms.skyHor.value.copy(hor);
  cloudMat.color.copy(C3(0xffffff).lerp(C3(0xffb48a), ss * 0.8).multiplyScalar(lerp(0.18, 1.0, day)));
  cloudMat.emissive.copy(glow.clone().multiplyScalar(0.25 * ss + 0.05));
  renderer.toneMappingExposure = lerp(1.0, 1.35, night);
  return { day, night, hour: hourAt(t), ss };
}

// ===================================================================== camaras
const orbit = (c, R, Y, a) => V(c.x + R * Math.cos(a), c.y + Y, c.z + R * Math.sin(a));
const tkByName = (n) => city.tasks.find((t) => t.name === n);
const progressY = (n, t) => { const tk = tkByName(n); const u = ramp(t, tk.t0, tk.t1); return G + 2 + u * (tk.focus[1] - G) * 2; };
const SHOTS = [];
const shot = (t0, t1, fn) => SHOTS.push({ t0, t1, fn });
const CEN = V(84, 10, 95);
shot(0, 9, (t) => { const u = sramp(t, 0, 9); return { pos: V(lerp(-6, 26, u), 12.4, lerp(30, 24, u)), target: V(84, 14, lerp(40, 60, u)), fov: 62, sh: 120, refl: true }; });
shot(9, 24, (t) => ({ pos: orbit(CEN, 130, 90, 1.95 + (t - 9) * 0.018), target: CEN.clone().add(V(0, -5, -10)), fov: 50, sh: 160 }));
shot(24, 38, (t) => { const y = Math.min(progressY('torre A', t), 58); const c = V(23, 0, 52); return { pos: orbit(c, 26, y + 6, -1.2 + (t - 24) * 0.05), target: V(23, y, 52).lerp(PS(t), 0.3), fov: 55, sh: 60 }; });
shot(38, 54, (t) => ({ pos: V(lerp(40, 120, ramp(t, 38, 54)), 34, -36), target: V(lerp(60, 96, ramp(t, 38, 54)), 30, 58), fov: 52, sh: 120, refl: true }));
shot(54, 66, (t) => { const z = lerp(104, 74, ramp(t, 54, 66)); return { pos: V(83.5, 11.6, z), target: V(83.5, 26, z - 30), fov: 72, sh: 80 }; });
shot(66, 80, (t) => { const u = sramp(t, 66, 80); return { pos: orbit(V(64.5, G, 53.5), 48, lerp(18, 88, u), 1.0 + u * 0.9), target: V(64.5, lerp(30, 70, u), 53.5), fov: 55, sh: 120 }; });
shot(80, 94, (t) => { const p = playerState(t); const off = V(Math.cos(t * 0.15) * 9, 3.5, Math.sin(t * 0.15) * 9); return { pos: p.pos.clone().add(off), target: p.pos.clone().lerp(p.look, 0.5), fov: 58, sh: 50, near: true }; });
shot(94, 114, (t) => ({ pos: orbit(V(65, G, 93), 52, 42, 0.6 + (t - 94) * 0.03), target: V(65, 14, 93), fov: 55, sh: 100 }));
shot(114, 130, (t) => { const u = ramp(t, 114, 130); return { pos: V(lerp(40, 120, u), 46, 184), target: V(lerp(60, 100, u), 12, 128), fov: 52, sh: 120 }; });
shot(130, 142, (t) => { const p = playerState(t); return { pos: p.pos.clone().add(V(-7, 2.5, 8)), target: p.pos.clone().lerp(p.look, 0.6), fov: 58, sh: 50, near: true }; });
shot(142, 156, (t) => { const u = ramp(t, 142, 156); return { pos: V(lerp(14, 62, u), 17, -7), target: V(lerp(40, 84, u), 20, 50), fov: 60, sh: 120, refl: true }; });
shot(156, 168, (t) => { const u = sramp(t, 156, 168); return { pos: V(lerp(56, 72, u), 10.4, 15.5), target: V(78, lerp(28, 34, u), 62), fov: 68, sh: 140, refl: true }; });
shot(168, 175.5, (t) => ({ pos: orbit(ROOF, 9, 3.2, 3.6 + (t - 168) * 0.07), target: ROOF.clone().add(V(0, 1.2, 0)).lerp(V(84, 25, 110), 0.12), fov: 60, sh: 60, near: true }));
shot(175.5, 181, (t) => { const u = sramp(t, 175.5, 180); return { pos: V(lerp(30, 10, u), lerp(70, 120, u), lerp(10, -60, u)), target: V(84, 20, 90), fov: 55, sh: 160, refl: true }; });
const camAt = (t) => { if (window.DEBUGCAM) return { pos: V(...window.DEBUGCAM.slice(0, 3)), target: V(...window.DEBUGCAM.slice(3, 6)), fov: 60, sh: 120 }; for (const s of SHOTS) if (t >= s.t0 && t < s.t1) return s.fn(t); return SHOTS[SHOTS.length - 1].fn(t); };

// ===================================================================== HUD
const out = document.createElement('canvas'); out.width = W; out.height = H;
const g2 = out.getContext('2d');
const k = H / 1080;
const HOT = [B.GRASS, B.BRICK, B.GLASS_BLUE, B.CONCRETE, B.ROOF, B.PLANKS, B.LEAVES, B.LAMP, B.ASPHALT];
const tileIcon = (b, x, y, s) => { const t = BDEF[b].tiles[1]; g2.imageSmoothingEnabled = false; g2.drawImage(atlas.canvas, (t % 8) * 16, Math.floor(t / 8) * 16, 16, 16, x, y, s, s); };
function hotbar(sel) {
  const sz = Math.round(66 * k), n = 9, x0 = Math.round(W / 2 - sz * n / 2), y0 = Math.round(H - sz - 16 * k);
  g2.fillStyle = 'rgba(20,20,20,0.5)'; g2.fillRect(x0 - 3 * k, y0 - 3 * k, sz * n + 6 * k, sz + 6 * k);
  for (let i = 0; i < n; i++) {
    g2.strokeStyle = 'rgba(140,140,140,0.9)'; g2.lineWidth = 3 * k; g2.strokeRect(x0 + i * sz + 2 * k, y0 + 2 * k, sz - 4 * k, sz - 4 * k);
    tileIcon(HOT[i], x0 + i * sz + 14 * k, y0 + 14 * k, sz - 28 * k);
  }
  g2.strokeStyle = '#fff'; g2.lineWidth = 5 * k; g2.strokeRect(x0 + sel * sz - 2 * k, y0 - 2 * k, sz + 4 * k, sz + 4 * k);
}
const slotOf = (b) => {
  const map = { [B.GRASS]: 0, [B.BRICK]: 1, [B.TERRACOTTA]: 1, [B.GLASS_BLUE]: 2, [B.GLASS]: 2, [B.GLASS_DARK]: 2, [B.HOUSE_WINDOW]: 2, [B.CONCRETE]: 3, [B.CONCRETE_GRAY]: 3, [B.SANDSTONE]: 3, [B.STONE_BRICK]: 3, [B.QUARTZ]: 3, [B.ROOF]: 4, [B.ROOF_RED]: 4, [B.COPPER]: 4, [B.PLANKS]: 5, [B.DARK_PLANKS]: 5, [B.LOG]: 5, [B.LEAVES]: 6, [B.CHERRY]: 6, [B.HEDGE]: 6, [B.LAMP]: 7, [B.BLACK]: 7 };
  return map[b] ?? 8;
};
const fmt = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
function drawHud(t, cam, e) {
  const i = Math.min(lowerBound(t), P.length);
  const cur = P[Math.max(0, i - 1)];
  if (t > 8.5 && t < 172) {
    const h = e.hour % 24, day = Math.floor(e.hour / 24) + 1;
    const hh = String(Math.floor(h)).padStart(2, '0'), mm = String(Math.floor((h % 1) * 6) * 10).padStart(2, '0');
    g2.fillStyle = 'rgba(0,0,0,0.35)'; g2.fillRect(24 * k, 24 * k, 470 * k, 104 * k);
    drawText(g2, `DIA ${day}  ${hh}:${mm}`, 44 * k, 40 * k, 4 * k, '#ffffff');
    drawText(g2, `BLOQUES: ${fmt(i)}`, 44 * k, 86 * k, 4 * k, '#ffe060');
    drawText(g2, 'TIMELAPSE  X600', W - 40 * k, 40 * k, 4 * k, '#ffffff', { align: 'right' });
    if (Math.floor(t * 2) % 2 === 0) { g2.fillStyle = '#ff3030'; g2.fillRect(W - 470 * k, 40 * k, 24 * k, 24 * k); }
    if (cam.near && t < 162) hotbar(slotOf(cur[4]));
  }
  if (t < 9) {
    const a = sramp(t, 1, 2.5) * (1 - sramp(t, 7.5, 8.8));
    g2.globalAlpha = a;
    drawText(g2, 'NUEVA SANTANDER', W / 2, H * 0.3, 14 * k, '#ffffff', { align: 'center', outline: 4 * k, outlineCol: '#1a2030', shadow: false });
    drawText(g2, 'TIMELAPSE  -  CONSTRUIDA BLOQUE A BLOQUE', W / 2, H * 0.3 + 130 * k, 5 * k, '#ffe060', { align: 'center' });
    drawText(g2, 'MODO CREATIVO', W / 2, H * 0.3 + 185 * k, 4 * k, '#bfe8ff', { align: 'center' });
    g2.globalAlpha = 1;
  }
  const a2 = sramp(t, 172.5, 174) * (1 - sramp(t, 179, 180));
  if (a2 > 0) {
    g2.globalAlpha = a2;
    drawText(g2, 'NUEVA SANTANDER', W / 2, H * 0.36, 14 * k, '#ffffff', { align: 'center', outline: 4 * k, outlineCol: '#1a2030', shadow: false });
    drawText(g2, `${fmt(P.length)} BLOQUES  -  3 DIAS DE CONSTRUCCION`, W / 2, H * 0.36 + 130 * k, 5 * k, '#ffe060', { align: 'center' });
    g2.globalAlpha = 1;
  }
}

// ===================================================================== render
function renderAt(t) {
  U.uTime.value = t;
  cityMesh.userData.update(t);
  const cam = camAt(t);
  const refl = !!cam.refl;
  water.visible = refl; water2.visible = !refl;
  const p = playerState(t);
  const e = env(t, cam.target.clone().lerp(p.pos, cam.near ? 0.6 : 0.0), cam.sh || 100);
  // jugador volando
  player.root.position.copy(p.pos).add(V(0, Math.sin(t * 2.1) * 0.12 - 0.6, 0));
  player.root.rotation.set(0, p.yaw, 0);
  const swing = p.building ? (t * 3.2) % 1 : -1;
  poseHumanoid(player, { t, walk: 0, phase: 0, swing: swing < 0.55 ? swing / 0.55 : -1 });
  if (!p.standing) { player.legL.rotation.x = 0.25 + Math.sin(t * 1.3) * 0.08; player.legR.rotation.x = 0.1 - Math.sin(t * 1.3) * 0.08; player.body.rotation.x = 0.08; }
  else player.root.position.y = ROOF.y;
  const cur = P[Math.max(0, Math.min(lowerBound(t), P.length) - 1)];
  held.material.color.copy(atlas.avg[BDEF[cur[4]].tiles[1]]);
  held.visible = p.building;
  // nubes
  for (const c of clouds.children) { const d = c.userData; c.position.set(((d.x0 + t * 2.2 + 260) % 700) - 260, d.y, d.z0); }
  beam.visible = t > city.beacon.t1 + 0.5;
  beamMat.uniforms.a.value = sramp(t, city.beacon.t1 + 0.5, city.beacon.t1 + 2) * (0.6 + 0.4 * e.night);
  parts.update(t);
  camera.position.copy(cam.pos);
  camera.fov = cam.fov || 60;
  camera.updateProjectionMatrix();
  camera.lookAt(cam.target);
  sky.position.copy(camera.position);
  parts.points.material.uniforms.scale.value = H / (2 * Math.tan(camera.fov * PI / 360));
  const gu = post.grade.uniforms;
  gu.uTime.value = t;
  gu.fade.value = Math.max(1 - ramp(t, 0, 1.5), ramp(t, 178.6, 180));
  gu.warp.value = 0; gu.hurt.value = 0; gu.flash.value = 0;
  gu.vig.value = 0.32; gu.sat.value = 1.12;
  post.bloom.strength = lerp(0.45, 0.8, Math.max(e.night, e.ss * 0.7));
  post.bloom.threshold = 0.82;
  post.rp.scene = scene; post.rp.camera = camera;
  renderer.shadowMap.needsUpdate = true;
  post.composer.render();
  g2.clearRect(0, 0, W, H);
  g2.drawImage(renderer.domElement, 0, 0);
  drawHud(t, cam, e);
  return out;
}

window.renderAt = (t) => { renderAt(t); return true; };
window.grab = (t, q = 0.93) => renderAt(t).toDataURL('image/jpeg', q);
window.EVENTS = { placements: P.map((p) => +p[0].toFixed(3)), dur: DUR };
window.DUR = DUR;
window.INFO = { faces: cityMesh.userData.faces, blocks: P.length };
window.__dbg = { water, sun, renderer, cityMesh, post, parts };
window.ready = true;
