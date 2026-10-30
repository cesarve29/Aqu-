// Motor de render: post-proceso tipo "shaders" y avance determinista por tiempo.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';
import { buildVillage, buildForest, buildGraveyard, buildMountain, buildCavern } from './sets.js';
import { makeRider, makeHorse, makeScarecrowKid } from './rider.js';
import { SCENES, SCENE_LEN } from './story.js';

const params = new URLSearchParams(location.search);
const W = +(params.get('w') || 1920), H = +(params.get('h') || 1080);

const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.shadowMap.enabled = !params.has('noshadow');
renderer.shadowMap.type = THREE.BasicShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(45, W / H, 0.08, 1200);

const GradeShader = {
  uniforms: {
    tDiffuse: { value: null }, uTime: { value: 0 }, uFade: { value: 0 }, uFlash: { value: 0 }, uFlashCol: { value: new THREE.Color(1, 1, 1) },
    uVig: { value: 0.45 }, uGrain: { value: 0.035 }, uCA: { value: 0.0015 }, uTint: { value: new THREE.Color(1, 1, 1) }, uSat: { value: 1.05 }, uContrast: { value: 1.06 }, uExposure: { value: 1.15 }, uPx: { value: new THREE.Vector2(1 / 1920, 1 / 1080) },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform vec2 uPx; uniform float uTime, uFade, uFlash, uVig, uGrain, uCA, uSat, uContrast, uExposure; uniform vec3 uTint, uFlashCol;
    varying vec2 vUv;
    vec3 hvRRT(vec3 v){ vec3 a = v * (v + 0.0245786) - 0.000090537; vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081; return a / b; }
    vec3 hvAces(vec3 color){
      const mat3 I = mat3(vec3(0.59719, 0.07600, 0.02840), vec3(0.35458, 0.90834, 0.13383), vec3(0.04823, 0.01566, 0.83777));
      const mat3 O = mat3(vec3(1.60475, -0.10208, -0.00327), vec3(-0.53108, 1.10813, -0.07276), vec3(-0.07367, -0.00605, 1.07602));
      color *= uExposure / 0.6;
      color = O * hvRRT(I * color);
      return clamp(color, 0.0, 1.0);
    }
    vec3 hvSrgb(vec3 c){ return mix(pow(c, vec3(0.41666)) * 1.055 - 0.055, c * 12.92, vec3(lessThanEqual(c, vec3(0.0031308)))); }
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233)) + uTime * 17.0) * 43758.5453); }
    void main(){
      vec2 d = vUv - 0.5;
      float r2 = dot(d, d);
      vec3 c = texture2D(tDiffuse, vUv).rgb;
      // antialias barato: mezcla con 4 muestras bilineales en los bordes de alto contraste
      vec2 px = uPx * 0.5;
      vec3 a1 = texture2D(tDiffuse, vUv + vec2(px.x, px.y)).rgb, a2 = texture2D(tDiffuse, vUv + vec2(-px.x, px.y)).rgb;
      vec3 a3 = texture2D(tDiffuse, vUv + vec2(px.x, -px.y)).rgb, a4 = texture2D(tDiffuse, vUv + vec2(-px.x, -px.y)).rgb;
      vec3 avg = (a1 + a2 + a3 + a4) * 0.25;
      float lc = log2(1.0 + dot(c, vec3(0.3, 0.6, 0.1))), la = log2(1.0 + dot(avg, vec3(0.3, 0.6, 0.1)));
      float lmax = max(max(dot(a1, vec3(0.3,0.6,0.1)), dot(a2, vec3(0.3,0.6,0.1))), max(dot(a3, vec3(0.3,0.6,0.1)), dot(a4, vec3(0.3,0.6,0.1))));
      float lmin = min(min(dot(a1, vec3(0.3,0.6,0.1)), dot(a2, vec3(0.3,0.6,0.1))), min(dot(a3, vec3(0.3,0.6,0.1)), dot(a4, vec3(0.3,0.6,0.1))));
      float edge = smoothstep(0.04, 0.25, log2(1.0 + lmax) - log2(1.0 + lmin));
      c = mix(c, avg, edge * 0.75);
      c.r = mix(c.r, texture2D(tDiffuse, vUv + d * uCA * r2 * 8.0).r, step(0.00001, uCA));
      c.b = mix(c.b, texture2D(tDiffuse, vUv - d * uCA * r2 * 8.0).b, step(0.00001, uCA));
      c = hvSrgb(hvAces(c));
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
      c = mix(vec3(l), c, uSat);
      c = (c - 0.5) * uContrast + 0.5;
      c *= uTint;
      c *= 1.0 - uVig * smoothstep(0.12, 0.62, r2 * 1.6);
      c += (h(vUv * 1000.0) - 0.5) * uGrain;
      c = mix(c, uFlashCol, uFlash);
      c *= 1.0 - uFade;
      gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
    }`,
};

const composer = new EffectComposer(renderer);
composer.setPixelRatio(1);
composer.setSize(W, H);
const renderPass = new RenderPass(new THREE.Scene(), camera);
composer.addPass(renderPass);
const bloom = new UnrealBloomPass(new THREE.Vector2(W / 4, H / 4), 0.85, 0.55, 0.82);
if (!params.has('nobloom')) composer.addPass(bloom);
const grade = new ShaderPass(GradeShader);
composer.addPass(grade);
const fxaa = new ShaderPass(FXAAShader);
fxaa.material.uniforms.resolution.value.set(1 / W, 1 / H);
if (params.has('fxaa')) composer.addPass(fxaa);
grade.uniforms.uPx.value.set(1 / W, 1 / H);

// ---------------------------------------------------------------------------
const S = {};
let rider, horse, kid, keyLight, fillLight;
function init() {
  const t0 = performance.now();
  S.village = buildVillage();
  S.forest = buildForest();
  S.graveyard = buildGraveyard();
  S.mountain = buildMountain();
  S.cavern = buildCavern();
  keyLight = new THREE.PointLight(0xd8e6ff, 0, 9, 2);
  fillLight = new THREE.PointLight(0xffa060, 0, 7, 2);
  rider = makeRider();
  horse = makeHorse();
  kid = makeScarecrowKid();
  console.log('init ms', Math.round(performance.now() - t0));
}

const ctx = {
  camera, S, grade: grade.uniforms, bloom, renderer,
  get rider() { return rider; },
  get horse() { return horse; },
  get kid() { return kid; },
  get key() { return keyLight; },
  get fill() { return fillLight; },
};

function resetGrade() {
  const u = grade.uniforms;
  u.uFade.value = 0; u.uFlash.value = 0; u.uFlashCol.value.set(1, 1, 1);
  u.uVig.value = 0.45; u.uGrain.value = 0.03; u.uCA.value = 0.0015; u.uTint.value.set(1, 1, 1); u.uSat.value = 1.05; u.uContrast.value = 1.06;
  bloom.strength = 0.6; bloom.radius = 0.5; bloom.threshold = 0.88;
  grade.uniforms.uExposure.value = 1.15;
  camera.fov = 45;
}

const _v = new THREE.Vector3();
function setFrame(t) {
  const i = Math.min(SCENES.length - 1, Math.floor(t / SCENE_LEN));
  const lt = t - i * SCENE_LEN;
  const sc = SCENES[i];
  const set = S[sc.set];
  resetGrade();
  rider.reset();
  horse.reset();
  kid.reset();
  if (set.fx) for (const k in set.fx) set.fx[k].visible = false;
  if (set.trail) set.trail.update([]);
  set.scene.add(horse.root, kid.root, keyLight, fillLight, rider.embers.points, rider.swordSparks.points);
  set.scene.add(rider.root);
  keyLight.intensity = 0;
  keyLight.distance = 9;
  keyLight.color.set(0xd8e6ff);
  fillLight.intensity = 0;
  fillLight.color.set(0xffa060);
  horse.root.visible = false;
  kid.root.visible = false;
  rider.root.visible = false;
  ctx.set = set;
  ctx.t = t;
  sc.update(lt, ctx);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  // tamano de particulas en pixeles
  const k = H / (2 * Math.tan((camera.fov * Math.PI) / 360));
  set.scene.traverse((o) => { if (o.isPoints && o.material.uniforms?.uScaleH) o.material.uniforms.uScaleH.value = k; });
  // el cielo sigue a la camara
  set.scene.traverse((o) => {
    if (o.userData.u?.uStars) o.position.copy(camera.position);
    if (o.userData.moon) o.lookAt(camera.position);
  });
  if (set.L?.dir && sc.shadow !== false) {
    const f = ctx.focus || camera.position;
    const dir = set.L.dir;
    const ld = _v.copy(set.L.dirVec || dir.userData.vec || dir.position.clone().normalize());
    dir.userData.vec = ld.clone();
    dir.target.position.copy(f);
    dir.position.copy(f).addScaledVector(ld, 120);
    dir.target.updateMatrixWorld();
  }
  ctx.focus = null;
  grade.uniforms.uTime.value = t;
  renderPass.scene = set.scene;
}

window.SCENE_COUNT = SCENES.length;
window.SCENE_LEN = SCENE_LEN;
window.renderAt = (t, quality = 0.92) => {
  setFrame(t);
  composer.render();
  return renderer.domElement.toDataURL('image/jpeg', quality);
};
window.renderOnly = (t) => {
  const a = performance.now();
  setFrame(t);
  const b = performance.now();
  const hide = (params.get('hide') || '').split(',');
  if (hide[0]) ctx.set.scene.traverse((o) => {
    if (hide.includes('sprites') && o.isSprite) o.visible = false;
    if (hide.includes('points') && o.isPoints) o.visible = false;
    if (hide.includes('shader') && o.material?.isShaderMaterial) o.visible = false;
    if (hide.includes('chars') && (o === rider.root || o === horse.root || o === kid.root)) o.visible = false;
    if (hide.includes('lights') && o.isPointLight) o.intensity = 0;
    if (hide.includes('voxels') && o.isMesh && Array.isArray(o.material)) o.visible = false;
  });
  renderer.info.autoReset = false;
  renderer.info.reset();
  if (params.has('direct')) renderer.render(ctx.set.scene, camera); else composer.render();
  window.info = JSON.stringify(renderer.info.render);
  renderer.getContext().readPixels(0, 0, 1, 1, 0x1908, 0x1401, new Uint8Array(4));
  const c = performance.now();
  renderer.domElement.toDataURL('image/jpeg', 0.92);
  return [Math.round(b - a), Math.round(c - b), Math.round(performance.now() - c)];
};
try {
  init();
  window.ready = true;
} catch (e) {
  console.error('INIT FAIL', e.stack || e);
  window.initError = String(e.stack || e);
}
