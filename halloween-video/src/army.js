// Ejercito de esqueletos instanciado: cientos de rigs con pocas llamadas de dibujo.
import * as THREE from 'three';
import { skeletonTemplate, bowMaterial } from './models.js';
import { rng } from './textures.js';

const PARTS = ['torso', 'head', 'armR', 'armL', 'legR', 'legL', 'bow'];
const _m = new THREE.Matrix4(), _r = new THREE.Matrix4(), _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion();
const _e = new THREE.Euler(), _v = new THREE.Vector3(), _v2 = new THREE.Vector3(), _s = new THREE.Vector3(), _one = new THREE.Vector3(1, 1, 1);

export class Army {
  constructor(list, seed = 1) {
    // list: [{x, y, z, yaw, scale, bow, sit}]
    this.list = list;
    const T = skeletonTemplate('normal');
    this.T = T;
    this.mat = T.mat;
    this.group = new THREE.Group();
    this.meshes = {};
    const n = list.length;
    for (const p of PARTS) {
      let geo;
      if (p === 'bow') {
        geo = new THREE.PlaneGeometry(0.8, 0.8);
        geo.rotateY(Math.PI / 2);
      } else geo = T.parts[p].geo;
      const im = new THREE.InstancedMesh(geo, p === 'bow' ? bowMaterial() : T.mat, n);
      im.castShadow = true;
      im.receiveShadow = true;
      im.frustumCulled = false;
      this.meshes[p] = im;
      this.group.add(im);
    }
    const r = rng(seed);
    this.fall = list.map(() => {
      const o = {};
      for (const p of PARTS) {
        const a = r() * Math.PI * 2, d = 0.2 + r() * 0.9;
        o[p] = {
          dx: Math.cos(a) * d, dz: Math.sin(a) * d, y: p === 'torso' ? 0.12 : p === 'head' ? 0.25 : 0.07,
          rot: new THREE.Euler(Math.PI / 2 * (r() < 0.5 ? 1 : -1), r() * Math.PI * 2, p === 'head' ? r() * 0.6 : 0),
          delay: r() * 0.35,
        };
      }
      return o;
    });
  }

  // poseFn(i, item) -> {x,y,z,yaw,scale,head:[x,y],armR:[x,z],armL:[x,z],legs:phase,walk,collapse,bow,sit}
  apply(poseFn) {
    const n = this.list.length;
    for (let i = 0; i < n; i++) {
      const it = this.list[i];
      const P = poseFn(i, it) || {};
      const x = P.x ?? it.x, y = P.y ?? it.y ?? 0, z = P.z ?? it.z;
      const yaw = P.yaw ?? it.yaw ?? 0, sc = P.scale ?? it.scale ?? 1;
      const sit = P.sit ?? it.sit ?? 0;
      const walk = P.walk ?? 0, ph = P.phase ?? 0;
      const col = P.collapse ?? 0;
      const root = new THREE.Matrix4().compose(_v.set(x, y - sit * 0.55, z), _q.setFromEuler(_e.set(0, yaw, 0)), _s.set(sc, sc, sc));
      const legSw = Math.sin(ph) * 0.8 * walk;
      const rot = {
        torso: [P.torsoX ?? 0, 0, 0],
        head: [P.head?.[0] ?? 0, P.head?.[1] ?? 0, 0],
        armR: [P.armR?.[0] ?? (-legSw * 0.8), 0, P.armR?.[1] ?? 0.08],
        armL: [P.armL?.[0] ?? (legSw * 0.8), 0, P.armL?.[1] ?? -0.08],
        legR: [-sit * 1.45 + legSw, 0, sit * 0.15],
        legL: [-sit * 1.45 - legSw, 0, -sit * 0.15],
      };
      const local = {};
      // torso
      const tp = this.T.parts.torso;
      const torsoPivot = new THREE.Matrix4().compose(_v.set(...tp.pivot), _q.setFromEuler(_e.set(...rot.torso)), _one);
      local.torso = torsoPivot.clone().multiply(_m.makeTranslation(...tp.off));
      for (const p of ['head', 'armR', 'armL']) {
        const pp = this.T.parts[p];
        const piv = _r.compose(_v.set(pp.pivot[0], pp.pivot[1] - 0.75, pp.pivot[2]), _q.setFromEuler(_e.set(...rot[p])), _one);
        local[p] = torsoPivot.clone().multiply(piv).multiply(_m.makeTranslation(...pp.off));
      }
      for (const p of ['legR', 'legL']) {
        const pp = this.T.parts[p];
        local[p] = new THREE.Matrix4().compose(_v.set(...pp.pivot), _q.setFromEuler(_e.set(...rot[p])), _one).multiply(_m.makeTranslation(...pp.off));
      }
      // arco en la mano izquierda
      const armLpiv = this.T.parts.armL;
      local.bow = torsoPivot.clone()
        .multiply(_r.compose(_v.set(armLpiv.pivot[0], armLpiv.pivot[1] - 0.75, armLpiv.pivot[2]), _q.setFromEuler(_e.set(...rot.armL)), _one))
        .multiply(_m.makeTranslation(0, -0.62, 0.02));
      for (const p of PARTS) {
        const im = this.meshes[p];
        if (p === 'bow' && !(P.bow ?? it.bow)) {
          im.setMatrixAt(i, _m.makeScale(0, 0, 0));
          continue;
        }
        let w = root.clone().multiply(local[p]);
        if (col > 0) {
          const f = this.fall[i][p];
          const k = THREE.MathUtils.clamp((col - f.delay) / (1 - f.delay * 0.9), 0, 1);
          if (k > 0) {
            const e = k * k * (3 - 2 * k);
            w.decompose(_v, _q, _s);
            _v2.set(x + f.dx * sc, y + f.y * sc, z + f.dz * sc);
            _q2.setFromEuler(f.rot);
            _v.lerp(_v2, e);
            _v.y += Math.sin(Math.PI * e) * 0.5 * sc;
            _q.slerp(_q2, e);
            w = new THREE.Matrix4().compose(_v, _q, _s);
          }
        }
        im.setMatrixAt(i, w);
      }
    }
    for (const p of PARTS) this.meshes[p].instanceMatrix.needsUpdate = true;
  }
}
