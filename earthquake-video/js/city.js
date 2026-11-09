import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import * as TX from './textures.js';
import { rng, T, smooth, clamp, lerp, shakeEnvelope } from './timeline.js';

// ---------- helpers ----------
export function meterBox(w, h, d, ox = 0, oy = 0, oz = 0, su = 1 / 12, sv = 1 / 12.8) {
  const g = new THREE.BoxGeometry(w, h, d);
  const p = g.attributes.position, n = g.attributes.normal, uv = g.attributes.uv;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i) + ox, y = p.getY(i) + oy, z = p.getZ(i) + oz;
    const nx = Math.abs(n.getX(i)), ny = Math.abs(n.getY(i));
    if (nx > 0.5) uv.setXY(i, z * su, y * sv);
    else if (ny > 0.5) uv.setXY(i, x * su, z * su);
    else uv.setXY(i, x * su, y * sv);
  }
  return g;
}

// Terrain height (m)
export function terrainHeight(x, z) {
  let h = 0;
  // coast: beach below z=-160, seabed beyond
  if (z < -160) {
    const d = -160 - z;
    h = -Math.min(1.6, d * 0.03) - Math.max(0, d - 55) * 0.045;
    h = Math.max(h, -16);
  }
  // inland hill
  if (z > 150) {
    const k = smooth(150, 290, z);
    h = 74 * k + 6 * Math.sin(x * 0.012) * k + 4 * Math.sin(x * 0.031 + z * 0.02) * k;
    if (z > 300) h += (z - 300) * 0.08;
  }
  return h;
}

export class City {
  constructor(scene, envMap) {
    this.scene = scene;
    this.buildings = [];
    this.collapsers = [];
    this.props = [];      // swaying props {obj, amp, freq, phase}
    this.cars = [];
    this.poles = [];
    this.cables = [];
    this.cracks = [];
    this.sinkers = [];
    this.trees = [];
    this.r = rng(1234);
    this.envMap = envMap;
    this.staticGroup = new THREE.Group();
    this.mats();
    this.ground();
    this.streets();
    this.makeBuildings();
    this.makeCollapser(-18, 47, 18, 18, 10, 'stucco', T.collapse);
    this.makeCollapser(-17, 18, 16, 16, 12, 'concrete', 67.6);
    this.streetProps();
    this.plaza();
    this.makeCars();
    this.makeCracks();
    this.hillAndCoast();
    if (!location.search.includes("nomerge")) this.mergeStatic(); else this.scene.add(this.staticGroup);
  }

  mergeStatic() {
    const buckets = new Map();
    this.staticGroup.updateMatrixWorld(true);
    this.staticGroup.traverse(o => {
      if (!o.isMesh) return;
      let g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone();
      for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
      g.applyMatrix4(o.matrixWorld);
      const parts = [];
      if (Array.isArray(o.material)) {
        for (const gr of o.geometry.groups) {
          const sub = new THREE.BufferGeometry();
          for (const k of ['position', 'normal', 'uv']) {
            const a = g.attributes[k];
            sub.setAttribute(k, new THREE.BufferAttribute(a.array.slice(gr.start * a.itemSize, (gr.start + gr.count) * a.itemSize), a.itemSize));
          }
          parts.push([o.material[gr.materialIndex], sub]);
        }
      } else parts.push([o.material, g]);
      for (const [m, geo] of parts) {
        if (!buckets.has(m)) buckets.set(m, []);
        buckets.get(m).push(geo);
      }
    });
    for (const [m, list] of buckets) {
      const merged = mergeGeometries(list, false);
      const mesh = new THREE.Mesh(merged, m);
      mesh.castShadow = true; mesh.receiveShadow = true;
      this.scene.add(mesh);
    }
  }

