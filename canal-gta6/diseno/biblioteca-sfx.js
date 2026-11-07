// Biblioteca de efectos de sonido del canal (generados con ElevenLabs, en ../sfx/<nombre>-<n>.mp3).
// mezclar(eventos, duracion, salida.wav): eventos = [{t, sfx, gain, pan, variante, alFinal}]
//   alFinal: true -> el efecto TERMINA en t (útil para subidas de tensión)
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const SR = 48000;
const DIR = path.join(__dirname, '..', 'sfx');
const cache = {};

function variantes(nombre) {
  return fs.readdirSync(DIR).filter(f => f.startsWith(nombre + '-') && f.endsWith('.mp3')).sort();
}
function cargar(nombre, v = 0) {
  const vs = variantes(nombre);
  if (!vs.length) throw new Error(`No hay efecto "${nombre}" en ${DIR}`);
  const file = vs[v % vs.length];
  if (cache[file]) return cache[file];
  // decodifica a estéreo float 48 kHz y recorta el silencio inicial
  const raw = execFileSync('ffmpeg', ['-nostdin', '-loglevel', 'error', '-i', path.join(DIR, file),
    '-af', 'silenceremove=start_periods=1:start_threshold=-45dB', '-ac', '2', '-ar', String(SR), '-f', 'f32le', '-'], { maxBuffer: 1 << 28 });
  const f = new Float32Array(raw.buffer, raw.byteOffset, raw.length / 4);
  let peak = 1e-9; for (const x of f) peak = Math.max(peak, Math.abs(x));
  const out = new Float32Array(f.length); for (let i = 0; i < f.length; i++) out[i] = f[i] / peak;
  return (cache[file] = out);
}

function mezclar(eventos, dur, salida) {
  const n = Math.round(dur * SR), L = new Float32Array(n), R = new Float32Array(n);
  for (const e of eventos) {
    const s = cargar(e.sfx, e.variante || 0), g = e.gain ?? 1, pan = e.pan ?? 0, len = s.length / 2;
    const off = Math.round((e.alFinal ? e.t - len / SR : e.t) * SR);
    for (let i = 0; i < len; i++) { const k = off + i; if (k < 0 || k >= n) continue;
      L[k] += s[2 * i] * g * Math.min(1, 1 - pan); R[k] += s[2 * i + 1] * g * Math.min(1, 1 + pan); }
  }
  // limitador suave + normalización
  let peak = 1e-9; for (let i = 0; i < n; i++) { L[i] = Math.tanh(L[i] * 0.9); R[i] = Math.tanh(R[i] * 0.9); peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i])); }
  const k = 0.93 / peak, buf = Buffer.alloc(44 + n * 4);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 4, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 4, 28);
  buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 4, 40);
  for (let i = 0; i < n; i++) { buf.writeInt16LE(Math.round(L[i] * k * 32767), 44 + i * 4); buf.writeInt16LE(Math.round(R[i] * k * 32767), 46 + i * 4); }
  fs.writeFileSync(salida, buf);
}

module.exports = { mezclar, variantes, SR };
