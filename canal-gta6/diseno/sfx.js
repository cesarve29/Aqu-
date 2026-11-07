// Efectos de sonido sintetizados (originales, sin derechos de terceros) + mezclador por línea de tiempo.
const fs = require('fs');
const SR = 48000;
let seed = 12345;
const noise = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;

// Cada efecto devuelve Float32Array mono
const fx = {
  // golpe cinematográfico: caída de tono grave + ruido
  impacto(len = 1.6) {
    const n = Math.round(len * SR), a = new Float32Array(n); let ph = 0, lp = 0;
    for (let i = 0; i < n; i++) { const t = i / SR;
      ph += 2 * Math.PI * (40 + 110 * Math.exp(-14 * t)) / SR;
      lp += 0.08 * (noise() - lp);
      a[i] = 0.95 * Math.sin(ph) * Math.exp(-2.6 * t) + 0.55 * lp * Math.exp(-9 * t) + 0.25 * noise() * Math.exp(-40 * t); }
    return a;
  },
  // tic de reloj (alto) / tac (más grave)
  tic(f = 2400) {
    const n = Math.round(0.07 * SR), a = new Float32Array(n);
    for (let i = 0; i < n; i++) { const t = i / SR;
      a[i] = 0.7 * Math.sin(2 * Math.PI * f * t) * Math.exp(-70 * t) + 0.35 * noise() * Math.exp(-160 * t) + 0.3 * Math.sin(2 * Math.PI * f * 0.5 * t) * Math.exp(-50 * t); }
    return a;
  },
  // barrido de aire para cortes / textos que entran
  whoosh(len = 0.45) {
    const n = Math.round(len * SR), a = new Float32Array(n); let lp = 0;
    for (let i = 0; i < n; i++) { const x = i / n;
      const c = 0.02 + 0.35 * Math.sin(Math.PI * x);   // filtro que se abre y cierra
      lp += c * (noise() - lp);
      a[i] = lp * Math.sin(Math.PI * x) ** 1.5 * 1.6; }
    return a;
  },
  // subida de tensión antes del golpe final
  subida(len = 1.0) {
    const n = Math.round(len * SR), a = new Float32Array(n); let ph = 0, lp = 0;
    for (let i = 0; i < n; i++) { const x = i / n;
      ph += 2 * Math.PI * (200 + 1400 * x * x) / SR; lp += (0.02 + 0.4 * x) * (noise() - lp);
      a[i] = (0.35 * Math.sign(Math.sin(ph)) * 0.5 + 0.5 * lp) * x * x; }
    return a;
  },
  // chispazo de neón (zumbido eléctrico corto)
  neon(len = 0.35) {
    const n = Math.round(len * SR), a = new Float32Array(n);
    for (let i = 0; i < n; i++) { const t = i / SR; const on = (Math.floor(t / 0.03) % 3) !== 1 ? 1 : 0.15;
      a[i] = on * (0.35 * Math.sign(Math.sin(2 * Math.PI * 120 * t)) * 0.4 + 0.25 * noise()) * Math.exp(-5 * t); }
    return a;
  },
  // "pop" para etiquetas
  pop() {
    const n = Math.round(0.15 * SR), a = new Float32Array(n); let ph = 0;
    for (let i = 0; i < n; i++) { const t = i / SR; ph += 2 * Math.PI * (300 + 900 * Math.exp(-30 * t)) / SR;
      a[i] = 0.8 * Math.sin(ph) * Math.exp(-28 * t); }
    return a;
  },
  // acorde synthwave corto (golpe final)
  stab(len = 1.4) {
    const n = Math.round(len * SR), a = new Float32Array(n), fr = [220, 277.18, 329.63, 440, 554.37];
    for (let i = 0; i < n; i++) { const t = i / SR; let v = 0;
      for (const f of fr) v += Math.sin(2 * Math.PI * f * t + 0.6 * Math.sin(2 * Math.PI * f * 2 * t)) + 0.4 * Math.sin(2 * Math.PI * f * 1.007 * t);
      a[i] = v / fr.length * 0.6 * Math.min(1, t / 0.005) * Math.exp(-2.2 * t); }
    return a;
  },
  // ráfaga de "glitch" para transiciones rápidas
  glitch(len = 0.18) {
    const n = Math.round(len * SR), a = new Float32Array(n); let hold = 0;
    for (let i = 0; i < n; i++) { if (i % 220 === 0) hold = noise(); a[i] = hold * 0.5 * (1 - i / n); }
    return a;
  },
};

// Mezcla eventos [{t, fx, gain, pan, args}] en un WAV estéreo de 'dur' segundos
function mix(events, dur, out) {
  const n = Math.round(dur * SR), L = new Float32Array(n), R = new Float32Array(n);
  for (const e of events) {
    const s = fx[e.fx](...(e.args || [])), g = e.gain ?? 1, pan = e.pan ?? 0;
    const off = Math.round(e.t * SR);
    for (let i = 0; i < s.length && off + i < n; i++) { if (off + i < 0) continue;
      L[off + i] += s[i] * g * (1 - Math.max(0, pan)); R[off + i] += s[i] * g * (1 + Math.min(0, pan)); }
  }
  // eco corto para dar espacio
  const d = Math.round(0.11 * SR);
  for (let i = d; i < n; i++) { L[i] += 0.22 * R[i - d]; R[i] += 0.22 * L[i - d]; }
  let peak = 1e-9; for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
  const k = 0.89 / peak, buf = Buffer.alloc(44 + n * 4);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 4, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 4, 28);
  buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) { buf.writeInt16LE(Math.round(L[i] * k * 32767), 44 + i * 4); buf.writeInt16LE(Math.round(R[i] * k * 32767), 46 + i * 4); }
  fs.writeFileSync(out, buf);
}

module.exports = { fx, mix, SR };
