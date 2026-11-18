// Render principal: renderer, postproceso (DOF, bloom, gradacion) y API renderFrame(t).
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { FXAAShader } from 'three/addons/shaders/FXAAShader.js';
import { Director } from './director.js';

const params = new URLSearchParams(location.search);
const W = +(params.get('w') || 1280), H = +(params.get('h') || 720);

const canvas = document.createElement('canvas');
canvas.width = W; canvas.height = H;
document.body.appendChild(canvas);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, W / H, 0.05, 900);

const rt = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: +(params.get('ms') ?? 4) });
const composer = new EffectComposer(renderer, rt);
composer.setPixelRatio(1);
composer.setSize(W, H);
const renderPass = new RenderPass(scene, camera);
composer.addPass(renderPass);
const bokeh = new BokehPass(scene, camera, { focus: 3.0, aperture: 0.002, maxblur: 0.012 });
composer.addPass(bokeh);
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.55, 0.6, 0.85);
composer.addPass(bloom);
composer.addPass(new OutputPass());
const fxaa = new ShaderPass(FXAAShader); fxaa.material.uniforms.resolution.value.set(1 / W, 1 / H);
if (!(+(params.get('ms') ?? 4))) composer.addPass(fxaa);

// gradacion de color en espacio de pantalla (sRGB)
const GradeShader = {
  uniforms: {
    tDiffuse: { value: null },
    uTint: { value: new THREE.Vector3(1, 1, 1) },
    uLift: { value: new THREE.Vector3(0, 0, 0) },
    uSat: { value: 1.0 },
    uContrast: { value: 1.0 },
    uVignette: { value: 0.35 },
    uGrain: { value: 0.035 },
    uFrame: { value: 0 },
    uFade: { value: 1.0 },
    uRes: { value: new THREE.Vector2(W, H) },
    tOver: { value: null },
    uOver: { value: 1.0 },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform vec3 uTint; uniform vec3 uLift; uniform float uSat; uniform float uContrast;
    uniform float uVignette; uniform float uGrain; uniform float uFrame; uniform float uFade; uniform vec2 uRes; uniform sampler2D tOver; uniform float uOver;
    varying vec2 vUv;
    float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
    void main(){
      vec3 c = texture2D(tDiffuse, vUv).rgb;
      c = c * uTint + uLift * (1.0 - c);
      float l = dot(c, vec3(0.2126,0.7152,0.0722));
      c = mix(vec3(l), c, uSat);
      c = (c - 0.5) * uContrast + 0.5;
      vec2 d = vUv - 0.5; d.x *= uRes.x/uRes.y;
      c *= 1.0 - uVignette * smoothstep(0.35, 1.05, length(d));
      float g = h(floor(vUv*uRes) + vec2(uFrame*1.37, uFrame*0.71)) - 0.5;
      c += g * uGrain;
      c *= uFade;
      vec4 o = texture2D(tOver, vUv);
      c = mix(c, o.rgb, o.a * uOver);
      gl_FragColor = vec4(clamp(c,0.0,1.0), 1.0);
    }`,
};
const grade = new ShaderPass(GradeShader);
composer.addPass(grade);

// capa 2D de creditos
const over = document.createElement('canvas'); over.width = W; over.height = H;
const overTex = new THREE.CanvasTexture(over); overTex.colorSpace = THREE.NoColorSpace; overTex.premultiplyAlpha = false;
grade.uniforms.tOver.value = overTex;
const ctx = { THREE, renderer, scene, camera, composer, bokeh, bloom, grade, W, H, over, overTex };
const director = new Director(ctx);
await director.init();

const tmp = new Uint8Array(W * H * 4);
window.renderFrame = async (t, frameIdx, wantPixels = true) => {
  director.update(t);
  grade.uniforms.uFrame.value = frameIdx ?? Math.round(t * 30);
  composer.render();
  if (!wantPixels) return null;
  const gl = renderer.getContext();
  gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, tmp);
  // RGBA -> RGB, base64
  const rgbBuf = new Uint8Array(W * H * 3);
  for (let i = 0, j = 0; i < tmp.length; i += 4, j += 3) { rgbBuf[j] = tmp[i]; rgbBuf[j + 1] = tmp[i + 1]; rgbBuf[j + 2] = tmp[i + 2]; }
  return await new Promise((res) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result.slice(fr.result.indexOf(',') + 1));
    fr.readAsDataURL(new Blob([rgbBuf]));
  });
};
window.renderPNG = (t, cam) => {
  director.update(t);
  grade.uniforms.uFrame.value = Math.round(t * 30);
  if (cam) { camera.position.set(cam[0], cam[1], cam[2]); camera.lookAt(cam[3], cam[4], cam[5]); camera.fov = cam[6] || 40; camera.updateProjectionMatrix(); bokeh.enabled = false; director.sky.position.copy(camera.position); }
  composer.render(); return canvas.toDataURL('image/png');
};
window.info = () => ({ calls: renderer.info.render.calls, tris: renderer.info.render.triangles, geos: renderer.info.memory.geometries });
window.ready = true;