  mats() {
    const r = this.r;
    this.facadeMats = {};
    const styles = ['glass', 'concrete', 'stucco', 'brick'];
    const tints = [[1, 1, 1], [1.0, 0.95, 0.88], [0.9, 0.93, 1.0], [1.0, 0.9, 0.85], [0.85, 0.9, 0.85]];
    this.roofMat = new THREE.MeshStandardMaterial({ color: 0x6d6a66, roughness: 0.95 });
    for (const s of styles) {
      this.facadeMats[s] = [];
      const t = TX.facadeTexture(s, s.length * 77);
      for (let i = 0; i < (s === 'glass' ? 3 : 5); i++) {
        const tn = tints[i];
        const m = new THREE.MeshStandardMaterial({
          map: t, color: new THREE.Color(tn[0], tn[1], tn[2]),
          roughness: s === 'glass' ? 0.18 : 0.88, metalness: s === 'glass' ? 0.45 : 0.0,
          envMapIntensity: s === 'glass' ? 1.2 : 0.5,
        });
        this.facadeMats[s].push(m);
      }
    }
    this.shopMats = [];
    for (let i = 0; i < 8; i++) this.shopMats.push(new THREE.MeshStandardMaterial({ map: TX.shopTexture(500 + i), roughness: 0.5, metalness: 0.1 }));
    this.concrete = new THREE.MeshStandardMaterial({ color: 0x9a948b, roughness: 0.95 });
    this.darkMetal = new THREE.MeshStandardMaterial({ color: 0x2e3236, roughness: 0.5, metalness: 0.6 });
    this.woodPole = new THREE.MeshStandardMaterial({ color: 0x5a4632, roughness: 0.9 });
    this.awningMats = [0xb03a2e, 0x1f618d, 0x196f3d, 0xb9770e, 0x6c3483].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8 }));
    this.leafMats = [0x3f7a32, 0x4f8a3a, 0x356b2a, 0x5f9440].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.9 }));
    this.barkMat = new THREE.MeshStandardMaterial({ color: 0x5b4636, roughness: 1 });
  }

  ground() {
    const W = 1600, D = 2400, nx = 160, nz = 300;
    const g = new THREE.PlaneGeometry(W, D, nx, nz);
    g.rotateX(-Math.PI / 2);
    g.translate(0, 0, -300);
    const p = g.attributes.position;
    const col = new Float32Array(p.count * 3);
    const c = new THREE.Color();
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i);
      const h = terrainHeight(x, z);
      p.setY(i, h);
      if (z < -158) {
        const wet = smooth(-168, -185, z);
        c.setRGB(lerp(0.86, 0.55, wet), lerp(0.78, 0.5, wet), lerp(0.62, 0.4, wet));
        const bed = smooth(-200, -260, z);
        const alg = 0.5 + 0.5 * Math.sin(x * 0.07) * Math.sin(z * 0.05);
        c.lerp(new THREE.Color(lerp(0.28, 0.2, alg), lerp(0.29, 0.27, alg), lerp(0.22, 0.17, alg)), bed);
      } else if (z > 140) {
        const v = 0.85 + 0.15 * Math.sin(x * 0.05 + z * 0.07);
        c.setRGB(0.42 * v, 0.6 * v, 0.3 * v);
      } else c.setRGB(0.55, 0.54, 0.5);
      col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    g.computeVertexNormals();
    const detail = TX.sandTexture();
    detail.repeat.set(160, 240);
    detail.colorSpace = THREE.NoColorSpace;
    const m = new THREE.MeshStandardMaterial({ vertexColors: true, map: detail, roughness: 0.95 });
    m.onBeforeCompile = (s) => {
      // use the detail map only as luminance modulation
      s.fragmentShader = s.fragmentShader.replace('#include <map_fragment>',
        `#ifdef USE_MAP
          vec4 sampledDiffuseColor = texture2D( map, vMapUv );
          float lum = dot(sampledDiffuseColor.rgb, vec3(0.333));
          diffuseColor.rgb *= 0.55 + lum * 0.6;
        #endif`);
    };
    const mesh = new THREE.Mesh(g, m);
    mesh.receiveShadow = true;
    this.scene.add(mesh);
  }

  streets() {
    const s = this.scene;
    const asphalt = TX.asphaltTexture();
    asphalt.repeat.set(2, 60);
    const road = new THREE.Mesh(new THREE.PlaneGeometry(10, 300), new THREE.MeshStandardMaterial({ map: asphalt, roughness: 0.92 }));
    road.rotation.x = -Math.PI / 2; road.position.set(0, 0.02, -5);
    road.receiveShadow = true; s.add(road);
    const marks = TX.roadMarkTexture();
    marks.repeat.set(1, 25);
    const mk = new THREE.Mesh(new THREE.PlaneGeometry(10, 300), new THREE.MeshStandardMaterial({ map: marks, transparent: true, roughness: 0.8, depthWrite: false }));
    mk.rotation.x = -Math.PI / 2; mk.position.set(0, 0.03, -5); mk.receiveShadow = true; s.add(mk);
    // crosswalk near plaza
    const zebra = new THREE.MeshStandardMaterial({ color: 0xeeeeea, roughness: 0.7 });
    for (let i = 0; i < 6; i++) {
      const st = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 4), zebra);
      st.rotation.x = -Math.PI / 2; st.position.set(-3.75 + i * 1.5, 0.035, 60); st.receiveShadow = true; s.add(st);
    }
    // sidewalks with curbs
    const sw = TX.sidewalkTexture();
    sw.repeat.set(1, 75);
    const swMat = new THREE.MeshStandardMaterial({ map: sw, roughness: 0.9 });
    for (const sx of [-1, 1]) {
      const b = new THREE.Mesh(new THREE.BoxGeometry(4, 0.15, 300), swMat);
      b.position.set(sx * 7, 0.075, -5); b.receiveShadow = true; b.castShadow = false; s.add(b);
    }
    // promenade at the coast
    const pz = TX.plazaTexture(); pz.repeat.set(60, 3);
    const prom = new THREE.Mesh(new THREE.BoxGeometry(800, 0.2, 14), new THREE.MeshStandardMaterial({ map: pz, roughness: 0.9 }));
    prom.position.set(0, 0.1, -156); prom.receiveShadow = true; s.add(prom);
    // sea wall

  }

  addBuilding(x, z, w, d, h, style, opts = {}) {
    const r = this.r;
    const group = new THREE.Group();
    group.position.set(x, 0, z);
    const mats = this.facadeMats[style];
    const m = mats[Math.floor(r() * mats.length)];
    const shopH = opts.shop ? 4.5 : 0;
    const body = new THREE.Mesh(meterBox(d, h - shopH, w, x, (h + shopH) / 2, z), [m, m, this.roofMat, this.roofMat, m, m]);
    body.position.y = (h + shopH) / 2;
    body.castShadow = true; body.receiveShadow = true;
    group.add(body);
    if (opts.shop) {
      const sm = this.shopMats[Math.floor(r() * this.shopMats.length)];
      const shop = new THREE.Mesh(meterBox(d - 0.2, shopH, w - 0.2, x, shopH / 2, z, 1 / w, 1 / shopH), sm);
      // UVs: map one shop texture per facade face
      shop.position.y = shopH / 2; shop.castShadow = true; shop.receiveShadow = true;
      group.add(shop);
      const side = opts.side; // which side faces street (+1 = faces -x)
      const aw = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.1, w * 0.85), this.awningMats[Math.floor(r() * this.awningMats.length)]);
      aw.position.set(-side * (d / 2 + 0.6), 3.7, 0); aw.rotation.z = side * 0.25; aw.castShadow = true;
      group.add(aw);
      // ledge between shop and upper floors
      const ledge = new THREE.Mesh(new THREE.BoxGeometry(d + 0.5, 0.35, w + 0.2), this.concrete);
      ledge.position.y = shopH; ledge.castShadow = true; group.add(ledge);
    }
    // cornice
    const corn = new THREE.Mesh(new THREE.BoxGeometry(d + 0.6, 0.6, w + 0.6), this.concrete);
    corn.position.y = h; corn.castShadow = true; group.add(corn);
    // rooftop stuff
    const nRoof = Math.floor(r() * 3);
    for (let i = 0; i < nRoof; i++) {
      const bw = 1.5 + r() * 3, bh = 1 + r() * 2.5;
      const b = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, bw * (0.6 + r())), r() < 0.5 ? this.concrete : this.darkMetal);
      b.position.set((r() - 0.5) * (d - 4), h + bh / 2, (r() - 0.5) * (w - 4)); b.castShadow = true; group.add(b);
    }
    if (r() < 0.25 && h > 20) { // water tank
      const tk = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.4, 2.6, 16), this.woodPole);
      tk.position.set((r() - 0.5) * (d - 5), h + 2.6, (r() - 0.5) * (w - 5)); tk.castShadow = true; group.add(tk);
    }
    const b = { group, h, w, d, x, z, phase: r() * 6.28, stiff: 0.6 + r() * 0.8, tilt: 0 };
    if (opts.static) { this.staticGroup.add(group); return b; }
    this.scene.add(group);
    this.buildings.push(b);
    return b;
  }

  makeBuildings() {
    const r = this.r;
    const styles = ['concrete', 'stucco', 'brick', 'glass'];
    for (const side of [-1, 1]) {
      for (let row = 0; row < 6; row++) {
        const xIn = 9 + row * 34;
        let z = -148;
        while (z < 140) {
          const w = 12 + r() * 10;
          const zc = z + w / 2;
          z += w + (row === 0 ? 0.3 : 4 + r() * 4);
          if (zc + w / 2 > 140) break;
          // leave space for the plaza and the collapsing buildings
          if (row === 0 && side === 1 && zc > 6 && zc < 64) continue;
          if (row === 0 && side === -1 && ((zc > 33 && zc < 62) || (zc > 5 && zc < 32))) continue;
          const d = row === 0 ? 16 + r() * 6 : 18 + r() * 10;
          const x = side * (xIn + d / 2);
          let h;
          if (row === 0) h = 14 + r() * 24;
          else h = 16 + r() * 30 + (row > 2 && r() < 0.35 ? 30 + r() * 45 : 0);
          if (zc < -110) h = Math.min(h, 26); // low-rise near the beach
          const style = h > 50 ? 'glass' : styles[Math.floor(r() * 3)];
          this.addBuilding(x, zc, w, d, h, style, { shop: row === 0, side, static: row >= 2 });
        }
      }
    }
    // coastal hotels facing the sea
    for (let i = -6; i <= 6; i++) {
      if (i === 0) continue;
      const x = i * 30 + (i > 0 ? 0 : 0);
      if (Math.abs(x) < 12) continue;
      this.addBuilding(x, -140, 22, 14, 14 + r() * 16, r() < 0.4 ? 'glass' : 'stucco', { static: Math.abs(x) > 60 });
    }
  }

  makeCollapser(x, z, w, d, floors, style, tCollapse) {
    const r = this.r;
    const fh = 3.2;
    const h = floors * fh;
    const b = this.addBuilding(x, z, w, d, h, style, { shop: false, side: x < 0 ? -1 : 1 });
    const mats = this.facadeMats[style];
    const m = mats[1];
    const chunks = [];
    const nx = 3, nz = 3;
    const group = new THREE.Group();
    this.scene.add(group);
    for (let f = 0; f < floors; f++) {
      for (let ix = 0; ix < nx; ix++) for (let iz = 0; iz < nz; iz++) {
        const cw = d / nx, cd = w / nz;
        const cx = x - d / 2 + cw * (ix + 0.5), cz = z - w / 2 + cd * (iz + 0.5), cy = f * fh + fh / 2;
        const outer = ix === 0 || ix === nx - 1 || iz === 0 || iz === nz - 1;
        const geo = meterBox(cw * (0.96 + r() * 0.08), fh * 0.98, cd * (0.96 + r() * 0.08), cx, cy, cz);
        const mesh = new THREE.Mesh(geo, outer ? [m, m, this.concrete, this.concrete, m, m] : this.concrete);
        mesh.position.set(cx, cy, cz);
        mesh.castShadow = true; mesh.receiveShadow = true;
        mesh.visible = false;
        group.add(mesh);
        // rest position: pile toward the street (+x for left side buildings)
        const toward = x < 0 ? 1 : -1;
        const spread = (floors - f) / floors;
        const rest = new THREE.Vector3(
          cx + toward * (2 + r() * 10 * (0.3 + f / floors)) + (r() - 0.5) * 4,
          0, cz + (r() - 0.5) * 10 * spread);
        const layer = Math.max(0, (1 - Math.hypot(rest.x - x, rest.z - z) / 22)) * 7;
        rest.y = cw * 0.25 + layer * (0.4 + r() * 0.6);
        chunks.push({
          mesh, start: new THREE.Vector3(cx, cy, cz), pos: new THREE.Vector3(cx, cy, cz), vel: new THREE.Vector3(),
          rest, rot: new THREE.Euler(), spin: new THREE.Vector3((r() - 0.5) * 2.5, (r() - 0.5) * 1.2, (r() - 0.5) * 2.5),
          delay: f * 0.11 + r() * 0.25 + (outer ? 0 : 0.15), settled: false, restRot: new THREE.Euler((r() - 0.5) * 1.2, (r() - 0.5) * 1.5, (r() - 0.5) * 1.2),
        });
      }
    }
    this.collapsers.push({ b, chunks, t0: tCollapse, x, z, w, d, h, done: false, started: false });
  }

  streetProps() {
    const r = this.r;
    const s = this.scene;
    const lampMat = new THREE.MeshStandardMaterial({ color: 0x3a3f44, roughness: 0.4, metalness: 0.7 });
    const bulb = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff1c8, emissiveIntensity: 0.4 });
    for (const side of [-1, 1]) {
      for (let z = -140; z < 135; z += 24) {
        if (side === 1 && z > 8 && z < 60) continue;
        const g = new THREE.Group();
        g.position.set(side * 5.6, 0.15, z + (side > 0 ? 12 : 0));
        const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.12, 7, 10), lampMat);
        pole.position.y = 3.5; pole.castShadow = true; g.add(pole);
        const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 1.8, 8), lampMat);
        arm.rotation.z = Math.PI / 2; arm.position.set(-side * 0.85, 6.9, 0); arm.castShadow = true; g.add(arm);
        const head = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.18, 0.35), lampMat);
        head.position.set(-side * 1.7, 6.85, 0); g.add(head);
        const lb = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.05, 0.25), bulb);
        lb.position.set(-side * 1.7, 6.74, 0); g.add(lb);
        s.add(g);
        this.props.push({ obj: g, amp: 0.05, freq: 2.1 + r(), phase: r() * 6 });
      }
      // trees
      for (let z = -136; z < 135; z += 16 + r() * 8) {
        if (side === 1 && z > 6 && z < 62) continue;
        this.tree(side * 7.6, 0.15, z, 0.8 + r() * 0.4);
      }
    }
    // utility poles + cables on the left sidewalk
    const polePts = [];
    for (let z = -20; z <= 135; z += 31) {
      const g = new THREE.Group();
      g.position.set(-8.2, 0.15, z);
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.18, 10, 10), this.woodPole);
      pole.position.y = 5; pole.castShadow = true; g.add(pole);
      const cross = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.12, 0.12), this.woodPole);
      cross.position.y = 9.4; cross.castShadow = true; g.add(cross);
      const tr = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 1.0, 12), this.darkMetal);
      tr.position.set(0.35, 8.2, 0); tr.castShadow = true; g.add(tr);
      s.add(g);
      const pd = { obj: g, z, fall: Math.abs(z - 73) < 2 ? T.poleFall : null, ang: 0 };
      this.poles.push(pd);
    }
    // cables between consecutive poles
    const cableMat = new THREE.LineBasicMaterial({ color: 0x15171a });
    for (let i = 0; i < this.poles.length - 1; i++) {
      for (const off of [-0.7, 0, 0.7]) {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(20 * 3), 3));
        const line = new THREE.Line(geo, cableMat);
        line.frustumCulled = false;
        s.add(line);
        this.cables.push({ line, a: this.poles[i], b: this.poles[i + 1], off, phase: r() * 6 });
      }
    }
  }

  tree(x, y, z, sc, isStatic = false) {
    const r = this.r;
    const g = new THREE.Group();
    g.position.set(x, y, z);
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.12 * sc, 0.2 * sc, 3.2 * sc, 8), this.barkMat);
    trunk.position.y = 1.6 * sc; trunk.castShadow = true; g.add(trunk);
    const crown = new THREE.Group();
    crown.position.y = 3.2 * sc;
    const lm = this.leafMats[Math.floor(r() * this.leafMats.length)];
    for (let i = 0; i < 5; i++) {
      const rad = (1.1 + r() * 0.7) * sc;
      const f = new THREE.Mesh(new THREE.IcosahedronGeometry(rad, 2), lm);
      f.position.set((r() - 0.5) * 1.6 * sc, (0.5 + r() * 1.5) * sc, (r() - 0.5) * 1.6 * sc);
      f.scale.y = 0.85;
      f.castShadow = true; f.receiveShadow = true;
      crown.add(f);
    }
    g.add(crown);
    if (isStatic) { this.staticGroup.add(g); return g; }
    this.scene.add(g);
    this.props.push({ obj: g, amp: 0.035, freq: 1.4 + r(), phase: r() * 6, crown });
    return g;
  }

  plaza() {
    const s = this.scene;
    const r = this.r;
    const tx = TX.plazaTexture(); tx.repeat.set(10, 12);
    const pl = new THREE.Mesh(new THREE.BoxGeometry(36, 0.16, 54), new THREE.MeshStandardMaterial({ map: tx, roughness: 0.85 }));
    pl.position.set(27, 0.08, 36); pl.receiveShadow = true; s.add(pl);
    // fountain
    const stone = new THREE.MeshStandardMaterial({ color: 0xbfb5a3, roughness: 0.8 });
    const basin = new THREE.Mesh(new THREE.CylinderGeometry(4, 4.2, 0.8, 40, 1, true), stone);
    basin.position.set(32, 0.55, 42); basin.castShadow = true; basin.receiveShadow = true; s.add(basin);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(4.05, 0.22, 10, 48), stone);
    rim.rotation.x = Math.PI / 2; rim.position.set(32, 0.95, 42); rim.castShadow = true; s.add(rim);
    this.fountainWater = new THREE.Mesh(new THREE.CircleGeometry(3.9, 40), new THREE.MeshStandardMaterial({ color: 0x2f6f86, roughness: 0.05, metalness: 0.1, envMapIntensity: 1.5 }));
    this.fountainWater.rotation.x = -Math.PI / 2; this.fountainWater.position.set(32, 0.75, 42); s.add(this.fountainWater);
    const col = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.6, 2.4, 16), stone);
    col.position.set(32, 1.6, 42); col.castShadow = true; s.add(col);
    const bowl = new THREE.Mesh(new THREE.SphereGeometry(1.2, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), stone);
    bowl.position.set(32, 3.0, 42); bowl.rotation.x = Math.PI; bowl.castShadow = true; s.add(bowl);
    this.fountainTop = bowl;
    // benches
    const wood = new THREE.MeshStandardMaterial({ color: 0x7a5a3a, roughness: 0.8 });
    for (let i = 0; i < 6; i++) {
      const g = new THREE.Group();
      const a = i / 6 * Math.PI * 2;
      g.position.set(32 + Math.cos(a) * 9, 0.16, 42 + Math.sin(a) * 9);
      g.rotation.y = -a + Math.PI / 2;
      const seat = new THREE.Mesh(new THREE.BoxGeometry(2, 0.08, 0.5), wood); seat.position.y = 0.45; seat.castShadow = true; g.add(seat);
      const back = new THREE.Mesh(new THREE.BoxGeometry(2, 0.5, 0.06), wood); back.position.set(0, 0.75, -0.24); back.castShadow = true; g.add(back);
      for (const lx of [-0.85, 0.85]) { const l = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.45, 0.45), this.darkMetal); l.position.set(lx, 0.22, 0); g.add(l); }
      s.add(g);
    }
    // plaza trees
    for (let i = 0; i < 9; i++) {
      this.tree(12 + r() * 30, 0.16, 12 + r() * 4 + (i % 3) * 18 + (i > 5 ? 10 : 0), 1.1 + r() * 0.4);
    }
    // kiosk
    const k = new THREE.Mesh(new THREE.BoxGeometry(2.5, 2.6, 2.5), new THREE.MeshStandardMaterial({ color: 0x2e7d5b, roughness: 0.6 }));
    k.position.set(40, 1.45, 22); k.castShadow = true; s.add(k);
  }

  makeCar(color) {
    const g = new THREE.Group();
    const paint = new THREE.MeshPhysicalMaterial({ color, roughness: 0.25, metalness: 0.5, clearcoat: 1, clearcoatRoughness: 0.08, envMapIntensity: 1.2 });
    const glass = new THREE.MeshStandardMaterial({ color: 0x1b242c, roughness: 0.05, metalness: 0.6, envMapIntensity: 1.5 });
    const tire = new THREE.MeshStandardMaterial({ color: 0x151515, roughness: 0.9 });
    const rimM = new THREE.MeshStandardMaterial({ color: 0xbfc4c8, roughness: 0.3, metalness: 0.9 });
    // body profile (side view: x=length, y=height)
    const sh = new THREE.Shape();
    sh.moveTo(-2.15, 0.35); sh.lineTo(2.1, 0.35); sh.quadraticCurveTo(2.3, 0.4, 2.28, 0.75);
    sh.lineTo(2.15, 0.95); sh.lineTo(0.9, 1.02); sh.lineTo(-1.9, 1.02); sh.quadraticCurveTo(-2.25, 0.98, -2.2, 0.6); sh.lineTo(-2.15, 0.35);
    const body = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, { depth: 1.7, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.06, bevelSegments: 3, curveSegments: 8 }), paint);
    body.position.z = -0.85; body.castShadow = true; body.receiveShadow = true; g.add(body);
    const cab = new THREE.Shape();
    cab.moveTo(-1.6, 1.0); cab.lineTo(0.8, 1.0); cab.quadraticCurveTo(0.2, 1.42, -0.1, 1.47); cab.lineTo(-1.2, 1.47); cab.quadraticCurveTo(-1.5, 1.42, -1.6, 1.0);
    const cabin = new THREE.Mesh(new THREE.ExtrudeGeometry(cab, { depth: 1.5, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.04, bevelSegments: 2, curveSegments: 8 }), glass);
    cabin.position.z = -0.75; cabin.castShadow = true; g.add(cabin);
    const roof = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.05, 1.5), paint); roof.position.set(-0.65, 1.5, 0); g.add(roof);
    for (const [wx, wz] of [[1.4, 0.88], [1.4, -0.88], [-1.4, 0.88], [-1.4, -0.88]]) {
      const w = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.24, 18), tire);
      w.rotation.x = Math.PI / 2; w.position.set(wx, 0.34, wz); w.castShadow = true; g.add(w);
      const rm = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.26, 12), rimM);
      rm.rotation.x = Math.PI / 2; rm.position.set(wx, 0.34, wz); g.add(rm);
    }
    const hl = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff4d6, emissiveIntensity: 0.6 });
    const tl = new THREE.MeshStandardMaterial({ color: 0x990000, emissive: 0xff1100, emissiveIntensity: 0.5 });
    for (const z of [-0.6, 0.6]) {
      const h = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.12, 0.35), hl); h.position.set(2.3, 0.78, z); g.add(h);
      const t = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.12, 0.3), tl); t.position.set(-2.24, 0.82, z); g.add(t);
    }
    g.userData.tail = tl;
    return g;
  }

  makeCars() {
    const r = this.r;
    const colors = [0xb71c1c, 0x0d47a1, 0xeeeeee, 0x212121, 0x9e9e9e, 0x1b5e20, 0xf9a825, 0x4a148c, 0x37474f, 0xd84315];
    // moving cars in both lanes
    for (let i = 0; i < 14; i++) {
      const lane = i % 2 === 0 ? 1 : -1; // lane +1: x=+2.4 driving -z
      const car = this.makeCar(colors[Math.floor(r() * colors.length)]);
      const z = -140 + (i / 14) * 280 + r() * 8;
      car.position.set(lane * 2.4, 0.02, z);
      car.rotation.y = lane > 0 ? Math.PI / 2 : -Math.PI / 2; // local +x forward
      this.scene.add(car);
      this.cars.push({ obj: car, lane, z, v: 9 + r() * 3, moving: true, phase: r() * 6, sink: 0 });
    }
    // parked cars along the curb
    for (const side of [-1, 1]) {
      for (let z = -130; z < 130; z += 9 + r() * 14) {
        if (side === 1 && z > 8 && z < 62) continue;
        if (r() < 0.35) continue;
        const car = this.makeCar(colors[Math.floor(r() * colors.length)]);
        car.position.set(side * 4.15, 0.02, z);
        car.rotation.y = side > 0 ? Math.PI / 2 : -Math.PI / 2;
        this.scene.add(car);
        this.cars.push({ obj: car, lane: side, z, v: 0, moving: false, phase: r() * 6, sink: 0, parked: true });
      }
    }
    // the car that will sink in liquefied ground near the plaza
    const sinkCar = this.makeCar(0x1565c0);
    sinkCar.position.set(4.1, 0.02, 44); sinkCar.rotation.y = Math.PI / 2;
    this.scene.add(sinkCar);
    this.sinkers.push({ obj: sinkCar, base: sinkCar.position.clone(), depth: 0.75, tilt: 0.18 });
  }

  makeCracks() {
    const r = this.r;
    const mat = new THREE.MeshBasicMaterial({ color: 0x070605, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4 });
    const lipMat = new THREE.MeshStandardMaterial({ color: 0x3b3128, roughness: 1, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3 });
    const mk = (x0, z0, ang, len, wmax, y, t0) => {
      // random walk polyline
      const pts = [];
      let x = x0, z = z0, a = ang;
      const n = 40;
      for (let i = 0; i <= n; i++) { pts.push([x, z]); a += (r() - 0.5) * 0.5; x += Math.cos(a) * len / n; z += Math.sin(a) * len / n; }
      const make = (scaleW, m, yy) => {
        const pos = new Float32Array((n + 1) * 2 * 3);
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        const idx = [];
        for (let i = 0; i < n; i++) { const a0 = i * 2; idx.push(a0, a0 + 2, a0 + 1, a0 + 1, a0 + 2, a0 + 3); }
        geo.setIndex(idx);
        const mesh = new THREE.Mesh(geo, m);
        mesh.receiveShadow = true;
        this.scene.add(mesh);
        return { mesh, pos, yy, scaleW };
      };
      const widths = pts.map((_, i) => Math.pow(Math.sin(Math.PI * i / n), 0.6) * (0.6 + r() * 0.4));
      const crack = { pts, widths, wmax, t0, layers: [make(1.6, lipMat, y + 0.005), make(1, mat, y + 0.01)] };
      this.cracks.push(crack);
    };
    mk(10, 34, 0.25, 38, 2.2, 0.17, T.cracks);
    mk(-6, 50, -0.25, 30, 1.6, 0.04, T.cracks + 0.8);
    mk(23, 50, -1.25, 26, 1.4, 0.17, T.cracks + 1.4);
    mk(-5, 26, 0.15, 22, 1.2, 0.04, T.cracks + 2.2);
    mk(14, 56, -0.1, 26, 1.5, 0.17, T.cracks + 3.0);
  }

  hillAndCoast() {
    const r = this.r;
    this.boats = [];
    const hullCols = [0xf2f2ee, 0x1f4e79, 0xc0392b, 0x2e7d32, 0xf1c40f];
    for (let i = 0; i < 9; i++) {
      const g = new THREE.Group();
      const sh = new THREE.Shape();
      sh.moveTo(-3, 0.9); sh.lineTo(3.4, 0.9); sh.quadraticCurveTo(3.2, 0.1, 2.0, -0.2); sh.lineTo(-2.8, -0.2); sh.lineTo(-3, 0.9);
      const hull = new THREE.Mesh(new THREE.ExtrudeGeometry(sh, { depth: 2.0, bevelEnabled: true, bevelSize: 0.15, bevelThickness: 0.2, bevelSegments: 2 }), new THREE.MeshStandardMaterial({ color: hullCols[i % 5], roughness: 0.5 }));
      hull.position.z = -1.0; hull.castShadow = true; g.add(hull);
      const cab = new THREE.Mesh(new THREE.BoxGeometry(1.8, 1.2, 1.6), new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6 }));
      cab.position.set(-0.6, 1.5, 0); cab.castShadow = true; g.add(cab);
      const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 4, 6), this.darkMetal);
      mast.position.set(0.3, 2.9, 0); g.add(mast);
      const x = -90 + i * 22 + r() * 8, z = -205 - r() * 70;
      g.position.set(x, 0, z); g.rotation.y = r() * 6.28;
      this.scene.add(g);
      this.boats.push({ obj: g, x, z, phase: r() * 6, tilt: (r() - 0.5) * 0.7 });
    }
    // trees on the hill
    for (let i = 0; i < 160; i++) {
      const x = (r() - 0.5) * 700, z = 175 + r() * 220;
      if (Math.abs(x - 40) < 40 && z > 235 && z < 300) continue; // keep viewpoint open
      this.tree(x, terrainHeight(x, z) - 0.2, z, 1.4 + r() * 1.2, !(Math.abs(x - 40) < 90 && z > 225));
    }
    // houses on the hill
    for (let i = 0; i < 30; i++) {
      const x = (r() - 0.5) * 600, z = 190 + r() * 180;
      if (Math.abs(x - 40) < 50 && z > 225) continue;
      const h = 6 + r() * 4;
      const b = this.addBuilding(x, z, 9 + r() * 4, 9 + r() * 4, h, r() < 0.5 ? 'stucco' : 'brick', { static: true });
      b.group.position.y = terrainHeight(x, z) - 0.5;
    }
    // viewpoint railing
    const rail = new THREE.Mesh(new THREE.BoxGeometry(60, 0.08, 0.08), this.darkMetal);
    rail.position.set(40, terrainHeight(40, 246) + 1.0, 246); this.scene.add(rail);
    for (let i = 0; i < 16; i++) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(0.08, 1.0, 0.08), this.darkMetal);
      p.position.set(10 + i * 4, terrainHeight(10 + i * 4, 246) + 0.5, 246); this.scene.add(p);
    }
    // distant mountains & headlands
    const mtn = new THREE.MeshStandardMaterial({ color: 0x5f7563, roughness: 1, flatShading: false });
    for (let i = 0; i < 14; i++) {
      const rad = 180 + r() * 220, hh = 120 + r() * 200;
      const m = new THREE.Mesh(new THREE.ConeGeometry(rad, hh, 24, 6), mtn);
      const pos = m.geometry.attributes.position;
      for (let k = 0; k < pos.count; k++) { pos.setX(k, pos.getX(k) * (0.85 + r() * 0.3)); pos.setZ(k, pos.getZ(k) * (0.85 + r() * 0.3)); }
      m.geometry.computeVertexNormals();
      m.position.set((r() - 0.5) * 2400, hh / 2 - 10, 700 + r() * 500);
      this.scene.add(m);
    }
    for (const sx of [-1, 1]) {
      const m = new THREE.Mesh(new THREE.ConeGeometry(300, 140, 24, 6), mtn);
      m.scale.set(1, 1, 2.2);
      m.position.set(sx * 950, 40, -500); this.scene.add(m);
    }
  }

  // --------------------------------------------------- per-frame update
  update(t, dt, gm, fx) {
    const e = shakeEnvelope(t);
    // building sway (rotation around base)
    for (const b of this.buildings) {
      const f = 0.5 + 18 / (b.h + 10);
      const a = e * (0.004 + b.h * 0.00016) * b.stiff;
      b.group.rotation.z = a * Math.sin(t * f * 6.28 * 0.45 + b.phase) + b.tilt;
      b.group.rotation.x = a * 0.8 * Math.sin(t * f * 6.28 * 0.38 + b.phase * 1.3);
      b.group.position.x = b.x + gm.x * 0.0; // ground motion applied to camera instead
    }
    // collapses
    for (const c of this.collapsers) {
      if (t >= c.t0 && !c.started) {
        c.started = true;
        c.b.group.visible = false;
        for (const ch of c.chunks) ch.mesh.visible = true;
        fx.burstDust(c.x + (c.x < 0 ? 6 : -6), 0, c.z, 90, 14, c.h);
        fx.debrisBurst(c.x, c.h * 0.5, c.z, 120, c.x < 0 ? 1 : -1);
      }
      if (!c.started) {
        // pre-collapse: building leans and shakes harder
        const k = smooth(c.t0 - 4, c.t0, t);
        c.b.tilt = (c.x < 0 ? -1 : 1) * 0.02 * k;
        continue;
      }
      const tc = t - c.t0;
      for (const ch of c.chunks) {
        if (ch.settled) continue;
        if (tc < ch.delay) { ch.mesh.position.copy(ch.start); continue; }
        // fall with gravity, drift toward rest position
        ch.vel.y -= 9.8 * dt;
        ch.pos.y += ch.vel.y * dt;
        const k = clamp((tc - ch.delay) / 2.2, 0, 1);
        ch.pos.x = lerp(ch.start.x, ch.rest.x, k * k * (3 - 2 * k));
        ch.pos.z = lerp(ch.start.z, ch.rest.z, k * k * (3 - 2 * k));
        ch.rot.x += ch.spin.x * dt; ch.rot.y += ch.spin.y * dt; ch.rot.z += ch.spin.z * dt;
        if (ch.pos.y <= ch.rest.y) {
          ch.pos.y = ch.rest.y;
          if (ch.vel.y < -3) { ch.vel.y *= -0.18; fx.puff(ch.pos.x, ch.pos.y, ch.pos.z, 2); }
          else { ch.settled = true; ch.rot.copy(ch.restRot); }
        }
        ch.mesh.position.copy(ch.pos);
        ch.mesh.rotation.copy(ch.rot);
      }
      if (tc < 3.5) fx.emitDustColumn(c.x, c.z, c.d, c.w, tc, dt);
    }
    // props sway
    for (const p of this.props) {
      const a = e * p.amp * 3;
      p.obj.rotation.z = a * Math.sin(t * p.freq * 3 + p.phase);
      p.obj.rotation.x = a * 0.7 * Math.sin(t * p.freq * 2.6 + p.phase * 2);
      if (p.crown) p.crown.rotation.z = 0.02 * Math.sin(t * 1.3 + p.phase) + a * 1.5 * Math.sin(t * p.freq * 4 + p.phase);
    }
    // utility poles
    for (const p of this.poles) {
      const sway = e * 0.06 * Math.sin(t * 5 + p.z);
      if (p.fall !== null && t > p.fall) {
        const k = t - p.fall;
        p.ang = Math.min(1.35, p.ang + dt * (0.3 + k * 2.2));
        if (!p.sparked) { p.sparked = true; fx.sparks(-6.5, 8.5, p.z, 70); }
      }
      p.obj.rotation.z = -(p.ang) - sway; // fall toward +x (street)
      p.obj.rotation.x = e * 0.03 * Math.sin(t * 4.3 + p.z);
    }
    // cables
    const tmp = new THREE.Vector3();
    for (const c of this.cables) {
      const pos = c.line.geometry.attributes.position;
      const A = new THREE.Vector3(c.off, 9.4, 0); c.a.obj.localToWorld(A);
      const B = new THREE.Vector3(c.off, 9.4, 0); c.b.obj.localToWorld(B);
      const sag = 1.2 + e * 0.6;
      for (let i = 0; i < 20; i++) {
        const k = i / 19;
        tmp.lerpVectors(A, B, k);
        tmp.y -= sag * 4 * k * (1 - k);
        tmp.x += e * 0.9 * Math.sin(t * 3.1 + c.phase) * 4 * k * (1 - k);
        pos.setXYZ(i, tmp.x, tmp.y, tmp.z);
      }
      pos.needsUpdate = true;
    }
    // cars
    for (const c of this.cars) {
      if (c.moving) {
        const brake = t > T.pStart + 1.5;
        if (brake) c.v = Math.max(0, c.v - dt * 5.5);
        c.z += -c.lane * c.v * dt;
        if (c.z < -150) c.z += 290;
        if (c.z > 140) c.z -= 290;
        c.obj.position.z = c.z;
        if (c.obj.userData.tail) c.obj.userData.tail.emissiveIntensity = brake ? 2.5 : 0.5;
      }
      // bounce on suspension
      c.obj.position.y = 0.02 + e * 0.06 * Math.abs(Math.sin(t * 9 + c.phase));
      c.obj.rotation.x = e * 0.04 * Math.sin(t * 7 + c.phase);
    }
    for (const s of this.sinkers) {
      const k = smooth(T.cracks + 0.5, T.cracks + 7, t);
      s.obj.position.y = s.base.y - s.depth * k;
      s.obj.rotation.x = s.tilt * k;
      s.obj.rotation.z = -0.08 * k;
    }
    // cracks
    for (const c of this.cracks) {
      const k = smooth(c.t0, c.t0 + 3.5, t) * (1 + 0.05 * Math.sin(t * 9) * e);
      for (const L of c.layers) {
        const n = c.pts.length;
        for (let i = 0; i < n; i++) {
          const [x, z] = c.pts[i];
          const [x2, z2] = c.pts[Math.min(n - 1, i + 1)];
          const [x1, z1] = c.pts[Math.max(0, i - 1)];
          let dx = x2 - x1, dz = z2 - z1; const l = Math.hypot(dx, dz) || 1; dx /= l; dz /= l;
          // propagation along the crack
          const grow = smooth(i / n - 0.3, i / n, k * 1.3);
          const w = c.widths[i] * c.wmax * k * grow * L.scaleW * 0.5 + 0.001;
          L.pos[i * 6] = x - dz * w; L.pos[i * 6 + 1] = L.yy; L.pos[i * 6 + 2] = z + dx * w;
          L.pos[i * 6 + 3] = x + dz * w; L.pos[i * 6 + 4] = L.yy; L.pos[i * 6 + 5] = z - dx * w;
        }
        L.mesh.geometry.attributes.position.needsUpdate = true;
        L.mesh.geometry.computeBoundingSphere();
        L.mesh.visible = k > 0.001;
      }
    }
    if (this.boats) {
      const sl = -0.4 - 7.5 * smooth(T.recedeStart, T.recedeStart + 8, t);
      for (const b of this.boats) {
        const ground = terrainHeight(b.x, b.z) + 0.25;
        const grounded = smooth(ground + 0.6, ground, sl);
        b.obj.position.y = Math.max(sl - 0.3, ground) + 0.1 * Math.sin(t * 1.2 + b.phase) * (1 - grounded);
        b.obj.rotation.z = 0.04 * Math.sin(t * 0.9 + b.phase) * (1 - grounded) + b.tilt * grounded;
      }
    }
    if (this.fountainWater) {
      this.fountainWater.position.y = 0.75 + e * 0.15 * Math.sin(t * 8);
      this.fountainWater.rotation.z = e * 0.05;
      this.fountainTop.rotation.z = e * 0.05 * Math.sin(t * 6);
    }
  }
}
