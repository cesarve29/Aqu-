// Lista de planos (tiempos medidos sobre el video original).
import * as THREE from 'three';
import { smooth, smoother, lerp, clamp, range } from './voxel.js';
import { blendPose } from './characters.js';

// interpolacion por keyframes: keys = [[t, valor(es)], ...]
export function kf(t, keys, ease = smooth) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [ta, va] = keys[i], [tb, vb] = keys[i + 1];
    if (t <= tb) {
      const k = ease((t - ta) / (tb - ta));
      if (typeof va === 'number') return lerp(va, vb, k);
      return va.map((v, j) => lerp(v, vb[j], k));
    }
  }
  return keys[keys.length - 1][1];
}
// pose por keyframes
export function kpose(t, keys) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [ta, a] = keys[i], [tb, b] = keys[i + 1];
    if (t <= tb) return blendPose(a, b, smooth((t - ta) / (tb - ta)));
  }
  return keys[keys.length - 1][1];
}
const sin = Math.sin, cos = Math.cos, PI = Math.PI;

// ---------------------------------------------------------------------------
// Poses
// ---------------------------------------------------------------------------
export const POSE = {
  jonCradle: {
    hpL: [-1.45, 0.25, 0], knL: [2.7, 0, 0], hpR: [-1.45, -0.25, 0], knR: [2.7, 0, 0],
    spine: [0.38, -0.15, 0], neck: [0.15, -0.2, 0], head: [0.3, -0.45, 0],
    shR: [-0.9, 0.3, -0.15], elR: [-0.7, 0, 0], shL: [-0.7, 0, 0.45], elL: [-1.2, 0, 0],
    expr: { eyes: 'squint', mouth: 'closed', brow: 'sad', tears: true },
  },
  danyCradled: {
    spine: [0.1, 0, 0], neck: [-0.3, -0.3, 0], head: [-0.25, -0.5, 0],
    shL: [0.1, 0, 0.25], elL: [-0.3, 0, 0], shR: [0.3, 0, -0.6], elR: [-0.2, 0, 0],
    hpL: [0.5, 0, 0.05], hpR: [0.5, 0, -0.05], hair: 0.6,
    expr: { eyes: 'closed', mouth: 'part', brow: 'neutral' }, dagger: false,
  },
};

// coloca a Dany acostada boca arriba con la cabeza hacia -x
function danyLying(D, pos, yaw = 0) {
  D.dany.root.position.set(...pos);
  D.dany.root.rotation.set(-PI / 2, PI / 2 + yaw, 0, 'YXZ');
}
// acostada con la cabeza hacia -x, el frente girado 'up' rad desde +z hacia el cielo
function danyCradledAt(D, pos, up = 0.9, yaw = 0) {
  D.dany.root.position.set(...pos);
  D.dany.root.rotation.set(-up, yaw, PI / 2, 'XYZ');
}

// ---------------------------------------------------------------------------
// Planos
// ---------------------------------------------------------------------------
export const SHOTS = [
  {
    // 0:00 - 0:45.8  Primer plano: Jon llora sosteniendo a Daenerys. Drogon aparece al fondo (~0:30).
    t0: 0, t1: 45.8,
    run(D, lt) {
      const jon = D.jon, dany = D.dany;
      jon.root.position.set(0, 0.42, 0); jon.root.rotation.set(0, 0, 0);
      const sob = sin(lt * 2.1) * 0.5 + 0.5;
      const p = { ...POSE.jonCradle };
      p.spine = [0.3 + sob * 0.04 + sin(lt * 0.4) * 0.03, -0.1 + sin(lt * 0.3) * 0.04, 0];
      p.neck = [0.12 + sin(lt * 0.7) * 0.04, -0.1, 0];
      p.head = [0.25 + kf(lt, [[0, 0], [8, 0.08], [16, -0.05], [26, 0.1], [34, 0], [40, -0.12], [45.8, -0.05]]), -0.25 + kf(lt, [[0, -0.05], [12, 0.05], [24, -0.1], [36, 0.0], [45.8, -0.05]]), 0];
      const crying = (lt > 9 && lt < 12) || (lt > 19 && lt < 22.5) || (lt > 27 && lt < 29);
      p.expr = { eyes: lt > 40 ? 'open' : 'squint', mouth: crying ? 'open' : 'closed', brow: 'sad', tears: true };
      jon.pose(p);
      danyCradledAt(D, [0.32, 0.52, 0.4], 0.9, 0);
      dany.pose(POSE.danyCradled);
      // Drogon al fondo (aparece a los ~30 s, desenfocado)
      if (lt > 28) {
        D.drogon.root.visible = true;
        const k = smooth(range(lt, 28, 45));
        D.drogon.pose({
          pos: [lerp(-14, -6.5, k), 0, lerp(-16, -8.5, k)], yaw: lerp(0.9, 0.75, k), bodyY: 2.2, pitch: 0.05,
          neckPitch0: -0.15, neckPitch1: 0.3, headPitch: 0.25, neckYaw0: 0.1, neckYaw1: 0.15,
          wing: { raise: -0.5, sweep: 1.1, elbow: 2.2, spread: 0.15, wrist: -0.4 }, hip: 0.4, knee: -0.6,
        });
      }
      // camara: leve deriva, a la altura del pecho de Jon mirando hacia el fondo
      const cp = kf(lt, [[0, [0.15, 0.48, 2.6]], [20, [0.2, 0.5, 2.55]], [30, [0.1, 0.46, 2.65]], [45.8, [0.15, 0.48, 2.58]]]);
      const cl = kf(lt, [[0, [-0.15, 0.85, 0.15]], [20, [-0.12, 0.86, 0.12]], [30, [-0.17, 0.85, 0.12]], [45.8, [-0.15, 0.85, 0.12]]]);
      D.camera([cp[0] + sin(lt * 0.5) * 0.01, cp[1] + sin(lt * 0.37) * 0.008, cp[2]], cl, 30);
      D.focus(2.5, 0.004, 0.02);
      D.setSun([-7, 14, -12], [0, 1, 0], 3);
      D.fx.ash.visible = true; D.fx.ash.update(lt, [0, 1.6, 0], [5, 4, 5], { speed: 0.25, scale: 0.8 });
    },
  },
];
