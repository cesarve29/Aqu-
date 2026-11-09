import * as THREE from 'three';
import * as TX from './textures.js';
import { T, smooth, lerp, rng } from './timeline.js';

export class Globe {
  constructor(aspect) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x02040a);
    this.camera = new THREE.PerspectiveCamera(35, aspect, 0.01, 100);
    const tex = TX.earthTexture();
    this.epi = new THREE.Vector3(Math.cos(-0.6) * Math.cos(0.3), Math.sin(-0.6), Math.cos(-0.6) * Math.sin(0.3)).normalize();
    this.mat = new THREE.ShaderMaterial({
      uniforms: {
        map: { value: tex }, sunDir: { value: new THREE.Vector3(0.6, 0.3, 0.75).normalize() },
        epi: { value: this.epi }, time: { value: 0 },
      },
      vertexShader: `
        varying vec2 vUv; varying vec3 vN; varying vec3 vObj; varying vec3 vView;
        void main(){ vUv = uv; vObj = normalize(position); vN = normalize(mat3(modelMatrix) * normal);
          vec4 wp = modelMatrix * vec4(position,1.0); vView = normalize(cameraPosition - wp.xyz);
          gl_Position = projectionMatrix * viewMatrix * wp; }`,
      fragmentShader: `
        uniform sampler2D map; uniform vec3 sunDir; uniform vec3 epi; uniform float time;
        varying vec2 vUv; varying vec3 vN; varying vec3 vObj; varying vec3 vView;
        void main(){
          vec3 base = texture2D(map, vUv).rgb;
          float d = max(dot(vN, sunDir), 0.0);
          vec3 col = base * (0.08 + 1.1 * d);
          // ocean specular
          float ocean = step(base.b, 0.5) * step(base.r, 0.25) * step(0.2, base.b);
          vec3 h = normalize(sunDir + vView);
          col += ocean * pow(max(dot(vN, h), 0.0), 60.0) * 0.6 * d;
          // seismic wavefronts spreading from the epicentre
          float ang = acos(clamp(dot(normalize(vObj), epi), -1.0, 1.0));
          float rings = 0.0;
          for (int i = 0; i < 6; i++) {
            float r = time * 0.55 - float(i) * 0.55;
            if (r > 0.0) {
              float rr = mod(r, 3.14159);
              float k = exp(-pow((ang - rr) * 22.0, 2.0)) * exp(-r * 0.12);
              rings += k;
            }
          }
          float core = exp(-ang * ang * 400.0) * (0.6 + 0.4 * sin(time * 8.0));
          col += vec3(1.0, 0.45, 0.15) * rings * 0.9 + vec3(1.0, 0.3, 0.1) * core * 1.5;
          // rim / atmosphere
          float fr = pow(1.0 - max(dot(vN, vView), 0.0), 3.0);
          col += vec3(0.25, 0.5, 1.0) * fr * (0.3 + 0.7 * d);
          gl_FragColor = vec4(col, 1.0);
          #include <colorspace_fragment>
        }`,
    });
    this.earth = new THREE.Mesh(new THREE.SphereGeometry(1, 128, 96), this.mat);
    this.pivot = new THREE.Group();
    this.pivot.add(this.earth);
    this.scene.add(this.pivot);
    // atmosphere glow
    const atm = new THREE.Mesh(new THREE.SphereGeometry(1.06, 64, 48), new THREE.ShaderMaterial({
      uniforms: {},
      vertexShader: `varying vec3 vN; varying vec3 vV; void main(){ vN = normalize(mat3(modelMatrix)*normal); vec4 wp = modelMatrix*vec4(position,1.0); vV = normalize(cameraPosition-wp.xyz); gl_Position = projectionMatrix*viewMatrix*wp; }`,
      fragmentShader: `varying vec3 vN; varying vec3 vV; void main(){ float f = pow(1.0 - abs(dot(vN, vV)), 2.5); gl_FragColor = vec4(vec3(0.3,0.6,1.0)*f*1.4, f); }`,
      side: THREE.BackSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    this.scene.add(atm);
    // rotation axis
    const axMat = new THREE.LineBasicMaterial({ color: 0x9fd3ff, transparent: true, opacity: 0.8 });
    const ax = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, -1.45, 0), new THREE.Vector3(0, 1.45, 0)]);
    this.axis = new THREE.Line(ax, axMat);
    this.pivot.add(this.axis);
    // stars
    const r = rng(5);
    const sp = new Float32Array(3000 * 3);
    for (let i = 0; i < 3000; i++) {
      const v = new THREE.Vector3(r() - 0.5, r() - 0.5, r() - 0.5).normalize().multiplyScalar(40);
      sp[i * 3] = v.x; sp[i * 3 + 1] = v.y; sp[i * 3 + 2] = v.z;
    }
    const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
    this.scene.add(new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: 0.06, sizeAttenuation: true })));
  }

  update(t) {
    const k = t - T.globeCut;
    this.mat.uniforms.time.value = Math.max(0, k - 0.5);
    // face the epicentre at first, then drift
    this.pivot.rotation.z = 0.41 + 0.05 * smooth(T.globeCut + 5, T.globeCut + 8, t); // axis shift (exaggerated)
    const dist = lerp(3.7, 4.8, smooth(T.globeCut, T.globeCut + 11, t));
    const ang = 0.15 + k * 0.015;
    this.camera.position.set(Math.sin(ang) * dist, 0.25, Math.cos(ang) * dist);
    if (this.theta0 === undefined) {
      // find the spin that turns the epicentre toward the camera
      const cdir = this.camera.position.clone().normalize();
      let best = -2, bt = 0;
      for (let i = 0; i < 720; i++) {
        const th = i / 720 * Math.PI * 2;
        this.earth.rotation.y = th; this.pivot.updateMatrixWorld(true);
        const v = this.epi.clone().applyMatrix4(this.earth.matrixWorld).normalize();
        const d = v.dot(cdir) + 0.3 * v.y;
        if (d > best) { best = d; bt = th; }
      }
      this.theta0 = bt;
    }
    this.earth.rotation.y = this.theta0 + 0.25 - k * 0.035;
    // globe sits on the left third, labels on the right
    const right = new THREE.Vector3().crossVectors(this.camera.position.clone().negate(), new THREE.Vector3(0, 1, 0)).normalize();
    const look = right.multiplyScalar(-0.6 * dist / 3.7);
    this.camera.lookAt(-look.x, 0.05 - look.y, -look.z);
  }
}
