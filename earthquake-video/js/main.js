import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { FPS, T, smooth, lerp, clamp, groundMotion } from './timeline.js';
import { City } from './city.js';
import { Crowd } from './people.js';
import { FX } from './fx.js';
import { CameraRig, Phone, shotAt } from './camera.js';
import { Globe } from './globe.js';
import { Overlay } from './overlay.js';

const W = 1920, H = 1080;
const params = new URLSearchParams(location.search);
const scale = parseFloat(params.get('scale') || '1');

const renderer = new THREE.WebGLRenderer({ antialias: params.get('aa') !== '0', preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(W * scale, H * scale, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, W / H, 0.05, 9000);
scene.add(camera);

// sky + environment
const sunDir = new THREE.Vector3(0.45, 0.5, 0.74).normalize();
const sky = new Sky();
sky.scale.setScalar(8000);
const su = sky.material.uniforms;
su.turbidity.value = 3.2; su.rayleigh.value = 1.3; su.mieCoefficient.value = 0.004; su.mieDirectionalG.value = 0.82;
su.sunPosition.value.copy(sunDir);
scene.add(sky);
const pmrem = new THREE.PMREMGenerator(renderer);
const skyScene = new THREE.Scene();
const sky2 = new Sky(); sky2.scale.setScalar(8000); Object.assign(sky2.material.uniforms.turbidity, { value: 3.2 });
sky2.material.uniforms.rayleigh.value = 1.3; sky2.material.uniforms.mieCoefficient.value = 0.004; sky2.material.uniforms.sunPosition.value.copy(sunDir);
skyScene.add(sky2);
const envRT = pmrem.fromScene(skyScene, 0, 1, 10000);
scene.environment = envRT.texture;
scene.environmentIntensity = 0.55;

const hemi = new THREE.HemisphereLight(0xcfe3ff, 0x6b6152, 0.42);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff0dc, 3.1);
sun.castShadow = true;
const sm = parseInt(params.get('sm') || '4096'); sun.shadow.mapSize.set(sm, sm);
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.04;
scene.add(sun); scene.add(sun.target);

const fogBase = new THREE.Color(0xa8c0d8);
const fogDust = new THREE.Color(0xb7a68d);
scene.fog = new THREE.FogExp2(fogBase.clone(), 0.0011);

const city = new City(scene, envRT.texture);
const crowd = new Crowd(scene);
const fx = new FX(scene, envRT.texture);
const rig = new CameraRig(camera);
const phone = new Phone(camera);
const globe = new Globe(W / H);
const overlay = new Overlay();

const out = document.createElement('canvas');
out.width = W; out.height = H;
const octx = out.getContext('2d');

let frame = -1;
const gm = { x: 0, y: 0, z: 0 };
let haze = 0;

function step(f) {
  const t = f / FPS, dt = 1 / FPS;
  groundMotion(t, gm);
  city.update(t, dt, gm, fx);
  crowd.update(t, dt);
  rig.update(t, dt);
  phone.update(t);
  // dust haze in the city after the collapse
  const hz = smooth(T.collapse, T.collapse + 4, t) * (1 - 0.45 * smooth(T.standUp, T.beachCut, t));
  haze = t < T.beachCut ? hz : 0;
  scene.fog.color.copy(fogBase).lerp(fogDust, haze);
  scene.fog.density = lerp(t < T.introEnd ? 0.0005 : 0.0008, 0.0034, haze);
  fx.update(t, dt, camera.position, scene.fog);
  if (t > T.globeCut - 0.5 && t < T.endingCut + 0.5) globe.update(t);
  // shadow frustum follows the camera
  const fwd = new THREE.Vector3(); camera.getWorldDirection(fwd);
  const shot = shotAt(t);
  const wide = !shot || !shot.fp || t >= T.hillCut;
  const ext = wide ? 420 : 70;
  const center = camera.position.clone().addScaledVector(fwd, wide ? 250 : 40);
  center.y = 0;
  sun.target.position.copy(center);
  sun.position.copy(center).addScaledVector(sunDir, 600);
  const sc = sun.shadow.camera;
  if (sc.right !== ext) { sc.left = -ext; sc.right = ext; sc.top = ext; sc.bottom = -ext; sc.near = 10; sc.far = 1400; sc.updateProjectionMatrix(); }
  sun.intensity = lerp(3.4, 2.0, haze);
  hemi.intensity = lerp(0.42, 0.7, haze);
  return t;
}

window.prof = { r: 0, c: 0, o: 0, e: 0, s: 0 };
function render(f) {
  const t = f / FPS;
  const isGlobe = t >= T.globeCut && t < T.endingCut;
  let a = performance.now();
  if (isGlobe) renderer.render(globe.scene, globe.camera);
  else renderer.render(scene, camera);
  renderer.getContext().finish();
  let b = performance.now(); window.prof.r += b - a; a = b;
  octx.drawImage(renderer.domElement, 0, 0, W, H);
  b = performance.now(); window.prof.c += b - a; a = b;
  overlay.draw(octx, t, f);
  b = performance.now(); window.prof.o += b - a;
}

window.ready = true;
window.advanceTo = (f) => { const a = performance.now(); while (frame < f) { frame++; step(frame); } window.prof.s += performance.now() - a; return frame; };
window.renderFrame = (f, quality = 0.93) => {
  window.advanceTo(f);
  render(f);
  const a = performance.now();
  const u = out.toDataURL('image/jpeg', quality);
  window.prof.e += performance.now() - a;
  return u;
};
window.stats = () => renderer.info.render;
