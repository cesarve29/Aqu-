// Interiores de Invernalia: pasadizo de arcos, patio y porton, Gran Salon con engranajes y criptas.
import { THREE, Grid, vox, mat, sd, hash3, rng, clamp, jitter, shade, mix } from './kit.js';
import { gearGrid } from './props.js';

export const IO = [1000, 0, 0]; // origen del set interior

const STONE = [0x4a4440, 0x55504a, 0x403a36, 0x5e5852];
const st = (x, y, z) => STONE[Math.floor(hash3(x >> 1, y >> 1, z >> 1) * 4)];

// pasadizo de arcos (eje z), patio y porton con dovelas
function buildPassage() {
  const v = 0.1, NX = 160, NY = 70, NZ = 200; // x -8..8 , z -10..10
  const g = new Grid(NX, NY, NZ);
  const cx = 80, cz = 100;
  // suelo
  g.box(0, 0, 0, NX - 1, 0, NZ - 1, (x, y, z) => (hash3(x >> 2, 0, z >> 2) < 0.5 ? 0x3a3532 : 0x45403c));
  // tunel de arcos: z de 0 a 8 (voxel cz..cz+80)
  for (let k = 0; k < 6; k++) {
    const zc = cz + 8 + k * 14;
    g.sdf((x, y, z) => {
      const outer = sd.box(x, y, z, cx, 24, zc, 26, 24, 3);
      const dx = x - cx; const archY = 26 + Math.sqrt(Math.max(0, 196 - dx * dx));
      const hole = Math.abs(dx) < 14 && y < archY ? -1 : 1;
      return Math.max(outer, -hole);
    }, st, [cx - 27, 0, zc - 4, cx + 27, 49, zc + 4]);
    // muros laterales del tunel
    g.box(cx - 26, 0, zc, cx - 22, 48, zc + 14, st); g.box(cx + 22, 0, zc, cx + 26, 48, zc + 14, st);
    g.box(cx - 26, 44, zc, cx + 26, 48, zc + 14, st);
  }
  // patio: muros con almenas (z negativo)
  for (let x = 0; x < NX; x++) for (let z = 0; z < cz - 2; z++) {
    const wallL = x < 8, wallBack = z < 8;
    if (!wallL && !wallBack) continue;
    const h = 52 + (((x + z) >> 2) % 2 ? 5 : 0);
    for (let y = 1; y < h; y++) g.set(x, y, z, st(x, y, z));
  }
  // muro derecho con porton (x alto)
  for (let z = 0; z < cz - 2; z++) for (let x = NX - 10; x < NX; x++) {
    const dz = z - (cz - 50); const archTop = 30 + Math.sqrt(Math.max(0, 256 - dz * dz));
    const door = Math.abs(dz) < 16 && 0 < archTop && true;
    for (let y = 1; y < 60; y++) {
      if (Math.abs(dz) < 16 && y < archTop) continue;
      // dovelas en abanico alrededor del arco
      const r = Math.hypot(dz, y - 30);
      const fan = r > 16 && r < 24 && y > 28;
      const col = fan ? (Math.floor(Math.atan2(y - 30, dz) * 9) % 2 ? 0x6a5a4c : 0x5a4c40) : st(x, y, z);
      g.set(x, y, z, col);
    }
  }
  const m = vox(g, v, [cx, 0, cz], 'istone', { roughness: 0.9 });
  return m;
}

