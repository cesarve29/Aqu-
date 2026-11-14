// Genera los efectos de sonido de la publicidad con síntesis pura (sin
// archivos externos). Todos son graves/cálidos: nada de timbres agudos.
// Uso: npm run sfx
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_RATE = 48000;
const outDir = join(dirname(fileURLToPath(import.meta.url)), "../public/sfx");

// Ruido determinista para que cada ejecución produzca el mismo archivo.
const makeNoise = (seed) => {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 2147483648 - 1;
  };
};

const render = (seconds, fn) => {
  const samples = new Float32Array(Math.round(seconds * SAMPLE_RATE));
  for (let i = 0; i < samples.length; i++) {
    samples[i] = fn(i / SAMPLE_RATE, i);
  }
  return samples;
};

// Filtro paso bajo de un polo: recorta los agudos.
const lowpass = (samples, cutoff) => {
  const k = 1 - Math.exp((-2 * Math.PI * cutoff) / SAMPLE_RATE);
  let y = 0;
  return samples.map((x) => (y += k * (x - y)));
};

// Ruido filtrado en una banda cuyo centro se mueve con el tiempo (barrido).
const sweptNoise = (seconds, seed, centerAt, q) => {
  const noise = makeNoise(seed);
  let low = 0;
  let band = 0;
  return render(seconds, (t) => {
    const f = 2 * Math.sin((Math.PI * centerAt(t)) / SAMPLE_RATE);
    const high = noise() - low - band / q;
    band += f * high;
    low += f * band;
    return band;
  });
};

// Tono cuya frecuencia cae rápido: el "golpe" de un bombo.
const drop = (seconds, from, to, speed) => {
  let phase = 0;
  return render(seconds, (t) => {
    phase +=
      (2 * Math.PI * (to + (from - to) * Math.exp(-t * speed))) / SAMPLE_RATE;
    return (
      Math.sin(phase) + 0.25 * Math.sin(2 * phase) + 0.1 * Math.sin(3 * phase)
    );
  });
};

const mix = (...layers) => {
  const length = Math.max(...layers.map((l) => l.length));
  const out = new Float32Array(length);
  for (const layer of layers) {
    for (let i = 0; i < layer.length; i++) out[i] += layer[i];
  }
  return out;
};

const shape = (samples, envelope) =>
  samples.map((x, i) => x * envelope(i / SAMPLE_RATE));

const gain = (samples, amount) => samples.map((x) => x * amount);

// Entrada suave para evitar chasquidos al inicio.
const attack = (t, time) => Math.min(1, t / time);

const save = (name, samples, peak) => {
  // Saturación suave + desvanecido final + normalizado.
  const fade = Math.round(0.02 * SAMPLE_RATE);
  let max = 0;
  const shaped = samples.map((x, i) => {
    const tail = Math.min(1, (samples.length - i) / fade);
    const y = Math.tanh(x * 1.4) * tail;
    max = Math.max(max, Math.abs(y));
    return y;
  });
  const buffer = Buffer.alloc(44 + shaped.length * 2);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + shaped.length * 2, 4);
  buffer.write("WAVEfmt ", 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(SAMPLE_RATE, 24);
  buffer.writeUInt32LE(SAMPLE_RATE * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(shaped.length * 2, 40);
  shaped.forEach((x, i) => {
    buffer.writeInt16LE(Math.round((x / max) * peak * 32767), 44 + i * 2);
  });
  writeFileSync(join(outDir, name), buffer);
  console.log(`${name}  ${(shaped.length / SAMPLE_RATE).toFixed(2)} s`);
};

mkdirSync(outDir, { recursive: true });

// Barrido de transición: aire grave que sube y baja (0,6 s como la transición).
{
  const d = 0.7;
  const bell = (t) => Math.sin((Math.PI * t) / d) ** 2;
  const air = lowpass(
    sweptNoise(d, 11, (t) => 170 + 560 * bell(t), 1.1),
    1100,
  );
  const body = drop(d, 95, 60, 3);
  save(
    "whoosh.wav",
    mix(
      shape(air, (t) => bell(t) ** 0.8),
      shape(gain(body, 0.12), bell),
    ),
    0.85,
  );
}

// Roce corto para textos que entran deslizando.
{
  const d = 0.34;
  const bell = (t) => Math.sin((Math.PI * t) / d) ** 2;
  const air = lowpass(
    sweptNoise(d, 23, (t) => 240 + 380 * bell(t), 1.3),
    900,
  );
  save("swish.wav", shape(air, bell), 0.7);
}

// Impacto grande: entrada del logo.
{
  const d = 0.95;
  const boom = shape(
    drop(d, 210, 58, 15),
    (t) => attack(t, 0.004) * Math.exp(-t * 5),
  );
  // Capa media para que el golpe se oiga también en parlantes de celular.
  const knock = shape(
    drop(d, 340, 120, 20),
    (t) => attack(t, 0.003) * Math.exp(-t * 11),
  );
  const punch = shape(
    lowpass(render(d, makeNoise(37)), 800),
    (t) => attack(t, 0.002) * Math.exp(-t * 30),
  );
  save("impact.wav", mix(boom, gain(knock, 0.45), gain(punch, 2.4)), 0.95);
}

// Golpe seco: tarjetas y botones que aterrizan.
{
  const d = 0.36;
  const boom = shape(
    drop(d, 190, 78, 26),
    (t) => attack(t, 0.003) * Math.exp(-t * 13),
  );
  const knock = shape(
    drop(d, 300, 150, 30),
    (t) => attack(t, 0.003) * Math.exp(-t * 24),
  );
  const punch = shape(
    lowpass(render(d, makeNoise(51)), 650),
    (t) => attack(t, 0.002) * Math.exp(-t * 44),
  );
  save("thud.wav", mix(boom, gain(knock, 0.4), gain(punch, 1.9)), 0.85);
}

// "Pop" redondo y grave: textos y sellos que aparecen.
{
  const d = 0.18;
  const tone = shape(
    drop(d, 390, 165, 42),
    (t) => attack(t, 0.003) * Math.exp(-t * 26),
  );
  save("pop.wav", lowpass(tone, 1400), 0.75);
}