// Gran Salon: eje +x
function buildHall() {
  const v = 0.1, NX = 240, NY = 90, NZ = 120;
  const g = new Grid(NX, NY, NZ);
  const cz = 60;
  const WOOD = [0x4a3424, 0x5a4230, 0x3c2a1e];
  const wd = (x, y, z) => WOOD[Math.floor(hash3(x, y >> 1, z >> 2) * 3)];
  g.box(0, 0, 0, NX - 1, 0, NZ - 1, (x, y, z) => (hash3(x >> 3, 0, z >> 1) < 0.5 ? 0x2a221c : 0x352b23));
  // muros
  g.box(0, 0, 0, NX - 1, 85, 4, st); g.box(0, 0, NZ - 5, NX - 1, 85, NZ - 1, st); g.box(NX - 5, 0, 0, NX - 1, 85, NZ - 1, st);
  // pilares
  for (let x = 20; x < NX - 20; x += 36) for (const z of [12, NZ - 13]) g.box(x - 3, 0, z - 3, x + 3, 85, z + 3, wd);
  // ventana de luz en el muro izquierdo
  g.carve((x, y, z) => sd.box(x, y, z, 40, 40, 2, 6, 14, 4));
  // mesas largas y bancos
  for (const z of [35, 85]) {
    g.box(30, 6, z - 4, 175, 7, z + 4, wd);
    for (let x = 34; x < 175; x += 20) for (const dz of [-3, 3]) g.box(x, 0, z + dz, x + 1, 6, z + dz, wd);
    g.box(30, 3, z - 9, 175, 3, z - 7, wd); g.box(30, 3, z + 7, 175, 3, z + 9, wd);
  }
  // tarima y mesa alta con mantel blanco
  g.box(190, 0, 10, 232, 4, 110, (x, y, z) => wd(x, y, z));
  g.box(198, 5, 25, 214, 11, 95, (x, y, z) => (y >= 10 || z < 26 || z > 94 || x < 199 ? 0xd8d2c4 : 0x2a2018));
  // barandilla delante de la tarima
  g.box(186, 5, 10, 187, 13, 110, (x, y, z) => (y === 13 ? 0xb8944a : 0x3a2c22));
  for (let z = 12; z < 110; z += 6) g.box(186, 5, z, 187, 12, z, 0xa8843e);
  // sillas altas
  for (let z = 32; z < 92; z += 10) g.box(218, 5, z, 222, 22, z + 5, wd);
  // chimenea con rejilla naranja en el fondo
  g.box(NX - 9, 0, cz - 18, NX - 5, 46, cz + 18, st);
  for (let y = 4; y < 34; y++) for (let z = cz - 12; z <= cz + 12; z++) {
    const bar = (z - cz + 12) % 3 === 0 || y % 4 === 0;
    g.set(NX - 10, y, z, bar ? 0x2a1c12 : 0xffa040);
    if (!bar) g.setE(NX - 10, y, z, 255);
  }
  // relieve de lobo sobre la chimenea (cuadrado tallado)
  g.box(NX - 10, 38, cz - 8, NX - 10, 52, cz + 8, (x, y, z) => ((y + z) % 5 === 0 ? 0x8a7a6a : 0x5a4e44));
  const m = vox(g, v, [0, 0, cz], 'hall', { roughness: 0.85, emiGain: 1.1, emiTint: 0xffb060 });
  return m;
}

// estatua de rey sentado
function statueGrid() {
  const g = new Grid(14, 34, 14);
  const S = (x, y, z) => jitter(0x6a645e, 0.2, x, y, z);
  g.box(1, 0, 1, 12, 5, 12, S); // pedestal
  g.box(3, 6, 4, 10, 13, 11, S); // regazo/trono
  g.box(3, 13, 6, 10, 22, 10, S); // torso
  g.box(4, 22, 6, 9, 28, 10, S); // cabeza
  g.box(4, 28, 6, 9, 29, 10, (x, y, z) => ((x + z) % 2 ? 0x7a746c : 0x5a544e)); // corona
  g.box(6, 6, 2, 7, 20, 3, 0x4a4642); // espada
  g.box(2, 13, 6, 3, 20, 10, S); g.box(10, 13, 6, 11, 20, 10, S); // brazos
  return g;
}

function buildCrypt() {
  const v = 0.1, NX = 600, NY = 40, NZ = 60; // x 0..60 , z -3..3 , y 0..4
  const g = new Grid(NX, NY, NZ);
  const cz = 30;
  g.box(0, 0, 0, NX - 1, 0, NZ - 1, (x, y, z) => (hash3(x >> 2, 0, z >> 2) < 0.15 ? 0x1e1a18 : (hash3(x >> 2, 1, z >> 2) < 0.5 ? 0x3a3430 : 0x2e2a26)));
  // boveda
  for (let x = 0; x < NX; x++) for (let z = 0; z < NZ; z++) {
    const dz = z - cz;
    const vault = 30 + Math.sqrt(Math.max(0, 900 - dz * dz)) * 0.25;
    for (let y = Math.floor(vault); y < NY; y++) g.set(x, y, z, st(x, y, z));
    if (Math.abs(dz) > 27) for (let y = 0; y < NY; y++) g.set(x, y, z, st(x, y, z));
  }
  // columnas cada 3 m
  for (let x = 15; x < NX; x += 30) for (const z of [4, NZ - 5]) g.box(x - 2, 0, z - 2, x + 2, NY - 1, z + 2, st);
  // arcos transversales
  for (let x = 15; x < NX; x += 30) g.box(x - 1, 34, 0, x + 1, NY - 1, NZ - 1, st);
  const m = vox(g, v, [0, 0, cz], 'crypt', { roughness: 0.9 });
  return m;
}

export class NorthInteriors {
  constructor(parent) {
    this.root = new THREE.Group(); this.root.position.set(...IO); parent.add(this.root);
    const r = this.root;
    this.passage = buildPassage(); r.add(this.passage);
    this.hall = buildHall(); this.hall.position.set(8.5, 0, -5); r.add(this.hall);
    // engranajes del techo
    this.gears = [];
    const R = rng(12);
    for (let i = 0; i < 26; i++) {
      const Rv = 10 + Math.floor(R() * 26);
      const m = vox(gearGrid(Rv, Math.round(Rv * 0.9), 3, R() < 0.5 ? 0xa07a3a : 0x8a6a40), 0.06, [Rv + 3, 0, Rv + 3], 'gear', { roughness: 0.4, metalness: 0.8 });
      m.position.set(8.5 + 2 + R() * 20, 5.2 + R() * 1.6, -5 - 4.5 + R() * 9); m.userData.sp = (R() - 0.5) * 1.2;
      r.add(m); this.gears.push(m);
    }
    this.crypt = buildCrypt(); this.crypt.position.set(8, -10, -5); r.add(this.crypt);
    // estatuas y velas
    const sg = statueGrid();
    const pts = [];
    const cand = [];
    for (let x = 1.5; x < 60; x += 3) for (const s of [-1, 1]) {
      pts.push([8 + x + 1.5, -10, -5 + s * 2.1, s > 0 ? Math.PI : 0]);
      cand.push([8 + x + 0.2, -10 + 1.9, -5 + s * 2.55]);
    }
    const stTmp = vox(sg, 0.1, [7, 0, 7], 'statue', { roughness: 0.9 });
    const im = new THREE.InstancedMesh(stTmp.geometry, stTmp.material, pts.length);
    const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), E = new THREE.Euler();
    pts.forEach((p, i) => { E.set(0, p[3] + Math.PI / 2, 0); Q.setFromEuler(E); M.compose(new THREE.Vector3(p[0], p[1], p[2]), Q, new THREE.Vector3(1, 1, 1)); im.setMatrixAt(i, M); });
    r.add(im);
    // velas: cuerpo + llama emisiva
    const cg = new Grid(3, 8, 3); cg.box(1, 0, 1, 1, 4, 1, 0xe8e0c8); cg.box(1, 5, 1, 1, 7, 1, 0xffc070); for (let y = 5; y < 8; y++) cg.setE(1, y, 1, 255);
    const cTmp = vox(cg, 0.04, [1.5, 0, 1.5], 'candle', { emiGain: 6, emiTint: 0xffb050 });
    const ci = new THREE.InstancedMesh(cTmp.geometry, cTmp.material, cand.length * 3);
    let k = 0;
    cand.forEach((p) => { for (let j = 0; j < 3; j++) { M.makeTranslation(p[0] + j * 0.12 - 0.12, p[1] + (j === 1 ? 0.05 : 0), p[2]); ci.setMatrixAt(k++, M); } });
    r.add(ci);
    this.candles = cand;
    this.cl = [0, 1, 2, 3, 4, 5].map(() => { const l = new THREE.PointLight(0xffa850, 4, 7, 1.6); r.add(l); return l; });
    // luz del salon
    this.hallFire = new THREE.PointLight(0xff9a40, 18, 22, 1.4); this.hallFire.position.set(31, 2, -5); r.add(this.hallFire);
    this.hallWin = new THREE.SpotLight(0xbcc8dc, 60, 30, 0.5, 0.6, 1.2); this.hallWin.position.set(12.5, 5, -12); this.hallWin.target.position.set(15, 0, -4); r.add(this.hallWin); r.add(this.hallWin.target);
    this.amb = new THREE.HemisphereLight(0x6a6a78, 0x1a1410, 0.5); r.add(this.amb);
    this.passLight = new THREE.DirectionalLight(0xaab4c8, 1.2); this.passLight.position.set(-5, 20, 15); r.add(this.passLight);
    // arciano visto por el tunel (copia)
    this.treeSpot = new THREE.Group(); this.treeSpot.position.set(0, 0, 16); r.add(this.treeSpot);
  }
  attachTree(trunkGeo, trunkMat, leafGeo, leafMat) {
    const a = new THREE.Mesh(trunkGeo, mat('bark')), b = new THREE.Mesh(leafGeo, leafMat);
    a.scale.setScalar(0.7); b.scale.setScalar(0.7);
    const l = new THREE.PointLight(0xc8d4ff, 30, 12, 1.5); l.position.set(1.5, 3, -2); this.treeSpot.add(l);
    this.treeSpot.add(a); this.treeSpot.add(b);
  }
  update(lt, cam, st) {
    this.amb.intensity = st.amb ?? 0.5;
    this.passLight.intensity = st.pass ?? 1.2;
    this.hallFire.intensity = st.fire ?? 8;
    this.hallWin.intensity = st.win ?? 60;
    this.gears.forEach((g) => (g.rotation.y = lt * g.userData.sp));
    // luces de vela mas cercanas por delante de la camara
    const cx = cam.position.x - this.root.position.x;
    const near = this.candles.filter((p) => p[0] > cx - 1).slice(0, 6);
    this.cl.forEach((l, i) => { const p = near[i] || [0, -50, 0]; l.position.set(p[0], p[1] + 0.3, p[2] - Math.sign(p[2] + 5) * 0.2); l.intensity = (st.candle ?? 4) * (0.85 + 0.15 * Math.sin(lt * 11 + i * 2)); });
  }
}
